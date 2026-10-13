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
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from systemap import config, identifier
from systemap.language import CONFIG_ONLY, NO_SOURCE, SOURCE
from systemap.typescript_config import (
    DECLARATION_SUFFIXES,
    SOURCE_SKIP,
    SOURCE_SUFFIXES,
    compiler_settings,
    discover_typescript_roots,
    load_typescript_config,
    package_json,
)

TSCONFIG = "tsconfig.json"
PARSER_PACKAGES = ("tree-sitter", "tree-sitter-typescript")
# The method name in a recorded method header. A header starts with optional modifiers
# and an optional `*`. The name can contain Unicode letters (`identifier.complete`).
METHOD = re.compile(
    r"(?:(?:public|static|async|override|abstract|get|set|declare)\s+)*"
    r"\*?\s*([^\s?!<(]+)\s*[?!]?\s*[<(]"
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

    The search skips node_modules, the other directories in `config.SKIP_WALK`, and
    directories with a name that starts with a period."""
    for dirpath, dirnames, filenames in os.walk(root):
        level = len(Path(dirpath).relative_to(root).parts)
        dirnames[:] = [
            d for d in dirnames if level < depth and d not in config.SKIP_WALK and d[0] != "."
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
    if out_dir is not None and path.resolve().is_relative_to(out_dir):
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


def _source_file(path: Path) -> bool:
    return path.suffix in SOURCE_SUFFIXES and not path.name.endswith(DECLARATION_SUFFIXES)


class TypeScriptRepository:
    """Give the TypeScript operations that do not extract facts."""

    name = "typescript"
    source_suffixes: tuple[str, ...] = SOURCE_SUFFIXES
    skip_dirs = SOURCE_SKIP
    model_sdks = MODEL_SDKS
    config_files: tuple[str, ...] = ("package.json", "tsconfig.json")
    install_extra = "typescript"
    roots_note = (
        '# Package roots use "path" = "module name".\n'
        "# Without explicit roots, the extractor uses src, then the repository root,\n"
        "# when the repository root has a tsconfig.json file."
    )
    roots_example = '# [package_roots]\n# "packages/web/src" = "web"'

    def discover_roots(self, root: Path) -> list[tuple[str, str]]:
        return discover_typescript_roots(root)

    def detect(self, root: Path, folders: Iterable[Path] = ()) -> int:
        """Find TypeScript source: a source root, or a source file in a configured folder.
        A tsconfig.json file without a source root is weaker evidence."""
        folders = tuple(folders)
        if folders:
            found = any(
                _source_file(path) and not skipped(path, folder, SOURCE_SKIP)
                for folder in folders
                if folder.is_dir()
                for path in folder.rglob("*")
            )
            return SOURCE if found else NO_SOURCE
        if discover_typescript_roots(root):
            return SOURCE
        return CONFIG_ONLY if has_tsconfig(root) else NO_SOURCE

    def package_dir(self, directory: Path) -> bool:
        """A TypeScript output directory is never source, so no directory is kept."""
        del directory
        return False

    def root_name_problem(self, rel: str, name: str) -> str:
        del rel, name
        return ""

    def missing_roots_message(self, root: Path) -> str:
        del root
        return (
            'No package roots are available. Set [package_roots] in systemap.toml ("path" '
            '= "module name"). No .ts or .tsx source is available in src or the repository '
            "root."
        )

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
        return found.group(1) if found and identifier.complete(found.group(1)) else ""


TYPESCRIPT_REPOSITORY = TypeScriptRepository()
