"""Read project settings from `systemap.toml` or `[tool.systemap]`.

The settings locate source, tests, the map model, output, figures, themes,
and evidence mechanisms. `docs/reference.md` lists every key and default.
Unknown keys fail validation so a misspelling cannot silently change what
the commands read.

`[judgement] answered` records a reason for each decision. An exact `item`
or `items` decision also records an evidence digest. Changed evidence
reopens it. A broad answer needs `policy = true`, and `reviewed` can list
the instances known when the policy was written. Unmatched answers are
reported as stale.
"""

from __future__ import annotations

import contextlib
import dataclasses
import os
import re
import subprocess
import sys
import tomllib
import types
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap.language_config import package_roots, tests_directories
from systemap.model import Meaning, Model

CONFIG_FILE = "systemap.toml"
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "build", "dist", "tests", "docs"}
# What a walk for tests directories or package candidates never enters:
# the skipped directories minus `tests` itself, plus a plain `venv`.
SKIP_WALK = (SKIP_DIRS - {"tests"}) | {"venv"}
TEST_DIR_NAMES = ("tests", "test")
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
    "agent",
}
FACTS_KEYS = {"model_sdks"}
FLOWS_KEYS = {"observed_by"}
JEV_KEYS = {"model", "cache", "enabled"}
AGENT_KEYS = {"command", "cache", "timeout"}
FIGURE_KEYS = {"out", "mode", "components", "caption", "interactive", "svg_id", "layer", "map"}
COVERAGE_KEYS = {"ignore"}
IGNORE_KEYS = {"module", "reason"}
JUDGEMENT_KEYS = {"answered"}
ANSWER_FORMS = ("item", "items", "crossing", "crossing_into", "crossing_from", "kind", "module_sdk")
ANSWER_KEYS = {*ANSWER_FORMS, "reason", "evidence", "policy", "reviewed"}
# The kinds of line `systemap judgement` prints, as `kind = "..."` names them.
LINE_KINDS = (
    "single module",
    "possible mis-fold",
    "no sentence",
    "thin layer",
    "entry point",
    "journey start",
    "drafted journey",
    "crossing import",
    "declared flow",
    "flow review",
    "model sdk",
    "unknown surface",
)
# The kinds of line `systemap audit` prints; answered in the same list.
AUDIT_KINDS = ("jev mis-fold", "jev owner", "jev sentence", "jev flow", "jev governs")


class ConfigError(Exception):
    """The configuration cannot be used; the message says what to fix."""


@dataclass(frozen=True)
class Figure:
    """One figure `systemap refresh` regenerates beside the page."""

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
    """One module the coverage rule may leave unmapped, and why.

    `module` is an exact module name or a package with `.*` for its
    subtree, the same convention `implemented_by` uses.
    """

    module: str
    reason: str


