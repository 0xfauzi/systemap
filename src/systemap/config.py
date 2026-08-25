"""Project configuration: `systemap.toml` at the repo root, or `[tool.systemap]`.

Everything project-specific the engine needs lives here, so the engine
itself holds no literal that belongs to one project: where the packages
are, where the tests are, where the model module is, where the output
goes, how an issue number becomes a link, and the theme.

    name           the page title; defaults to the repo directory's name
    package_roots  table of path = import name; default: every top-level
                   directory that holds an __init__.py
    tests_dir      where test_*.py files live (default "tests")
    model          the module exporting MODEL and MEANING (default
                   "map/model.py")
    out_dir        where the facts, the page and the figures are written
                   (default "docs/map")
    facts_file     the facts file's name inside out_dir (default "map.json")
    issue_url      a template with {n}, used for tracker issue numbers
    spec_path      optional document whose ##-headings become spec sections
    planes         optional list of second-level package names that count as
                   their own architectural plane in the facts
    outside_label  the index heading for actors outside every region
    [theme]        tokens laid over the default theme
    [[figures]]    figures `systemap refresh` regenerates: out, mode
                   ("system" or "reach"), components, caption, interactive
    [coverage]     ignore = [{module = "pkg.mod", reason = "..."}]: modules
                   the coverage rule of `systemap check` may leave unmapped;
                   every entry needs a reason, since an unexplained hole in
                   the map is the thing the rule exists to refuse

Unknown keys are a configuration error: a misspelt key that silently did
nothing would be worse than a refusal.
"""

from __future__ import annotations

import importlib.util
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from systemap.model import Meaning, Model

CONFIG_FILE = "systemap.toml"
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__", "build", "dist", "tests", "docs"}

KNOWN_KEYS = {
    "name",
    "package_roots",
    "tests_dir",
    "model",
    "out_dir",
    "facts_file",
    "issue_url",
    "spec_path",
    "planes",
    "outside_label",
    "theme",
    "figures",
    "coverage",
}
FIGURE_KEYS = {"out", "mode", "components", "caption", "interactive", "svg_id"}
COVERAGE_KEYS = {"ignore"}
IGNORE_KEYS = {"module", "reason"}


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


@dataclass(frozen=True)
class Ignore:
    """One module the coverage rule may leave unmapped, and why.

    `module` is an exact module name or a package with `.*` for its
    subtree, the same convention `implemented_by` uses.
    """

    module: str
    reason: str


@dataclass(frozen=True)
class Config:
    root: Path
    name: str
    package_roots: tuple[tuple[str, str], ...]
    tests_dir: str = "tests"
    model: str = "map/model.py"
    out_dir: str = "docs/map"
    facts_file: str = "map.json"
    issue_url: str = ""
    spec_path: str = ""
    planes: tuple[str, ...] = ()
    outside_label: str = "OUTSIDE THE SYSTEM"
    theme: dict[str, Any] = field(default_factory=dict)
    figures: tuple[Figure, ...] = ()
    coverage_ignore: tuple[Ignore, ...] = ()
    source: str = ""

    @property
    def model_path(self) -> Path:
        return self.root / self.model

    @property
    def out_path(self) -> Path:
        return self.root / self.out_dir

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

    def rel(self, path: Path) -> str:
        """A path shown to the user, relative to the root when it is under it."""
        try:
            return str(path.relative_to(self.root))
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


def discover_roots(root: Path) -> list[tuple[str, str]]:
    """Every top-level directory holding an __init__.py, plus src/<pkg> layouts."""
    found: list[tuple[str, str]] = []
    for parent in (root, root / "src"):
        if not parent.is_dir():
            continue
        for child in sorted(parent.iterdir()):
            if not child.is_dir() or child.name in SKIP_DIRS or child.name.startswith("."):
                continue
            if (child / "__init__.py").is_file():
                found.append((str(child.relative_to(root)), child.name))
    return found


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

    roots_raw = raw.get("package_roots")
    if roots_raw is None:
        package_roots = tuple(discover_roots(root))
    elif isinstance(roots_raw, dict) and all(
        isinstance(k, str) and isinstance(v, str) for k, v in roots_raw.items()
    ):
        package_roots = tuple((k, v) for k, v in roots_raw.items())
    else:
        raise ConfigError(f'{where}: package_roots must be a table of "path" = "name"')

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
            )
        )

    issue_url = _str(raw, "issue_url", "", where)
    if issue_url and "{n}" not in issue_url:
        raise ConfigError(f"{where}: issue_url must contain {{n}}")

    return Config(
        coverage_ignore=_coverage_ignore(raw, where),
        root=root,
        name=_str(raw, "name", root.name, where),
        package_roots=package_roots,
        tests_dir=_str(raw, "tests_dir", "tests", where),
        model=_str(raw, "model", "map/model.py", where),
        out_dir=_str(raw, "out_dir", "docs/map", where),
        facts_file=_str(raw, "facts_file", "map.json", where),
        issue_url=issue_url,
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


def load_model(path: Path) -> tuple[Model, Meaning]:
    """Import the model module by path and return its MODEL and MEANING."""
    if not path.is_file():
        raise ConfigError(f"model module not found: {path}")
    spec = importlib.util.spec_from_file_location(f"systemap_model_{abs(hash(str(path)))}", path)
    if spec is None or spec.loader is None:
        raise ConfigError(f"cannot import model module: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - the consumer's module may fail any way
        raise ConfigError(f"{path}: {type(exc).__name__}: {exc}") from exc
    finally:
        sys.modules.pop(spec.name, None)
    model = getattr(module, "MODEL", None)
    meaning = getattr(module, "MEANING", None)
    if not isinstance(model, Model):
        raise ConfigError(f"{path}: MODEL must be a systemap.Model")
    if not isinstance(meaning, Meaning):
        raise ConfigError(f"{path}: MEANING must be a systemap.Meaning")
    return model, meaning
