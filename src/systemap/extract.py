"""Extract the derived tier of the system map from the working tree.

Everything here is a fact read out of the code: module graph, public surface,
owned types, refusals, every public module-level name, the third-party
imports, the tests that guard each component, and the entry points a run of
the system can start from. No prose is invented; what the system is MEANT
to do lives in the consumer's model module, and the page styles the two
differently on purpose.

Every field written is declared once, in `FIELDS`; the skill's schema
reference is generated from that table and a test compares the two, so
the facts file cannot carry a field the reader was not told about.
"""

from __future__ import annotations

import ast
import contextlib
import hashlib
import json
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from pathlib import Path
from typing import Any

from systemap.config import Config
from systemap.model import Model, is_symbol, module_matches

SKIP_PARTS = {".git", ".venv", "node_modules", "__pycache__", "build", "dist"}
TESTS_KEPT = 25
CONSTANTS_KEPT = 14
UPPER_NAME = re.compile(r"[A-Z][A-Z0-9_]{2,}")

# Every field the extractor writes: (scope, field, what it holds). The
# scopes are the file itself, each module record under `components`, and
# each record under `entry_points`. `facts_doc` renders this table for the
# skill's schema reference; the test compares the rendered text with the
# shipped reference and the table with what `build` actually writes.
FIELDS: tuple[tuple[str, str, str], ...] = (
    ("facts", "version", "the facts format; 1"),
    ("facts", "built_at_commit", "the commit the tree was at, or empty outside git"),
    ("facts", "packages", "the import names of the package roots"),
    (
        "facts",
        "tests_dirs",
        "the directories test files were read from, relative to the root: the "
        "configured `tests_dir`, or every directory named `tests` or `test`",
    ),
    ("facts", "spec_sections", "the `##` headings of `spec_path`, each with `level` and `title`"),
    ("facts", "entry_points", "where a run can start: one record per point, fields below"),
    ("facts", "components", "one record per module, keyed by its dotted name, fields below"),
    ("module", "id", "the dotted module name"),
    ("module", "file", "the path relative to the root"),
    ("module", "package", "the first segment of the name"),
    ("module", "plane", "the second segment when `planes` names it, else `core`"),
    ("module", "loc", "lines in the file"),
    ("module", "sha", "twelve hex digits of the source's SHA-1: the change detector's key"),
    ("module", "docstring", "the first paragraph of the module docstring, capped"),
    (
        "module",
        "functions",
        "public functions: `name`, `signature`, `doc` (the first docstring line)",
    ),
    (
        "module",
        "classes",
        "public classes that are not errors: `name`, `doc`, `methods` (public method signatures)",
    ),
    ("module", "errors", "public classes named or based on Error or Exception, the same fields"),
    ("module", "constants", "UPPER_CASE assignments: `name` and `value`, the first 14"),
    (
        "module",
        "names",
        "every public module-level name in source order, with its `kind`: `function`, "
        "`class`, `error`, `constant` (UPPER_CASE) or `object` (any other assignment, "
        "such as `app` or `root_agent`); a component's `entry` may name any of them",
    ),
    (
        "module",
        "uses",
        "the package's modules this one imports, each with the names taken from it, "
        "or `*` for the whole module",
    ),
    ("module", "imports", "the keys of `uses`"),
    ("module", "imported_by", "the package's modules that import this one"),
    (
        "module",
        "external",
        "third-party modules imported, as the dotted names written in the import "
        "(`anthropic`, `google.adk`); the standard library and the package's own "
        "modules are left out. The judgement's `model sdk` line reads it",
    ),
    ("module", "tests_total", "how many test functions import this module"),
    ("module", "tests_primary", "how many of those sit in a file named after the module"),
    ("module", "tests", "the names of up to 25 of those tests, primary first"),
    (
        "entry point",
        "kind",
        "`console_script`, `main_module`, `main_function`, `subcommand` or `public_function`",
    ),
    (
        "entry point",
        "name",
        "the script name, the `python -m` line, `main`, the subcommand word, or the function name",
    ),
    ("entry point", "module", "the module that defines it"),
    (
        "entry point",
        "target",
        "the function a console script names, or the console script a subcommand "
        "belongs to; else empty",
    ),
)