@dataclass(frozen=True)
class Answer:
    """One or more judgement lines the maintainer has answered, and why.

    `items` are the lines exactly as `systemap judgement` prints them
    (without the two-space indent). The bulk forms answer a family with
    one reason: `crossing` every crossing-import line between any two of
    its ids (two or more) in either direction, `crossing_into` every one
    whose imported module belongs to the named card, `crossing_from`
    every one whose importing module does, `kind` every line of one kind,
    `module_sdk` every model sdk line for one import. Exactly one form
    is set. The answer is the hand-back: it lives in the repository
    beside the model, not in a conversation. `evidence` binds exact
    decisions to the source reviewed. `policy` deliberately covers a
    family, and `reviewed` marks the instances known when it was recorded.
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

    @property
    def label(self) -> str:
        """The answer as the configuration wrote it, for the stale report."""
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
    language: str = "python"
    tests_dirs: tuple[str, ...] = ()
    test_patterns: tuple[str, ...] = ()
    model: str = "map/model.py"
    out_dir: str = "docs/map"
    facts_file: str = "map.json"
    spec_path: str = ""
    planes: tuple[str, ...] = ()
    outside_label: str = "OUTSIDE THE SYSTEM"
    theme: dict[str, Any] = field(default_factory=dict)
    figures: tuple[Figure, ...] = ()
    coverage_ignore: tuple[Ignore, ...] = ()
    judgement_answered: tuple[Answer, ...] = ()
    model_sdks: tuple[str, ...] = ()
    observed_by: tuple[str, ...] = ()
    jev_model: str = "jev-latest"
    jev_cache: str = ".systemap/jev-cache.json"
    # false: delta does not ask Jev on its own, and no command says what Jev would add
    jev_enabled: bool = True
    # The command that writes the prose systemap asks for; none by default, and
    # then the commands that would ask print their structure and say so.
    agent_command: str = ""
    agent_cache: str = ".systemap/agent-cache.json"
    agent_timeout: float = 300.0
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
        """(package directory, import name) for every package root that exists."""
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
        """The directories test files are read from: configured, else discovered."""
        return self.tests_dirs or tuple(discover_tests(self.root))

    def rel(self, path: Path) -> str:
        """A path shown to the user, relative to the root when it is under it."""
        try:
            return path.relative_to(self.root).as_posix()
        except ValueError:
            return str(path)


def find_root(start: Path) -> Path | None:
    """The nearest ancestor (or `start`) holding a configuration or a .git."""
    for candidate in (start, *start.parents):
        if (candidate / CONFIG_FILE).is_file():
            return candidate
        pyproject = candidate / "pyproject.toml"
        if pyproject.is_file() and "[tool.systemap]" in pyproject.read_text(encoding="utf-8"):
            return candidate
        if (candidate / ".git").exists():
            return candidate
    return None


def _pyproject(root: Path) -> dict[str, Any]:
    path = root / "pyproject.toml"
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def workspace_members(root: Path) -> list[Path]:
    """The directories `[tool.uv.workspace] members` names, by its globs."""
    workspace = _pyproject(root).get("tool", {}).get("uv", {}).get("workspace", {})
    members = workspace.get("members", []) if isinstance(workspace, dict) else []
    out: list[Path] = []
    for pattern in members:
        if not isinstance(pattern, str):
            continue
        for path in sorted(root.glob(pattern)):
            if path.is_dir() and path.resolve() != root.resolve() and path not in out:
                out.append(path)
    return out


def discover_roots(root: Path) -> list[tuple[str, str]]:
    """Every top-level directory holding an __init__.py, plus src/<pkg> layouts.

    The root is searched, then every workspace member (`packages/<m>/src/<pkg>`
    and `packages/<m>/<pkg>`), so a uv workspace needs no configuration.
    """
    found: list[tuple[str, str]] = []
    for base in (root, *workspace_members(root)):
        for parent in (base, base / "src"):
            if not parent.is_dir():
                continue
            for child in sorted(parent.iterdir()):
                if not child.is_dir() or child.name in SKIP_DIRS or child.name.startswith("."):
                    continue
                if (child / "__init__.py").is_file():
                    entry = (child.relative_to(root).as_posix(), child.name)
                    if entry not in found:
                        found.append(entry)
    return found


def _walk(root: Path, depth: int | None = None) -> list[Path]:
    """Every directory under `root`, skipping what a walk never enters."""
    out: list[Path] = []
    for dirpath, dirnames, _files in os.walk(root):
        here = Path(dirpath)
        level = len(here.relative_to(root).parts)
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_WALK and not d.startswith("."))
        if depth is not None and level >= depth:
            dirnames[:] = []
        if here != root:
            out.append(here)
    return out


def discover_tests(root: Path) -> list[str]:
    """Every directory named tests or test under the root, relative, in walk order.

    A found directory is not entered again: its subdirectories are its own.
    """
    out: list[str] = []
    for dirpath, dirnames, _files in os.walk(root):
        here = Path(dirpath)
        keep: list[str] = []
        for d in sorted(dirnames):
            if d in SKIP_WALK or d.startswith("."):
                continue
            if d in TEST_DIR_NAMES:
                out.append((here / d).relative_to(root).as_posix())
            else:
                keep.append(d)
        dirnames[:] = keep
    return out


def candidate_packages(root: Path, depth: int = CANDIDATE_DEPTH) -> list[str]:
    """Directories holding an __init__.py up to `depth` below the root, relative.

    Listed when discovery finds no package root, so the fix names what is
    there rather than asking the reader to search.
    """
    return [
        d.relative_to(root).as_posix() for d in _walk(root, depth) if (d / "__init__.py").is_file()
    ]


def default_name(root: Path) -> str:
    """`[project] name`, else the git repository's directory, else the root's name.

    The repository's directory is the one holding the common git dir, so
    a worktree is named after the checkout it belongs to, not after the
    worktree's own directory.
    """
    project = _pyproject(root).get("project", {})
    name = project.get("name") if isinstance(project, dict) else None
    if isinstance(name, str) and name.strip():
        return name.strip()
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
    """The raw table and where it came from: systemap.toml first, then pyproject."""
    toml = root / CONFIG_FILE
    if toml.is_file():
        try:
            return tomllib.loads(toml.read_text(encoding="utf-8")), CONFIG_FILE
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"{CONFIG_FILE}: {exc}") from exc
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"pyproject.toml: {exc}") from exc
        section = data.get("tool", {}).get("systemap")
        if isinstance(section, dict):
            return section, "pyproject.toml [tool.systemap]"
    return {}, ""


def _str(raw: dict[str, Any], key: str, default: str, source: str) -> str:
    value = raw.get(key, default)
    if not isinstance(value, str):
        raise ConfigError(f"{source}: {key} must be a string")
    return value


def _str_list(raw: dict[str, Any], key: str, source: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ConfigError(f"{source}: {key} must be a list of strings")
    return tuple(value)


def load(root: Path) -> Config:
    """The configuration for the project at `root`, defaults filled in."""
    root = root.resolve()
    raw, source = read_raw(root)
    where = source or "defaults"
    unknown = sorted(set(raw) - KNOWN_KEYS)
    if unknown:
        raise ConfigError(
            f"{where}: unknown key{'s' if len(unknown) > 1 else ''}: {', '.join(unknown)}"
        )

    language = _str(raw, "language", "python", where)
    if language not in ("python", "typescript"):
        raise ConfigError(f'{where}: language must be "python" or "typescript"')

    try:
        roots = package_roots(root, language, raw.get("package_roots"), where)
        tests_dirs = tests_directories(raw.get("tests_dir", []), where)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc

    theme = raw.get("theme", {})
    if not isinstance(theme, dict):
        raise ConfigError(f"{where}: theme must be a table")

    figures: list[Figure] = []
    for k, item in enumerate(raw.get("figures", []), start=1):
        if not isinstance(item, dict):
            raise ConfigError(f"{where}: figures[{k}] must be a table")
        bad = sorted(set(item) - FIGURE_KEYS)
        if bad:
            raise ConfigError(f"{where}: figures[{k}] has unknown key: {', '.join(bad)}")
        out = item.get("out")
        if not isinstance(out, str) or not out:
            raise ConfigError(f"{where}: figures[{k}] needs an out file name")
        mode = _str(item, "mode", "system", where)
        if mode not in ("system", "reach"):
            raise ConfigError(f'{where}: figures[{k}] mode must be "system" or "reach"')
        components = _str_list(item, "components", where)
        if mode == "reach" and not components:
            raise ConfigError(f"{where}: figures[{k}] is a reach figure with no components")
        interactive = item.get("interactive", True)
        if not isinstance(interactive, bool):
            raise ConfigError(f"{where}: figures[{k}] interactive must be true or false")
        figures.append(
            Figure(
                out=out,
                mode=mode,
                components=components,
                caption=_str(item, "caption", "", where),
                interactive=interactive,
                svg_id=_str(item, "svg_id", "lessonmap", where),
                layer=_str(item, "layer", "", where),
                map=_str(item, "map", "", where),
            )
        )

    return Config(
        coverage_ignore=_coverage_ignore(raw, where),
        judgement_answered=_judgement_answered(raw, where),
        model_sdks=_facts(raw, where),
        observed_by=_flows(raw, where),
        **_jev(raw, where),
        **_agent(raw, where),
        root=root,
        name=_str(raw, "name", "", where) or default_name(root),
        package_roots=roots,
        language=language,
        tests_dirs=tests_dirs,
        test_patterns=_str_list(raw, "test_patterns", where),
        model=_str(raw, "model", "map/model.py", where),
        out_dir=_str(raw, "out_dir", "docs/map", where),
        facts_file=_str(raw, "facts_file", "map.json", where),
        spec_path=_str(raw, "spec_path", "", where),
        planes=_str_list(raw, "planes", where),
        outside_label=_str(raw, "outside_label", "OUTSIDE THE SYSTEM", where),
        theme=theme,
        figures=tuple(figures),
        source=source,
    )


def _coverage_ignore(raw: dict[str, Any], where: str) -> tuple[Ignore, ...]:
    """The `[coverage] ignore` list; an entry without a reason is refused."""
    coverage = raw.get("coverage", {})
    if not isinstance(coverage, dict):
        raise ConfigError(f"{where}: coverage must be a table")
    bad = sorted(set(coverage) - COVERAGE_KEYS)
    if bad:
        raise ConfigError(f"{where}: coverage has unknown key: {', '.join(bad)}")
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
            raise ConfigError(f"{where}: coverage.ignore[{k}] has unknown key: {', '.join(bad)}")
        module = item.get("module")
        if not isinstance(module, str) or not module:
            raise ConfigError(f"{where}: coverage.ignore[{k}] needs a module name")
        reason = item.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ConfigError(
                f"{where}: coverage.ignore[{k}] ({module}) needs a reason: "
                "say why the map may leave this module unmapped"
            )
        out.append(Ignore(module=module, reason=reason))
    return tuple(out)


def _facts(raw: dict[str, Any], where: str) -> tuple[str, ...]:
    """The `[facts]` table: `model_sdks` extends the judgement's built-in list."""
    facts = raw.get("facts", {})
    if not isinstance(facts, dict):
        raise ConfigError(f"{where}: facts must be a table")
    bad = sorted(set(facts) - FACTS_KEYS)
    if bad:
        raise ConfigError(f"{where}: facts has unknown key: {', '.join(bad)}")
    return _str_list(facts, "model_sdks", f"{where}: facts")


