"""The `systemap` command: what the agent runs.

    systemap init [--no-ci]            configuration, starter model, the skill, a workflow
    systemap extract [--check]         read the facts out of the tree
    systemap facts [--modules ...]     read the facts back, one view at a time (never the JSON)
    systemap place [--all] [--print] [--keep-order]
                                       a position for every card without one; --all for every card
    systemap render [--check]          render the page from facts and model
    systemap check                     every rule; exit 1 with each fix named
    systemap figure ... --out FILE     one figure from the same generator; --map ID for a sub-map
    systemap refresh                   extract, check, render, figures
    systemap judgement [--strict]      the list the maintainer must confirm; --kind, --verbose
    systemap delta --base REF          what a change did to the map, each line with its fix
    systemap suggest                   a first grouping from the facts, to argue with
    systemap describe                  what a look at the picture would tell you, in numbers
    systemap serve [--port N]          serve the output directory over HTTP, print the URL
    systemap skill [--dir PATH|--print] reinstall the skill directory, or print SKILL.md

Exit codes: 0 the map is current or the check passed; 1 the map is stale or
a check failed; 2 the configuration or the model cannot be used. Every
non-zero exit prints one line saying what to run.

Every command that reads the model walks the tree of maps (`nest`): the
top map, then the map inside each card that opens one. A sub-map's lines
carry its id in front, and its page is written under the output directory
at `<id>/index.html`.
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
    delta,
    describe,
    extract,
    figure,
    judgement,
    nest,
    page,
    place,
    scaffold,
    skill,
)
from systemap import facts as facts_mod
from systemap import suggest as suggest_mod
from systemap.config import Config, ConfigError
from systemap.model import Meaning, Model
from systemap.model import problems as model_problems

OK, STALE, BAD_CONFIG = 0, 1, 2


@dataclass(frozen=True)
class Project:
    """The configuration and the tree of maps under the configured model."""

    cfg: Config
    tree: nest.Tree

    @property
    def model(self) -> Model:
        return self.tree.top.model

    @property
    def meaning(self) -> Meaning:
        return self.tree.top.meaning

    @property
    def theme(self) -> dict[str, Any]:
        return self.tree.top.theme


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
    return Project(cfg, nest.load(cfg))


# ---- init ------------------------------------------------------------------


AGENT_SENTENCE = "Map this repository with systemap. Follow the systemap skill."
# The sentence for a repository that already has a map: the skill's "the
# code changed" path, with the ref the map is compared against.
MAINTENANCE_SENTENCE = (
    "The code changed. Update the map with systemap: follow the systemap skill's "
    "maintenance path, with base {base}."
)


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    roots = config.discover_roots(root)
    package = roots[0][1] if roots else "mypackage"
    name = args.name or config.default_name(root)
    say(*scaffold.write(root, name, package, roots, ci=not args.no_ci))
    skill_path = skill.write(root / skill.DEFAULT_DIR)
    references = len(skill.files()) - 1
    say(
        f"wrote {skill_path.parent.relative_to(root).as_posix()}/ "
        f"({skill.FILE_NAME} and {references} references)"
    )
    say(*scaffold.TOOLING_NOTE)
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
        problems = [
            m.prefix + line
            for m in p.tree.maps
            for line in check.stale_facts(fresh, stored, m.model, p.cfg.prefixes)
        ]
        # The drift is the facts' own and is reported once, on the top map.
        problems = list(dict.fromkeys(problems))
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
    for m in p.tree.maps:
        for line in extract.mapping_drift(fresh, m.model, p.cfg.prefixes):
            say(f"  warning: {m.prefix}{line}")
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
        elif args.docstrings:
            lines = facts_mod.docstrings(facts)
        elif args.module:
            lines = facts_mod.module(facts, args.module)
        elif args.names:
            lines = facts_mod.names(facts, args.names)
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


def _model_ok(p: Project, maps: list[nest.Map] | None = None) -> bool:
    """Every map (or the ones given) free of its own contradictions, else said."""
    ok = True
    for m in maps if maps is not None else list(p.tree.maps):
        problems = model_problems(m.model, m.meaning)
        if problems:
            say(*(m.prefix + line for line in problems), f"fix {m.rel}, then run: systemap check")
            ok = False
    return ok


def _render_page(p: Project, m: nest.Map, facts: dict[str, Any], args: argparse.Namespace) -> str:
    ch: dict[str, Any] = {"has_change": False}
    base = getattr(args, "base", "")
    if base:
        ch = change.compute(p.cfg, m.model, base, facts, getattr(args, "head", "HEAD"))
        ch["pr"] = change.pr_meta(p.cfg.root, getattr(args, "pr", ""))
    return page.build(
        p.cfg, m.model, m.meaning, m.theme, facts, ch, nesting=page.nesting_of(p.cfg, p.tree, m)
    )


def cmd_render(args: argparse.Namespace) -> int:
    p = _project(args)
    facts = _facts_or_stale(p)
    if facts is None:
        return STALE
    if not _model_ok(p):
        return STALE
    code = OK
    for m in p.tree.maps:
        html = _render_page(p, m, facts, args)
        out = m.page_path(p.cfg)
        if args.check:
            current = out.read_text(encoding="utf-8") if out.is_file() else ""
            if current != html:
                say(f"{p.cfg.rel(out)} is stale: it differs from what systemap renders")
                code = STALE
            else:
                say(f"{p.cfg.rel(out)} is current")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8", newline="\n")
        say(f"wrote {p.cfg.rel(out)} ({out.stat().st_size / 1024:.0f} KB)")
    if code == STALE:
        say("run: systemap refresh")
    return code


# ---- check -----------------------------------------------------------------


NO_COMPONENTS = "the model has no components yet; see the skill"


def _empty(p: Project) -> bool:
    """An empty model has one thing to say, and nothing else can be judged."""
    if p.model.components:
        return False
    say(NO_COMPONENTS)
    return True


def _fix_line(p: Project, results: dict[str, check.Result]) -> str:
    """The one line naming what to do first about a failed check.

    The model's own contradictions come first, since nothing else can be
    judged until they are gone; then the facts; then the rules that read
    the two together; then the outputs, which refresh regenerates. The
    top map's file is named first, then a sub-map's.
    """
    for m in p.tree.maps:
        if results[m.id].problems:
            return f"fix {m.rel}, then run: systemap check"
    top = results[p.tree.top.id]
    if not top.coverage.checked:
        return "run: systemap extract"
    if top.coverage.problems:
        return (
            f"map every module in {p.cfg.model}, or ignore it with a reason under "
            "[coverage] in the configuration, then run: systemap check"
        )
    for m in p.tree.maps:
        result = results[m.id]
        if result.entry or result.interface or result.nesting:
            return f"fix {m.rel}, then run: systemap check"
    return "run: systemap refresh"


def _check_tree(p: Project, facts: dict[str, Any]) -> dict[str, check.Result]:
    return check.run_tree(p.tree, facts, p.cfg.coverage_ignore, p.cfg.observed_by)


def _report_tree(p: Project, results: dict[str, check.Result], stale: list[str]) -> list[str]:
    """Every map's report in tree order, then the stale group once."""
    out: list[str] = []
    for m in p.tree.maps:
        out += check.report(m.model, results[m.id], m.rel, m.prefix)
    return out + check.report_stale(stale)


