"""
RepoMind — Code Parser Module

Parse Python source code into structured representation using the `ast` module.

Input:  Raw Python source code string + file path
Output: ParsedCode object containing functions, classes, imports, and docstrings

How it works:
    1. ast.parse(source) → Abstract Syntax Tree
    2. ast.iter_child_nodes(tree) → iterate top-level nodes
    3. For each FunctionDef → ParsedFunction
    4. For each ClassDef → ParsedClass (with nested methods)
    5. For each Import/ImportFrom → ParsedImport

Why ast.iter_child_nodes() instead of ast.walk()?
    ast.walk() traverses ALL nodes including nested ones. A method inside
    a class would be extracted TWICE: once as a class method, once as a
    top-level function. iter_child_nodes() only visits direct children
    of the tree root, so methods stay inside their classes.

Reference:
    - Module Design → Section 2 (core/parsing/code_parser.py)
    - RAG Workflow → Stage 4 (Parsing)
"""

import ast
from app.models.schemas import ParsedCode, ParsedFunction, ParsedClass, ParsedImport


class CodeParseError(Exception):
    """Raised when ast.parse() fails due to syntax errors."""
    pass


class CodeParser:
    """
    Parse Python source code into a structured ParsedCode representation.

    Extracts:
    - Top-level functions (with args, return types, docstrings, decorators)
    - Classes (with methods, bases, docstrings)
    - Import statements (import X and from X import Y)

    Usage:
        parser = CodeParser()
        result = parser.parse(source_code, "auth/middleware.py")
        print(result.functions)  # [ParsedFunction(...), ...]
    """

    def parse(self, source: str, file_path: str) -> ParsedCode:
        """
        Parse Python source code into structured representation.

        Args:
            source: Raw Python source code string
            file_path: Relative file path (for metadata in ParsedCode)

        Returns:
            ParsedCode with extracted functions, classes, and imports

        Raises:
            CodeParseError: If ast.parse() fails (syntax error in source)
        """
        if not source or not source.strip():
            return ParsedCode(
                file_path=file_path,
                functions=[],
                classes=[],
                imports=[],
            )

        try:
            tree = ast.parse(source)
        except SyntaxError as e:
            raise CodeParseError(
                f"Syntax error in {file_path}: {e}"
            ) from e

        source_lines = source.splitlines()

        functions = self._extract_functions(tree, source, source_lines)
        classes = self._extract_classes(tree, source, source_lines)
        imports = self._extract_imports(tree)

        return ParsedCode(
            file_path=file_path,
            functions=functions,
            classes=classes,
            imports=imports,
        )

    def _extract_functions(
        self, tree: ast.Module, source: str, source_lines: list[str]
    ) -> list[ParsedFunction]:
        """
        Extract top-level function definitions.

        Only iterates direct children of the module — so methods inside
        classes are NOT extracted here (they're extracted inside _extract_classes).
        """
        functions: list[ParsedFunction] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                fn = self._node_to_function(node, source, source_lines)
                functions.append(fn)

        return functions

    def _extract_classes(
        self, tree: ast.Module, source: str, source_lines: list[str]
    ) -> list[ParsedClass]:
        """
        Extract class definitions with their methods.

        Each ClassDef node's body is scanned for FunctionDef nodes,
        which become the class's methods list.
        """
        classes: list[ParsedClass] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                # Extract methods within this class
                methods: list[ParsedFunction] = []
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        fn = self._node_to_function(item, source, source_lines)
                        methods.append(fn)

                # Extract base classes
                bases: list[str] = []
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        bases.append(base.id)
                    elif isinstance(base, ast.Attribute):
                        bases.append(ast.unparse(base))
                    else:
                        bases.append(ast.unparse(base))

                # Get class body source
                body = self._get_source_segment(source, source_lines, node)

                classes.append(ParsedClass(
                    name=node.name,
                    bases=bases,
                    docstring=ast.get_docstring(node),
                    methods=methods,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    body=body,
                ))

        return classes

    def _extract_imports(self, tree: ast.Module) -> list[ParsedImport]:
        """
        Extract import and from-import statements.

        Handles:
            import os              → ParsedImport(module="os", names=["os"], is_from=False)
            from os import path    → ParsedImport(module="os", names=["path"], is_from=True)
            from . import utils    → ParsedImport(module=".", names=["utils"], is_from=True)
        """
        imports: list[ParsedImport] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(ParsedImport(
                        module=alias.name,
                        names=[alias.asname or alias.name],
                        is_from=False,
                        line=node.lineno,
                    ))
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                # Handle relative imports: from . import X
                if node.level and node.level > 0:
                    module = "." * node.level + module
                names = [alias.name for alias in node.names]
                imports.append(ParsedImport(
                    module=module,
                    names=names,
                    is_from=True,
                    line=node.lineno,
                ))

        return imports

    def _node_to_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef,
        source: str, source_lines: list[str]
    ) -> ParsedFunction:
        """
        Convert an AST FunctionDef node to a ParsedFunction dataclass.

        Extracts: name, args, return_type, docstring, decorators, line range, body.
        """
        # ─── Args ───
        args: list[str] = []
        for arg in node.args.args:
            arg_str = arg.arg
            if arg.annotation:
                try:
                    arg_str += f": {ast.unparse(arg.annotation)}"
                except Exception:
                    pass
            args.append(arg_str)

        # ─── Return type ───
        return_type = None
        if node.returns:
            try:
                return_type = ast.unparse(node.returns)
            except Exception:
                pass

        # ─── Decorators ───
        decorators: list[str] = []
        for dec in node.decorator_list:
            try:
                decorators.append(f"@{ast.unparse(dec)}")
            except Exception:
                decorators.append("@<unknown>")

        # ─── Body source ───
        body = self._get_source_segment(source, source_lines, node)

        return ParsedFunction(
            name=node.name,
            args=args,
            return_type=return_type,
            docstring=ast.get_docstring(node),
            decorators=decorators,
            start_line=node.lineno,
            end_line=node.end_lineno or node.lineno,
            body=body,
        )

    def _get_source_segment(
        self, source: str, source_lines: list[str], node: ast.AST
    ) -> str:
        """
        Get the source code for an AST node.

        Tries ast.get_source_segment() first (accurate but can return None),
        falls back to line-number slicing.
        """
        # Try the accurate method first
        segment = ast.get_source_segment(source, node)
        if segment is not None:
            return segment

        # Fallback: slice by line numbers
        start = node.lineno - 1  # 0-indexed
        end = getattr(node, "end_lineno", node.lineno)
        return "\n".join(source_lines[start:end])