def _flows(raw: dict[str, Any], where: str) -> tuple[str, ...]:
    """The `[flows]` table: `observed_by` names the non-import mechanisms."""
    flows = raw.get("flows", {})
    if not isinstance(flows, dict):
        raise ConfigError(f"{where}: flows must be a table")
    bad = sorted(set(flows) - FLOWS_KEYS)
    if bad:
        raise ConfigError(f"{where}: flows has unknown key: {', '.join(bad)}")
    names = _str_list(flows, "observed_by", f"{where}: flows")
    if any(not name.strip() for name in names):
        raise ConfigError(f"{where}: flows.observed_by must name each mechanism with a word")
    return tuple(name.strip() for name in names)


def _jev(raw: dict[str, Any], where: str) -> dict[str, Any]:
    """The `[jev]` table: which model the Jev commands ask, where answers are cached,
    and whether delta asks it on its own when a key is set."""
    jev = raw.get("jev", {})
    if not isinstance(jev, dict):
        raise ConfigError(f"{where}: jev must be a table")
    bad = sorted(set(jev) - JEV_KEYS)
    if bad:
        raise ConfigError(f"{where}: jev has unknown key: {', '.join(bad)}")
    model = _str(jev, "model", "jev-latest", f"{where}: jev").strip()
    cache = _str(jev, "cache", ".systemap/jev-cache.json", f"{where}: jev").strip()
    if not model or not cache:
        raise ConfigError(f"{where}: jev.model and jev.cache must not be empty")
    enabled = jev.get("enabled", True)
    if not isinstance(enabled, bool):
        raise ConfigError(f"{where}: jev.enabled must be true or false")
    return {"jev_model": model, "jev_cache": cache, "jev_enabled": enabled}


