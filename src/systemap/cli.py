"""The `systemap` CLI gives commands for map extraction, checks, rendering, and
maintenance.

Each diagnostic line is an identifier that the maintainer can use in an exact answer.
The command prints an explanation under each diagnostic kind unless the user selects
`--brief`.

Exit code 0 means success. Exit code 1 means a stale map, a check error, an open finding,
or a necessary map update. Exit code 2 means a configuration, model, option, or revision
error. Commands that read the model include nested maps. Nested lines have a map ID prefix.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from systemap import (
    __version__,
    change,
    check,
    config,
    decision_kinds,
    decisions_cli,
    delta,
    delta_jev,
    delta_link,
    describe,
    drift_order,
    explain,
    extract,
    extract_check,
    extraction,
    failures,
    figure,
    history,
    import_rules,
    init_language,
    jev_cli,
    judgement,
    judgement_json,
    model_convert,
    nest,
    out_paths,
    page,
    place,
    providers,
    review,
    scaffold,
    serve,
    skill,
    trend,
)
from systemap import facts as facts_mod
from systemap import language as languages
from systemap import suggest as suggest_mod
from systemap.config import CONFIG_FILE, ArgumentError, Config, ConfigError
from systemap.model import Meaning, Model, import_rule_problems
from systemap.model import problems as model_problems
from systemap.serve import DEFAULT_PORT, make_server

OK, STALE = 0, 1


@dataclass(frozen=True)
class Project:
    """This record contains the configuration and the tree of maps."""

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


AGENT_SENTENCE = (
    "Make a map of this repository with systemap. Obey the systemap skill and its writing rules."
)
# The sentence for a repository that already has a map: the skill's "the
# code changed" path, with the ref the map is compared against.
MAINTENANCE_SENTENCE = (
    "The code changed. Update the map with systemap. Obey the maintenance procedure "
    "of the systemap skill and its writing rules. Use base {base}."
)


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    language, roots = init_language.language_roots(root)
    package = roots[0][1] if roots else "mypackage"
    name = args.name or config.default_name(root, language)
    adapter = languages.repository(language)
    skill.check(root / skill.DEFAULT_DIR, root)
    say(*scaffold.write(root, name, package, roots, ci=scaffold.ci_mode(args), language=adapter))
    skill_path = skill.write(root / skill.DEFAULT_DIR, root)
    references = len(skill.files()) - 1
    say(
        f"The command wrote {skill_path.parent.relative_to(root).as_posix()}/ "
        f"({skill.FILE_NAME} and {references} references)"
    )
    say(*scaffold.tooling_note(root, adapter))
    say("Next, give this instruction to your coding agent:", f"  {AGENT_SENTENCE}")
    return OK


# ---- extract ---------------------------------------------------------------


def _require_roots(p: Project) -> None:
    if not p.cfg.roots:
        raise _missing_roots_error(p)


def _missing_roots_error(project: Project) -> ConfigError:
    adapter = languages.repository(project.cfg.language)
    return ConfigError(adapter.missing_roots_message(project.cfg.root))


def cmd_extract(args: argparse.Namespace) -> int:
    p = _project(args)
    _require_roots(p)
    fresh = extraction.build(p.cfg)
    stored = extract.read_facts(p.cfg.facts_path)
    if args.check:
        lines, code = extract_check.report(fresh, stored, p.tree, p.cfg.prefixes)
        say(*lines)
        return code
    extract.write_facts(out_paths.checked(p.cfg, p.cfg.facts_path), fresh)
    say(*extract.summary(fresh))
    for m in p.tree.maps:
        for line in extraction.mapping_drift(fresh, m.model, p.cfg.prefixes):
            say(f"  warning: {m.prefix}{line}")
    say(f"The command wrote {p.cfg.rel(p.cfg.facts_path)}")
    return OK


# ---- facts -----------------------------------------------------------------


def cmd_facts(args: argparse.Namespace) -> int:
    """Print a view of the facts.

    Without an option, print the extraction summary and available views. For an unknown
    module, print the nearest name and exit 1.
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
        hint = f". The nearest name is {exc.closest}" if exc.closest else ""
        say(f"The facts contain no module {exc.name}{hint}", "run: systemap facts --modules")
        return STALE
    say(*lines)
    return OK


# ---- render ----------------------------------------------------------------


def _facts_or_stale(p: Project) -> dict[str, Any] | None:
    facts = extract.read_facts(p.cfg.facts_path)
    if not facts:
        say(f"No facts are available at {p.cfg.rel(p.cfg.facts_path)}", "run: systemap extract")
        return None
    return facts


