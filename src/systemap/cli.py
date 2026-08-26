"""The `systemap` command: what the agent runs.

    systemap init [--no-ci]            configuration, starter model, the skill, a workflow
    systemap extract [--check]         read the facts out of the tree
    systemap facts [--modules ...]     read the facts back, one view at a time
    systemap place [--print]           a first position for every card without one
    systemap render [--check]          render the page from facts and model
    systemap check                     every rule; exit 1 with each fix named
    systemap figure ... --out FILE     one figure from the same generator
    systemap refresh                   extract, check, render, figures
    systemap judgement [--strict]      the list the maintainer must confirm
    systemap suggest                   a first grouping from the facts, to argue with
    systemap describe                  what a look at the picture would tell you, in numbers
    systemap serve [--port N]          serve the output directory over HTTP, print the URL
    systemap skill [--dir PATH|--print] reinstall the skill directory, or print SKILL.md

Exit codes: 0 the map is current or the check passed; 1 the map is stale or
a check failed; 2 the configuration or the model cannot be used. Every
non-zero exit prints one line saying what to run.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from systemap import (
    __version__,
    change,
    check,
    config,
    describe,
    extract,
    figure,
    judgement,
    page,
    place,
    scaffold,
    skill,
)
from systemap import facts as facts_mod
from systemap import suggest as suggest_mod
from systemap import theme as theme_mod
from systemap.config import Config, ConfigError
from systemap.model import Meaning, Model, all_layers
from systemap.model import problems as model_problems

OK, STALE, BAD_CONFIG = 0, 1, 2


@dataclass(frozen=True)
class Project:
    cfg: Config
    model: Model
    meaning: Meaning
    theme: dict[str, Any]


def say(*lines: str) -> None:
    for line in lines:
        print(line)


def warn(*lines: str) -> None:
    for line in lines:
        print(line, file=sys.stderr)


def _root(args: argparse.Namespace) -> Path:
    if args.root:
        return Path(args.root).resolve()
    found = config.find_root(Path.cwd().resolve())
    return found or Path.cwd().resolve()


def _project(args: argparse.Namespace) -> Project:
    cfg = config.load(_root(args))
    model, meaning = config.load_model(cfg.model_path, cfg.model)
    return Project(cfg, model, meaning, theme_mod.resolve(cfg.theme, all_layers(model, meaning)))


# ---- init ------------------------------------------------------------------


AGENT_SENTENCE = "Map this repository with systemap. Follow the systemap skill."


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    roots = config.discover_roots(root)
    package = roots[0][1] if roots else "mypackage"
    name = args.name or config.default_name(root)
    say(*scaffold.write(root, name, package, roots, ci=not args.no_ci))
    skill_path = skill.write(root / skill.DEFAULT_DIR)
    references = len(skill.files()) - 1
    say(
        f"wrote {skill_path.parent.relative_to(root)}/ "
        f"({skill.FILE_NAME} and {references} references)"
    )
    say("next: give your coding agent this sentence:", f"  {AGENT_SENTENCE}")
    return OK


# ---- extract ---------------------------------------------------------------


def _require_roots(p: Project) -> None:
    if not p.cfg.roots:
        found = config.candidate_packages(p.cfg.root)
        where = (
            "directories holding an __init__.py: " + ", ".join(found)
            if found
            else f"no directory holding an __init__.py up to {config.CANDIDATE_DEPTH} deep"
        )
        raise ConfigError(
            "no package roots found; set [package_roots] in systemap.toml "
            f'("path" = "import name"); {where}'
        )


def cmd_extract(args: argparse.Namespace) -> int:
    p = _project(args)
    _require_roots(p)
    fresh = extract.build(p.cfg)
    stored = extract.read_facts(p.cfg.facts_path)
    if args.check:
        problems = check.stale_facts(fresh, stored, p.model, p.cfg.prefixes)
        if problems:
            noun = "problem" if len(problems) == 1 else "problems"
            say(f"map is out of date ({len(problems)} {noun}):")
            say(*(f"  {line}" for line in problems[:25]))
            if len(problems) > 25:
                say(f"  ... and {len(problems) - 25} more")
            say("run: systemap extract")
            return STALE
        say(f"map is current: {len(fresh['components'])} modules match the tree")
        return OK
    extract.write_facts(p.cfg.facts_path, fresh)
    say(*extract.summary(fresh))
    for line in extract.mapping_drift(fresh, p.model, p.cfg.prefixes):
        say(f"  warning: {line}")
    say(f"written to {p.cfg.rel(p.cfg.facts_path)}")
    return OK


# ---- facts -----------------------------------------------------------------


def cmd_facts(args: argparse.Namespace) -> int:
    """Read the facts back one view at a time, so nobody opens the JSON.

    With no option: the extract summary and the views. A module name the
    facts do not have is one line with the closest they do, exit 1.
    """
    p = _project(args)
    facts = _facts_or_stale(p)
    if facts is None:
        return STALE
    try:
        if args.modules:
            lines = facts_mod.modules(facts)
        elif args.module:
            lines = facts_mod.module(facts, args.module)
        elif args.entry_points:
            lines = facts_mod.entry_points(facts)
        elif args.external:
            lines = facts_mod.external(facts)
        elif args.imports:
            lines = facts_mod.imports(facts, args.imports)
        else:
            lines = facts_mod.overview(extract.summary(facts))
    except facts_mod.UnknownModule as exc:
        hint = f"; closest: {exc.closest}" if exc.closest else ""
        say(f"no module {exc.name} in the facts{hint}", "run: systemap facts --modules")
        return STALE
    say(*lines)
    return OK


# ---- render ----------------------------------------------------------------


def _facts_or_stale(p: Project) -> dict[str, Any] | None:
    facts = extract.read_facts(p.cfg.facts_path)
    if not facts:
        say(f"no facts at {p.cfg.rel(p.cfg.facts_path)}", "run: systemap extract")
        return None
    return facts


def _model_ok(p: Project) -> bool:
    problems = model_problems(p.model, p.meaning)
    if problems:
        say(*problems, f"fix {p.cfg.model}, then run: systemap check")
        return False
    return True


def _render_page(p: Project, facts: dict[str, Any], args: argparse.Namespace) -> str:
    ch: dict[str, Any] = {"has_change": False}
    base = getattr(args, "base", "")
    if base:
        ch = change.compute(p.cfg, p.model, base, facts, getattr(args, "head", "HEAD"))
        ch["pr"] = change.pr_meta(p.cfg.root, getattr(args, "pr", ""))
    return page.build(p.cfg, p.model, p.meaning, p.theme, facts, ch)


def cmd_render(args: argparse.Namespace) -> int:
    p = _project(args)
    facts = _facts_or_stale(p)
    if facts is None:
        return STALE
    if not _model_ok(p):
        return STALE
    html = _render_page(p, facts, args)
    out = p.cfg.page_path
    if args.check:
        current = out.read_text(encoding="utf-8") if out.is_file() else ""
        if current != html:
            say(
                f"{p.cfg.rel(out)} is stale: it differs from what systemap renders",
                "run: systemap refresh",
            )
            return STALE
        say(f"{p.cfg.rel(out)} is current")
        return OK
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    say(f"wrote {p.cfg.rel(out)} ({out.stat().st_size / 1024:.0f} KB)")
    return OK


# ---- check -----------------------------------------------------------------


NO_COMPONENTS = "the model has no components yet; see the skill"


def _empty(p: Project) -> bool:
    """An empty model has one thing to say, and nothing else can be judged."""
    if p.model.components:
        return False
    say(NO_COMPONENTS)
    return True


def _fix_line(p: Project, result: check.Result) -> str:
    """The one line naming what to do first about a failed check.

    The model's own contradictions come first, since nothing else can be
    judged until they are gone; then the facts; then the rules that read
    the two together; then the outputs, which refresh regenerates.
    """
    if result.problems:
        return f"fix {p.cfg.model}, then run: systemap check"
    if not result.coverage.checked:
        return "run: systemap extract"
    if result.coverage.problems:
        return (
            f"map every module in {p.cfg.model}, or ignore it with a reason under "
            "[coverage] in the configuration, then run: systemap check"
        )
    if result.entry or result.interface:
        return f"fix {p.cfg.model}, then run: systemap check"
    return "run: systemap refresh"


def cmd_check(args: argparse.Namespace) -> int:
    p = _project(args)
    _require_roots(p)
    if _empty(p):
        return STALE
    facts = extract.read_facts(p.cfg.facts_path)
    result = check.run(p.model, p.meaning, p.theme, facts, p.cfg.coverage_ignore, p.cfg.observed_by)
    result = check.with_stale(result, check.stale(p.cfg, p.model, p.meaning, p.theme))
    say(*check.report(p.model, result, p.cfg.model))
    if not result.ok:
        say(_fix_line(p, result))
        return STALE
    return OK


# ---- figure ----------------------------------------------------------------


def _ids(values: list[str] | None) -> tuple[str, ...]:
    out: list[str] = []
    for value in values or []:
        out.extend(s.strip() for s in value.split(",") if s.strip())
    return tuple(out)


def cmd_figure(args: argparse.Namespace) -> int:
    p = _project(args)
    facts = _facts_or_stale(p)
    if facts is None:
        return STALE
    if not _model_ok(p):
        return STALE
    html, collisions = figure.make(
        p.cfg,
        p.model,
        p.meaning,
        p.theme,
        facts,
        mode=args.mode or "",
        components=_ids(args.components),
        base=args.base or "",
        head=args.head,
        caption=args.caption or "",
        svg_id=args.svg_id,
        interactive=bool(args.interactive),
        bare=bool(args.out) and args.out.endswith(".svg"),
        layer=args.layer or "",
    )
    for line in collisions:
        warn(line)
    if args.out:
        # Relative to the output directory, like a [[figures]] out; an
        # absolute path is written where it says.
        out = Path(args.out)
        if not out.is_absolute():
            out = p.cfg.out_path / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        say(f"wrote {p.cfg.rel(out)} ({len(html) / 1024:.0f} KB)")
    else:
        sys.stdout.write(html)
    if collisions:
        warn(f"fix {p.cfg.model}, then run: systemap check")
        return STALE
    return OK


# ---- refresh ---------------------------------------------------------------

# Current means the page is what the renderer draws from the model's
# rendered fields and the stored facts, and the facts describe the tree.
ALREADY_CURRENT = "map: already current: the page matches the model's rendered fields and the facts"


def cmd_refresh(args: argparse.Namespace) -> int:
    p = _project(args)
    quiet = bool(args.quiet)

    def note(line: str) -> None:
        if not quiet:
            say(line)

    _require_roots(p)
    if _empty(p):
        return STALE
    fresh = extract.build(p.cfg)
    # Current means two things at once: nothing on disk is older than the
    # tree or the model, and the check passes. A stale-free map that fails
    # coverage is not current; it is incomplete.
    stale_lines = check.stale(p.cfg, p.model, p.meaning, p.theme, fresh)
    result = check.run(p.model, p.meaning, p.theme, fresh, p.cfg.coverage_ignore, p.cfg.observed_by)
    if not stale_lines and result.ok:
        note(ALREADY_CURRENT)
        return OK

    note("map: refreshing against the working tree")
    extract.write_facts(p.cfg.facts_path, fresh)
    written = [p.cfg.rel(p.cfg.facts_path)]
    if not result.ok:
        say(*check.report(p.model, result, p.cfg.model))
        fix = _fix_line(p, result).replace("systemap check", "systemap refresh")
        say(f"map: check failed; {fix}")
        return STALE
    html = _render_page(p, fresh, argparse.Namespace())
    p.cfg.page_path.write_text(html, encoding="utf-8")
    written.append(p.cfg.rel(p.cfg.page_path))
    for fig in p.cfg.figures:
        html, collisions = figure.configured(p.cfg, p.model, p.meaning, p.theme, fresh, fig)
        for line in collisions:
            warn(line)
        out = p.cfg.out_path / fig.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        written.append(p.cfg.rel(out))
    # What was written is checked as `systemap check` would check it. A
    # refresh that leaves the check failing is not a refresh, whatever it
    # wrote; the exit code says so.
    after = check.with_stale(
        check.run(p.model, p.meaning, p.theme, fresh, p.cfg.coverage_ignore, p.cfg.observed_by),
        check.stale(p.cfg, p.model, p.meaning, p.theme, fresh),
    )
    if not after.ok:
        say(*check.report(p.model, after, p.cfg.model))
        fix = _fix_line(p, after).replace("systemap check", "systemap refresh")
        say(f"map: check failed after the refresh; {fix}")
        return STALE
    note(f"map: updated {', '.join(written)}")
    note(f"map: commit {p.cfg.out_dir}/ to record this state of the system")
    return OK


# ---- judgement -------------------------------------------------------------


def cmd_judgement(args: argparse.Namespace) -> int:
    """The list the maintainer confirms. A report, not a gate: exit 0.

    Lines answered under `[judgement] answered` in the configuration are
    suppressed and counted; an answer that matches no line is reported as
    stale so it can be removed. With `--strict` the report is a gate for
    a workflow: exit 1 while any line is open. A stale answer is reported
    either way and fails neither.
    """
    p = _project(args)
    if _empty(p):
        return OK
    facts = extract.read_facts(p.cfg.facts_path)
    if not facts:
        say(f"no facts at {p.cfg.rel(p.cfg.facts_path)}; the list below reads the model alone")
    lines = judgement.run(
        p.model,
        p.meaning,
        facts,
        judgement.sdk_list(p.cfg.model_sdks),
        p.cfg.observed_by,
    )
    result = judgement.apply_answers(lines, p.cfg.judgement_answered)
    say(*judgement.report(result))
    if args.strict and result.open:
        say("answer every line in [judgement] answered in systemap.toml, or act on it")
        return STALE
    return OK


# ---- suggest ---------------------------------------------------------------


def cmd_suggest(args: argparse.Namespace) -> int:
    """A first grouping from the facts alone, to argue with; never the answer."""
    cfg = config.load(_root(args))
    facts = extract.read_facts(cfg.facts_path)
    if not facts:
        say(f"no facts at {cfg.rel(cfg.facts_path)}", "run: systemap extract")
        return STALE
    say(*suggest_mod.lines(facts))
    return OK


# ---- describe --------------------------------------------------------------


def cmd_describe(args: argparse.Namespace) -> int:
    """The picture in numbers, for an agent that cannot open the page.

    The drawing is made the way the page makes it and read back: cards
    per region, bends and length per edge (worst first), seats per
    gutter, cards and edges per reading. A model that contradicts itself
    cannot be drawn, so that is reported instead, as `check` reports it.
    """
    p = _project(args)
    if _empty(p):
        return STALE
    # A card without a position is placed for this look, as `systemap
    # place` would place it, and the positions line says which.
    placement = place.compute(p.model)
    if placement.positions:
        p = Project(p.cfg, place.apply(p.model, placement), p.meaning, p.theme)
    if not _model_ok(p):
        return STALE
    facts = extract.read_facts(p.cfg.facts_path)
    say(*describe.run(p.model, p.meaning, p.theme, facts, p.cfg.observed_by, placement.placed))
    return OK


# ---- place -----------------------------------------------------------------


def cmd_place(args: argparse.Namespace) -> int:
    """A first position for every card without one, written into the model.

    A card with `x` and `y` is pinned and never moved. With no card
    pinned the regions, the containers and the canvas are laid out too;
    with any pinned, the boxes stay as written and the unpinned cards
    take the free slots inside them. `--print` prints the positions
    instead of writing them. The check decides, as before: run it next.
    """
    p = _project(args)
    if _empty(p):
        return STALE
    placement = place.compute(p.model)
    if args.print or not placement.positions:
        say(*place.lines(placement))
        return OK
    source = place.write(p.cfg.model_path, placement)
    # The file is read back and compared with what was computed, so a card
    # the edit could not reach is reported, never assumed written.
    reloaded, _meaning = config.load_model(p.cfg.model_path, p.cfg.model)
    wrong = place.unwritten(reloaded, placement)
    if wrong:
        p.cfg.model_path.write_text(source, encoding="utf-8")
        raise place.PlaceError(
            f"could not write a position for {', '.join(wrong)} into {p.cfg.model}: the card "
            "is not a Component(id=...) call the file spells out; add x and y by hand from "
            "systemap place --print"
        )
    n, m = len(placement.positions), len(placement.pinned)
    laid = "; every box and the canvas laid out" if placement.fresh else ""
    say(
        f"place: wrote {p.cfg.model}: {n} card{'s' if n != 1 else ''} placed, {m} pinned{laid}",
        "run: systemap check",
    )
    return OK


# ---- serve -----------------------------------------------------------------


DEFAULT_PORT = 8765


def make_server(directory: Path, port: int) -> ThreadingHTTPServer:
    """An HTTP server over `directory` on 127.0.0.1; port 0 picks a free one."""
    handler = partial(SimpleHTTPRequestHandler, directory=str(directory))
    return ThreadingHTTPServer(("127.0.0.1", port), handler)


def cmd_serve(args: argparse.Namespace) -> int:
    """Serve the output directory, since the page's script does not run from file://.

    The standard library's server, over the output directory alone, on the
    loopback address. It runs until interrupted and prints the URL first,
    so an agent can open it without knowing the port.
    """
    cfg = config.load(_root(args))
    if not cfg.page_path.is_file():
        say(f"no page at {cfg.rel(cfg.page_path)}", "run: systemap refresh")
        return STALE
    httpd = make_server(cfg.out_path, int(args.port))
    port = httpd.server_address[1]
    say(f"serving {cfg.rel(cfg.out_path)} at http://127.0.0.1:{port}/ (Ctrl-C to stop)")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return OK


# ---- skill -----------------------------------------------------------------


def cmd_skill(args: argparse.Namespace) -> int:
    if args.print:
        sys.stdout.write(skill.text())
        return OK
    target = Path(args.dir).resolve() if args.dir else _root(args) / skill.DEFAULT_DIR
    path = skill.write(target)
    references = len(skill.files()) - 1
    say(f"wrote {path}", f"wrote {target / skill.REFERENCES}/ ({references} files)")
    return OK


# ---- the parser ------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="systemap",
        description="A generated, interactive map of a Python system.",
    )
    parser.add_argument("--version", action="version", version=f"systemap {__version__}")
    parser.add_argument(
        "--root",
        default="",
        help="project root (default: the nearest directory with systemap.toml, "
        "[tool.systemap] in pyproject.toml, or .git); accepted before or after the command",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    def add_root(s: argparse.ArgumentParser) -> None:
        # The global --root, accepted after the subcommand as well. The
        # subparser's default is suppressed so it never overwrites a --root
        # given before the subcommand.
        s.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    s = sub.add_parser(
        "init", help="write systemap.toml, a starter model, the agent skill and a workflow"
    )
    add_root(s)
    s.add_argument(
        "--name",
        default="",
        help="the page title (default: [project] name in pyproject.toml, then the git "
        "repository's directory, then the directory name)",
    )
    s.add_argument(
        "--no-ci", action="store_true", help="do not write .github/workflows/systemap.yml"
    )
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("extract", help="read the facts out of the tree")
    add_root(s)
    s.add_argument("--check", action="store_true", help="exit 1 if the stored facts are stale")
    s.set_defaults(func=cmd_extract)

    s = sub.add_parser(
        "facts",
        help="read the facts back one view at a time: --modules (one line per module), "
        "--module NAME (its record), --entry-points, --external, --imports NAME; with no "
        "option, the extract summary",
    )
    add_root(s)
    view = s.add_mutually_exclusive_group()
    view.add_argument(
        "--modules",
        action="store_true",
        help="one line per module: public names, imports and tests counted",
    )
    view.add_argument("--module", default="", metavar="NAME", help="one module's full record")
    view.add_argument(
        "--entry-points",
        dest="entry_points",
        action="store_true",
        help="where a run can start, each named the way a person types it",
    )
    view.add_argument(
        "--external",
        action="store_true",
        help="every third-party import, with the modules that import it",
    )
    view.add_argument(
        "--imports",
        default="",
        metavar="NAME",
        help="what one module imports from the package, and what imports it",
    )
    s.set_defaults(func=cmd_facts)

    s = sub.add_parser(
        "place",
        help="write a first position into the model for every card without one (a card "
        "with x and y is pinned and never moved); with no card pinned, the regions, "
        "containers and canvas are laid out too; --print prints instead of writing",
    )
    add_root(s)
    s.add_argument("--print", action="store_true", help="print the positions; write nothing")
    s.set_defaults(func=cmd_place)

    s = sub.add_parser("render", help="render the page from the facts and the model")
    add_root(s)
    s.add_argument("--check", action="store_true", help="exit 1 if the page is stale")
    s.add_argument("--base", default="", help="also draw a change map of HEAD against this ref")
    s.add_argument("--head", default="HEAD")
    s.add_argument("--pr", default="", help="a pull request number, for the change map title")
    s.set_defaults(func=cmd_render)

    s = sub.add_parser(
        "check",
        help="every rule: placement, routes, labels, type size, meaning, wheels, coverage, "
        "entry, stale outputs; exit 1 with each fix named",
    )
    add_root(s)
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("figure", help="draw one figure with the same generator")
    add_root(s)
    kind = s.add_mutually_exclusive_group()
    kind.add_argument("--interactive", action="store_true", help="carry the focus interaction")
    kind.add_argument("--static", action="store_true", help="a plain figure (default)")
    s.add_argument(
        "--components",
        nargs="*",
        metavar="ID",
        help="component ids a plan reaches (comma or space separated)",
    )
    s.add_argument("--mode", choices=["system", "change"], default="")
    s.add_argument("--base", default="", help="the ref a change figure compares against")
    s.add_argument("--head", default="HEAD")
    s.add_argument(
        "--layer",
        default="",
        metavar="ID",
        help="one reading only: that layer's edges, every card, the legend reduced to it "
        "(structure, system, data, control, or a layer of the model's own)",
    )
    s.add_argument("--caption", default="")
    s.add_argument("--svg-id", dest="svg_id", default="lessonmap")
    s.add_argument(
        "--out",
        default="",
        help="the file to write, relative to out_dir like a [[figures]] out (default: "
        "stdout); a .svg name writes the drawing alone",
    )
    s.set_defaults(func=cmd_figure)

    s = sub.add_parser("refresh", help="extract, check, render, and draw the configured figures")
    add_root(s)
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(func=cmd_refresh)

    s = sub.add_parser(
        "judgement",
        help="print the list the maintainer must confirm: thin components, odd folds, "
        "flows without a sentence, thin layers, entry points without a journey, imports "
        "across a boundary with no flow, flows no import backs, model sdk imports outside "
        "an agent; lines "
        "answered under [judgement] in the configuration are suppressed and counted; "
        "exit 0, or 1 with --strict while any line is open",
    )
    add_root(s)
    s.add_argument(
        "--strict", action="store_true", help="exit 1 while any line is unanswered, for CI"
    )
    s.set_defaults(func=cmd_judgement)

    s = sub.add_parser(
        "suggest",
        help="a first grouping to argue with, never the answer: one proposed card per "
        "package with two or more modules, its modules, and the crossing imports between "
        "proposals, from the facts alone",
    )
    add_root(s)
    s.set_defaults(func=cmd_suggest)

    s = sub.add_parser(
        "describe",
        help="what a look at the picture would tell you, in numbers: cards per region, "
        "bends and length per edge (worst first), seats per gutter, cards and edges per "
        "reading; for an agent that cannot open the page",
    )
    add_root(s)
    s.set_defaults(func=cmd_describe)

    s = sub.add_parser(
        "serve",
        help="serve the output directory over HTTP on the loopback address and print the "
        "URL; the page's script does not run from a file:// address",
    )
    add_root(s)
    s.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"default {DEFAULT_PORT}")
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser(
        "skill",
        help="reinstall the agent skill directory (SKILL.md and references/) init installs, "
        "or print SKILL.md",
    )
    add_root(s)
    s.add_argument(
        "--dir",
        default="",
        help=f"the directory to write the skill into (default: {skill.DEFAULT_DIR} under the root)",
    )
    s.add_argument("--print", action="store_true", help="write SKILL.md to stdout instead")
    s.set_defaults(func=cmd_skill)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        code = args.func(args)
    except ConfigError as exc:
        warn(f"systemap: {exc}", "fix systemap.toml or the model module, then run again")
        return BAD_CONFIG
    except figure.FigureError as exc:
        warn(f"systemap: {exc}")
        return STALE
    except place.PlaceError as exc:
        warn(f"systemap: {exc}")
        return STALE
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
