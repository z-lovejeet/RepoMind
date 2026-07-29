"""
RepoMind — Config Parser Module

Parse configuration files (JSON, YAML, TOML, .env) into Python dicts.

Input:  Raw config file content string + file path + format name
Output: Python dict representing the config

Format handling:
    "json" → json.loads()         (stdlib)
    "yaml" → yaml.safe_load()     (pyyaml)
    "toml" → tomllib.loads()      (stdlib 3.11+)
    "env"  → custom KEY=VALUE parser

Why yaml.safe_load() and not yaml.load()?
    yaml.load() can execute arbitrary Python code via YAML tags
    like !!python/object. safe_load() restricts to safe types
    (str, int, float, list, dict, bool, None). This is a SECURITY
    requirement — we're parsing untrusted repo config files.

Reference:
    - Module Design → Section 2 (core/parsing/config_parser.py)
    - RAG Workflow → Stage 4 (Parsing)
"""

import json
import tomllib


class ConfigParseError(Exception):
    """Raised when a config file cannot be parsed."""
    pass


class ConfigParser:
    """
    Parse configuration files into Python dictionaries.

    Supports JSON, YAML, TOML, and .env formats.

    Usage:
        parser = ConfigParser()
        data = parser.parse('{"key": "value"}', "config.json", "json")
    """

    def parse(self, source: str, file_path: str, format: str) -> dict:
        """
        Parse a config file into a dictionary.

        Args:
            source: Raw config file content
            file_path: Relative file path (for error messages)
            format: One of "json", "yaml", "toml", "env"

        Returns:
            Parsed dictionary of config values

        Raises:
            ConfigParseError: If parsing fails or format is unsupported
        """
        if not source or not source.strip():
            return {}

        format = format.lower().strip()

        try:
            if format == "json":
                return self._parse_json(source, file_path)
            elif format in ("yaml", "yml"):
                return self._parse_yaml(source, file_path)
            elif format == "toml":
                return self._parse_toml(source, file_path)
            elif format == "env":
                return self._parse_env(source, file_path)
            else:
                raise ConfigParseError(
                    f"Unsupported config format '{format}' for {file_path}. "
                    "Supported: json, yaml, toml, env"
                )
        except ConfigParseError:
            raise
        except Exception as e:
            raise ConfigParseError(
                f"Failed to parse {file_path} as {format}: {e}"
            ) from e

    def _parse_json(self, source: str, file_path: str) -> dict:
        """Parse JSON config file."""
        try:
            result = json.loads(source)
        except json.JSONDecodeError as e:
            raise ConfigParseError(
                f"Invalid JSON in {file_path}: {e}"
            ) from e

        # JSON can be a list or scalar at top level — wrap non-dict
        if not isinstance(result, dict):
            return {"_root": result}

        return result

    def _parse_yaml(self, source: str, file_path: str) -> dict:
        """
        Parse YAML config file.

        Uses safe_load() to prevent arbitrary code execution
        via !!python/object YAML tags.
        """
        try:
            import yaml
        except ImportError:
            raise ConfigParseError(
                "PyYAML is not installed. Run: pip install pyyaml"
            )

        try:
            result = yaml.safe_load(source)
        except yaml.YAMLError as e:
            raise ConfigParseError(
                f"Invalid YAML in {file_path}: {e}"
            ) from e

        # safe_load returns None for empty YAML
        if result is None:
            return {}

        if not isinstance(result, dict):
            return {"_root": result}

        return result

    def _parse_toml(self, source: str, file_path: str) -> dict:
        """Parse TOML config file using stdlib tomllib (Python 3.11+)."""
        try:
            return tomllib.loads(source)
        except tomllib.TOMLDecodeError as e:
            raise ConfigParseError(
                f"Invalid TOML in {file_path}: {e}"
            ) from e

    def _parse_env(self, source: str, file_path: str) -> dict:
        """
        Parse .env file (KEY=VALUE format).

        Handles:
            KEY=VALUE
            KEY="quoted value"
            KEY='single quoted'
            # comments
            empty lines
            export KEY=VALUE  (optional export prefix)
        """
        result: dict = {}

        for line_num, line in enumerate(source.splitlines(), start=1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Remove optional 'export ' prefix
            if line.startswith("export "):
                line = line[7:].strip()

            # Split on first '='
            if "=" not in line:
                continue  # Skip malformed lines silently

            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()

            # Remove surrounding quotes
            if (
                len(value) >= 2
                and (
                    (value.startswith('"') and value.endswith('"'))
                    or (value.startswith("'") and value.endswith("'"))
                )
            ):
                value = value[1:-1]

            # Remove inline comments (but not inside quotes)
            if " #" in value and not value.startswith('"'):
                value = value.split(" #")[0].strip()

            if key:
                result[key] = value

        return result
