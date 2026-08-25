"""The `systemap` command.

    systemap init                      write a configuration and a starter model
    systemap extract [--check]         read the facts out of the tree
    systemap render [--check]          render the page from facts and model
    systemap check                     check layout, routes, labels and meaning
    systemap figure ... --out FILE     one figure from the same generator
    systemap refresh                   extract, check, render, figures

Exit codes: 0 the map is current or the check passed; 1 the map is stale or
a check failed; 2 the configuration or the model cannot be used. Every
non-zero exit prints one line saying what to run.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from systemap import __version__, change, check, config, extract, figure, page, scaffold
from systemap import theme as theme_mod
from systemap.config import Config, ConfigError
from systemap.model import Meaning, Model
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
    model, meaning = config.load_model(cfg.model_path)
    return Project(cfg, model, meaning, theme_mod.resolve(cfg.theme, meaning.layers))


# ---- init ------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve() if args.root else Path.cwd().resolve()
    roots = config.discover_roots(root)
    package = roots[0][1] if roots else "mypackage"
    name = args.name or root.name
    say(*scaffold.write(root, name, package, roots))
    say(
        "next: edit atlas/model.py, then run: systemap refresh",
        "then open docs/atlas/index.html",
    )
    return OK


# ---- extract ---------------------------------------------------------------


def _extract_problems(p: Project, fresh: dict[str, Any], stored: dict[str, Any]) -> list[str]:
    problems = extract.drift(fresh, stored) + extract.mapping_drift(fresh, p.model, p.cfg.prefixes)
    if not stored:
        problems.insert(0, "no facts have been built yet")
    return problems


def cmd_extract(args: argparse.Namespace) -> int:
    p = _project(args)
    if not p.cfg.roots:
        raise ConfigError(
            'no package roots found; set [package_roots] in systemap.toml ("path" = "import name")'
        )
    fresh = extract.build(p.cfg)
    stored = extract.read_facts(p.cfg.facts_path)
    if args.check:
        problems = _extract_problems(p, fresh, stored)
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


def cmd_check(args: argparse.Namespace) -> int:
    p = _project(args)
    facts = extract.read_facts(p.cfg.facts_path)
    problems, notes, counts = check.run(p.model, p.meaning, p.theme, facts, p.cfg.issue_url)
    say(*check.report(p.model, problems, notes, counts))
    if problems:
        say(f"fix {p.cfg.model}, then run: systemap check")
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
    )
    for line in collisions:
        warn(f"label collision: {line}")
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        say(f"wrote {args.out} ({len(html) / 1024:.0f} KB)")
    else:
        sys.stdout.write(html)
    if collisions:
        warn(f"fix {p.cfg.model}, then run: systemap check")
        return STALE
    return OK


# ---- refresh ---------------------------------------------------------------


def cmd_refresh(args: argparse.Namespace) -> int:
    p = _project(args)
    quiet = bool(args.quiet)

    def note(line: str) -> None:
        if not quiet:
            say(line)

    if not p.cfg.roots:
        raise ConfigError(
            'no package roots found; set [package_roots] in systemap.toml ("path" = "import name")'
        )
    fresh = extract.build(p.cfg)
    stored = extract.read_facts(p.cfg.facts_path)
    facts_ok = not _extract_problems(p, fresh, stored)
    page_ok = False
    if facts_ok and not model_problems(p.model, p.meaning):
        current = p.cfg.page_path.read_text(encoding="utf-8") if p.cfg.page_path.is_file() else ""
        page_ok = current == _render_page(p, stored, argparse.Namespace())
    figures_ok = all((p.cfg.out_path / f.out).is_file() for f in p.cfg.figures)
    if facts_ok and page_ok and figures_ok:
        note("map: already current")
        return OK

    note("map: refreshing against the working tree")
    extract.write_facts(p.cfg.facts_path, fresh)
    written = [p.cfg.rel(p.cfg.facts_path)]
    problems, notes, counts = check.run(p.model, p.meaning, p.theme, fresh, p.cfg.issue_url)
    if problems:
        say(*check.report(p.model, problems, notes, counts))
        say(f"map: layout check failed; fix {p.cfg.model}, then run: systemap refresh")
        return STALE
    html = _render_page(p, fresh, argparse.Namespace())
    p.cfg.page_path.write_text(html, encoding="utf-8")
    written.append(p.cfg.rel(p.cfg.page_path))
    for fig in p.cfg.figures:
        html, collisions = figure.make(
            p.cfg,
            p.model,
            p.meaning,
            p.theme,
            fresh,
            mode="change" if fig.mode == "reach" else "system",
            components=fig.components,
            caption=fig.caption,
            svg_id=fig.svg_id,
            interactive=fig.interactive,
        )
        for line in collisions:
            warn(f"label collision: {line}")
        out = p.cfg.out_path / fig.out
        out.write_text(html, encoding="utf-8")
        written.append(p.cfg.rel(out))
    note(f"map: updated {', '.join(written)}")
    note(f"map: commit {p.cfg.out_dir}/ to record this state of the system")
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
        "[tool.systemap] in pyproject.toml, or .git)",
    )
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    s = sub.add_parser("init", help="write systemap.toml, a starter model and a workflow")
    s.add_argument("--name", default="", help="the page title (default: the directory name)")
    s.set_defaults(func=cmd_init)

    s = sub.add_parser("extract", help="read the facts out of the tree")
    s.add_argument("--check", action="store_true", help="exit 1 if the stored facts are stale")
    s.set_defaults(func=cmd_extract)

    s = sub.add_parser("render", help="render the page from the facts and the model")
    s.add_argument("--check", action="store_true", help="exit 1 if the page is stale")
    s.add_argument("--base", default="", help="also draw a change map of HEAD against this ref")
    s.add_argument("--head", default="HEAD")
    s.add_argument("--pr", default="", help="a pull request number, for the change map title")
    s.set_defaults(func=cmd_render)

    s = sub.add_parser("check", help="check layout, routes, labels and the meaning tables")
    s.set_defaults(func=cmd_check)

    s = sub.add_parser("figure", help="draw one figure with the same generator")
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
    s.add_argument("--caption", default="")
    s.add_argument("--svg-id", dest="svg_id", default="lessonmap")
    s.add_argument("--out", default="", help="the file to write (default: stdout)")
    s.set_defaults(func=cmd_figure)

    s = sub.add_parser("refresh", help="extract, check, render, and draw the configured figures")
    s.add_argument("--quiet", action="store_true")
    s.set_defaults(func=cmd_refresh)
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
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
