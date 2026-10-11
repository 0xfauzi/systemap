"""Ask Jev about a delta, and print its answers as suggestions.

Jev gets two types of questions:

- Which new module did a removed module become? Delta asks only about removed modules
  that its own rules left unpaired. A pick at confidence MOVE_AT or more prints as
  a `jev move` line.
- Which component has the function of a module that no component claims? Delta takes
  these modules from the `module` field of its lines. An answer prints as a
  `jev owner` line.

A Jev answer is a suggestion for source examination, not evidence. It does not change
the delta lines or the exit code. Thus a run with Jev, a run without
a key, and a run where Jev does not answer give the same result.
If there is no question, no client is made and no message prints.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

from systemap import audit, explain, extract, jev, moves, nest
from systemap.config import Config
from systemap.delta import Delta
from systemap.jev import Ask, JevError

BECAME_Q = (
    "The commit removed `old_module` and added the option modules. Which "
    "new module is the removed module after a move, rename, or edit? If no option "
    "continues the removed module, select the deleted option."
)
NOT_MOVED = "not moved: deleted"
# How many new modules the question offers: the measured cap.
MOVE_OPTIONS = 250
# A pick at this confidence or more prints. Delta and these picks found 82 renames
# against delta's 66, and 16 of the 17 added pairs were right, with earlier prompts
# on Python repositories (bench/jev/README.md, "What did tests 7 and 8 measure?").
MOVE_AT = 0.8
LABEL = "delta --jev"


@dataclass(frozen=True)
class Asked:
    """Jev's suggestions for one delta, and the reasons for absent answers."""

    lines: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()


NOTHING = Asked()


# ---- the questions ----------------------------------------------------------------


@dataclass(frozen=True)
class Unpaired:
    """The removed modules that delta did not pair, the new modules, and delta's pairs."""

    left: list[str]
    options: list[str]
    found: dict[str, tuple[str, str]]


def unpaired(base: dict[str, Any], head: dict[str, Any]) -> Unpaired:
    """Give the removed modules to ask about. Without new modules, there are none."""
    b, h = base.get("components", {}), head.get("components", {})
    gone = sorted(set(b) - set(h))
    new = sorted(set(h) - set(b))
    found = moves.find(b, h, gone, new)
    left = [m for m in gone if m not in found and not extract.is_empty_marker(b[m])]
    options = [m for m in new if not extract.is_empty_marker(h[m])]
    return Unpaired(left if options else [], options, found)


def unclaimed(d: Delta) -> dict[str, list[str]]:
    """Give the modules that no component claims, by nested map id, from the delta lines."""
    out: dict[str, list[str]] = {}
    for line in d.lines:
        if line.decide and line.module:
            out.setdefault(line.map_id, []).append(line.module)
    return out


def _first_sentence(text: str, cap: int) -> str:
    text = " ".join((text or "").split())
    for end in (". ", ".\n"):
        i = text.find(end)
        if i != -1:
            text = text[: i + 1]
            break
    return text[:cap]


def _brief(record: dict[str, Any]) -> str:
    names = ", ".join(n["name"] for n in record.get("names", [])[:12])
    doc = _first_sentence(record.get("docstring") or "", 160)
    return f"{record.get('file')}: {doc} Names: {names}"


def _move_ask(base: dict[str, Any], old: str, criteria: dict[str, str]) -> Ask:
    record = base[old]
    state = {
        "old_module": {
            "module": old,
            "file": record.get("file"),
            "docstring": record.get("docstring"),
            "names": [n["name"] for n in record.get("names", [])][:40],
        }
    }
    question = {"type": "choice", "instructions": BECAME_Q, "criteria": criteria}
    return Ask(old, state, {"became": question})