SCOPE_TITLES = {
    "facts": "The file",
    "module": "Each module, under `components`",
    "entry point": "Each entry point, under `entry_points`",
}


def fields_of(scope: str) -> set[str]:
    return {name for sc, name, _ in FIELDS if sc == scope}


def facts_doc() -> str:
    """The facts section of the skill's schema reference, from `FIELDS`."""
    out = [
        "## The facts file",
        "",
        "`docs/map/map.json` by default, written by `systemap extract`. Every field,",
        "from the extractor's own table (`systemap.extract.FIELDS`):",
    ]
    for scope, title in SCOPE_TITLES.items():
        out += ["", f"**{title}**", ""]
        out += [f"- `{name}`: {what}." for sc, name, what in FIELDS if sc == scope]
    return "\n".join(out) + "\n"


def module_of(path: Path, pkg_dir: Path, pkg_name: str) -> str:
    rel = path.relative_to(pkg_dir).with_suffix("")
    parts = [p for p in rel.parts if p != "__init__"]
    return ".".join([pkg_name, *parts]) if parts else pkg_name


def plane_of(module: str, planes: tuple[str, ...]) -> str:
    """The architectural plane a module belongs to, from its dotted path."""
    parts = module.split(".")
    if len(parts) > 2 and parts[1] in planes:
        return parts[1]
    return "core"


def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    try:
        args = ast.unparse(node.args)
    except (AttributeError, ValueError):
        args = "..."
    ret = ""
    if node.returns is not None:
        try:
            ret = f" -> {ast.unparse(node.returns)}"
        except (AttributeError, ValueError):
            ret = ""
    prefix = "async def " if isinstance(node, ast.AsyncFunctionDef) else "def "
    return f"{prefix}{node.name}({args}){ret}"


def opening(text: str | None) -> str:
    """The first paragraph of a docstring, capped.

    The map is read for orientation, not as a mirror of the source: the page
    shows a module's opening line, and the file itself is one click away. Storing
    every docstring in full doubled the facts file for text nobody rendered.
    """
    if not text:
        return ""
    para = text.strip().split("\n\n")[0]
    para = " ".join(para.split())
    return para if len(para) <= 320 else para[:319] + "\u2026"


def first_line(text: str | None) -> str:
    if not text:
        return ""
    for line in text.strip().splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def sentence(test_name: str) -> str:
    body = test_name[5:] if test_name.startswith("test_") else test_name
    return body.replace("_", " ").strip() or test_name


def parse_surface(raw: str) -> dict[str, Any] | None:
    """The public surface of one module's source, or None if it cannot parse.

    This is the ONE definition of "public surface" in the map: the extractor
    stores it and the change detector diffs it between two git blobs, so the
    two can never disagree about what a module exports.
    """
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return None
    functions: list[dict[str, Any]] = []
    classes: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    constants: list[dict[str, str]] = []
    # Every public module-level name with its kind, so an `entry` can be a
    # lower-case object (`app`, `root_agent`) as well as a function or class.
    names: list[dict[str, str]] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            if node.name.startswith("_"):
                continue
            names.append({"name": node.name, "kind": "function"})
            functions.append(
                {
                    "name": node.name,
                    "signature": signature(node),
                    "doc": first_line(ast.get_docstring(node)),
                }
            )
        elif isinstance(node, ast.ClassDef):
            if node.name.startswith("_"):
                continue
            bases = []
            for b in node.bases:
                with contextlib.suppress(AttributeError, ValueError):
                    bases.append(ast.unparse(b))
            is_error = node.name.endswith(("Error", "Exception")) or any(
                "Error" in b or "Exception" in b for b in bases
            )
            record = {
                "name": node.name,
                "doc": first_line(ast.get_docstring(node)),
                # Full signatures, not names: a class's surface includes what
                # its methods accept and return, so a parameter change is a
                # change to the type.
                "methods": [
                    signature(n)
                    for n in node.body
                    if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                    and not n.name.startswith("_")
                ],
            }
            (errors if is_error else classes).append(record)
            names.append({"name": node.name, "kind": "error" if is_error else "class"})
        elif isinstance(node, ast.Assign | ast.AnnAssign):
            # A measured cap declared as `NAME: Final = ...` is an AnnAssign;
            # handling only Assign missed every tuning module.
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if not isinstance(target, ast.Name) or target.id.startswith("_"):
                    continue
                if node.value is None:
                    continue
                if not UPPER_NAME.fullmatch(target.id):
                    names.append({"name": target.id, "kind": "object"})
                    continue
                try:
                    value = ast.unparse(node.value)
                except (AttributeError, ValueError):
                    value = "?"
                constants.append({"name": target.id, "value": value[:80]})
                names.append({"name": target.id, "kind": "constant"})
    return {
        "docstring": opening(ast.get_docstring(tree)),
        "functions": functions,
        "classes": classes,
        "errors": errors,
        "constants": constants,
        "names": names,
    }