def _model_ok(p: Project, maps: list[nest.Map] | None = None) -> bool:
    """Make sure that the selected maps have no model contradictions."""
    ok = True
    for m in maps if maps is not None else list(p.tree.maps):
        problems = model_problems(m.model, m.meaning)
        if problems:
            say(
                *(m.prefix + line for line in problems),
                f"Correct {m.rel}. Then use systemap check.",
            )
            ok = False
    return ok


def _render_page(p: Project, m: nest.Map, facts: dict[str, Any], args: argparse.Namespace) -> str:
    ch: dict[str, Any] = {"has_change": False}
    base = getattr(args, "base", "")
    if base:
        ch = change.for_page(p.cfg, m, base, facts, getattr(args, "head", "HEAD"))
        ch["pr"] = change.pr_meta(p.cfg.root, getattr(args, "pr", ""))
    return page.build(
        p.cfg,
        m.model,
        m.meaning,
        m.theme,
        facts,
        ch,
        nesting=page.nesting_of(p.cfg, p.tree, m, facts),
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
        out = out_paths.checked(p.cfg, m.page_path(p.cfg))
        if args.check:
            current = out.read_text(encoding="utf-8") if out.is_file() else ""
            if current != html:
                say(f"{p.cfg.rel(out)} is stale: it differs from the rendered output.")
                code = STALE
            else:
                say(f"{p.cfg.rel(out)} agrees with the rendered output.")
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8", newline="\n")
        say(f"The command wrote {p.cfg.rel(out)} ({out.stat().st_size / 1024:.0f} KB)")
    if code == STALE:
        say("run: systemap refresh")
    return code


# ---- check -----------------------------------------------------------------


NO_COMPONENTS = "The model has no components. Read the skill instructions."


def _empty(p: Project) -> bool:
    """Report a model without components before other checks."""
    if p.model.components:
        return False
    say(NO_COMPONENTS)
    return True


def _fix_line(p: Project, results: dict[str, check.Result]) -> str:
    """Give the action for the check error with the highest priority.

    Model errors come first, then facts, combined checks, and outputs. The top map comes
    before nested maps.
    """
    for m in p.tree.maps:
        if results[m.id].problems:
            return f"Correct {m.rel}. Then use systemap check."
    top = results[p.tree.top.id]
    if not top.coverage.checked:
        return "run: systemap extract"
    coverage = _coverage_fix(p, top)
    if coverage:
        return coverage
    for m in p.tree.maps:
        result = results[m.id]
        if result.entry or result.interface or result.nesting:
            return f"Correct {m.rel}. Then use systemap check."
    return "run: systemap refresh"


def _coverage_fix(p: Project, top: check.Result) -> str:
    """Give the action for facts without modules or for coverage errors, or no action.

    Facts without modules and a model with source components need new package roots."""
    if top.coverage.total == 0 and top.entry:
        return (
            f"Set [package_roots] in {p.cfg.source or CONFIG_FILE} to the directories that "
            f"contain the source files. Then use systemap check."
        )
    if top.coverage.problems:
        return (
            f"Give each module a component in {p.cfg.model}, or give a reason to ignore it "
            f"in [coverage]. Then use systemap check."
        )
    return ""


def _check_tree(p: Project, facts: dict[str, Any]) -> dict[str, check.Result]:
    return check.run_tree(p.tree, facts, p.cfg.coverage_ignore, p.cfg.observed_by)


def _report_tree(
    p: Project, results: dict[str, check.Result], stale: list[str], teach: bool = True
) -> list[str]:
    """Give each map report in tree order, then the stale output report."""
    out: list[str] = []
    for m in p.tree.maps:
        out += check.report(m.model, results[m.id], m.rel, m.prefix, teach)
    return out + check.report_stale(stale, teach)


def cmd_check(args: argparse.Namespace) -> int:
    p = _project(args)
    _require_roots(p)
    if _empty(p):
        return STALE
    facts = extract.read_facts(p.cfg.facts_path)
    results = _check_tree(p, facts)
    stale = check.stale(p.cfg, p.tree)
    say(*_report_tree(p, results, stale, not args.brief))
    code = _rules_check(p, facts, not args.brief)
    if not check.tree_ok(results) or stale:
        say(_fix_line(p, results) if not check.tree_ok(results) else "run: systemap refresh")
        return STALE
    return code


def _rules_check(p: Project, facts: dict[str, Any], teach: bool) -> int:
    """Print the import rule results. Give exit 1 for a fail, or for an unknown result
    under [rules] unknown = "fail"."""
    ruled = import_rules.run_tree(p.tree, facts)
    say(*import_rules.report(ruled, p.cfg.rules_unknown, teach))
    return OK if import_rules.ok(ruled, p.cfg.rules_unknown) else STALE


def cmd_rules(args: argparse.Namespace) -> int:
    """Print the result of each import rule: pass, fail, or unknown.

    `--json` writes one JSON object. Notices for a person go to stderr.
    """
    p = _project(args)
    facts = extract.read_facts(p.cfg.facts_path)
    problems = [m.prefix + line for m in p.tree.maps for line in import_rule_problems(m.model)]
    ruled = import_rules.run_tree(p.tree, facts)
    if not facts:
        warn(f"No facts are available at {p.cfg.rel(p.cfg.facts_path)}", "run: systemap extract")
    if args.json:
        say(json.dumps(import_rules.payload(ruled, p.cfg.rules_unknown, problems), indent=2))
    else:
        lines = import_rules.report(ruled, p.cfg.rules_unknown, not args.brief)
        say(*problems, *(lines or ["import rules: The model has no import rules."]))
    passed = facts and not problems and import_rules.ok(ruled, p.cfg.rules_unknown)
    return OK if passed else STALE


# ---- figure ----------------------------------------------------------------


def _ids(values: list[str] | None) -> tuple[str, ...]:
    out: list[str] = []
    for value in values or []:
        out.extend(s.strip() for s in value.split(",") if s.strip())
    return tuple(out)


def _map(p: Project, map_id: str, error: type[ConfigError] = ConfigError) -> nest.Map:
    """Select the map from `--map ID`, or the top map if there is no ID."""
    if not p.tree.has(map_id):
        raise nest.unknown_map(p.tree, map_id, error)
    return p.tree.get(map_id)


def cmd_figure(args: argparse.Namespace) -> int:
    p = _project(args)
    facts = _facts_or_stale(p)
    if facts is None:
        return STALE
    m = _map(p, args.map or "", ArgumentError)
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
        say(f"The command wrote {p.cfg.rel(out)} ({len(html) / 1024:.0f} KB)")
    else:
        sys.stdout.write(html)
    if collisions:
        warn(f"Correct {m.rel}. Then use systemap check.")
        return STALE
    return OK


# ---- refresh ---------------------------------------------------------------

# Current means the page is what the renderer draws from the model's
# rendered fields and the stored facts, and the facts describe the tree.
ALREADY_CURRENT = "map: The page agrees with the rendered model fields and the facts."


def cmd_refresh(args: argparse.Namespace) -> int:
    p = _project(args)
    quiet = bool(args.quiet)

    def note(line: str) -> None:
        if not quiet:
            say(line)

    _require_roots(p)
    if _empty(p):
        return STALE
    fresh = extraction.build(p.cfg)
    # Current means two things at once: nothing on disk is older than the
    # tree or the model, and the check passes. A stale-free map that fails
    # coverage is not current; it is incomplete.
    stale_lines = check.stale(p.cfg, p.tree, fresh)
    results = _check_tree(p, fresh)
    if not stale_lines and check.tree_ok(results):
        note(ALREADY_CURRENT)
        return OK

    note("map: The refresh uses the working tree.")
    extract.write_facts(out_paths.checked(p.cfg, p.cfg.facts_path), fresh)
    written = [p.cfg.rel(p.cfg.facts_path)]
    if not check.tree_ok(results):
        say(*_report_tree(p, results, []))
        fix = _fix_line(p, results).replace("systemap check", "systemap refresh")
        say(f"map: The check found an error. {fix}")
        return STALE
    for m in p.tree.maps:
        html = _render_page(p, m, fresh, argparse.Namespace())
        out = out_paths.checked(p.cfg, m.page_path(p.cfg))
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8", newline="\n")
        written.append(p.cfg.rel(out))
    for fig in p.cfg.figures:
        html, collisions = figure.configured(p.cfg, p.tree, _map(p, fig.map), fresh, fig)
        for line in collisions:
            warn(line)
        out = out_paths.checked(p.cfg, p.cfg.out_path / fig.out)
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
        say(f"map: The check found an error after the refresh. {fix}")
        return STALE
    note(f"map: The command updated {', '.join(written)}")
    note(f"map: Commit {p.cfg.out_dir}/ to record this system state.")
    return OK


# ---- judgement -------------------------------------------------------------


def cmd_judgement(args: argparse.Namespace) -> int:
    """Print the possible map errors that the maintainer must examine.

    Exact answers must have the printed line and correct evidence. Family answers must
    have an explicit policy. The command gives stale answers but does not reject them.
    With `--strict`, an open line gives exit code 1. `--json` writes one JSON object.
    """
    p = _project(args)
    return (_judgement_json if args.json else _judgement_text)(p, args)


def _no_facts(p: Project) -> str:
    return (
        f"No facts are available at {p.cfg.rel(p.cfg.facts_path)}. The report uses only the model."
    )


STRICT_ACTION = (
    "Answer each line in [judgement] answered in systemap.toml, or do the specified action."
)


def _judgement_text(p: Project, args: argparse.Namespace) -> int:
    """Print the judgement report as text for a person."""
    if _empty(p):
        return OK
    facts = extract.read_facts(p.cfg.facts_path)
    if not facts:
        say(_no_facts(p))
    judged = judgement_json.evaluate(p.tree, facts, p.cfg)
    result = judged.result
    detail = judgement.crossing_detail_tree(p.tree, facts) if args.verbose else None
    result, detail, notes = drift_order.text(p.cfg, p.tree, facts, result, detail, args)
    say(*judgement.report(result, detail, args.kind or "", teach=not args.brief))
    say(*notes)
    say(*judgement.review_counts(p.tree, facts))
    say(*decisions_cli.unknown_text(decisions_cli.judgement_unknown(p.cfg, p.tree, facts, judged)))
    warn(*decision_kinds.warnings(p.cfg.judgement_answered))
    jev_cli.hint(p.cfg, jev_cli.JUDGEMENT_HINT)
    if args.strict and result.open:
        say(STRICT_ACTION)
        return STALE
    return OK


def _judgement_json(p: Project, args: argparse.Namespace) -> int:
    """Write the judgement report as one JSON object. Notices for a person go to stderr."""
    if not p.model.components:
        warn(NO_COMPONENTS)
        say(json.dumps(judgement_json.empty(p.cfg.require_reviews), indent=2))
        return OK
    facts = extract.read_facts(p.cfg.facts_path)
    if not facts:
        warn(_no_facts(p))
    judged = judgement_json.evaluate(p.tree, facts, p.cfg)
    detail = judgement.crossing_detail_tree(p.tree, facts)
    reviews = judgement.review_states(p.tree, facts)
    obj, notes = drift_order.payload(p.cfg, p.tree, facts, judged, detail, reviews, args)
    obj["unknown_requests"] = decisions_cli.judgement_unknown(p.cfg, p.tree, facts, judged)
    say(json.dumps(obj, indent=2))
    warn(*notes, *decision_kinds.warnings(p.cfg.judgement_answered))
    if args.strict and judged.result.open:
        warn(STRICT_ACTION)
        return STALE
    return OK


# ---- delta -----------------------------------------------------------------


def cmd_delta(args: argparse.Namespace) -> int:
    """Print map changes from the facts at two Git commits.

    The command reads committed trees and uses the model on disk. If the map needs an
    update, the exit code is 1. `--comment` writes the link comment if `page_url` is set.
    """
    p = _project(args)
    _require_roots(p)
    if _empty(p):
        return STALE
    root = p.cfg.root
    base_sha = delta.resolve(root, args.base)
    head_sha = delta.resolve(root, args.head)
    compared = delta.merge_base(root, base_sha, head_sha)
    head = delta.facts_at(p.cfg, head_sha)
    base = delta.facts_at(p.cfg, compared)
    d = delta.compute_tree(p.cfg, p.tree, base, head, base_ref=args.base, head_ref=args.head)
    # Provider answers are suggestions: they never change the lines or the exit code.
    cfg = providers.chosen(p.cfg, args.provider)
    selected = jev_cli.uses_jev(cfg, args.decide)
    asked = delta_jev.ask(cfg, p.tree, base, head, d) if selected else delta_jev.NOTHING
    say(*delta.report(d, teach=not args.brief), *delta_jev.text(asked, not args.brief))
    if args.comment:
        delta_link.write(args.comment, p.cfg.delta_page_url, args.pr, len(d.open))
    if args.decide is None and not selected and d.added and d.removed:
        jev_cli.delta_hint(p.cfg)
    return STALE if d.open else OK


# ---- suggest ---------------------------------------------------------------


def cmd_suggest(args: argparse.Namespace) -> int:
    """Print possible module groups from the facts.

    If a model has components, also print possible nested maps.
    """
    cfg = config.load(_root(args))
    facts = extract.read_facts(cfg.facts_path)
    if not facts:
        say(f"No facts are available at {cfg.rel(cfg.facts_path)}", "run: systemap extract")
        return STALE
    if args.decide:
        return jev_cli.cmd_suggest_jev(providers.chosen(cfg, args.provider), facts)
    say(*suggest_mod.lines(facts))
    if cfg.model_path.is_file():
        tree = nest.load(cfg)
        if tree.top.model.components:
            say(*suggest_mod.nesting_lines(tree, facts))
    return OK


# ---- describe --------------------------------------------------------------


def cmd_history(args: argparse.Namespace) -> int:
    """Print changes across a set of historical source snapshots."""
    p = _project(args)
    if _empty(p):
        return STALE
    try:
        shas = history.sample(p.cfg.root, args.since, args.every, args.ref)
    except delta.DeltaError as exc:
        say(f"history: {exc}")
        return STALE
    if len(shas) < 2:
        say(history.too_few(len(shas), args.since))
        return OK
    say(
        f"history: The command reads facts at {len(shas)} commits. The cache reduces "
        f"the time of later runs."
    )
    try:
        windows = trend.walk(p.cfg, p.tree.top.model, shas)
    except delta.DeltaError as exc:
        say(f"history: {exc}")
        return STALE
    say(*trend.report(windows, p.cfg.root, args.since, args.every, args.top))
    return OK


def cmd_explain(args: argparse.Namespace) -> int:
    """Print a full explanation for one diagnostic kind, or list all kinds."""
    if not args.kind:
        say("explain: The diagnostic kinds and their meanings follow.")
        for kind in sorted(explain.LESSONS):
            say(f"  {kind}: {explain.LESSONS[kind].means}")
        say('  Use systemap explain "<kind>" for the explanation and action.')
        return OK
    lines = explain.whole(args.kind)
    say(*lines)
    return OK if explain.lesson(args.kind) else STALE


def cmd_describe(args: argparse.Namespace) -> int:
    """Print measurements of the map geometry.

    The command uses the page generator. If the model has contradictions, it gives them
    instead.
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
            say(
                *(m.prefix + line for line in problems),
                f"Correct {m.rel}. Then use systemap check.",
            )
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
    """Write component positions into the model.

    The command keeps existing positions unless the user selects `--all`. The `--all`
    option keeps only positioned components with `pinned=True`. If no position stays the
    same, the command also sets boxes and searches region orders. The `--keep-order`
    option uses the listed region order. The `--print` option gives positions without a
    model write.
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
                f"The command could not write a position for {', '.join(wrong)} in {m.rel}: "
                f"the source has no explicit Component(id=...) call. Use systemap place "
                f"--print to show x and y. Add these values manually."
            )
        laid = ". The command set all boxes and the canvas" if placement.fresh else ""
        say(f"{m.prefix}place: The command wrote {m.rel}: {place.head(placement)}{laid}")
        if placement.fresh:
            say(f"{m.prefix}  {place.order_line(placement)}")
        wrote = True
    if wrote:
        say("run: systemap check")
    return OK


