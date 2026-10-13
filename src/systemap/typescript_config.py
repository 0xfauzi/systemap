"""The TypeScript configuration reader supplies package settings, compiler paths, aliases,
and source inputs.
"""

from __future__ import annotations

import itertools
import json
import os
import re
from collections.abc import Collection, Iterable, Iterator
from dataclasses import asdict, dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any

from systemap import repo_files
from systemap.config import ConfigError

SOURCE_SUFFIXES = (".ts", ".tsx", ".mts", ".cts")
DECLARATION_SUFFIXES = (".d.ts", ".d.mts", ".d.cts")
# The folders below a project folder that hold no project source. tsc reads all other
# folders except outDir, so a source folder called build or dist is source.
SOURCE_SKIP = frozenset({".git", ".venv", "node_modules"})
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
    """This record gives files, include, and exclude patterns relative to the tsconfig
    directory.

    A None value means that the key is missing. An empty list means that the key is
    available without entries.
    """

    files: tuple[str, ...] | None = None
    include: tuple[str, ...] | None = None
    exclude: tuple[str, ...] | None = None


@dataclass(frozen=True)
class TypeScriptConfig:
    """This record contains resolved compiler paths and output directories for a project."""

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
    # The configurations that the file names in `references`, and the references of
    # those configurations, in the order that they are found.
    projects: tuple[TypeScriptConfig, ...] = ()


