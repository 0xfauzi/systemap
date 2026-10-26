"""The configuration reader gets project settings from `systemap.toml` or
`[tool.systemap]`.

These settings specify source roots, tests, the model, outputs, figures, themes, and
evidence mechanisms. The reference document lists the keys and defaults.
"""

from __future__ import annotations

import dataclasses
import os
import re
import subprocess
import tomllib
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap import (
    config_decisions,
    contract_file,
    decision_kinds,
    file_names,
    flow_ids,
    model_fields,
    model_load,
    repo_files,
    tool_table,
)
from systemap import language as languages
from systemap.config_paths import names as written_names
from systemap.delta_link import page_url
from systemap.language_config import package_roots, tests_directories, writing_profile
from systemap.model import Meaning, Model
from systemap.root_check import checked_roots

CONFIG_FILE = "systemap.toml"
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "build", "dist", "tests", "docs"}
# What a walk for tests directories or package candidates never enters:
# the skipped directories minus `tests` itself, plus a plain `venv`.
SKIP_WALK = (SKIP_DIRS - {"tests"}) | {"venv"}
TEST_DIR_NAMES = ("tests", "test")
# Output directory names. If the language adapter identifies a directory with one of
# these names as a package, such as the pypa/build package, the walks go into it.
OUTPUT_DIRS = frozenset({"build", "dist"})
CANDIDATE_DEPTH = 4

KNOWN_KEYS = {
    "language",
    "name",
    "package_roots",
    "tests_dir",
    "test_patterns",
    "model",
    "out_dir",
    "facts_file",
    "spec_path",
    "planes",
    "outside_label",
    "theme",
    "figures",
    "coverage",
    "facts",
    "judgement",
    "flows",
    "jev",
    # Only for a clear error: config_decisions refuses the old [decision] table.
    "decision",
    "openai",
    "agent",
    "delta",
    "writing",
    "rules",
    "decisions",
}
FACTS_KEYS = {"model_sdks"}
FLOWS_KEYS = {"observed_by"}
JEV_KEYS = {"model", "cache", "enabled"}
AGENT_KEYS = {"command", "cache", "timeout"}
FIGURE_KEYS = {"out", "mode", "components", "caption", "interactive", "svg_id", "layer", "map"}
COVERAGE_KEYS = {"ignore"}
IGNORE_KEYS = {"module", "reason"}
JUDGEMENT_KEYS = {"answered", "require_reviews"}
ANSWER_FORMS = ("item", "items", "crossing", "crossing_into", "crossing_from", "kind", "module_sdk")
ANSWER_KEYS = {*ANSWER_FORMS, "reason", "evidence", "policy", "reviewed", "citations"}
# The kinds of line `systemap judgement` prints, as `kind = "..."` names them.
LINE_KINDS = (
    "single module",
    "possible mis-fold",
    "no sentence",
    "thin layer",
    "entry point",
    "journey start",
    "drafted journey",
    "step source",
    "crossing import",
    "declared flow",
    "flow review",
    "no endpoint source",
    "stale source review",
    "missing source review",
    "model sdk",
    "unknown surface",
    "contract reason",
)
# The kinds of line `systemap audit` prints; answered in the same list.
AUDIT_KINDS = decision_kinds.KINDS


class ConfigError(Exception):
    """The configuration has an error. The message gives the necessary correction."""


class ArgumentError(ConfigError):
    """A command option has a value that the command cannot use. The message gives the reason."""


@dataclass(frozen=True)
class Figure:
    """This record specifies one configured figure for `systemap refresh`."""

    out: str
    mode: str = "system"
    components: tuple[str, ...] = ()
    caption: str = ""
    interactive: bool = True
    svg_id: str = "lessonmap"
    layer: str = ""
    map: str = ""


@dataclass(frozen=True)
class Ignore:
    """This record lets the map omit a module from coverage and gives the reason.

    The module selector uses an exact name or a package pattern with `.*`."""

    module: str
    reason: str