# ---- serve -----------------------------------------------------------------


def cmd_serve(args: argparse.Namespace) -> int:
    """Serve the output directory over HTTP.

    The command prints the URL before the server starts. The server uses the loopback
    address.
    """
    cfg = config.load(_root(args))
    if not cfg.page_path.is_file():
        say(f"No page is available at {cfg.rel(cfg.page_path)}", "run: systemap refresh")
        return STALE
    httpd = make_server(cfg.out_path, int(args.port))
    port = httpd.server_address[1]
    say(
        f"The server serves {cfg.rel(cfg.out_path)} at http://127.0.0.1:{port}/. Use "
        f"Ctrl-C to stop the server."
    )
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
    path = skill.write(target, None if args.dir else _root(args))
    references = len(skill.files()) - 1
    say(
        f"The command wrote {path}",
        f"The command wrote {target / skill.REFERENCES}/ ({references} files)",
    )
    return OK


# ---- the parser ------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="systemap",
        description="An interactive map of a Python or TypeScript system.",
    )
    parser.add_argument("--version", action="version", version=f"systemap {__version__}")
    parser.add_argument(
        "--root",
        default="",
        help=(
            "Set the project root. The default is the nearest directory with "
            "systemap.toml, [tool.systemap], or .git. Put --root before or after the "
            "command."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    def add_root(s: argparse.ArgumentParser) -> None:
        # The global --root, accepted after the subcommand as well. The
        # subparser's default is suppressed so it never overwrites a --root
        # given before the subcommand.
        s.add_argument("--root", default=argparse.SUPPRESS, help=argparse.SUPPRESS)

    s = sub.add_parser(
        "init",
        help="Make a configuration, model, skill directory, and CI workflow.",
        description=(
            "A map must have a configuration, a model, and a skill for the coding agent. "
            "This command writes these files and a GitHub workflow. The workflow gives map "
            "changes and warns about stale maps. Use this command once in the project root."
        ),
    )
    add_root(s)
    s.add_argument(
        "--name",
        default="",
        help=(
            "Set the page title. The default is the project name, Git repository directory "
            "name, or root directory name."
        ),
    )
    scaffold.add_ci_options(s)
    s.set_defaults(func=cmd_init)

    s = sub.add_parser(
        "extract",
        help="Read modules, public names, imports, tests, and entry points from the source.",
        description=(
            "Other commands read the facts from this command. It parses the source tree "
            "and records module descriptions, public names, imports, tests, and entry "
            "points. The facts give the source data. The model gives the meaning of that "
            "data."
        ),
    )
    add_root(s)
    s.add_argument("--check", action="store_true", help="Exit 1 if the stored facts are stale.")
    s.set_defaults(func=cmd_extract)

    s = sub.add_parser(
        "facts",
        help="Print one view of the extracted facts.",
        description=(
            "The facts file contains JSON data. Each option prints one view of that data. "
            "Without an option, this command prints the extraction summary."
        ),
    )
    add_root(s)
    view = s.add_mutually_exclusive_group()
    view.add_argument(
        "--modules",
        action="store_true",
        help=(
            "Print the first sentence of each module description, with public name, import, "
            "and test counts."
        ),
    )
    view.add_argument(
        "--docstrings",
        action="store_true",
        help="Print the first sentence of each module description.",
    )
    view.add_argument(
        "--module",
        default="",
        metavar="NAME",
        help=(
            "Print the module description, public names, imports, external imports, and test count."
        ),
    )
    view.add_argument(
        "--names",
        default="",
        metavar="NAME",
        help="Print the public names and their kinds. A re-export gives its source module.",
    )
    view.add_argument(
        "--entry-points",
        dest="entry_points",
        action="store_true",
        help="Print the entry point names and source targets.",
    )
    view.add_argument(
        "--external",
        action="store_true",
        help="Print external imports and the modules that use them.",
    )
    view.add_argument(
        "--imports",
        default="",
        metavar="NAME",
        help="Print the internal imports to and from one module.",
    )
    s.set_defaults(func=cmd_facts)

    s = sub.add_parser(
        "place",
        help="Set component positions and region positions.",
        description=(
            "A component must have a position on the map. This command sets positions for "
            "components without positions. The --all option sets all component positions "
            "again, but keeps components with pinned=True. If no component keeps its "
            "position, the command also sets the region, container, and canvas geometry. "
            "It selects the region order with the best routing score."
        ),
    )
    add_root(s)
    s.add_argument(
        "--all",
        action="store_true",
        help="Set all component positions again, but keep components with pinned=True.",
    )
    s.add_argument(
        "--print", action="store_true", help="Print the positions. Do not write the model."
    )
    s.add_argument(
        "--keep-order",
        action="store_true",
        help="Use the region order in the model. Do not search other orders.",
    )
    s.set_defaults(func=cmd_place)

    s = sub.add_parser(
        "render",
        help="Make the page from the facts and model.",
        description=(
            "This command reads the facts and model, then writes the page. The generated "
            "page uses the same facts as the checks."
        ),
    )
    add_root(s)
    s.add_argument("--check", action="store_true", help="Exit 1 if the page is stale.")
    s.add_argument(
        "--base", default="", help="Include a change map of HEAD relative to this Git ref."
    )
    s.add_argument("--head", default="HEAD")
    s.add_argument(
        "--pr", default="", help="Use this pull request number for the change map title."
    )
    s.set_defaults(func=cmd_render)

    s = sub.add_parser(
        "check",
        help="Do the map checks. Exit 1 if a check finds an error.",
        description=(
            "This command does all checks on all maps. The checks include geometry, "
            "meaning, coverage, nested maps, entries, interfaces, and stale outputs. The "
            "command gives the errors and necessary actions. The --brief option omits the "
            "explanations."
        ),
    )
    add_root(s)
    s.add_argument(
        "--brief",
        action="store_true",
        help="Print diagnostic lines only. Use systemap explain KIND for the full explanation.",
    )
    s.set_defaults(func=cmd_check)

    s = sub.add_parser(
        "figure",
        help="Make a figure with the page generator.",
        description=(
            "This command makes a figure with the same generator as the page. Thus, the "
            "figure and page use the same map data."
        ),
    )
    add_root(s)
    kind = s.add_mutually_exclusive_group()
    kind.add_argument("--interactive", action="store_true", help="Include the focus interaction.")
    kind.add_argument(
        "--static", action="store_true", help="Make a static figure. This is the default."
    )
    s.add_argument(
        "--components",
        nargs="*",
        metavar="ID",
        help="Give component IDs for the plan. Separate IDs with commas or spaces.",
    )
    s.add_argument("--mode", choices=["system", "change"], default="")
    s.add_argument("--base", default="", help="Set the base Git ref for a change figure.")
    s.add_argument("--head", default="HEAD")
    s.add_argument(
        "--layer",
        default="",
        metavar="ID",
        help=(
            "Show one layer and all components. Use structure, system, data, control, or a "
            "configured layer ID."
        ),
    )
    s.add_argument(
        "--map",
        default="",
        metavar="ID",
        help=(
            "Select a nested map by component ID, such as Gateway or Gateway/Routes. The "
            "default is the top map."
        ),
    )
    s.add_argument("--caption", default="")
    s.add_argument("--svg-id", dest="svg_id", default="lessonmap")
    s.add_argument(
        "--out",
        default="",
        help=(
            "Write to a path relative to out_dir, or an absolute path. The default is "
            "stdout. A .svg path gives SVG only."
        ),
    )
    s.set_defaults(func=cmd_figure)

    s = sub.add_parser(
        "refresh",
        help="Extract the facts, do the checks, and make the pages and figures.",
        description=(
            "This command first extracts the facts. Then it does the checks and makes the "
            "pages and configured figures. Use this command in a pull request workflow."
        ),
    )
    add_root(s)
    s.add_argument(
        "-q", "--quiet", action="store_true", help="Print only errors and check results."
    )
    s.set_defaults(func=cmd_refresh)

    s = sub.add_parser(
        "judgement",
        help="Print the possible map errors for the maintainer to examine.",
        description=(
            "This command gives possible errors that mechanical checks cannot identify with "
            "certainty. The diagnostics include module groups, flow descriptions, entry points, "
            "and source evidence. An answer in [judgement] answered can accept an exact line "
            "or a family of lines. Exact answers must have source evidence. Family answers "
            "must have policy=true. The command exits 0, or 1 with --strict if a line "
            "remains open."
        ),
    )
    add_root(s)
    s.add_argument(
        "--strict", action="store_true", help="Exit 1 if a line remains open. Use for CI."
    )
    s.add_argument(
        "--kind",
        default="",
        metavar="KIND",
        choices=config.LINE_KINDS,
        help="Print open lines of this kind only. The header and exit code include all kinds.",
    )
    s.add_argument(
        "--verbose",
        action="store_true",
        help="Print the imports for each crossing-import diagnostic.",
    )
    s.add_argument(
        "--brief",
        action="store_true",
        help="Print diagnostic lines only. Use systemap explain KIND for the full explanation.",
    )
    s.add_argument(
        "--json",
        action="store_true",
        help=(
            "Write one JSON object with the open lines, answers, and counts. "
            "The object has no explanation text."
        ),
    )
    s.add_argument(
        "--order-by-drift",
        action="store_true",
        help=(
            "Send one Jev question for each open stale source review line. Put these lines "
            "in sequence from the lowest probability that the claims agree with the source. "
            "The option does not change the open lines or the exit code. "
            "It must have TYPESAFE_API_KEY."
        ),
    )
    s.set_defaults(func=cmd_judgement)

    s = sub.add_parser(
        "rules",
        help="Print the result of each import rule: pass, fail, or unknown.",
        description=(
            "This command compares the import rules of the model with the resolved imports "
            "in the facts. The result fail gives each import against the rule. The result "
            "unknown gives each module with imports that are possibly not in the facts. The "
            'command exits 1 for the result fail. With [rules] unknown = "fail", it also '
            "exits 1 for the result unknown."
        ),
    )
    add_root(s)
    s.add_argument(
        "--brief",
        action="store_true",
        help="Print result lines only. Use systemap explain KIND for the full explanation.",
    )
    s.add_argument(
        "--json",
        action="store_true",
        help="Write one JSON object with the result of each rule and the counts.",
    )
    s.set_defaults(func=cmd_rules)

    s = sub.add_parser(
        "delta",
        help="Print map changes from the facts at two commits.",
        description=(
            "This command reads the facts at two Git commits. It gives added, removed, and "
            "moved modules, missing entries and interfaces, new imports, and changes to "
            "flow evidence. Each diagnostic gives the necessary action. The command exits "
            "0 if the map is current, or 1 if a map update is necessary."
        ),
    )
    add_root(s)
    s.add_argument("--base", required=True, help="Set the base commit, branch, or tag.")
    s.add_argument("--head", default="HEAD", help="Set the head commit. The default is HEAD.")
    s.add_argument("--pr", type=delta_link.number, default=0, help="Set the pull request number.")
    s.add_argument(
        "--comment",
        metavar="FILE",
        help="Write the pull request comment to FILE. Without [delta] page_url, write no file.",
    )
    s.add_argument(
        "--decide",
        "--jev",
        dest="decide",
        action=argparse.BooleanOptionalAction,
        default=None,
        help=(
            "Ask the decision provider for possible module moves and owners of modules "
            "without components. The answers are suggestions. They do not change the delta "
            "lines or the exit code. Use --no-decide to send no request. Without --decide, "
            "delta sends questions only if systemap.toml sets [jev] enabled = true and the "
            "key of the provider is set. --jev and --no-jev are the previous names of these "
            "options. They stay for one release."
        ),
    )
    providers.add_option(s)
    s.add_argument(
        "--brief",
        action="store_true",
        help="Print diagnostic lines only. Use systemap explain KIND for the full explanation.",
    )
    s.set_defaults(func=cmd_delta)

    s = sub.add_parser(
        "suggest",
        help="Print possible component groups from the facts.",
        description=(
            "This command gives possible component groups for review. It gives one "
            "component for each package with two or more modules. It gives a list of the "
            "modules and imports across group boundaries."
        ),
    )
    add_root(s)
    s.add_argument(
        "--decide",
        "--jev",
        dest="decide",
        action="store_true",
        help=(
            "Use the answers of the decision provider about module pairs to make groups. "
            "This option must have the key of the provider. --jev is the previous name of "
            "this option. It stays for one release."
        ),
    )
    providers.add_option(s)
    s.set_defaults(func=cmd_suggest)

    s = sub.add_parser(
        "describe",
        help="Print measurements of the map geometry.",
        description=(
            "This command gives map measurements for a reader without a browser. It gives "
            "components in each region, region order, routing score, flow path bends and "
            "lengths, gutter capacity, and layer contents."
        ),
    )
    add_root(s)
    s.set_defaults(func=cmd_describe)

    s = sub.add_parser(
        "history",
        help="Print map changes across a set of historical commits.",
        description=(
            "This command reads source snapshots at historical commits and compares them "
            "with the model components. Each window compares two snapshots. The largest "
            "windows occur first, with the commits that added the modules. The facts cache "
            "is in .systemap/facts."
        ),
    )
    add_root(s)
    s.add_argument(
        "--since",
        default="1 year ago",
        help="Set the start time for the samples. The default is 1 year ago.",
    )
    s.add_argument(
        "--every",
        type=int,
        default=14,
        help="Set the number of days between samples. The default is 14.",
    )
    s.add_argument(
        "--top", type=int, default=5, help="Set the number of windows to print. The default is 5."
    )
    s.add_argument(
        "--ref", default="HEAD", help="Set the branch or commit for the historical samples."
    )
    s.set_defaults(func=cmd_history)

    s = sub.add_parser(
        "explain",
        help="Print the meaning, importance, and action for a diagnostic kind.",
        description=(
            "Each diagnostic has a kind in its prefix. This command gives the explanation "
            "for one kind. Without a kind, it gives a list of all kinds."
        ),
    )
    s.add_argument("kind", nargs="?", default="", help="Give the kind from the diagnostic prefix.")
    s.set_defaults(func=cmd_explain)

    s = sub.add_parser(
        "serve",
        help="Serve the output directory over HTTP.",
        description=(
            "The page script must have an HTTP address. This command starts a server for "
            "the output directory and prints its loopback URL."
        ),
    )
    add_root(s)
    s.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Set the server port. The default is 8765."
    )
    s.set_defaults(func=cmd_serve)

    s = sub.add_parser(
        "skill",
        help="Install the skill directory, or print SKILL.md.",
        description=(
            "The coding agent uses the instructions in SKILL.md and references/. This "
            "command installs the skill directory again after a package update. The "
            "--print option prints SKILL.md."
        ),
    )
    add_root(s)
    s.add_argument(
        "--dir",
        default="",
        help=f"Set the skill directory. The default is {skill.DEFAULT_DIR} under the project root.",
    )
    s.add_argument("--print", action="store_true", help="Print SKILL.md to stdout.")
    s.set_defaults(func=cmd_skill)
    jev_cli.add_parsers(sub, add_root)
    serve.add_parsers(sub, add_root)
    model_convert.add_parsers(sub, add_root)
    review.add_parsers(sub, add_root)
    decisions_cli.add_parsers(sub, add_root)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return failures.run(args.func, args)


if __name__ == "__main__":
    raise SystemExit(main())