def compiler_settings(config: TypeScriptConfig, repo: Path) -> dict[str, Any]:
    """This function gives compiler settings with repository-relative paths for provenance."""

    def relative(value: Any) -> Any:
        if isinstance(value, Path):
            return Path(os.path.relpath(value, repo)).as_posix()
        if isinstance(value, dict):
            return {key: relative(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return [relative(item) for item in value]
        return value

    return dict(relative(asdict(config)))


def package_json(root: Path, repo: Path | None = None) -> dict[str, Any]:
    """This function reads package metadata, or gives an empty table if package.json is
    missing.

    A package.json file that cannot be read, or that does not contain a JSON object, gives
    a configuration error. npm also refuses such a file. Empty metadata would show a
    package without entry points, and that result is not known.
    The function reads only a regular file in the repository. Without `repo`, the root
    is the repository. A link out of the repository and a FIFO give a configuration
    error with the cause, as `_read_config` does.
    """
    path = root / "package.json"
    if not config_present(path):
        return {}
    base = root if repo is None else repo
    try:
        text = repo_files.read_text(base, repo_files.relative(base, path))
        data = json.loads(text)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ConfigError(f"The parser could not read {path.as_posix()}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path.as_posix()} must contain a JSON object.")
    return data


def typescript_name(root: Path) -> str:
    """This function selects the TypeScript package name, or the directory name if there is
    no package name.
    """
    name = package_json(root).get("name")
    if not isinstance(name, str) or not name.strip():
        return root.name.replace("-", "_")
    return name.strip().removeprefix("@").replace("/", ".").replace("-", "_")


def typescript_major(root: Path) -> int | None:
    """This function gets the installed TypeScript major version, or the package.json
    version range if no package is installed.
    """
    installed = package_json(root / "node_modules" / "typescript", root).get("version")
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


def _strip_jsonc(text: str) -> str:
    """This function removes JSONC comments and trailing commas without changing string
    values.
    """

    def blank_comment(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith('"'):
            return token
        return "".join(char if char in "\r\n" else " " for char in token)

    without_comments = _JSONC_TOKEN.sub(blank_comment, text.lstrip("\ufeff"))

    def keep_string_remove_comma(match: re.Match[str]) -> str:
        return match.group(0) if match.group(0).startswith('"') else ""

    return _TRAILING_COMMA.sub(keep_string_remove_comma, without_comments)


def _read_config(path: Path, repo: Path) -> dict[str, Any]:
    """This function reads a tsconfig file only if it is a regular file in the repository.

    A file outside the repository, a link to a file outside it, and a file that is not a
    regular file give ValueError with the path and the cause. The function does not open
    such a file. Thus a FIFO does not stop the reader.
    """
    try:
        text = repo_files.read_text(repo, repo_files.relative(repo, path))
        value = json.loads(_strip_jsonc(text))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"The parser could not read {path.as_posix()}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{path.as_posix()} must contain an object.")
    return value


def _config_reference(parent: Path, reference: str) -> Path:
    """This function resolves a relative or node_modules extends reference."""
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
            # tsc adds `.json` to the full name: `./tsconfig.base` is `tsconfig.base.json`.
            choices += [candidate.with_name(candidate.name + ".json"), candidate / "tsconfig.json"]
        # A file that is not regular, such as a FIFO, is found, and the reader refuses it
        # with its cause.
        found = next((choice for choice in choices if _not_folder(choice)), None)
        if found is not None:
            return found.resolve()
    raise ValueError(f"The parser could not resolve tsconfig extends {reference!r} from {parent}")


def _not_folder(path: Path) -> bool:
    return path.exists() and not path.is_dir()


def config_present(path: Path) -> bool:
    """This function tells if a tsconfig path names an entry that is not a folder.

    A link, a FIFO, and a link to a file outside the repository are present. Then the
    reader refuses them with the cause, and the project does not silently lose them.
    """
    return os.path.lexists(path) and not path.is_dir()


def _compiler_options(
    path: Path,
    repo: Path,
    issues: list[tuple[Path, str]],
    inputs: Options,
    active: frozenset[Path] = frozenset(),
) -> Options:
    """This function reads compiler options and inherited settings, and records input
    specifications.
    """
    path = path.resolve()
    if path in active:
        raise ValueError(f"A circular tsconfig extends relation occurs at {path.as_posix()}")
    data = _read_config(path, repo)
    options: Options = {}
    for reference in _extends_references(data, path):
        options.update(_inherited_options(path, repo, reference, issues, inputs, active))
    compiler = data.get("compilerOptions", {})
    if isinstance(compiler, dict):
        options.update({name: (value, path.parent) for name, value in compiler.items()})
    inputs.update({key: (data[key], path.parent) for key in INPUT_KEYS if key in data})
    return options


def _extends_references(data: dict[str, Any], path: Path) -> list[str]:
    """This function reads one or more inherited configuration references."""
    extends = data.get("extends")
    if isinstance(extends, str):
        return [extends]
    if isinstance(extends, list) and all(isinstance(item, str) for item in extends):
        return extends
    if extends is None:
        return []
    raise ValueError(f"{path.as_posix()}: extends must be a string or a list of strings.")


def _inherited_options(
    path: Path,
    repo: Path,
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
    return _compiler_options(inherited, repo, issues, inputs, active | {path})


def load_typescript_config(repo: Path) -> TypeScriptConfig:
    """This function reads compiler options, aliases, comments, and output directories.

    The result also contains the configurations in `references`.
    """
    path = repo / "tsconfig.json"
    if not config_present(path):
        return TypeScriptConfig()
    return load_project_config(path, repo, typescript_major(repo))


def load_project_config(path: Path, repo: Path, major: int | None) -> TypeScriptConfig:
    """This function reads one tsconfig file and the configurations that it references.

    The `issues` of the result include the issues of the referenced configurations.
    """
    issues: list[tuple[Path, str]] = []
    config = _project_config(path, repo, issues, major)
    projects = tuple(_project_config(ref, repo, issues, major) for ref in _references(path, repo))
    return replace(
        config,
        issues=tuple(
            dict.fromkeys((_issue_path(source, repo), reference) for source, reference in issues)
        ),
        projects=projects,
    )


def _project_config(
    path: Path, repo: Path, issues: list[tuple[Path, str]], major: int | None
) -> TypeScriptConfig:
    inputs: Options = {}
    options = _compiler_options(path, repo, issues, inputs)
    config_dir = path.parent.resolve()
    return TypeScriptConfig(
        aliases=_configured_aliases(options, repo, config_dir),
        base_url=_base_url(options, repo, config_dir) if "baseUrl" in options else None,
        root_dir=_option_path(options, "rootDir", config_dir),
        root_dirs=_option_paths(options, "rootDirs", config_dir),
        out_dir=_option_path(options, "outDir", config_dir),
        config_dir=config_dir,
        composite=options.get("composite", (False, config_dir))[0] is True,
        inputs=_input_spec(inputs, config_dir),
        typescript_major=major,
    )


def _references(path: Path, repo: Path) -> list[Path]:
    """This function gives the configurations that `references` names, and their own
    references, without repeats.

    A reference to a directory uses the tsconfig.json file in that directory, as in tsc.
    A reference to a missing file has no effect. A reference to a file outside the
    repository, or to a file that is not a regular file, gives ValueError.
    """
    start = path.resolve()
    found: dict[Path, None] = {}
    queue = [start]
    for current in queue:
        for reference in _direct_references(current, repo):
            if reference != start and reference not in found:
                found[reference] = None
                queue.append(reference)
    return list(found)


def _direct_references(path: Path, repo: Path) -> list[Path]:
    references = _read_config(path, repo).get("references")
    if not isinstance(references, list):
        return []
    out: list[Path] = []
    for reference in references:
        raw = reference.get("path") if isinstance(reference, dict) else None
        if not isinstance(raw, str):
            continue
        target = path.parent / raw
        if not raw.endswith(".json"):
            target = target / "tsconfig.json"
        # A FIFO or a link out of the repository is in the result. The reader refuses it.
        if os.path.lexists(target):
            out.append(target.resolve())
    return out


def _issue_path(source: Path, repo: Path) -> str:
    return source.relative_to(repo).as_posix() if source.is_relative_to(repo) else str(source)


def _expand(value: str, config_dir: Path) -> str:
    """This function replaces an initial ${configDir} with the top-level tsconfig
    directory.

    The result is an absolute path. Other occurrences of the token stay the same.
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
    """This function converts files, include, and exclude patterns to tsconfig-relative
    paths.
    """

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
    """This function resolves one input pattern relative to its declaring configuration.

    An initial ${configDir} uses the top-level tsconfig directory instead.
    """
    joined = os.path.normpath(os.path.join(origin, _expand(entry, config_dir)))
    return Path(os.path.relpath(joined, config_dir)).as_posix()


def _glob_regex(pattern: str, config_dir: Path) -> re.Pattern[str]:
    """This function makes a regular expression for a directory-relative tsconfig pattern.

    The **/ pattern crosses directories. The * and ? patterns stay inside a directory. A
    directory name includes its contents.
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


def input_files(config: TypeScriptConfig, repo: Path) -> list[Path]:
    """This function selects source files from compiler input patterns, without declaration
    files.

    If files and include are missing, all source files under the tsconfig directory are
    candidates. A pattern can select files outside the tsconfig directory, as in tsc, but
    only files in the repository. The selection excludes outDir and the .git, .venv, and
    node_modules directories, as the source path rule does.
    """
    root, spec = config.config_dir, config.inputs
    if root is None or spec is None:
        return []
    repo = repo.resolve()
    found: dict[Path, None] = {}
    for entry in spec.files or ():
        if _is_input(root / entry) and (root / entry).resolve().is_relative_to(repo):
            found[(root / entry).resolve()] = None
    patterns = _include_patterns(spec)
    wanted = [_glob_regex(pattern, root) for pattern in patterns]
    unwanted = [_glob_regex(pattern, root) for pattern in _exclude_patterns(spec, config)]
    for path in _candidate_inputs(root, patterns, repo):
        if _selected(Path(os.path.relpath(path, root)).as_posix(), wanted, unwanted):
            found[path.resolve()] = None
    return list(found)


def _include_patterns(spec: InputSpec) -> tuple[str, ...]:
    """This function reads include patterns, or selects all files if include and files are
    missing.
    """
    if spec.include is None and spec.files is None:
        return ("**/*",)
    return spec.include or ()


def _exclude_patterns(spec: InputSpec, config: TypeScriptConfig) -> list[str]:
    """This function reads exclusion patterns and adds outDir to the exclusions."""
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
    return (
        path.is_file()
        and path.suffix in SOURCE_SUFFIXES
        and not path.name.endswith(DECLARATION_SUFFIXES)
    )


def _candidate_inputs(root: Path, patterns: tuple[str, ...], repo: Path) -> Iterator[Path]:
    """This function gives the source files below the fixed directories of the include
    patterns.

    The walk does not enter .git, .venv, or node_modules. Thus the files in node_modules do
    not make the walk slower. A source directory called build or dist is source, as tsc
    reads it.
    """
    directories = (
        directory
        for directory in _include_directories(root, patterns, repo)
        if not any(part in SOURCE_SKIP for part in Path(os.path.relpath(directory, root)).parts)
    )
    return (
        path
        for directory in directories
        for path in source_files(directory, SOURCE_SKIP)
        if _is_input(path)
    )


def _include_directories(root: Path, patterns: tuple[str, ...], repo: Path) -> list[Path]:
    """This function gives the directory before the first wildcard of each pattern.

    The result does not include a directory inside another directory of the result.
    A pattern can name a directory outside the tsconfig directory, as `../src/**/*.ts`
    does. A directory outside the repository is not in the result.
    """
    directories: set[Path] = set()
    for pattern in patterns:
        fixed = list(
            itertools.takewhile(
                lambda part: not _GLOB_CHARS.search(part), PurePosixPath(pattern).parts
            )
        )
        directory = Path(os.path.normpath(root.joinpath(*fixed)))
        if not directory.resolve().is_relative_to(repo):
            continue
        while directory.resolve() != repo and not directory.is_dir():
            directory = directory.parent
        directories.add(directory)
    return sorted(
        directory
        for directory in directories
        if not any(other != directory and directory.is_relative_to(other) for other in directories)
    )


def source_files(directory: Path, skip: Collection[str]) -> Iterator[Path]:
    """This function gives the TypeScript files below a directory in a stable order.

    The walk does not enter a directory whose name is in skip. The result does not
    include declaration files.
    """
    for current, names, files in os.walk(directory):
        names[:] = sorted(name for name in names if name not in skip)
        for name in sorted(files):
            if name.endswith(SOURCE_SUFFIXES) and not name.endswith(DECLARATION_SUFFIXES):
                yield Path(current, name)


def common_source_dir(paths: Iterable[Path]) -> Path | None:
    """This function finds the longest common parent directory, or gives None if there are
    no paths.
    """
    folders = [str(path.parent) for path in paths]
    if not folders:
        return None
    return Path(os.path.commonpath(folders))


def root_candidates(config: TypeScriptConfig, inputs: Iterable[Path]) -> tuple[Path, ...]:
    """This function lists possible compiler source roots in resolution order.

    An explicit rootDir has priority. The composite option uses the tsconfig directory.
    Otherwise, the TypeScript version controls the inferred root.
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
    """This function resolves configured alias targets relative to the tsconfig roots.

    Without `baseUrl`, tsc does not look for a bare specifier in a project directory.
    """
    del repo
    out: list[Path] = []
    matches = _alias_matches(specifier, config)
    if matches:
        _priority, targets, matched = max(matches, key=lambda item: item[0])
        out.extend(_replace_star(target, matched) for target in targets)
    if config.base_url is not None:
        out.append(config.base_url / specifier)
    return out


def is_alias(specifier: str, config: TypeScriptConfig) -> bool:
    """This function tells if a `paths` pattern in the configuration matches a specifier."""
    return bool(_alias_matches(specifier, config))


def _alias_matches(
    specifier: str, config: TypeScriptConfig
) -> list[tuple[tuple[int, int, int], tuple[Path, ...], str]]:
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
    return matches


def _replace_star(target: Path, matched: str) -> Path:
    """This function replaces a wildcard in a resolved alias target."""
    return Path(str(target).replace("*", matched))


def source_targets(
    target: str, repo: Path, config: TypeScriptConfig, roots: Iterable[Path]
) -> list[Path]:
    """This function resolves package output targets to source paths for each root.

    A target outside outDir, or without configured outDir, stays unchanged because it
    can already refer to source.
    """
    built = (repo / target).resolve()
    if config.out_dir is None or not built.is_relative_to(config.out_dir):
        return [built]
    relative = built.relative_to(config.out_dir)
    return [root / relative for root in roots]