def _agent(raw: dict[str, Any], where: str) -> dict[str, Any]:
    """The `[agent]` table: the command that writes prose, where its answers are
    cached, and how long it may take."""
    agent = raw.get("agent", {})
    if not isinstance(agent, dict):
        raise ConfigError(f"{where}: agent must be a table")
    bad = sorted(set(agent) - AGENT_KEYS)
    if bad:
        raise ConfigError(f"{where}: agent has unknown key: {', '.join(bad)}")
    command = _str(agent, "command", "", f"{where}: agent").strip()
    cache = _str(agent, "cache", ".systemap/agent-cache.json", f"{where}: agent").strip()
    timeout = agent.get("timeout", 300.0)
    if not isinstance(timeout, int | float) or isinstance(timeout, bool) or timeout <= 0:
        raise ConfigError(f"{where}: agent.timeout must be a number of seconds above zero")
    if not cache:
        raise ConfigError(f"{where}: agent.cache must not be empty")
    return {"agent_command": command, "agent_cache": cache, "agent_timeout": float(timeout)}


def _answer_selector(form: str, value: Any, location: str) -> Answer:
    """Validate the selected answer form without its reason or evidence."""
    if form in ("item", "items"):
        return Answer(items=_answer_lines(form, value, location), reason="")
    if form == "crossing":
        return Answer(items=(), reason="", crossing=_answer_crossing(value, location))
    if form in ("crossing_into", "crossing_from"):
        name = _answer_name(value, f"{location} {form} must name one component id")
        if form == "crossing_into":
            return Answer(items=(), reason="", crossing_into=name)
        return Answer(items=(), reason="", crossing_from=name)
    if form == "kind":
        name = _answer_name(
            value, f"{location} kind must be one of {', '.join((*LINE_KINDS, *AUDIT_KINDS))}"
        )
        if name not in (*LINE_KINDS, *AUDIT_KINDS):
            raise ConfigError(
                f"{location} kind must be one of {', '.join((*LINE_KINDS, *AUDIT_KINDS))}"
            )
        return Answer(items=(), reason="", kind=name)
    name = _answer_name(value, f"{location} module_sdk must be an import name")
    return Answer(items=(), reason="", module_sdk=name)


