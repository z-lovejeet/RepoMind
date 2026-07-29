"""
RepoMind — Documentation Parser Module

Parse Markdown and RST documentation files into sections by heading.

Input:  Raw markdown/RST source string + file path
Output: List of DocSection objects

How it works (Markdown):
    1. Split source into lines
    2. Track whether we're inside a fenced code block (``` or ~~~)
    3. Find lines matching ^#{1,6}\\s+(.+)$ (heading pattern)
    4. Group lines between headings into DocSection objects

Why track code blocks?
    Without this, a line like "# This is a comment" inside a Python
    code block would be treated as a heading, breaking the document
    structure. We skip all headings inside fenced code blocks.

Reference:
    - Module Design → Section 2 (core/parsing/doc_parser.py)
    - RAG Workflow → Stage 4 (Parsing)
"""

import re
from app.models.schemas import DocSection


# ─── Heading Patterns ───
# Matches: # Heading, ## Heading, ### Heading, etc.
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+)$")

# RST heading underline characters (in order of conventional priority)
RST_UNDERLINE_CHARS = set("=-~^\"'+`:.#*_")


class DocParser:
    """
    Parse documentation files into sections by heading.

    Each section contains the heading text, its level, the content
    under it, and line numbers.

    Usage:
        parser = DocParser()
        sections = parser.parse_markdown(source, "README.md")
        for s in sections:
            print(f"{'#' * s.level} {s.heading} ({s.start_line}-{s.end_line})")
    """

    def parse_markdown(self, source: str, file_path: str) -> list[DocSection]:
        """
        Split markdown into sections by heading level.

        Each section includes the heading and all content until the next
        heading of equal or higher level.

        Args:
            source: Raw markdown source string
            file_path: Relative file path (for metadata)

        Returns:
            List of DocSection objects. Empty list if source is empty.
            If no headings found, returns a single section with heading=""
            and level=0 containing all content.
        """
        if not source or not source.strip():
            return []

        lines = source.splitlines()
        sections: list[DocSection] = []

        # State tracking
        in_code_block = False
        current_heading = ""
        current_level = 0
        current_content_lines: list[str] = []
        current_start_line = 1

        for i, line in enumerate(lines, start=1):
            # ─── Track fenced code blocks ───
            # Lines starting with ``` or ~~~ toggle the code block state.
            stripped = line.strip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_code_block = not in_code_block
                current_content_lines.append(line)
                continue

            # ─── Skip headings inside code blocks ───
            if in_code_block:
                current_content_lines.append(line)
                continue

            # ─── Check for heading ───
            match = MARKDOWN_HEADING_RE.match(line)
            if match:
                # Save previous section (if any content exists)
                if current_heading or current_content_lines:
                    content = "\n".join(current_content_lines).strip()
                    sections.append(DocSection(
                        heading=current_heading,
                        level=current_level,
                        content=content,
                        start_line=current_start_line,
                        end_line=i - 1,
                    ))

                # Start new section
                hashes, heading_text = match.groups()
                current_heading = heading_text.strip()
                current_level = len(hashes)
                current_content_lines = []
                current_start_line = i
            else:
                current_content_lines.append(line)

        # ─── Final section ───
        if current_heading or current_content_lines:
            content = "\n".join(current_content_lines).strip()
            sections.append(DocSection(
                heading=current_heading,
                level=current_level,
                content=content,
                start_line=current_start_line,
                end_line=len(lines),
            ))

        # ─── No headings found → single section with all content ───
        if not sections:
            sections.append(DocSection(
                heading="",
                level=0,
                content=source.strip(),
                start_line=1,
                end_line=len(lines),
            ))

        return sections

    def parse_rst(self, source: str, file_path: str) -> list[DocSection]:
        """
        Split reStructuredText into sections by heading level.

        RST headings are detected by underline characters (=, -, ~, etc.)
        on the line following the heading text.

        Args:
            source: Raw RST source string
            file_path: Relative file path (for metadata)

        Returns:
            List of DocSection objects
        """
        if not source or not source.strip():
            return []

        lines = source.splitlines()
        sections: list[DocSection] = []

        # Track which underline chars map to which level
        char_to_level: dict[str, int] = {}
        next_level = 1

        current_heading = ""
        current_level = 0
        current_content_lines: list[str] = []
        current_start_line = 1

        i = 0
        while i < len(lines):
            line = lines[i]

            # Check if the NEXT line is an RST underline
            if (
                i + 1 < len(lines)
                and len(lines[i + 1].strip()) >= 2
                and len(set(lines[i + 1].strip())) == 1
                and lines[i + 1].strip()[0] in RST_UNDERLINE_CHARS
                and line.strip()  # heading text must not be empty
            ):
                # This is a heading!
                underline_char = lines[i + 1].strip()[0]

                # Assign level based on first-seen order
                if underline_char not in char_to_level:
                    char_to_level[underline_char] = next_level
                    next_level += 1

                # Save previous section
                if current_heading or current_content_lines:
                    content = "\n".join(current_content_lines).strip()
                    sections.append(DocSection(
                        heading=current_heading,
                        level=current_level,
                        content=content,
                        start_line=current_start_line,
                        end_line=i,  # line before this heading
                    ))

                current_heading = line.strip()
                current_level = char_to_level[underline_char]
                current_content_lines = []
                current_start_line = i + 1  # 1-indexed
                i += 2  # Skip the underline
                continue
            else:
                current_content_lines.append(line)

            i += 1

        # Final section
        if current_heading or current_content_lines:
            content = "\n".join(current_content_lines).strip()
            sections.append(DocSection(
                heading=current_heading,
                level=current_level,
                content=content,
                start_line=current_start_line,
                end_line=len(lines),
            ))

        if not sections:
            sections.append(DocSection(
                heading="",
                level=0,
                content=source.strip(),
                start_line=1,
                end_line=len(lines),
            ))

        return sections
