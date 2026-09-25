"""Read the TypeScript project settings systemap needs."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SOURCE_SUFFIXES = (".ts", ".tsx")
SKIP_PARTS = {".git", ".venv", "node_modules", "build", "dist"}
_JSONC_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/')
_TRAILING_COMMA = re.compile(r'"(?:\\.|[^"\\])*"|,(?=\s*[}\]])')


@dataclass(frozen=True)
class TypeScriptConfig:
    """Resolved compiler paths and output directories for one project."""

    aliases: tuple[tuple[str, tuple[Path, ...]], ...] = ()
    base_url: Path | None = None
    root_dir: Path | None = None
    out_dir: Path | None = None


def package_json(root: Path) -> dict[str, Any]:
    """The package metadata, or an empty table when it is absent."""
    path = root / "package.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(data) if isinstance(data, dict) else {}


def typescript_name(root: Path) -> str:
    """The TypeScript package name, using the folder name when unnamed."""
    name = package_json(root).get("name")
    if not isinstance(name, str) or not name.strip():
        return root.name.replace("-", "_")
    return name.strip().removeprefix("@").replace("/", ".").replace("-", "_")


def discover_typescript_roots(root: Path) -> list[tuple[str, str]]:
    """The conventional TypeScript source root for a configured project."""
    if not (root / "tsconfig.json").is_file():
        return []
    for candidate in (root / "src", root):
        sources = (
            path
            for path in candidate.rglob("*")
            if path.is_file()
            and path.suffix in SOURCE_SUFFIXES
            and not path.name.endswith(".d.ts")
            and not any(part in SKIP_PARTS for part in path.parts)
        )
        if next(sources, None) is not None:
            return [(candidate.relative_to(root).as_posix() or ".", typescript_name(root))]
    return []


def _strip_jsonc(text: str) -> str:
    """Remove JSONC comments and trailing commas without touching strings."""

    def blank_comment(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith('"'):
            return token
        return "".join(char if char in "\r\n" else " " for char in token)

    without_comments = _JSONC_TOKEN.sub(blank_comment, text.lstrip("\ufeff"))

    def keep_string_remove_comma(match: re.Match[str]) -> str:
        return match.group(0) if match.group(0).startswith('"') else ""

    return _TRAILING_COMMA.sub(keep_string_remove_comma, without_comments)


def _read_config(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_strip_jsonc(path.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"could not read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _config_reference(parent: Path, reference: str) -> Path:
    """Resolve one relative or node_modules `extends` reference."""
    ref = Path(reference)
    candidates: list[Path] = []
    if ref.is_absolute():
        candidates.append(ref)
    elif reference.startswith("."):
        candidates.append(parent / ref)
    else:
        candidates.extend(folder / "node_modules" / ref for folder in (parent, *parent.parents))
    for candidate in candidates:
        choices = [candidate]
        if candidate.suffix != ".json":
            choices += [candidate.with_suffix(".json"), candidate / "tsconfig.json"]
        found = next((choice for choice in choices if choice.is_file()), None)
        if found is not None:
            return found.resolve()
    raise ValueError(f"could not resolve tsconfig extends {reference!r} from {parent}")


def _compiler_options(
    path: Path, active: frozenset[Path] = frozenset()
) -> dict[str, tuple[Any, Path]]:
    path = path.resolve()
    if path in active:
        raise ValueError(f"circular tsconfig extends at {path}")
    data = _read_config(path)
    options: dict[str, tuple[Any, Path]] = {}
    extends = data.get("extends")
    if isinstance(extends, str):
        references = [extends]
    elif isinstance(extends, list) and all(isinstance(item, str) for item in extends):
        references = extends
    elif extends is None:
        references = []
    else:
        raise ValueError(f"{path}: extends must be a string or a list of strings")
    for reference in references:
        options.update(
            _compiler_options(_config_reference(path.parent, reference), active | {path})
        )
    compiler = data.get("compilerOptions", {})
    if isinstance(compiler, dict):
        options.update({name: (value, path.parent) for name, value in compiler.items()})
    return options


def load_typescript_config(repo: Path) -> TypeScriptConfig:
    """Read comments, inherited compiler options, aliases and emit directories."""
    path = repo / "tsconfig.json"
    if not path.is_file():
        return TypeScriptConfig()
    options = _compiler_options(path)
    return TypeScriptConfig(
        aliases=_configured_aliases(options, repo),
        base_url=_base_url(options, repo) if "baseUrl" in options else None,
        root_dir=_option_path(options, "rootDir"),
        out_dir=_option_path(options, "outDir"),
    )


def _base_url(options: dict[str, tuple[Any, Path]], repo: Path) -> Path:
    raw, origin = options.get("baseUrl", (".", repo))
    return (origin / str(raw)).resolve()


def _configured_aliases(
    options: dict[str, tuple[Any, Path]], repo: Path
) -> tuple[tuple[str, tuple[Path, ...]], ...]:
    paths_raw, paths_origin = options.get("paths", ({}, repo))
    paths_base = _base_url(options, repo) if "baseUrl" in options else paths_origin.resolve()
    aliases: list[tuple[str, tuple[Path, ...]]] = []
    if isinstance(paths_raw, dict):
        for pattern, targets in paths_raw.items():
            if isinstance(pattern, str) and isinstance(targets, list):
                aliases.append(
                    (
                        pattern,
                        tuple(paths_base / target for target in targets if isinstance(target, str)),
                    )
                )
    return tuple(aliases)


def _option_path(options: dict[str, tuple[Any, Path]], name: str) -> Path | None:
    option = options.get(name)
    if option is None or not isinstance(option[0], str):
        return None
    return (option[1] / option[0]).resolve()


def alias_targets(specifier: str, config: TypeScriptConfig, repo: Path) -> list[Path]:
    """Paths matching a configured alias, preserving tsconfig-relative roots."""
    out: list[Path] = []
    for pattern, targets in config.aliases:
        before, marker, after = pattern.partition("*")
        if marker and specifier.startswith(before) and specifier.endswith(after):
            matched = specifier[len(before) : len(specifier) - len(after) if after else None]
        elif not marker and specifier == pattern:
            matched = ""
        else:
            continue
        out.extend(_replace_star(target, matched) for target in targets)
    base = config.base_url or repo
    return [*out, base / specifier]


def _replace_star(target: Path, matched: str) -> Path:
    """Substitute a wildcard in a resolved alias target."""
    return Path(str(target).replace("*", matched))


def source_target(target: str, repo: Path, config: TypeScriptConfig) -> Path:
    """Map a package target such as `dist/index.js` back to its TS source path."""
    built = (repo / target).resolve()
    if config.out_dir is not None and built.is_relative_to(config.out_dir):
        source_root = config.root_dir or (repo / "src" if (repo / "src").is_dir() else repo)
        return source_root / built.relative_to(config.out_dir)
    return built