def collect_module(path: Path, repo: Path) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    surface = parse_surface(raw)
    if surface is None:
        return None
    return {
        "file": str(path.relative_to(repo)),
        "loc": len(raw.splitlines()),
        # A change detector for the map, never a security claim: usedforsecurity=False
        # states that and keeps the digest byte-identical, so committed facts files
        # stay comparable across the flag.
        "sha": hashlib.sha1(raw.encode("utf-8"), usedforsecurity=False).hexdigest()[:12],
        **surface,
        "constants": surface["constants"][:CONSTANTS_KEPT],
    }


# In a `uses` mapping, this marks "the whole module": `import m` gives access
# to every name in m, so no list of names would be honest.
WHOLE_MODULE = "*"


def internal_uses(
    raw: str,
    prefixes: set[str],
    known: set[str],
    module: str = "",
    is_package: bool = False,
) -> dict[str, set[str]]:
    """target module -> the names this source takes from it.

    A value containing WHOLE_MODULE means the source imported the module
    itself, so any name in it may be used. Relative imports resolve against
    `module` (the importer's own dotted name); without it they are skipped.
    """
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return {}

    def resolve(name: str) -> str | None:
        if name in known:
            return name
        parts = name.split(".")
        while len(parts) > 1:
            parts.pop()
            candidate = ".".join(parts)
            if candidate in known:
                return candidate
        return None

    uses: dict[str, set[str]] = defaultdict(set)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in prefixes:
                    target = resolve(alias.name)
                    if target:
                        uses[target].add(WHOLE_MODULE)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if not module:
                    continue
                # The anchor package: a module's own package, or the package
                # itself when the source is an __init__. Each further level
                # climbs one package up.
                anchor = module.split(".")
                if not is_package:
                    anchor = anchor[:-1]
                if node.level > 1:
                    anchor = anchor[: len(anchor) - (node.level - 1)]
                if not anchor:
                    continue
                parts = [*anchor, *node.module.split(".")] if node.module else anchor
                src = ".".join(parts)
            else:
                if not node.module:
                    continue
                src = node.module
            if src.split(".")[0] not in prefixes:
                continue
            base = resolve(src)
            for alias in node.names:
                if alias.name == "*":
                    if base:
                        uses[base].add(WHOLE_MODULE)
                    continue
                # Exact membership only: resolve() walks prefixes upward, so it
                # would resolve a class name to its module and misread every
                # from-import as a whole-module import.
                if f"{src}.{alias.name}" in known:
                    uses[f"{src}.{alias.name}"].add(WHOLE_MODULE)
                elif base:
                    uses[base].add(alias.name)
    return dict(uses)


def external_imports(raw: str, prefixes: set[str]) -> list[str]:
    """The third-party modules one source imports, as the dotted names written.

    The standard library, `__future__` and the package's own modules are
    left out; relative imports are the package's own. The names are kept
    dotted (`google.adk`, not `google`) because that is the level at which
    a model SDK is told apart from its namespace.
    """
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return []
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            candidates = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and not node.level and node.module:
            candidates = [node.module]
        else:
            continue
        for name in candidates:
            top = name.split(".")[0]
            if top in prefixes or top in sys.stdlib_module_names or top == "__future__":
                continue
            out.add(name)
    return sorted(out)