@dataclass(frozen=True)
class Answer:
    """This record gives a maintainer answer for exact diagnostic lines or a family of
    lines.

    Exact items contain the full printed line without the two-space indent. Family
    selectors use component IDs, a diagnostic kind, or an SDK import. Evidence binds
    exact answers to source data. A policy lets family answers accept diagnostics.
    """

    items: tuple[str, ...]
    reason: str
    crossing: tuple[str, ...] | None = None
    kind: str = ""
    module_sdk: str = ""
    crossing_into: str = ""
    crossing_from: str = ""
    evidence: str = ""
    policy: bool = False
    reviewed: tuple[str, ...] = ()
    # (file, start_line, end_line, sha256) for each source span that supports the answer.
    citations: tuple[tuple[str, int, int, str], ...] = ()

    @property
    def label(self) -> str:
        """This property gives the answer selector as configuration text for stale-answer
        reports."""
        if self.crossing is not None:
            return "crossing = [" + ", ".join(f'"{cid}"' for cid in self.crossing) + "]"
        if self.crossing_into:
            return f'crossing_into = "{self.crossing_into}"'
        if self.crossing_from:
            return f'crossing_from = "{self.crossing_from}"'
        if self.kind:
            return f'kind = "{self.kind}"'
        if self.module_sdk:
            return f'module_sdk = "{self.module_sdk}"'
        return self.items[0] if len(self.items) == 1 else f"items = {list(self.items)}"


@dataclass(frozen=True)
class Config:
    root: Path
    name: str
    package_roots: tuple[tuple[str, str], ...]
    language: str
    tests_dirs: tuple[str, ...] = ()
    test_patterns: tuple[str, ...] = ()
    model: str = "map/model.py"
    out_dir: str = "docs/map"
    facts_file: str = "map.json"
    spec_path: str = ""
    planes: tuple[str, ...] = ()
    outside_label: str = "EXTERNAL COMPONENTS"
    theme: dict[str, Any] = field(default_factory=dict)
    figures: tuple[Figure, ...] = ()
    coverage_ignore: tuple[Ignore, ...] = ()
    judgement_answered: tuple[Answer, ...] = ()
    model_sdks: tuple[str, ...] = ()
    observed_by: tuple[str, ...] = ()
    jev_model: str = "jev-latest"
    jev_cache: str = ".systemap/jev-cache.json"
    # None: no explicit value. Only true makes delta ask Jev without --jev.
    # false also stops the hints that tell what Jev can add.
    jev_enabled: bool | None = None
    # The decision provider of the commands that ask questions. A key never selects it.
    decision_provider: str = "jev"
    openai_model: str = "gpt-6-luna"
    openai_cache: str = ".systemap/openai-cache.json"
    # The command that writes the prose systemap asks for; none by default, and
    # then the commands that would ask print their structure and say so.
    agent_command: str = ""
    agent_cache: str = ".systemap/agent-cache.json"
    agent_timeout: float = 300.0
    # The URL of the published map page of a pull request, with {number}. Empty: no comment.
    delta_page_url: str = ""
    writing_profile: str = "plain"  # the writing profile for map text
    # "fail": an import rule with the result unknown makes `systemap check` fail.
    rules_unknown: str = "warn"
    require_reviews: bool = False  # [judgement] require_reviews: a missing review is a finding
    max_contradicted: int = 3  # [decisions] max_contradicted: a loop bound, not a measurement
    source: str = ""

    @property
    def model_path(self) -> Path:
        return self.root / self.model

    @property
    def out_path(self) -> Path:
        return self.root / self.out_dir

    @property
    def jev_cache_path(self) -> Path:
        return self.root / self.jev_cache

    @property
    def openai_cache_path(self) -> Path:
        return self.root / self.openai_cache

    @property
    def agent_cache_path(self) -> Path:
        return self.root / self.agent_cache

    @property
    def facts_path(self) -> Path:
        return self.out_path / self.facts_file

    @property
    def page_path(self) -> Path:
        return self.out_path / "index.html"

    @property
    def roots(self) -> list[tuple[Path, str]]:
        """This property gives each existing package directory and import name."""
        out: list[tuple[Path, str]] = []
        for rel, name in self.package_roots:
            pkg = self.root / rel
            if pkg.is_dir():
                out.append((pkg, name))
        return out

    @property
    def prefixes(self) -> set[str]:
        return {name for _, name in self.package_roots}

    @property
    def test_dirs(self) -> tuple[str, ...]:
        """This property gives configured test directories, or discovered directories if
        none are configured.
        """
        if self.tests_dirs:
            return self.tests_dirs
        package_dir = languages.repository(self.language).package_dir if self.language else _none
        return tuple(discover_tests(self.root, package_dir))

    def rel(self, path: Path) -> str:
        """This method gives a path relative to the root when the path is inside the root."""
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return str(path)