def _answer_name(value: Any, error: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(error)
    return value.strip()


def _answer_lines(form: str, value: Any, location: str) -> tuple[str, ...]:
    if form == "item":
        return (_answer_name(value, f"{location} item must be a line"),)
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(v, str) and v.strip() for v in value)
    ):
        raise ConfigError(f"{location} items must be a non-empty list of lines")
    return tuple(v.strip() for v in value)


def _answer_crossing(value: Any, location: str) -> tuple[str, ...]:
    ids = [v.strip() for v in value] if isinstance(value, list) else []
    if len(ids) < 2 or not all(isinstance(v, str) and v for v in ids) or len(set(ids)) != len(ids):
        raise ConfigError(
            f'{location} crossing must name two or more different component ids, ["A", "B"]'
        )
    return tuple(ids)


def _judgement_answered(raw: dict[str, Any], where: str) -> tuple[Answer, ...]:
    """The `[judgement] answered` list; an entry without a reason is refused."""
    judgement = raw.get("judgement", {})
    if not isinstance(judgement, dict):
        raise ConfigError(f"{where}: judgement must be a table")
    bad = sorted(set(judgement) - JUDGEMENT_KEYS)
    if bad:
        raise ConfigError(f"{where}: judgement has unknown key: {', '.join(bad)}")
    entries = judgement.get("answered", [])
    if not isinstance(entries, list):
        raise ConfigError(f"{where}: judgement.answered must be a list of tables")
    return tuple(
        _answer_entry(entry, f"{where}: judgement.answered[{k}]")
        for k, entry in enumerate(entries, start=1)
    )


