"""The TypeScript repository adapter gives the TypeScript operations that do not extract
facts.

It finds TypeScript source roots, the project name, and the folders that tsc does not
read. It also reads the name of a recorded method.
It does not load the parser, so a configuration loads without the TypeScript extra.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from systemap import config, file_names, identifier
from systemap.language import CONFIG_ONLY, NO_SOURCE, SOURCE
from systemap.typescript_config import (
    SOURCE_SKIP,
    SOURCE_SUFFIXES,
    compiler_settings,
    load_typescript_config,
    package_json,
    resolved,
    source_files,
)
from systemap.typescript_config_files import (
    typescript_config_paths,
    typescript_extraction_inputs,
)
from systemap.typescript_roots import (
    discover_typescript_roots,
    missing_roots_message,
    type_test_patterns,
)
from systemap.typescript_strings import QUOTED, decode_quoted

TSCONFIG = "tsconfig.json"
PARSER_PACKAGES = ("tree-sitter", "tree-sitter-typescript")
# The method name in a recorded method header. A header starts with optional modifiers
# and an optional `*`. The name can contain Unicode letters (`identifier.complete`). A
# quoted name, such as `"get"`, gives the value of the string.
METHOD = re.compile(
    r"(?:(?:public|static|async|override|abstract|get|set|declare)\s+)*"
    rf"\*?\s*({QUOTED}|[^\s?!<(]+)\s*[?!]?\s*[<(]"
)
# npm package names of model SDKs and agent frameworks. A scope such as `@ai-sdk`
# matches each package in that scope. A name matches as a prefix of the import name.
MODEL_SDKS: tuple[str, ...] = (
    "openai",
    "langchain",
    "@anthropic-ai/sdk",
    "@google/genai",
    "@google/generative-ai",
    "@mistralai/mistralai",
    "@langchain",
    "@ai-sdk",
    "ai",
    "cohere-ai",
)


def has_tsconfig(root: Path, depth: int = config.CANDIDATE_DEPTH) -> bool:
    """Find a tsconfig.json file within `depth` directory levels of the root.

    The search skips node_modules, the other directories in `config.SKIP_WALK`,
    directories with a name that starts with a period, and directories with a name that
    is not valid UTF-8."""
    for dirpath, dirnames, filenames in os.walk(root):
        level = len(Path(dirpath).relative_to(root).parts)
        names = file_names.folders(dirnames)
        dirnames[:] = [
            d for d in names if level < depth and d not in config.SKIP_WALK and d[0] != "."
        ]
        if TSCONFIG in filenames:
            return True
    return False


def skipped(path: Path, base: Path, names: frozenset[str]) -> bool:
    """Find a skip name in the path parts below the base folder."""
    return any(part in names for part in path.relative_to(base).parts)


def ts_skipped(path: Path, base: Path, out_dir: Path | None) -> bool:
    """Find a file that tsc does not read: a file in node_modules, outDir, or a similar
    folder below the base folder. The folders above the base do not count."""
    if out_dir is not None and resolved(path).is_relative_to(out_dir):
        return True
    return skipped(path, base, SOURCE_SKIP)


def out_dir_below(base: Path, out_dir: Path | None) -> Path | None:
    """Give outDir if it is a folder below the base folder. An outDir that contains the
    base folder does not remove its source."""
    folder = base.resolve()
    if out_dir is None or out_dir == folder or not out_dir.is_relative_to(folder):
        return None
    return out_dir


def configured_out_dir(repo: Path, base: Path) -> Path | None:
    """Give the configured outDir below the base folder. The TypeScript context reports a
    configuration error."""
    try:
        out_dir = load_typescript_config(repo).out_dir
    except ValueError:
        return None
    return out_dir_below(base, out_dir)


def compiler_record(compiler: Any, repo: Path) -> dict[str, str]:
    """Give the digest of the TypeScript compiler settings.

    The compiler settings have a record that is separate from the configuration settings,
    because installed npm packages can change them."""
    if compiler is None:
        return {}
    settings = json.dumps(compiler_settings(compiler, repo), sort_keys=True)
    return {"compiler": hashlib.sha256(settings.encode()).hexdigest()}


class TypeScriptRepository:
    """Give the TypeScript operations that do not extract facts."""

    name = "typescript"
    source_suffixes: tuple[str, ...] = SOURCE_SUFFIXES
    skip_dirs = SOURCE_SKIP
    model_sdks = MODEL_SDKS
    # An npm import name continues after a slash, for a subpath or a package in a scope.
    # A dot is part of an npm package name: `chart.js` is not a part of `chart`.
    import_separator = "/"
    config_files: tuple[str, ...] = ("package.json", "tsconfig.json")
    install_extra = "typescript"
    roots_note = (
        '# Package roots use "path" = "module name".\n'
        "# Without explicit roots, the extractor uses the one source folder that the\n"
        "# tsconfig.json include entries name, then src, then the repository root.\n"
        "# The repository root must have a tsconfig.json file."
    )
    roots_example = '# [package_roots]\n# "packages/web/src" = "web"'

    def discover_roots(self, root: Path) -> list[tuple[str, str]]:
        return discover_typescript_roots(root)

    def discover_test_patterns(self, root: Path) -> list[str]:
        """Give the `test_patterns` entries for the type-test folders and files."""
        return type_test_patterns(root)

    def detect(self, root: Path, folders: Iterable[Path] = ()) -> int:
        """Find TypeScript source: a source root, or a source file in a configured folder.
        A tsconfig.json file without a source root is weaker evidence."""
        folders = tuple(folders)
        if folders:
            # The walk does not enter node_modules and the other SOURCE_SKIP folders.
            found = any(
                path.is_file()
                for folder in folders
                if folder.is_dir()
                for path in source_files(folder, SOURCE_SKIP)
            )
            return SOURCE if found else NO_SOURCE
        if discover_typescript_roots(root):
            return SOURCE
        return CONFIG_ONLY if has_tsconfig(root) else NO_SOURCE

    def package_dir(self, directory: Path) -> bool:
        """A TypeScript output directory is never source, so no directory is kept."""
        del directory
        return False

    def config_paths(self, root: Path, folders: Sequence[Path]) -> list[Path]:
        """Give package.json and tsconfig.json near the folders, and each tsconfig file
        that a tsconfig file names in `extends` or `references`."""
        return typescript_config_paths(root, folders)

    def extraction_inputs(self, root: Path, folders: Sequence[Path]) -> dict[Path, bytes]:
        return typescript_extraction_inputs(root, folders)

    def root_name_problem(self, rel: str, name: str) -> str:
        del rel, name
        return ""

    def missing_roots_message(self, root: Path) -> str:
        return missing_roots_message(root)

    def project_name(self, root: Path) -> str:
        name = package_json(root).get("name")
        return name.strip() if isinstance(name, str) else ""

    def parser_version(self) -> str:
        found = []
        for package in PARSER_PACKAGES:
            try:
                found.append(f"{package} {importlib.metadata.version(package)}")
            except importlib.metadata.PackageNotFoundError:
                found.append(f"{package} not installed")
        return ", ".join(found)

    def method_name(self, signature: str) -> str:
        found = METHOD.match(signature)
        name = decode_quoted(found.group(1)) if found else ""
        return name if identifier.complete(name) else ""


TYPESCRIPT_REPOSITORY = TypeScriptRepository()