def jev_moves(
    base: dict[str, Any], head: dict[str, Any], client: jev.Jev
) -> dict[str, tuple[str, str]]:
    """Pair removed modules with new modules at confidence MOVE_AT or more.

    Delta's rules first remove known pairs. Jev selects from the new modules. A new
    module that delta paired, or that a pick with more confidence took, is not used again.
    """
    b, h = base.get("components", {}), head.get("components", {})
    found = unpaired(base, head)
    if not found.left:
        return {}
    criteria = {m: _brief(h[m]) for m in found.options[:MOVE_OPTIONS]}
    criteria[NOT_MOVED] = "The removed module was deleted. No new module continues its function."
    asks = [_move_ask(b, old, criteria) for old in found.left]
    answered = client.ask(asks)
    picks = sorted(
        ((answered[a.key]["became"], a.key) for a in asks),
        key=lambda p: (-p[0]["confidence"], p[1]),
    )
    taken = {new for new, _how in found.found.values()}
    out: dict[str, tuple[str, str]] = {}
    for a, old in picks:
        if a["choice"] == NOT_MOVED or a["confidence"] < MOVE_AT or a["choice"] in taken:
            continue
        taken.add(a["choice"])
        out[old] = (
            a["choice"],
            f"read as the same module by Jev, confidence {a['confidence']:.2f}",
        )
    return out


def owner_suggestions(
    cfg: Config,
    tree: nest.Tree,
    head: dict[str, Any],
    modules: dict[str, list[str]],
    client: jev.Jev,
) -> list[str]:
    """Give one owner prediction or three candidates per unclaimed module, in its own map."""
    plan = audit.Plan()
    for m in tree.maps:
        if modules.get(m.id):
            audit.plan_owner(plan, m, head, modules[m.id], cfg.name, placed_too=False)
    answered = client.ask(plan.asks)
    out = []
    for ask in plan.asks:
        line = audit.owner_line(plan.reads[ask.key], answered[ask.key])
        if line is not None:
            out.append(f"{line.text} ({'; '.join(line.detail)})")
    return out


# ---- asking -----------------------------------------------------------------------


def ask(
    cfg: Config,
    tree: nest.Tree,
    base: dict[str, Any],
    head: dict[str, Any],
    d: Delta,
    send: jev.Send | None = None,
) -> Asked:
    """Ask Jev about the delta. A missing key or a Jev error gives a reason, not an error."""
    left = unpaired(base, head).left
    owners = unclaimed(d)
    if not left and not owners:
        return NOTHING
    try:
        client = jev.from_env(cfg.jev_model, cfg.jev_cache_path, send)
    except JevError as exc:
        return Asked(errors=(f"{LABEL}: {exc}",))
    lines: list[str] = []
    try:
        moved = jev_moves(base, head, client) if left else {}
        lines += [f"jev move: {old} -> {new} ({how})" for old, (new, how) in moved.items()]
        lines += owner_suggestions(cfg, tree, head, owners, client) if owners else []
    except JevError as exc:
        return Asked(tuple(lines), (f"{LABEL}: {exc}",))
    finally:
        if client.usage.sent or client.usage.cached:
            print(client.usage.line(), file=sys.stderr)
    return Asked(tuple(lines))


# ---- the report -------------------------------------------------------------------

HEAD = "Jev suggestions. They do not change the delta lines or the exit code"


def text(asked: Asked, teach: bool = True) -> list[str]:
    """Give the suggestions with one explanation per kind, then the reasons."""
    out: list[str] = []
    if asked.lines:
        out.append(f"{HEAD} ({len(asked.lines)}):")
    taught: set[str] = set()
    for line in asked.lines:
        out.append(f"  {line}")
        kind = audit._bare(line).split(": ", 1)[0]
        if teach and kind not in taught:
            taught.add(kind)
            out += explain.rows(kind)
    return out + list(asked.errors)


def markdown(asked: Asked) -> str:
    """Give the suggestions and the reasons for a pull request comment, each under a heading."""
    out: list[str] = []
    if asked.lines:
        out += ["", f"**{HEAD} ({len(asked.lines)})**", ""]
        out += [f"- `{line}`" for line in asked.lines]
    if asked.errors:
        out += ["", "**Jev did not answer**", ""]
        out += [f"- {line}" for line in asked.errors]
    return "\n".join(out) + "\n" if out else ""