def internal_imports(path: Path, prefixes: set[str], known: set[str]) -> set[str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(internal_uses(raw, prefixes, known))


def test_names(raw: str) -> list[str]:
    """Test functions in one test file's source, at any nesting depth."""
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return []
    return [
        n.name
        for n in ast.walk(tree)
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name.startswith("test_")
    ]


def collect_tests(
    repo: Path, tests_dirs: tuple[str, ...], prefixes: set[str], known: set[str]
) -> dict[str, list[dict[str, Any]]]:
    """module -> the behaviours asserted by tests that import it.

    `tests_dirs` are read in order; a file under two of them is read once.
    """
    guards: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen: set[Path] = set()
    files: list[Path] = []
    for rel in tests_dirs:
        test_dir = repo / rel
        if not rel or not test_dir.is_dir():
            continue
        for path in sorted(test_dir.rglob("test_*.py")):
            if path in seen or any(p in SKIP_PARTS for p in path.parts):
                continue
            seen.add(path)
            files.append(path)
    for path in files:
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            continue
        targets = set(internal_uses(raw, prefixes, known))
        if not targets:
            continue
        names = test_names(raw)
        stem = path.stem[5:] if path.stem.startswith("test_") else path.stem
        for target in targets:
            # A test file named after the module is its primary guard; a file
            # that merely imports it exercises it. Both are true, and the
            # distinction is what stops a shared helper from claiming every test.
            primary = stem == target.split(".")[-1]
            for name in names:
                guards[target].append({"name": name, "primary": primary})
    return guards


def spec_sections(repo: Path, spec_path: str) -> list[dict[str, str]]:
    if not spec_path:
        return []
    path = repo / spec_path
    if not path.is_file():
        return []
    out: list[dict[str, str]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for match in re.finditer(r"^(#{2,4})\s+(.+)$", text, re.M):
        out.append({"level": str(len(match.group(1))), "title": match.group(2).strip()})
    return out


# ---- entry points: where a run of the system starts ----------------------------


def subcommands(raw: str) -> list[str]:
    """The argparse subcommand names one module's source adds, where detectable.

    A call `<anything>.add_parser("name", ...)` with a literal first
    argument is a subcommand. A name built from a variable is not
    detected; the judgement can only ask about what the tree states.
    """
    try:
        tree = ast.parse(raw)
    except (SyntaxError, ValueError):
        return []
    out: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_parser"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            out.append(node.args[0].value)
    return out


def console_scripts(repo: Path) -> dict[str, tuple[str, str]]:
    """name -> (module, function) from `[project.scripts]` in pyproject.toml."""
    path = repo / "pyproject.toml"
    if not path.is_file():
        return {}
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}
    scripts = data.get("project", {}).get("scripts", {})
    out: dict[str, tuple[str, str]] = {}
    if isinstance(scripts, dict):
        for name, target in scripts.items():
            if isinstance(target, str) and ":" in target:
                module, func = target.split(":", 1)
                out[str(name)] = (module.strip(), func.strip())
    return out


def entry_points(
    repo: Path, prefixes: set[str], components: dict[str, Any], sources: dict[str, str]
) -> list[dict[str, str]]:
    """Where a run of the system can start, read out of the tree.

    Console scripts in pyproject.toml, `__main__` modules, `main`
    functions, argparse subcommands where detectable, and the public
    functions of each package root. Every one is a walk a reader may
    need; `systemap judgement` asks about each that has no journey.
    A subcommand carries the console script that reaches its module, so
    the judgement can name it the way a person types it.
    """
    scripts = {
        name: (module, func)
        for name, (module, func) in sorted(console_scripts(repo).items())
        if module in components
    }
    script_of_module = {module: name for name, (module, _f) in scripts.items()}
    out: list[dict[str, str]] = []
    for name, (module, func) in scripts.items():
        out.append({"kind": "console_script", "name": name, "module": module, "target": func})
    for module, record in sorted(components.items()):
        if module.endswith(".__main__"):
            pkg = module[: -len(".__main__")]
            out.append(
                {"kind": "main_module", "name": f"python -m {pkg}", "module": module, "target": ""}
            )
        if any(f["name"] == "main" for f in record["functions"]):
            out.append(
                {"kind": "main_function", "name": "main", "module": module, "target": "main"}
            )
        for sub in subcommands(sources.get(module, "")):
            out.append(
                {
                    "kind": "subcommand",
                    "name": sub,
                    "module": module,
                    "target": script_of_module.get(module, ""),
                }
            )
        if module in prefixes:
            for f in record["functions"]:
                out.append(
                    {"kind": "public_function", "name": f["name"], "module": module, "target": ""}
                )
    return out


def entry_label(point: dict[str, str]) -> str:
    """The entry point the way a person would name it."""
    kind, name, module, target = point["kind"], point["name"], point["module"], point["target"]
    if kind == "console_script":
        return f"{name} (console script)"
    if kind == "main_module":
        return name
    if kind == "main_function":
        return f"main() in {module}"
    if kind == "subcommand":
        return f"{target} {name} (subcommand)" if target else f"{name} (subcommand in {module})"
    return f"{name}() in {module}"


def build(cfg: Config) -> dict[str, Any]:
    """The facts for the tree at `cfg.root`, ready to be written as JSON."""
    repo = cfg.root
    roots = cfg.roots
    prefixes = {name for _, name in roots}
    paths: dict[str, Path] = {}
    for pkg_dir, pkg_name in roots:
        for path in pkg_dir.rglob("*.py"):
            if any(p in SKIP_PARTS for p in path.parts):
                continue
            paths[module_of(path, pkg_dir, pkg_name)] = path
    known = set(paths)

    components: dict[str, Any] = {}
    imports: dict[str, set[str]] = {}
    sources: dict[str, str] = {}
    for module, path in sorted(paths.items()):
        record = collect_module(path, repo)
        if record is None:
            continue
        record["id"] = module
        record["package"] = module.split(".")[0]
        record["plane"] = plane_of(module, cfg.planes)
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError:
            raw = ""
        sources[module] = raw
        uses = internal_uses(
            raw, prefixes, known, module=module, is_package=path.name == "__init__.py"
        )
        uses.pop(module, None)
        record["uses"] = {
            target: [WHOLE_MODULE] if WHOLE_MODULE in names else sorted(names)
            for target, names in sorted(uses.items())
        }
        record["external"] = external_imports(raw, prefixes)
        imports[module] = set(uses)
        components[module] = record

    importers: dict[str, set[str]] = defaultdict(set)
    for module, deps in imports.items():
        for dep in deps:
            importers[dep].add(module)
    for module, record in components.items():
        record["imports"] = sorted(imports.get(module, set()))
        record["imported_by"] = sorted(importers.get(module, set()))

    tests_dirs = cfg.test_dirs
    guards = collect_tests(repo, tests_dirs, prefixes, known)
    for module, record in components.items():
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for item in guards.get(module, []):
            if item["name"] in seen:
                continue
            seen.add(item["name"])
            unique.append(item)
        unique.sort(key=lambda t: (not t["primary"], t["name"]))
        record["tests_total"] = len(unique)
        record["tests_primary"] = sum(1 for t in unique if t["primary"])
        # The full list is recoverable from the tree; the map keeps a sample so
        # a committed file that changes on every merge stays diffable by eye.
        # Names only: the sentence is derived where it is displayed.
        record["tests"] = [t["name"] for t in unique[:TESTS_KEPT]]

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True)
    return {
        "version": 1,
        "built_at_commit": head.stdout.strip() if head.returncode == 0 else "",
        "packages": sorted(prefixes),
        "tests_dirs": list(tests_dirs),
        "spec_sections": spec_sections(repo, cfg.spec_path),
        "entry_points": entry_points(repo, prefixes, components, sources),
        "components": components,
    }


