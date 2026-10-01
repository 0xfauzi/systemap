"""Read the TypeScript project settings systemap needs."""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

SOURCE_SUFFIXES = (".ts", ".tsx")
SKIP_PARTS = {".git", ".venv", "node_modules", "build", "dist"}
# A shared base config cannot know where the project that extends it lives, so
# TypeScript lets a path option start with this variable, which stands for the
# folder of the top-level tsconfig.json: the one the project owns, not the file
# that declares the option. Measured with `tsc --showConfig` (7.0.2): the
# variable is replaced only at the start of a value, and a value such as
# `cache/${configDir}/x` is left as written.
CONFIG_DIR = "${configDir}"
# The top-level keys that choose the compiler's input files. The inheriting
# config's value replaces the base config's whole value, as compilerOptions do.
INPUT_KEYS = ("files", "include", "exclude")
# The major version from which an unset `rootDir` means the tsconfig folder.
# Measured: tsc 5.9.3 emits from the longest common folder of the inputs,
# 6.0.3 emits from the tsconfig folder and reports TS5011 asking for an
# explicit `rootDir`, and 7.0.2 emits from the tsconfig folder.
CONFIG_DIR_ROOT_SINCE = 6
_JSONC_TOKEN = re.compile(r'"(?:\\.|[^"\\])*"|//[^\r\n]*|/\*[\s\S]*?\*/')
_TRAILING_COMMA = re.compile(r'"(?:\\.|[^"\\])*"|,(?=\s*[}\]])')
_GLOB_CHARS = re.compile(r"[*?]")

# Each value with the folder of the file that declared it, because a relative
# path in an inherited config means that file's folder.
Options = dict[str, tuple[Any, Path]]


@dataclass(frozen=True)
class InputSpec:
    """`files`, `include` and `exclude`, as paths relative to the tsconfig folder.

    None for `include` or `exclude` means the key was not written, which tsc
    treats differently from an empty list.
    """

    files: tuple[str, ...] | None = None
    include: tuple[str, ...] | None = None
    exclude: tuple[str, ...] | None = None


@dataclass(frozen=True)
class TypeScriptConfig:
    """Resolved compiler paths and output directories for one project."""

    aliases: tuple[tuple[str, tuple[Path, ...]], ...] = ()
    base_url: Path | None = None
    root_dir: Path | None = None
    root_dirs: tuple[Path, ...] = ()
    out_dir: Path | None = None
    issues: tuple[tuple[str, str], ...] = ()
    config_dir: Path | None = None
    composite: bool = False
    inputs: InputSpec | None = None
    typescript_major: int | None = None