def find_root(start: Path) -> Path | None:
    """This function finds the nearest parent directory with configuration or .git,
    including the start directory."""
    for candidate in (start, *start.parents):
        if repo_files.present(candidate / CONFIG_FILE):
            return candidate
        pyproject = candidate / "pyproject.toml"
        if repo_files.present(pyproject) and configures(pyproject):
            return candidate
        if (candidate / ".git").exists():
            return candidate
    return None


def configures(pyproject: Path) -> bool:
    """Tell if pyproject.toml has a tool.systemap table.

    If the file is not correct TOML and it contains the text tool.systemap, the result is
    `True`. Then the configuration reader gives the TOML error for that file. A file
    that the reader refuses, such as a link out of the folder, also gives `True`. A `tool`
    or `tool.systemap` value that is not a table also gives `True` (see tool_table)."""
    try:
        text = repo_files.read_text(pyproject.parent, pyproject.name, encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return True
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        return "tool.systemap" in text
    try:
        return tool_table.section(data) is not None
    except ValueError:
        return True


PackageDir = Callable[[Path], bool]


def skipped(directory: Path, names: Collection[str], package_dir: PackageDir) -> bool:
    """This function finds a directory that a walk does not go into.

    A hidden directory, a directory with a name that is not valid UTF-8, and a directory
    in `names` are skipped. If the language adapter identifies a directory with the name
    of an output directory as a package, the directory is not skipped."""
    name = directory.name
    if name.startswith(".") or not file_names.valid(name):
        return True
    return name in names and not (name in OUTPUT_DIRS and package_dir(directory))


def walk(root: Path, package_dir: PackageDir, depth: int | None = None) -> list[Path]:
    """This function lists directories under the root, except for excluded directories."""
    out: list[Path] = []
    for dirpath, dirnames, _files in os.walk(root):
        here = Path(dirpath)
        level = len(here.relative_to(root).parts)
        dirnames[:] = sorted(d for d in dirnames if not skipped(here / d, SKIP_WALK, package_dir))
        if depth is not None and level >= depth:
            dirnames[:] = []
        if here != root:
            out.append(here)
    return out


def _none(directory: Path) -> bool:
    """Without a known language, no directory is a package."""
    del directory
    return False


def discover_tests(root: Path, package_dir: PackageDir) -> list[str]:
    """This function finds test and tests directories under the root. It does not search
    inside a discovered test directory.
    """
    out: list[str] = []
    for dirpath, dirnames, _files in os.walk(root):
        here = Path(dirpath)
        keep: list[str] = []
        for d in sorted(dirnames):
            if skipped(here / d, SKIP_WALK, package_dir):
                continue
            if d in TEST_DIR_NAMES:
                out.append((here / d).relative_to(root).as_posix())
            else:
                keep.append(d)
        dirnames[:] = keep
    return out


def default_name(root: Path, language: str) -> str:
    """This function selects the project name, Git repository directory name, or root
    directory name.

    The adapter reads the project name from the package metadata. A name with a control
    character is not used. A worktree uses the common Git directory to identify its repository.
    """
    name = languages.repository(language).project_name(root) if language else ""
    if name and file_names.valid(name):
        return name
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        proc = None
    if proc is not None and proc.returncode == 0 and proc.stdout.strip():
        common = (root / proc.stdout.strip()).resolve()
        holder = common.parent.name if common.name == ".git" else common.name.removesuffix(".git")
        if holder:
            return holder
    return root.name


def read_raw(root: Path) -> tuple[dict[str, Any], str]:
    """This function reads the configuration table from systemap.toml first, then
    pyproject.toml.
    """
    if repo_files.present(root / CONFIG_FILE):
        try:
            text = repo_files.read_text(root, CONFIG_FILE, encoding="utf-8-sig")
            return tomllib.loads(text), CONFIG_FILE
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise ConfigError(f"{CONFIG_FILE}: {exc}") from exc
    if repo_files.present(root / "pyproject.toml"):
        try:
            text = repo_files.read_text(root, "pyproject.toml", encoding="utf-8-sig")
            section = tool_table.section(tomllib.loads(text))
        except (OSError, ValueError) as exc:
            raise ConfigError(f"pyproject.toml: {exc}") from exc
        if section is not None:
            return section, "pyproject.toml [tool.systemap]"
    return {}, ""


def _str(raw: dict[str, Any], key: str, default: str, source: str) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(f"{source}: {key} must be a string.")
    return value


def _str_list(raw: dict[str, Any], key: str, source: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{source}: {key} must be a list of strings.")
    return tuple(value)


def load(root: Path) -> Config:
    """This function reads and validates the project configuration, including defaults."""
    root = root.resolve()
    raw, source = read_raw(root)
    where = source or "defaults"
    unknown = sorted(set(raw) - KNOWN_KEYS)
    if unknown:
        raise ConfigError(
            f"{where}: unknown key{'s' if len(unknown) > 1 else ''}: {', '.join(unknown)}"
        )

    try:
        language = _language(root, raw, where)
        roots = package_roots(root, language, raw.get("package_roots"), where)
        roots = checked_roots(root, language, raw, roots, KNOWN_KEYS, where)
        tests_dirs = tests_directories(raw.get("tests_dir", []), where)
        delta_page_url = page_url(raw, where)
        writing = writing_profile(raw.get("writing"), where)
        decided = {**config_decisions.read(raw, where), **written_names(raw, where)}
        decided["rules_unknown"] = config_decisions.rules_unknown(raw, where)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    theme = raw.get("theme", {})
    if not isinstance(theme, dict):
        raise ConfigError(f"{where}: theme must be a table")

    return Config(
        coverage_ignore=_coverage_ignore(raw, where),
        judgement_answered=_judgement_answered(raw, where),
        model_sdks=_facts(raw, where),
        observed_by=_flows(raw, where),
        **_jev(raw, where),
        **_agent(raw, where),
        **decided,
        root=root,
        name=_str(raw, "name", "", where) or default_name(root, language),
        package_roots=roots,
        language=language,
        tests_dirs=tests_dirs,
        test_patterns=_str_list(raw, "test_patterns", where),
        model=_str(raw, "model", "map/model.py", where),
        out_dir=_str(raw, "out_dir", "docs/map", where),
        spec_path=_str(raw, "spec_path", "", where),
        planes=_str_list(raw, "planes", where),
        outside_label=_str(raw, "outside_label", "EXTERNAL COMPONENTS", where),
        theme=theme,
        figures=_figures(raw, where),
        delta_page_url=delta_page_url,
        writing_profile=writing,
        source=source,
    )


def _language(root: Path, raw: dict[str, Any], where: str) -> str:
    """This function gives the configured language, or the language of the source.

    Without the language key, the adapters examine the configured package roots, or
    they find their own package roots. If the language is not clear, the function
    stops and tells the maintainer to set the language key."""
    if "language" not in raw:
        folders = _root_folders(root, raw.get("package_roots"))
        try:
            return languages.detect(root, folders)
        except languages.LanguageError as exc:
            raise ValueError(f"{where}: {exc}") from exc
    language = _str(raw, "language", "", where)
    if language not in languages.names():
        choices = " or ".join(f'"{name}"' for name in languages.names())
        raise ValueError(f"{where}: language must be {choices}")
    return language


def _root_folders(root: Path, value: Any) -> tuple[Path, ...]:
    if not isinstance(value, dict):
        return ()
    return tuple(root / str(path) for path in value)


def _figures(raw: dict[str, Any], where: str) -> tuple[Figure, ...]:
    """This function reads the `[[figures]]` tables."""
    items = raw.get("figures", [])
    if not isinstance(items, list):
        raise ConfigError(f"{where}: figures must be a list of tables. Use [[figures]].")
    return tuple(_figure(item, k, where) for k, item in enumerate(items, start=1))


def _figure(item: Any, k: int, where: str) -> Figure:
    if not isinstance(item, dict):
        raise ConfigError(f"{where}: figures[{k}] must be a table")
    bad = sorted(set(item) - FIGURE_KEYS)
    if bad:
        raise ConfigError(f"{where}: figures[{k}] has an unknown key: {', '.join(bad)}")
    out = item.get("out")
    if not isinstance(out, str) or not out:
        raise ConfigError(f"{where}: figures[{k}] must contain an out file name.")
    mode = _str(item, "mode", "system", where)
    if mode not in ("system", "reach"):
        raise ConfigError(f'{where}: figures[{k}] mode must be "system" or "reach"')
    components = _str_list(item, "components", where)
    if mode == "reach" and not components:
        raise ConfigError(f"{where}: figures[{k}] is a reach figure with no components")
    interactive = item.get("interactive", True)
    if not isinstance(interactive, bool):
        raise ConfigError(f"{where}: figures[{k}] interactive must be true or false")
    return Figure(
        out=out,
        mode=mode,
        components=components,
        caption=_str(item, "caption", "", where),
        interactive=interactive,
        svg_id=_str(item, "svg_id", "lessonmap", where),
        layer=_str(item, "layer", "", where),
        map=_str(item, "map", "", where),
    )


def _coverage_ignore(raw: dict[str, Any], where: str) -> tuple[Ignore, ...]:
    """This function reads `[coverage] ignore`. Each ignore entry must have a reason."""
    coverage = raw.get("coverage", {})
    if not isinstance(coverage, dict):
        raise ConfigError(f"{where}: coverage must be a table")
    bad = sorted(set(coverage) - COVERAGE_KEYS)
    if bad:
        raise ConfigError(f"{where}: coverage has an unknown key: {', '.join(bad)}")
    entries = coverage.get("ignore", [])
    if not isinstance(entries, list):
        raise ConfigError(f"{where}: coverage.ignore must be a list of tables")
    out: list[Ignore] = []
    for k, item in enumerate(entries, start=1):
        if not isinstance(item, dict):
            raise ConfigError(
                f"{where}: coverage.ignore[{k}] must be a table with module and reason"
            )
        bad = sorted(set(item) - IGNORE_KEYS)
        if bad:
            raise ConfigError(f"{where}: coverage.ignore[{k}] has an unknown key: {', '.join(bad)}")
        module = item.get("module")
        if not isinstance(module, str) or not module:
            raise ConfigError(f"{where}: coverage.ignore[{k}] must contain a module name.")
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ConfigError(
                f"{where}: coverage.ignore[{k}] ({module}) must contain a reason. Give the "
                f"reason that the map can omit this module."
            )
        out.append(Ignore(module=module, reason=reason))
    return tuple(out)


def _facts(raw: dict[str, Any], where: str) -> tuple[str, ...]:
    """This function reads `[facts]`, including additions and removals for the model SDK
    list.
    """
    facts = raw.get("facts", {})
    if not isinstance(facts, dict):
        raise ConfigError(f"{where}: facts must be a table")
    bad = sorted(set(facts) - FACTS_KEYS)
    if bad:
        raise ConfigError(f"{where}: facts has an unknown key: {', '.join(bad)}")
    return _str_list(facts, "model_sdks", f"{where}: facts")


def _flows(raw: dict[str, Any], where: str) -> tuple[str, ...]:
    """This function reads `[flows]`. The observed_by list specifies mechanisms other than
    imports.
    """
    flows = raw.get("flows", {})
    if not isinstance(flows, dict):
        raise ConfigError(f"{where}: flows must be a table")
    bad = sorted(set(flows) - FLOWS_KEYS)
    if bad:
        raise ConfigError(f"{where}: flows has an unknown key: {', '.join(bad)}")
    names = _str_list(flows, "observed_by", f"{where}: flows")
    if any(not name.strip() for name in names):
        raise ConfigError(f"{where}: flows.observed_by must contain a word for each mechanism.")
    return tuple(name.strip() for name in names)


def _jev(raw: dict[str, Any], where: str) -> dict[str, Any]:
    """This function reads the Jev model, cache, and automatic-request settings."""
    jev = raw.get("jev", {})
    if not isinstance(jev, dict):
        raise ConfigError(f"{where}: jev must be a table")
    bad = sorted(set(jev) - JEV_KEYS)
    if bad:
        raise ConfigError(f"{where}: jev has an unknown key: {', '.join(bad)}")
    model = _str(jev, "model", "jev-latest", f"{where}: jev").strip()
    cache = _str(jev, "cache", ".systemap/jev-cache.json", f"{where}: jev").strip()
    if not model or not cache:
        raise ConfigError(f"{where}: jev.model and jev.cache must not be empty")
    enabled = jev.get("enabled")
    if enabled is not None and not isinstance(enabled, bool):
        raise ConfigError(f"{where}: jev.enabled must be true or false")
    return {"jev_model": model, "jev_cache": cache, "jev_enabled": enabled}


def _agent(raw: dict[str, Any], where: str) -> dict[str, Any]:
    """This function reads the agent command, cache path, and timeout."""
    agent = raw.get("agent", {})
    if not isinstance(agent, dict):
        raise ConfigError(f"{where}: agent must be a table")
    bad = sorted(set(agent) - AGENT_KEYS)
    if bad:
        raise ConfigError(f"{where}: agent has an unknown key: {', '.join(bad)}")
    command = _str(agent, "command", "", f"{where}: agent").strip()
    cache = _str(agent, "cache", ".systemap/agent-cache.json", f"{where}: agent").strip()
    timeout = agent.get("timeout", 300.0)
    if not isinstance(timeout, int | float) or isinstance(timeout, bool) or timeout <= 0:
        raise ConfigError(f"{where}: agent.timeout must be a number of seconds more than zero.")
    if not cache:
        raise ConfigError(f"{where}: agent.cache must not be empty")
    return {"agent_command": command, "agent_cache": cache, "agent_timeout": float(timeout)}


def _answer_selector(form: str, value: Any, location: str) -> Answer:
    """Validate the answer selector without its reason or evidence."""
    if form in ("item", "items"):
        return Answer(items=_answer_lines(form, value, location), reason="")
    if form == "crossing":
        return Answer(items=(), reason="", crossing=_answer_crossing(value, location))
    if form in ("crossing_into", "crossing_from"):
        name = _answer_name(value, f"{location} {form} must contain one component ID.")
        if form == "crossing_into":
            return Answer(items=(), reason="", crossing_into=name)
        return Answer(items=(), reason="", crossing_from=name)
    if form == "kind":
        error = f"{location} kind must be one of {', '.join((*LINE_KINDS, *AUDIT_KINDS))}"
        name = _answer_name(value, error)
        # A previous name of a decision kind stays correct for one release.
        if name not in (*LINE_KINDS, *decision_kinds.AUDIT_NAMES):
            raise ConfigError(error)
        return Answer(items=(), reason="", kind=name)
    name = _answer_name(value, f"{location} module_sdk must be an import name.")
    return Answer(items=(), reason="", module_sdk=name)


def _answer_name(value: Any, error: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(error)
    return value.strip()


def _answer_lines(form: str, value: Any, location: str) -> tuple[str, ...]:
    if form == "item":
        return (_answer_name(value, f"{location} item must be a line."),)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(v, str) and v.strip() for v in value)
    ):
        raise ConfigError(f"{location} items must be a list with one or more lines.")
    return tuple(v.strip() for v in value)


def _answer_crossing(value: Any, location: str) -> tuple[str, ...]:
    ids = (
        [v.strip() if isinstance(v, str) else "" for v in value] if isinstance(value, list) else []
    )
    if len(ids) < 2 or not all(ids) or len(set(ids)) != len(ids):
        raise ConfigError(
            f"{location} crossing must contain two or more different component IDs, such "
            f'as ["A", "B"].'
        )
    return tuple(ids)


def _judgement_answered(raw: dict[str, Any], where: str) -> tuple[Answer, ...]:
    """This function reads and validates `[judgement] answered`, including reasons and
    evidence.
    """
    judgement = raw.get("judgement", {})
    if not isinstance(judgement, dict):
        raise ConfigError(f"{where}: judgement must be a table")
    bad = sorted(set(judgement) - JUDGEMENT_KEYS)
    if bad:
        raise ConfigError(f"{where}: judgement has an unknown key: {', '.join(bad)}")
    entries = judgement.get("answered", [])
    if not isinstance(entries, list):
        raise ConfigError(f"{where}: judgement.answered must be a list of tables")
    return tuple(
        _answer_entry(entry, f"{where}: judgement.answered[{k}]")
        for k, entry in enumerate(entries, start=1)
    )


def _answer_entry(entry: Any, location: str) -> Answer:
    if not isinstance(entry, dict):
        raise ConfigError(f"{location} must be a table with item (or items) and reason.")
    bad = sorted(set(entry) - ANSWER_KEYS)
    if bad:
        raise ConfigError(f"{location} has an unknown key: {', '.join(bad)}")
    forms = [form for form in ANSWER_FORMS if entry.get(form) is not None]
    if len(forms) != 1:
        raise ConfigError(
            f"{location} must contain one selector: item, items, crossing, crossing_into, "
            f"crossing_from, kind, or module_sdk. The selector count is {len(forms)}"
        )
    (form,) = forms
    answer = _answer_selector(form, entry[form], location)
    evidence, policy, reviewed = _answer_review(entry, form, location)
    reason = entry.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ConfigError(
            f"{location} ({answer.label}) must contain a reason. Give the reason for the answer."
        )
    try:
        cited = config_decisions.citations(entry.get("citations"), location)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    return dataclasses.replace(
        answer, reason=reason, evidence=evidence, policy=policy, reviewed=reviewed, citations=cited
    )


def _answer_review(
    entry: dict[str, Any], form: str, location: str
) -> tuple[str, bool, tuple[str, ...]]:
    exact = form in ("item", "items")
    evidence = entry.get("evidence", "")
    policy = entry.get("policy", False)
    reviewed = entry.get("reviewed", [])
    if not isinstance(evidence, str) or (evidence and not exact):
        raise ConfigError(f"{location} evidence is permitted only for an exact item.")
    if evidence and re.fullmatch(r"[0-9a-f]{64}", evidence) is None:
        raise ConfigError(f"{location} evidence must be a SHA-256 digest")
    if not isinstance(policy, bool) or (policy and exact):
        raise ConfigError(f"{location} policy is permitted only for a family selector.")
    if not isinstance(reviewed, list) or not all(isinstance(v, str) and v for v in reviewed):
        raise ConfigError(f"{location} reviewed must be a list of lines")
    if reviewed and not policy:
        raise ConfigError(f"{location} reviewed is permitted only with policy = true.")
    return evidence, policy, tuple(reviewed)


def load_model(path: Path, label: str = "", root: Path | None = None) -> tuple[Model, Meaning]:
    """This function reads the model file and gets MODEL and MEANING.

    The reader runs no code from the file. Only the environment of the command can permit
    code, with SYSTEMAP_TRUST_MODEL_CODE=1 (see model_load). MODEL gets the rules of the
    contract file (`contract_file.merged`). The optional label supplies the path name in
    error messages. The optional root must contain the map files (see model_load.read). A
    refusal, an import error, or a name that the page cannot use (see model_names) gives a
    configuration diagnostic. A sequence step that names its flow by id gets the edge."""
    if not path.is_file():
        problem = "not a regular file" if repo_files.present(path) else "missing"
        raise ConfigError(f"The model module is {problem}: {path}")
    label = label or str(path)
    try:
        names = model_load.load(path, label, root)
        names["MODEL"] = contract_file.merged(path, label, names.get("MODEL"), root)
    except model_load.ModelFileError as exc:
        raise ConfigError(str(exc)) from exc
    model = names.get("MODEL")
    meaning = names.get("MEANING")
    if not isinstance(model, Model):
        raise ConfigError(f"{label}: MODEL must be a systemap.Model")
    if not isinstance(meaning, Meaning):
        raise ConfigError(f"{label}: MEANING must be a systemap.Meaning")
    found, model, meaning = model_fields.checked(model, meaning)
    if found:
        raise ConfigError(f"{label}: {found}")
    return model, flow_ids.resolve(model, meaning)