def drift(fresh: dict[str, Any], stored: dict[str, Any]) -> list[str]:
    """Ways the stored facts no longer describe the tree. Empty means current."""
    out: list[str] = []
    new_c, old_c = fresh["components"], (stored or {}).get("components", {})
    # Entry points come partly from pyproject.toml, which no module hash
    # covers, so they are compared on their own.
    new_e = {entry_label(e) for e in fresh.get("entry_points", [])}
    old_e = {entry_label(e) for e in (stored or {}).get("entry_points", [])}
    for label in sorted(new_e - old_e):
        out.append(f"entry point not in the map: {label}")
    for label in sorted(old_e - new_e):
        out.append(f"entry point in the map but gone from the tree: {label}")
    added = sorted(set(new_c) - set(old_c))
    gone = sorted(set(old_c) - set(new_c))
    moved = sorted(m for m in set(new_c) & set(old_c) if new_c[m]["sha"] != old_c[m]["sha"])
    # A source module's hash says nothing about the TESTS that guard it. A new
    # test file changes what the system guarantees without touching a single
    # module, and comparing only shas would let that pass as current. `fresh`
    # is a full rebuild, so the attribution is authoritative here.
    guards_changed = sorted(
        m
        for m in set(new_c) & set(old_c)
        if new_c[m].get("tests_total") != old_c[m].get("tests_total")
    )
    for m in added:
        out.append(f"missing from the map: {m}")
    for m in gone:
        out.append(f"in the map but gone from the tree: {m}")
    for m in moved:
        out.append(f"code changed since the map was built: {m}")
    for m in guards_changed:
        was = (old_c[m] or {}).get("tests_total", 0)
        now = new_c[m].get("tests_total", 0)
        out.append(f"tests guarding it changed ({was} -> {now}): {m}")
    return out