def compiler_settings(config: TypeScriptConfig, repo: Path) -> dict[str, Any]:
    """Compiler settings with paths relative to the repository, for provenance."""

    def relative(value: Any) -> Any:
        if isinstance(value, Path):
            return Path(os.path.relpath(value, repo)).as_posix()
        if isinstance(value, dict):
            return {key: relative(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [relative(item) for item in value]
        return value

    return dict(relative(asdict(config)))


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


def typescript_major(root: Path) -> int | None:
    """The major version of the project's TypeScript, or None when nothing says.

    The installed package is the truth when it is present. Otherwise the range
    in package.json names the major first, as in `^5.9.3` or `~6.0`. A range
    with no digit, such as `latest`, says nothing.
    """
    installed = package_json(root / "node_modules" / "typescript").get("version")
    if isinstance(installed, str) and (match := re.match(r"\d+", installed)):
        return int(match.group())
    package = package_json(root)
    for key in ("devDependencies", "dependencies"):
        dependencies = package.get(key)
        if not isinstance(dependencies, dict):
            continue
        declared = dependencies.get("typescript")
        if isinstance(declared, str) and (match := re.search(r"\d+", declared)):
            return int(match.group())
    return None


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
    path: Path,
    issues: list[tuple[Path, str]],
    inputs: Options,
    active: frozenset[Path] = frozenset(),
) -> Options:
    """The compiler options of one config and its bases; `inputs` fills as it goes."""
    path = path.resolve()
    if path in active:
        raise ValueError(f"circular tsconfig extends at {path}")
    data = _read_config(path)
    options: Options = {}
    for reference in _extends_references(data, path):
        options.update(_inherited_options(path, reference, issues, inputs, active))
    compiler = data.get("compilerOptions", {})
    if isinstance(compiler, dict):
        options.update({name: (value, path.parent) for name, value in compiler.items()})
    inputs.update({key: (data[key], path.parent) for key in INPUT_KEYS if key in data})
    return options


def _extends_references(data: dict[str, Any], path: Path) -> list[str]:
    """The configs this one extends: one, several, or none."""
    extends = data.get("extends")
    if isinstance(extends, str):
        return [extends]
    if isinstance(extends, list) and all(isinstance(item, str) for item in extends):
        return extends
    if extends is None:
        return []
    raise ValueError(f"{path}: extends must be a string or a list of strings")


def _inherited_options(
    path: Path,
    reference: str,
    issues: list[tuple[Path, str]],
    inputs: Options,
    active: frozenset[Path],
) -> Options:
    try:
        inherited = _config_reference(path.parent, reference)
    except ValueError:
        if reference.startswith(".") or Path(reference).is_absolute():
            raise
        issues.append((path, reference))
        return {}
    return _compiler_options(inherited, issues, inputs, active | {path})


def load_typescript_config(repo: Path) -> TypeScriptConfig:
    """Read comments, inherited compiler options, aliases and emit directories."""
    path = repo / "tsconfig.json"
    if not path.is_file():
        return TypeScriptConfig()
    issues: list[tuple[Path, str]] = []
    inputs: Options = {}
    options = _compiler_options(path, issues, inputs)
    config_dir = path.parent.resolve()
    return TypeScriptConfig(
        aliases=_configured_aliases(options, repo, config_dir),
        base_url=_base_url(options, repo, config_dir) if "baseUrl" in options else None,
        root_dir=_option_path(options, "rootDir", config_dir),
        root_dirs=_option_paths(options, "rootDirs", config_dir),
        out_dir=_option_path(options, "outDir", config_dir),
        issues=tuple((_issue_path(source, repo), reference) for source, reference in issues),
        config_dir=config_dir,
        composite=options.get("composite", (False, config_dir))[0] is True,
        inputs=_input_spec(inputs, config_dir),
        typescript_major=typescript_major(repo),
    )


def _issue_path(source: Path, repo: Path) -> str:
    return source.relative_to(repo).as_posix() if source.is_relative_to(repo) else str(source)


def _expand(value: str, config_dir: Path) -> str:
    """Replace a leading `${configDir}` with the top-level tsconfig's folder.

    The result is an absolute path, so joining it onto the declaring file's
    folder leaves it unchanged. Anywhere else in the value the text is kept,
    which is what tsc does.
    """
    if value.startswith(CONFIG_DIR):
        return str(config_dir) + value[len(CONFIG_DIR) :]
    return value


def _base_url(options: Options, repo: Path, config_dir: Path) -> Path:
    raw, origin = options.get("baseUrl", (".", repo))
    return (origin / _expand(str(raw), config_dir)).resolve()


def _configured_aliases(
    options: Options, repo: Path, config_dir: Path
) -> tuple[tuple[str, tuple[Path, ...]], ...]:
    paths_raw, paths_origin = options.get("paths", ({}, repo))
    if "baseUrl" in options:
        paths_base = _base_url(options, repo, config_dir)
    else:
        paths_base = paths_origin.resolve()
    aliases: list[tuple[str, tuple[Path, ...]]] = []
    if isinstance(paths_raw, dict):
        for pattern, targets in paths_raw.items():
            if isinstance(pattern, str) and isinstance(targets, list):
                aliases.append(
                    (
                        pattern,
                        tuple(
                            paths_base / _expand(target, config_dir)
                            for target in targets
                            if isinstance(target, str)
                        ),
                    )
                )
    return tuple(aliases)


def _option_path(options: Options, name: str, config_dir: Path) -> Path | None:
    option = options.get(name)
    if option is None or not isinstance(option[0], str):
        return None
    return (option[1] / _expand(option[0], config_dir)).resolve()


def _option_paths(options: Options, name: str, config_dir: Path) -> tuple[Path, ...]:
    option = options.get(name)
    if option is None or not isinstance(option[0], list):
        return ()
    return tuple(
        (option[1] / _expand(value, config_dir)).resolve()
        for value in option[0]
        if isinstance(value, str)
    )


def _input_spec(inputs: Options, config_dir: Path) -> InputSpec:
    """`files`, `include` and `exclude` rewritten relative to the tsconfig folder."""

    def entries(key: str) -> tuple[str, ...] | None:
        option = inputs.get(key)
        if option is None or not isinstance(option[0], list):
            return None
        raw, origin = option
        return tuple(
            _relative_pattern(entry, origin, config_dir) for entry in raw if isinstance(entry, str)
        )

    return InputSpec(files=entries("files"), include=entries("include"), exclude=entries("exclude"))


def _relative_pattern(entry: str, origin: Path, config_dir: Path) -> str:
    """One `files`, `include` or `exclude` entry, relative to the tsconfig folder.

    A relative entry means the folder of the file that declares it, and a
    leading `${configDir}` means the tsconfig folder, as for compiler options.
    """
    joined = os.path.normpath(os.path.join(origin, _expand(entry, config_dir)))
    return Path(os.path.relpath(joined, config_dir)).as_posix()


def _glob_regex(pattern: str, config_dir: Path) -> re.Pattern[str]:
    """The regular expression for one tsconfig glob, over folder-relative paths.

    `**/` crosses folders, `*` and `?` stay inside one, and an entry that
    names a folder means everything under it.
    """
    escaped = re.escape(pattern.strip("/"))
    regex = (
        escaped.replace(r"\*\*/", "(?:[^/]+/)*")
        .replace(r"\*\*", ".*")
        .replace(r"\*", "[^/]*")
        .replace(r"\?", "[^/]")
    )
    if not _GLOB_CHARS.search(pattern) and (config_dir / pattern).is_dir():
        regex += "(?:/.*)?"
    return re.compile(regex)


def input_files(config: TypeScriptConfig) -> list[Path]:
    """The non-declaration source files the compiler would take as input.

    With neither `files` nor `include` written, everything under the tsconfig
    folder counts, as it does for tsc. `outDir` and systemap's skipped folders
    are left out. Test files count: tsc does not know they are tests.
    """
    root, spec = config.config_dir, config.inputs
    if root is None or spec is None:
        return []
    found: dict[Path, None] = {}
    for entry in spec.files or ():
        if _is_input(root / entry):
            found[(root / entry).resolve()] = None
    wanted = [_glob_regex(pattern, root) for pattern in _include_patterns(spec)]
    unwanted = [_glob_regex(pattern, root) for pattern in _exclude_patterns(spec, config)]
    for path in _candidate_inputs(root, wanted):
        if _selected(path.relative_to(root).as_posix(), wanted, unwanted):
            found[path.resolve()] = None
    return list(found)


def _include_patterns(spec: InputSpec) -> tuple[str, ...]:
    """What `include` selects: everything when neither it nor `files` is written."""
    if spec.include is None and spec.files is None:
        return ("**/*",)
    return spec.include or ()


def _exclude_patterns(spec: InputSpec, config: TypeScriptConfig) -> list[str]:
    """What `exclude` removes, plus `outDir`, which tsc never reads from."""
    exclude = list(spec.exclude or ())
    root = config.config_dir
    if root is not None and config.out_dir is not None and config.out_dir.is_relative_to(root):
        exclude.append(config.out_dir.relative_to(root).as_posix())
    return exclude


def _selected(
    relative: str, wanted: list[re.Pattern[str]], unwanted: list[re.Pattern[str]]
) -> bool:
    return any(w.fullmatch(relative) for w in wanted) and not any(
        u.fullmatch(relative) for u in unwanted
    )


def _is_input(path: Path) -> bool:
    return path.is_file() and path.suffix in SOURCE_SUFFIXES and not path.name.endswith(".d.ts")


def _candidate_inputs(root: Path, wanted: list[re.Pattern[str]]) -> Iterable[Path]:
    if not wanted:
        return ()
    return (
        path
        for suffix in SOURCE_SUFFIXES
        for path in root.rglob(f"*{suffix}")
        if not any(part in SKIP_PARTS for part in path.relative_to(root).parts) and _is_input(path)
    )


def common_source_dir(paths: Iterable[Path]) -> Path | None:
    """The longest folder every path is under, or None with nothing to compare."""
    folders = [str(path.parent) for path in paths]
    if not folders:
        return None
    return Path(os.path.commonpath(folders))


def root_candidates(config: TypeScriptConfig, inputs: Iterable[Path]) -> tuple[Path, ...]:
    """The folders the project's tsc takes as `rootDir`, in the order to try.

    An explicit `rootDir` is the answer. `composite` makes tsc use the tsconfig
    folder on every version. Otherwise the project's TypeScript major decides:
    5 takes the longest common folder of the input files, 6 and later take the
    tsconfig folder. When nothing names the version, both are returned, and the
    caller accepts a mapping only when exactly one of them fits.
    """
    if config.root_dir is not None:
        return (config.root_dir,)
    if config.config_dir is None:
        return ()
    if config.composite:
        return (config.config_dir,)
    major = config.typescript_major
    if major is not None and major >= CONFIG_DIR_ROOT_SINCE:
        return (config.config_dir,)
    common = common_source_dir(inputs)
    if major is not None:
        return (common,) if common is not None else ()
    return tuple(dict.fromkeys(folder for folder in (common, config.config_dir) if folder))


def alias_targets(specifier: str, config: TypeScriptConfig, repo: Path) -> list[Path]:
    """Paths matching a configured alias, preserving tsconfig-relative roots."""
    matches: list[tuple[tuple[int, int, int], tuple[Path, ...], str]] = []
    for pattern, targets in config.aliases:
        before, marker, after = pattern.partition("*")
        if marker and specifier.startswith(before) and specifier.endswith(after):
            matched = specifier[len(before) : len(specifier) - len(after) if after else None]
            priority = (0, len(before), len(after))
        elif not marker and specifier == pattern:
            matched = ""
            priority = (1, len(before), 0)
        else:
            continue
        matches.append((priority, targets, matched))
    out: list[Path] = []
    if matches:
        _priority, targets, matched = max(matches, key=lambda item: item[0])
        out.extend(_replace_star(target, matched) for target in targets)
    base = config.base_url or repo
    return [*out, base / specifier]


def _replace_star(target: Path, matched: str) -> Path:
    """Substitute a wildcard in a resolved alias target."""
    return Path(str(target).replace("*", matched))


def source_targets(
    target: str, repo: Path, config: TypeScriptConfig, roots: Iterable[Path]
) -> list[Path]:
    """Where a package target such as `dist/index.js` came from, one path per root.

    A target outside `outDir`, or with no `outDir` configured, is taken as it
    is written: a `bin` may name a source file directly.
    """
    built = (repo / target).resolve()
    if config.out_dir is None or not built.is_relative_to(config.out_dir):
        return [built]
    relative = built.relative_to(config.out_dir)
    return [root / relative for root in roots]