def _answer_entry(entry: Any, location: str) -> Answer:
    if not isinstance(entry, dict):
        raise ConfigError(f"{location} must be a table with item (or items) and reason")
    bad = sorted(set(entry) - ANSWER_KEYS)
    if bad:
        raise ConfigError(f"{location} has unknown key: {', '.join(bad)}")
    forms = [form for form in ANSWER_FORMS if entry.get(form) is not None]
    if len(forms) != 1:
        raise ConfigError(
            f"{location} needs exactly one of item (one line), "
            "items (a list), crossing (two or more component ids), crossing_into or "
            "crossing_from (one component id), kind (a line kind) or module_sdk (an "
            f"import name); it has {len(forms)}"
        )
    (form,) = forms
    answer = _answer_selector(form, entry[form], location)
    evidence, policy, reviewed = _answer_review(entry, form, location)
    reason = entry.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ConfigError(
            f"{location} ({answer.label}) needs a reason: "
            "say why the line is answered rather than acted on"
        )
    return dataclasses.replace(
        answer, reason=reason, evidence=evidence, policy=policy, reviewed=reviewed
    )


def _answer_review(
    entry: dict[str, Any], form: str, location: str
) -> tuple[str, bool, tuple[str, ...]]:
    exact = form in ("item", "items")
    evidence = entry.get("evidence", "")
    policy = entry.get("policy", False)
    reviewed = entry.get("reviewed", [])
    if not isinstance(evidence, str) or (evidence and not exact):
        raise ConfigError(f"{location} evidence needs an exact item")
    if evidence and re.fullmatch(r"[0-9a-f]{64}", evidence) is None:
        raise ConfigError(f"{location} evidence must be a SHA-256 digest")
    if not isinstance(policy, bool) or (policy and exact):
        raise ConfigError(f"{location} policy needs a broad form")
    if not isinstance(reviewed, list) or not all(isinstance(v, str) and v for v in reviewed):
        raise ConfigError(f"{location} reviewed must be a list of lines")
    if reviewed and not policy:
        raise ConfigError(f"{location} reviewed needs policy = true")
    return evidence, policy, tuple(reviewed)


@contextlib.contextmanager
def _beside(folder: Path) -> Iterator[None]:
    """The model's own directory on the path while it runs, and nothing kept after.

    A map outgrows one file, and `import journeys` beside the model is how a
    person would split it. Afterwards the directory comes off the path and
    what it imported is dropped, so the next run reads what is on disk.
    """
    sys.path.insert(0, str(folder))
    held = set(sys.modules)
    try:
        yield
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(str(folder))
        for name in set(sys.modules) - held:
            found = getattr(sys.modules[name], "__file__", None) or ""
            if found and Path(found).resolve().parent == folder:
                del sys.modules[name]


def load_model(path: Path, label: str = "") -> tuple[Model, Meaning]:
    """Import the model module by path and return its MODEL and MEANING.

    `label` is the name the messages call the module by (the configured
    `model`, `map/model.py`); the path itself when not given. A name the
    module could not import or does not know is reported as such, with
    the fix: the starter imports every schema name, and an agent that
    trims the import and then uses `Layer` gets one line, not a traceback.

    The source is compiled and run directly rather than through the import
    system's loader: that loader keeps bytecode keyed by the source's size
    and whole-second mtime, so an edit that changes neither (one name for
    another of the same length, within the same second) would be read back
    as the old model. An agent runs the check after every edit; the model it
    checks must be the one on disk.
    """
    if not path.is_file():
        raise ConfigError(f"model module not found: {path}")
    label = label or str(path)
    name = f"systemap_model_{abs(hash(str(path)))}"
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    beside = path.parent.resolve()
    try:
        source = path.read_text(encoding="utf-8")
        with _beside(beside):
            exec(compile(source, str(path), "exec"), module.__dict__)  # noqa: S102 - it is code
    except (ImportError, NameError) as exc:
        raise ConfigError(
            f"{label} failed to import: {exc}; add the missing name to the import from systemap"
        ) from exc
    except Exception as exc:  # noqa: BLE001 - the consumer's module may fail any way
        raise ConfigError(f"{label} failed to import: {type(exc).__name__}: {exc}") from exc
    finally:
        sys.modules.pop(name, None)
    model = getattr(module, "MODEL", None)
    meaning = getattr(module, "MEANING", None)
    if not isinstance(model, Model):
        raise ConfigError(f"{label}: MODEL must be a systemap.Model")
    if not isinstance(meaning, Meaning):
        raise ConfigError(f"{label}: MEANING must be a systemap.Meaning")
    return model, meaning