def mapping_drift(fresh: dict[str, Any], model: Model, prefixes: set[str]) -> list[str]:
    """Modules the model claims but the tree does not have.

    The component-to-module mapping is the one hand-authored input the facts
    have. Left unchecked, a rename would quietly leave a card on the page
    for code that is gone instead of failing loudly. The layout itself is
    checked too, since a card drawn outside its band is the same kind of
    quiet lie.
    """
    known = set(fresh["components"])
    out: list[str] = []
    for c in model.components:
        for m in c.implemented_by:
            # A symbol claim names its module before the colon; the name
            # itself is the entry rule's business.
            module = m.partition(":")[0] if is_symbol(m) else m
            if module.split(".")[0] in prefixes and not any(
                module_matches(module, k) for k in known
            ):
                out.append(f"{c.id} names module {module} which is not in the facts")
    out.extend(f"layout: {p}" for p in model.layout_problems())
    return out


def read_facts(path: Path) -> dict[str, Any]:
    """The stored facts, or an empty table when there are none or they do not parse."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(data) if isinstance(data, dict) else {}


def write_facts(path: Path, facts: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(facts, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def summary(facts: dict[str, Any]) -> list[str]:
    """The counts printed after an extract, labelled for what they are.

    The map carries no counts (the skill's rule); these feed the change
    detector, and the header says so, so an agent reading the numbers does
    not copy them onto a card.
    """
    comps = facts["components"]
    guarded = sum(c["tests_total"] for c in comps.values())
    primary = sum(c["tests_primary"] for c in comps.values())
    dirs: list[str] = list(facts.get("tests_dirs", []))
    if guarded:
        tests = f"{guarded} tests ({primary} primary)"
    elif dirs:
        # Zero is a finding, not a count: say where the extractor looked, so
        # a tests directory it did not find is set in `tests_dir`.
        tests = f"no tests import a module; searched {', '.join(dirs)}"
    else:
        tests = "no tests import a module; no directory named tests or test was found"
    return [
        "facts for the change detector (these never appear on the map):",
        f"  modules:          {len(comps)}",
        f"  public functions: {sum(len(c['functions']) for c in comps.values())}",
        f"  types:            {sum(len(c['classes']) for c in comps.values())}",
        f"  refusals:         {sum(len(c['errors']) for c in comps.values())}",
        f"  guarded by:       {tests}",
    ]