def cmd_check(args: argparse.Namespace) -> int:
    p = _project(args)
    _require_roots(p)
    if _empty(p):
        return STALE
    facts = extract.read_facts(p.cfg.facts_path)
    results = _check_tree(p, facts)
    stale = check.stale(p.cfg, p.tree)
    say(*_report_tree(p, results, stale))
    if not check.tree_ok(results) or stale:
        say(_fix_line(p, results) if not check.tree_ok(results) else "run: systemap refresh")
        return STALE
    return OK


# ---- figure ----------------------------------------------------------------


def _ids(values: list[str] | None) -> tuple[str, ...]:
    out: list[str] = []
    for value in values or []:
        out.extend(s.strip() for s in value.split(",") if s.strip())
    return tuple(out)


def _map(p: Project, map_id: str) -> nest.Map:
    """The map a `--map ID` names; the top map for none; unknown is refused."""
    if not p.tree.has(map_id):
        raise nest.unknown_map(p.tree, map_id)
    return p.tree.get(map_id)


def cmd_figure(args: argparse.Namespace) -> int:
    p = _project(args)
    facts = _facts_or_stale(p)
    if facts is None:
        return STALE
    m = _map(p, args.map or "")
    if not _model_ok(p, [m]):
        return STALE
    html, collisions = figure.make(
        p.cfg,
        m.model,
        m.meaning,
        m.theme,
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
        map_id=m.id,
        opens=nest.opens(p.tree, m, links=False),
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
        out.write_text(html, encoding="utf-8", newline="\n")
        say(f"wrote {p.cfg.rel(out)} ({len(html) / 1024:.0f} KB)")
    else:
        sys.stdout.write(html)
    if collisions:
        warn(f"fix {m.rel}, then run: systemap check")
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
    stale_lines = check.stale(p.cfg, p.tree, fresh)
    results = _check_tree(p, fresh)
    if not stale_lines and check.tree_ok(results):
        note(ALREADY_CURRENT)
        return OK

    note("map: refreshing against the working tree")
    extract.write_facts(p.cfg.facts_path, fresh)
    written = [p.cfg.rel(p.cfg.facts_path)]
    if not check.tree_ok(results):
        say(*_report_tree(p, results, []))
        fix = _fix_line(p, results).replace("systemap check", "systemap refresh")
        say(f"map: check failed; {fix}")
        return STALE
    for m in p.tree.maps:
        html = _render_page(p, m, fresh, argparse.Namespace())
        out = m.page_path(p.cfg)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8", newline="\n")
        written.append(p.cfg.rel(out))
    for fig in p.cfg.figures:
        html, collisions = figure.configured(p.cfg, p.tree, _map(p, fig.map), fresh, fig)
        for line in collisions:
            warn(line)
        out = p.cfg.out_path / fig.out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8", newline="\n")
        written.append(p.cfg.rel(out))
    # What was written is checked as `systemap check` would check it. A
    # refresh that leaves the check failing is not a refresh, whatever it
    # wrote; the exit code says so.
    after = _check_tree(p, fresh)
    stale_after = check.stale(p.cfg, p.tree, fresh)
    if not check.tree_ok(after) or stale_after:
        say(*_report_tree(p, after, stale_after))
        fix = (
            _fix_line(p, after) if not check.tree_ok(after) else "run: systemap refresh"
        ).replace("systemap check", "systemap refresh")
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
    lines = judgement.run_tree(
        p.tree,
        facts,
        judgement.sdk_list(p.cfg.model_sdks),
        p.cfg.observed_by,
    )
    result = judgement.apply_answers(lines, p.cfg.judgement_answered)
    detail = judgement.crossing_detail_tree(p.tree, facts) if args.verbose else None
    say(*judgement.report(result, detail, args.kind or ""))
    if args.strict and result.open:
        say("answer every line in [judgement] answered in systemap.toml, or act on it")
        return STALE
    return OK


# ---- delta -----------------------------------------------------------------


def cmd_delta(args: argparse.Namespace) -> int:
    """What a change did to the map, from the facts at two commits.

    Both trees are read from git, never from the working copy; the model
    is the one on disk. Exit 0 when nothing needs a person, 1 when a line
    does, each line naming its fix; `--format markdown` prints the report
    as a pull-request comment, with the committed map at the head commit
    where a GitHub remote and a figure make that possible.
    """
    p = _project(args)
    _require_roots(p)
    if _empty(p):
        return STALE
    root = p.cfg.root
    base_sha = delta.resolve(root, args.base)
    head_sha = delta.resolve(root, args.head)
    compared = delta.merge_base(root, base_sha, head_sha)
    d = delta.compute_tree(
        p.cfg,
        p.tree,
        delta.facts_at(p.cfg, compared),
        delta.facts_at(p.cfg, head_sha),
        base_ref=args.base,
        head_ref=args.head,
    )
    if args.format == "markdown":
        sys.stdout.write(delta.markdown(d, delta.figure_url(p.cfg, head_sha)))
    else:
        say(*delta.report(d))
    return STALE if d.open else OK


# ---- suggest ---------------------------------------------------------------


def cmd_suggest(args: argparse.Namespace) -> int:
    """A first grouping from the facts alone, to argue with; never the answer.

    With a model that has cards, the tree is read too, for when a map is
    past forty cards and which cards to open a map inside.
    """
    cfg = config.load(_root(args))
    facts = extract.read_facts(cfg.facts_path)
    if not facts:
        say(f"no facts at {cfg.rel(cfg.facts_path)}", "run: systemap extract")
        return STALE
    say(*suggest_mod.lines(facts))
    if cfg.model_path.is_file():
        tree = nest.load(cfg)
        if tree.top.model.components:
            say(*suggest_mod.nesting_lines(tree, facts))
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
    facts = extract.read_facts(p.cfg.facts_path)
    code = OK
    for m in p.tree.maps:
        # A card without a position is placed for this look, as `systemap
        # place` would place it, and the positions line says which; a
        # whole layout searched the region order, and the order line says
        # how many orders it tried.
        placement = place.compute(m.model)
        model = place.apply(m.model, placement) if placement.positions else m.model
        problems = model_problems(model, m.meaning)
        if problems:
            say(*(m.prefix + line for line in problems), f"fix {m.rel}, then run: systemap check")
            code = STALE
            continue
        lines = describe.run(
            model,
            m.meaning,
            m.theme,
            facts,
            p.cfg.observed_by,
            placement.placed,
            searched=(placement.tried, placement.routed) if placement.fresh else None,
        )
        say(*(m.prefix + line for line in lines))
    return code


# ---- place -----------------------------------------------------------------


def cmd_place(args: argparse.Namespace) -> int:
    """A position for every card without one, written into the model.

    A card with `x` and `y` is kept where it is; `--all` lays every card
    out again and keeps only the cards marked `pinned=True`. With no card
    kept the regions, the containers and the canvas are laid out too;
    with any kept, the boxes stay as written and the other cards take
    the free slots inside them; with none kept the region order is
    searched (`--keep-order` lays them as listed) and the chosen order
    and its score are printed. `--print` prints the positions instead
    of writing them. The check decides, as before: run it next.
    """
    p = _project(args)
    if _empty(p):
        return STALE
    wrote = False
    for m in p.tree.maps:
        placement = place.compute(
            m.model, all_cards=bool(args.all), keep_order=bool(args.keep_order)
        )
        if args.print or not placement.positions:
            say(*(m.prefix + line for line in place.lines(placement)))
            continue
        source = place.write(m.path, placement)
        # The file is read back and compared with what was computed, so a
        # card the edit could not reach is reported, never assumed written.
        reloaded, _meaning = config.load_model(m.path, m.rel)
        wrong = place.unwritten(reloaded, placement)
        if wrong:
            m.path.write_text(source, encoding="utf-8", newline="\n")
            raise place.PlaceError(
                f"could not write a position for {', '.join(wrong)} into {m.rel}: the card "
                "is not a Component(id=...) call the file spells out; add x and y by hand from "
                "systemap place --print"
            )
        laid = "; every box and the canvas laid out" if placement.fresh else ""
        say(f"{m.prefix}place: wrote {m.rel}: {place.head(placement)}{laid}")
        if placement.fresh:
            say(f"{m.prefix}  {place.order_line(placement)}")
        wrote = True
    if wrote:
        say("run: systemap check")
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
        help="read the facts back one view at a time: --modules (one line per module: the "
        "docstring's first sentence, then public names, imports and tests counted), "
        "--docstrings (the first sentence only), --module NAME (its record, rendered), "
        "--names NAME (its public names with kinds), --entry-points (with targets), "
        "--external, --imports NAME; with no option, the extract summary",
    )
    add_root(s)
    view = s.add_mutually_exclusive_group()
    view.add_argument(
        "--modules",
        action="store_true",
        help="one line per module: the first sentence of its docstring, then its public "
        "names, imports and tests counted",
    )
    view.add_argument(
        "--docstrings",
        action="store_true",
        help="one line per module: the first sentence of its docstring",
    )
    view.add_argument(
        "--module",
        default="",
        metavar="NAME",
        help="one module's record, rendered: docstring, public names with kinds, imports, "
        "imported by, external imports, test count",
    )
    view.add_argument(
        "--names",
        default="",
        metavar="NAME",
        help="one module's public names with their kinds; a re-export names its module",
    )
    view.add_argument(
        "--entry-points",
        dest="entry_points",
        action="store_true",
        help="where a run can start, each named the way a person types it, with its target",
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
        help="write a position into the model for every card without one, keeping every "
        "card that has one; --all lays every card out again and keeps only the cards "
        "marked pinned=True (run it after adding or removing a card); with no card kept, "
        "the regions, containers and canvas are laid out too, and the order of the regions "
        "on the grid is searched: every order tried, the best routed, the one with the "
        "fewest label collisions, refused routes, bends and length chosen; --keep-order "
        "lays them as the model lists them; --print prints instead of writing",
    )
    add_root(s)
    s.add_argument(
        "--all",
        action="store_true",
        help="lay every card out again, keeping only the cards marked pinned=True",
    )
    s.add_argument("--print", action="store_true", help="print the positions; write nothing")
    s.add_argument(
        "--keep-order",
        action="store_true",
        help="lay the regions in the order the model lists them; skip the search",
    )
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
        "nesting, entry, stale outputs, on every map; exit 1 with each fix named",
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
    s.add_argument(
        "--map",
        default="",
        metavar="ID",
        help="the map inside a card, by the card's id (Gateway, or Gateway/Routes for a map "
        "inside a map); the top map when not given",
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
        "exit 0, or 1 with --strict while any line is open; --kind KIND prints one kind, "
        "--verbose lists the imports behind each crossing-import line",
    )
    add_root(s)
    s.add_argument(
        "--strict", action="store_true", help="exit 1 while any line is unanswered, for CI"
    )
    s.add_argument(
        "--kind",
        default="",
        metavar="KIND",
        choices=config.LINE_KINDS,
        help="print the open lines of one kind only (one of: "
        + ", ".join(f'"{kind}"' for kind in config.LINE_KINDS)
        + "); the head and the exit code still count every line",
    )
    s.add_argument(
        "--verbose",
        action="store_true",
        help="under each crossing-import line, the imports it counts, one per line",
    )
    s.set_defaults(func=cmd_judgement)

    s = sub.add_parser(
        "delta",
        help="what a change did to the map, from the facts at two commits read out of git: "
        "modules added, removed and moved with the card each belongs to, entry and interface "
        "names that vanished, new imports across a card boundary with no flow, flows the "
        "code stopped backing; each line names its fix; exit 0 when nothing needs a person, "
        "1 when something does",
    )
    add_root(s)
    s.add_argument(
        "--base", required=True, help="the commit, branch or tag the map is compared against"
    )
    s.add_argument("--head", default="HEAD", help="the commit under study (default HEAD)")
    s.add_argument(
        "--format",
        choices=["text", "markdown"],
        default="text",
        help="markdown prints the report as a pull-request comment with the committed map",
    )
    s.set_defaults(func=cmd_delta)

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
        "the region order and its score, bends and length per edge (worst first), seats "
        "per gutter, cards and edges per reading; for an agent that cannot open the page",
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
    except delta.DeltaError as exc:
        warn(f"systemap: {exc}", "give delta a ref git can resolve, then run again")
        return BAD_CONFIG
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
