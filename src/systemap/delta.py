"""The delta compares source facts at two commits and gives the necessary map changes.

It finds added, removed, and moved modules, missing public names, new imports, and
changes to flow evidence. The model on disk supplies the component claims. The report
identifies decisions and gives actions without changing the model.

Only source facts, the model, and the configured answers set the lines and the exit
code. A Jev answer does not change them (`systemap.delta_jev`), so a run with Jev and
a run without Jev give the same decisions.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from systemap import card_review, delta_git, delta_report, evidence, extract, graph, nest
from systemap import moves as moves_mod
from systemap.check import interface_head, interface_problem
from systemap.config import Config
from systemap.judgement import apply_answers, crossing_line, crossing_pairs
from systemap.judgement_evidence import answer_state
from systemap.model import (
    Component,
    Meaning,
    Model,
    claimed,
    defines_entry,
    is_symbol,
    module_matches,
    symbol_claims,
)

# Keep the public delta API while rendering lives in its own module.
FULL_LOOP = delta_report.FULL_LOOP
FULL_LOOP_SHARE = delta_report.FULL_LOOP_SHARE
MARKER = delta_report.MARKER
NEXT = delta_report.NEXT
markdown = delta_report.markdown
near_lines = delta_report.near_lines
report = delta_report.report
# Keep the public delta API while Git reading lives in its own module.
DeltaError = delta_git.DeltaError
resolve = delta_git.resolve
merge_base = delta_git.merge_base
facts_at = delta_git.facts_at
figure_url = delta_git.figure_url

# Every kind of line this module prints, for the teaching in `systemap.explain`.
KINDS = (
    "moved",
    "added",
    "removed",
    "entry vanished",
    "interface vanished",
    "new crossing import",
    "evidence lost",
    "structural evidence lost",
    "source review",
    "move candidate",
)


def comment(cfg: Config, d: Delta, head_sha: str) -> str:
    """This function gives the pull request comment with the committed figure, if any."""
    path = delta_git.committed_figure(cfg, head_sha)
    return markdown(d, delta_git.figure_url(cfg, head_sha, path), path)


# ---- the comparison --------------------------------------------------------------


@dataclass(frozen=True)
class Line:
    """This record gives one map change and its necessary action.

    `module` is the module that no component claims, for an added or moved module.
    `map_id` identifies the nested map of the line. The top map has an empty id.
    """

    kind: str
    text: str
    cards: tuple[str, ...] = ()
    decide: bool = False
    module: str = ""
    map_id: str = ""


@dataclass(frozen=True)
class Delta:
    """This record contains the map-change report for two commits."""

    base: str
    head: str
    base_ref: str
    head_ref: str
    changed: int
    added: int
    removed: int
    moved: int
    cards: int
    lines: tuple[Line, ...]
    seed: str = ""
    near: tuple[str, ...] = ()

    @property
    def open(self) -> list[Line]:
        return [line for line in self.lines if line.decide]

    @property
    def quiet(self) -> list[Line]:
        return [line for line in self.lines if not line.decide]

    @property
    def named(self) -> list[str]:
        return sorted({card for line in self.lines for card in line.cards})

    @property
    def has_change(self) -> bool:
        return bool(self.changed or self.added or self.removed or self.moved or self.lines)

    @property
    def past_a_third(self) -> bool:
        return self.cards > 0 and len(self.named) > self.cards * FULL_LOOP_SHARE


def _mapped(pattern: str, mapping: dict[str, str]) -> str:
    """This function renames a moved module in one implemented_by entry. It keeps package
    patterns.
    """
    if is_symbol(pattern):
        module, _, name = pattern.partition(":")
        return f"{mapping.get(module, module)}:{name}"
    return mapping.get(pattern, pattern)


def with_claims(model: Model, mapping: dict[str, str]) -> Model:
    """This function renames model claims through the module mapping and keeps the
    geometry.
    """
    return dataclasses.replace(
        model,
        components=tuple(
            dataclasses.replace(
                c, implemented_by=tuple(_mapped(p, mapping) for p in c.implemented_by)
            )
            for c in model.components
        ),
    )


def _names_it(c: Component, module: str) -> bool:
    """This function finds an exact module claim or a symbol claim for the specified
    module.
    """
    return module in c.implemented_by or any(m == module for m, _n in symbol_claims(c))


def compute(
    cfg: Config,
    model: Model,
    meaning: Meaning,
    base: dict[str, Any],
    head: dict[str, Any],
    base_ref: str = "",
    head_ref: str = "",
    *,
    model_file: str = "",
    within: str = "",
    prefix: str = "",
) -> Delta:
    """This function compares base and head facts against the model on disk.

    The model_file parameter supplies the path for correction instructions. The within
    parameter identifies the parent component of a nested map.
    """
    b: dict[str, Any] = base.get("components", {})
    h: dict[str, Any] = head.get("components", {})
    gone = sorted(set(b) - set(h))
    new = sorted(set(h) - set(b))
    moves = moves_mod.find(b, h, gone, new)
    renamed = {old: new_name for old, (new_name, _how) in moves.items()}
    inverse = {new_name: old for old, new_name in renamed.items()}
    model_file = model_file or cfg.model
    base_short = base.get("built_at_commit", "")[:7]
    at_base = f" at {base_short}" if base_short else " at the base commit"

    # The map as written names what the person can edit; the two views are
    # the same claims carried to each commit's names.
    head_model = with_claims(model, renamed)
    base_model = with_claims(model, inverse)
    owner_written = evidence.owners(model, head)
    owner_head = evidence.owners(head_model, head)
    owner_base = evidence.owners(base_model, base)
    ignores = [i.module for i in cfg.coverage_ignore]

    def ignored(module: str) -> bool:
        return any(module_matches(i, module) for i in ignores)

    lines: list[Line] = []

    for old, alternatives in moves_mod.candidates(b, h, gone, new, moves).items():
        named = any(_names_it(c, old) for c in model.components)
        homes = [_home(m, owner_written, ignored, within) for m in alternatives]
        lines.append(_candidate(old, alternatives, owner_base.get(old, ""), named, homes))

    # ---- moved, added, removed ------------------------------------------------
    for old, (new_name, how) in moves.items():
        explicit = [c.id for c in model.components if _names_it(c, old)]
        claimed_by = owner_written.get(new_name)
        if explicit:
            who = ", ".join(explicit)
            lines.append(
                Line(
                    "moved",
                    (
                        "moved: "
                        f"{old}"
                        " -> "
                        f"{new_name}"
                        " ("
                        f"{how}"
                        "). "
                        f"{who}"
                        " specifies "
                        f"{old}"
                        " in implemented_by. Change this claim to "
                        f"{new_name}"
                        " in "
                        f"{model_file}"
                    ),
                    tuple(explicit),
                    decide=True,
                )
            )
        elif (
            claimed_by is None
            and not ignored(new_name)
            and not extract.is_empty_marker(h[new_name])
        ):
            was = owner_base.get(old)
            lines.append(
                Line(
                    "moved",
                    (
                        "moved: "
                        f"{old}"
                        " -> "
                        f"{new_name}"
                        " ("
                        f"{how}"
                        "). No component has a claim for "
                        f"{new_name}"
                        ". Add it to a component implemented_by in "
                        f"{model_file}"
                    ),
                    (was,) if was else (),
                    decide=True,
                    module=new_name,
                )
            )
        else:
            where = f", with a claim in {claimed_by}" if claimed_by else ", ignored in [coverage]"
            lines.append(
                Line(
                    "moved",
                    f"moved: {old} -> {new_name} ({how}){where}",
                    (claimed_by,) if claimed_by else (),
                )
            )
    for module in new:
        if module in inverse:
            continue
        claimed_by = owner_written.get(module)
        if claimed_by:
            lines.append(
                Line("added", f"added: {module}, with a claim in {claimed_by}", (claimed_by,))
            )
        elif extract.is_empty_marker(h[module]):
            lines.append(Line("added", f"added: {module}, an empty package marker"))
        elif ignored(module) and not within:
            lines.append(Line("added", f"added: {module}, ignored in [coverage]"))
        else:
            # Inside a card there is no ignoring: the sub-map claims
            # exactly what the card claims.
            way_out = (
                f"the map inside {within} has the same module claims as {within}"
                if within
                else "or give a reason to ignore it in [coverage]"
            )
            lines.append(
                Line(
                    "added",
                    (
                        f"added: {module}, No component has a claim for it. Add it to a component "
                        f"implemented_by in {model_file}, {way_out}"
                    ),
                    decide=True,
                    module=module,
                )
            )
    for module in gone:
        if module in renamed:
            continue
        explicit = [c.id for c in model.components if module in c.implemented_by]
        symbols = [
            (c.id, name) for c in model.components for m, name in symbol_claims(c) if m == module
        ]
        if explicit:
            who = ", ".join(explicit)
            lines.append(
                Line(
                    "removed",
                    (
                        "removed: "
                        f"{module}"
                        ". "
                        f"{who}"
                        " specifies it in implemented_by. Remove the claim in "
                        f"{model_file}"
                    ),
                    tuple(explicit),
                    decide=True,
                )
            )
        elif symbols:
            who = ", ".join(
                f"{cid} has a symbol claim for {module}:{name}" for cid, name in symbols
            )
            lines.append(
                Line(
                    "removed",
                    f"removed: {module}. {who}. Remove the claim in {model_file}",
                    tuple(cid for cid, _n in symbols),
                    decide=True,
                )
            )
        elif module in ignores and not within:
            lines.append(
                Line(
                    "removed",
                    f"removed: {module}. Its [coverage] ignore is stale. Remove the entry.",
                    decide=True,
                )
            )
        else:
            was = owner_base.get(module)
            tail = f", with a previous claim in {was} through a pattern" if was else ""
            lines.append(Line("removed", f"removed: {module}{tail}", (was,) if was else ()))

    # ---- entry and interface names that vanished ---------------------------------
    # A card told to rename or drop a module is not asked about its names
    # too: the rename or the drop comes first, and delta is run again.
    touched = {card for line in lines if line.decide for card in line.cards}
    for c_base, c_head in zip(base_model.components, head_model.components, strict=True):
        if c_head.kind == "actor" or c_head.id in touched:
            continue
        if c_head.entry and defines_entry(c_base, base) and not defines_entry(c_head, head):
            lines.append(
                Line(
                    "entry vanished",
                    (
                        "entry vanished: "
                        f"{c_head.id}"
                        " has entry "
                        f"{c_head.entry}"
                        ", which its modules defined"
                        f"{at_base}"
                        " but no longer define it. Set entry to an available public "
                        "name in "
                        f"{model_file}"
                    ),
                    (c_head.id,),
                    decide=True,
                )
            )
        if not c_head.interface.strip() or interface_problem(c_base, b):
            continue
        if interface_problem(c_head, h):
            found = interface_head(c_head.interface)
            name = ".".join(part for part in (found or ("", "")) if part)
            lines.append(
                Line(
                    "interface vanished",
                    (
                        "interface vanished: "
                        f"{c_head.id}"
                        "'s interface starts with "
                        f"{name}"
                        ", which its modules defined"
                        f"{at_base}"
                        " but no longer define it. Start with a public name from these "
                        "modules in "
                        f"{model_file}"
                        ", or leave it empty"
                    ),
                    (c_head.id,),
                    decide=True,
                )
            )

    # ---- new crossing imports ------------------------------------------------------
    joined = {frozenset(f.edge) for f in model.flows}
    before = {(renamed.get(m, m), renamed.get(t, t)) for m in b for t in b[m].get("uses", {})}
    # The judgement's line for the pair at the head commit, so an answer
    # that covers the pair there (by pair, into, from, kind or the exact
    # line) covers the new import here.
    pairs = crossing_pairs(h, owner_head)
    for module in sorted(h):
        p = owner_head.get(module)
        if not p:
            continue
        for target in sorted(h[module].get("uses", {})):
            q = owner_head.get(target)
            if not q or q == p or frozenset((p, q)) in joined or (module, target) in before:
                continue
            imports = pairs.get((p, q), [(module, target)])
            if _answered(cfg, prefix + crossing_line(p, q, imports), h, imports):
                continue
            lines.append(
                Line(
                    "new crossing import",
                    (
                        "new crossing import: "
                        f"{module}"
                        " (component "
                        f"{p}"
                        ") imports "
                        f"{target}"
                        " (component "
                        f"{q}"
                        ") and no flow connects "
                        f"{p}"
                        " and "
                        f"{q}"
                        ". Add the flow and its description in "
                        f"{model_file}"
                        ", or answer the diagnostic in [judgement] answered."
                    ),
                    (p, q),
                    decide=True,
                )
            )

    lines.extend(
        _evidence_review_lines(
            cfg, model, meaning, base, head, base_model, head_model, at_base, model_file
        )
    )

    changed, seed, near = _around(model, b, h, new, owner_written)
    return Delta(
        base=base.get("built_at_commit", ""),
        head=head.get("built_at_commit", ""),
        base_ref=base_ref,
        head_ref=head_ref,
        changed=changed,
        added=len(new) - len(moves),
        removed=len(gone) - len(moves),
        moved=len(moves),
        cards=sum(1 for c in model.components if c.kind != "actor"),
        lines=tuple(lines),
        seed=seed,
        near=near,
    )


def _home(module: str, owner: dict[str, str], ignored: Callable[[str], bool], within: str) -> str:
    """This function tells where the model puts a module, or gives an empty string."""
    if owner.get(module):
        return f"{module} has a claim in {owner[module]}"
    return f"{module} is ignored in [coverage]" if ignored(module) and not within else ""


def _candidate(
    old: str, alternatives: tuple[str, ...], who: str, named: bool, homes: list[str]
) -> Line:
    """This function gives a move candidate line.

    The line is a decision while a component specifies the removed module, or while the
    model has no place for an added module. A model change closes it.
    """
    pair = f"move candidate: {old} and {', '.join(alternatives)} have some of the same public names"
    if named or not all(homes):
        text = f"{pair}. Examine the source before you accept a pair as a move."
        return Line("move candidate", text, (who,) if who else (), decide=True)
    text = f"{pair}. No component specifies {old} in implemented_by. {'. '.join(homes)}"
    return Line("move candidate", text, (who,) if who else ())


def _answered(
    cfg: Config, line: str, components: dict[str, Any], imports: list[tuple[str, str]]
) -> bool:
    """This function accepts an answer for a crossing line with the judgement rule.

    An exact answer must have the current evidence digest. A family answer must have
    `policy = true`. The digest uses the working tree source, as judgement does.
    """
    state = answer_state(components, cfg.root, "", imports)
    digest = hashlib.sha256(json.dumps(state, sort_keys=True, default=str).encode()).hexdigest()
    return not apply_answers([line], cfg.judgement_answered, {line: digest}).open


def _flow_review_lines(
    model: Model,
    ev_base: dict[tuple[str, str], evidence.Evidence],
    ev_head: dict[tuple[str, str], evidence.Evidence],
    at_base: str,
    model_file: str,
) -> list[Line]:
    """This function gives flows with lost source or structural evidence."""
    lines: list[Line] = []
    for f in model.flows:
        was_observed = ev_base[f.edge].state == evidence.OBSERVED
        if was_observed and ev_head[f.edge].state == evidence.DECLARED:
            lines.append(
                Line(
                    "evidence lost",
                    (
                        "evidence lost: "
                        f"{f.src}"
                        " -> "
                        f"{f.dst}"
                        " ("
                        f"{f.artifact}"
                        ") was observed"
                        f"{at_base}"
                        " and no import connects them now. Find the evidence, give the "
                        "mechanism, or remove the flow in "
                        f"{model_file}"
                    ),
                    (f.src, f.dst),
                    decide=True,
                )
            )
        elif was_observed and ev_head[f.edge].state != evidence.OBSERVED:
            lines.append(
                Line(
                    "source evidence lost",
                    (
                        f"source evidence lost: {f.src} -> {f.dst} ({f.artifact}) was source "
                        f"reviewed{at_base} and is now {ev_head[f.edge].state}. Examine its source "
                        f"references, direction, and artifact."
                    ),
                    (f.src, f.dst),
                    decide=True,
                )
            )
        if (
            ev_base[f.edge].state == evidence.STRUCTURAL
            and ev_head[f.edge].state == evidence.DECLARED
        ):
            lines.append(
                Line(
                    "structural evidence lost",
                    (
                        "structural evidence lost: "
                        f"{f.src}"
                        " -> "
                        f"{f.dst}"
                        " ("
                        f"{f.artifact}"
                        ") had an import or declared mechanism at the base commit. "
                        "That evidence is missing now. Examine the flow."
                    ),
                    (f.src, f.dst),
                    decide=True,
                )
            )

    return lines


def _evidence_review_lines(
    cfg: Config,
    model: Model,
    meaning: Meaning,
    base: dict[str, Any],
    head: dict[str, Any],
    base_model: Model,
    head_model: Model,
    at_base: str,
    model_file: str,
) -> list[Line]:
    """This function gives flows with lost evidence and components with changed source
    claims.
    """
    lines: list[Line] = []
    b: dict[str, Any] = base.get("components", {})
    h: dict[str, Any] = head.get("components", {})
    ev_base = evidence.of_model(base_model, meaning, base, cfg.observed_by)
    ev_head = evidence.of_model(head_model, meaning, head, cfg.observed_by)
    lines.extend(_flow_review_lines(model, ev_base, ev_head, at_base, model_file))

    semantic = {
        module
        for module in set(b) & set(h)
        if b[module].get("syntax_sha", b[module].get("sha"))
        != h[module].get("syntax_sha", h[module].get("sha"))
    }
    for card in model.components:
        before = set(claimed(card, b))
        after = set(claimed(card, h))
        affected = sorted((semantic & (before | after)) | (before ^ after))
        current_review = card_review.digest(card, model, meaning, head)
        if affected and (not current_review or card.source_review != current_review):
            lines.append(
                Line(
                    "source review",
                    (
                        "source review: "
                        f"{card.id}"
                        " has changed code in "
                        f"{', '.join(affected)}"
                        ". Compare its description, flows, sequences, and invariants "
                        "with the new source."
                    ),
                    (card.id,),
                    decide=True,
                )
            )

    return lines


def _around(
    model: Model,
    b: dict[str, Any],
    h: dict[str, Any],
    new: list[str],
    owner: dict[str, str],
) -> tuple[int, str, tuple[str, ...]]:
    """This function counts changed modules and identifies the primary changed component
    and its connected components.
    """
    rewritten = {m for m in set(b) & set(h) if b[m].get("sha") != h[m].get("sha")}
    seed = _seed(rewritten | set(new), owner)
    return len(rewritten), seed, tuple(graph.neighbours(model, seed)) if seed else ()


def _seed(touched: set[str], owner: dict[str, str]) -> str:
    """This function selects the component with the most changed modules. Equal counts use
    component name order.
    """
    counted: dict[str, int] = {}
    for module in touched:
        card = owner.get(module, "")
        if card:
            counted[card] = counted.get(card, 0) + 1
    return max(sorted(counted), key=lambda c: counted[c]) if counted else ""


def _view(facts: dict[str, Any], modules: set[str]) -> dict[str, Any]:
    """This function selects the facts for the specified nested-map module set."""
    components: dict[str, Any] = facts.get("components", {})
    return {**facts, "components": {m: r for m, r in components.items() if m in modules}}


def compute_tree(
    cfg: Config,
    tree: nest.Tree,
    base: dict[str, Any],
    head: dict[str, Any],
    base_ref: str = "",
    head_ref: str = "",
) -> Delta:
    """This function compares all maps in one report.

    The top map uses all modules. Each nested map uses its parent component modules at
    each commit. The move mapping keeps renamed modules in the nested comparison.
    """
    top = compute(cfg, tree.top.model, tree.top.meaning, base, head, base_ref, head_ref)
    b: dict[str, Any] = base.get("components", {})
    h: dict[str, Any] = head.get("components", {})
    gone = sorted(set(b) - set(h))
    new = sorted(set(h) - set(b))
    moves = moves_mod.find(b, h, gone, new)
    renamed = {old: new_name for old, (new_name, _how) in moves.items()}
    inverse = {new_name: old for old, new_name in renamed.items()}
    lines = list(top.lines)
    cards = top.cards
    for m in tree.maps[1:]:
        card = tree.opening_card(m)
        if card is None:
            continue
        at_head = set(claimed(with_claims_of(card, renamed), h))
        at_base = set(claimed(with_claims_of(card, inverse), b))
        sub = compute(
            cfg,
            m.model,
            m.meaning,
            _view(base, at_base),
            _view(head, at_head),
            base_ref,
            head_ref,
            model_file=m.rel,
            within=card.id,
            prefix=m.prefix,
        )
        cards += sub.cards
        lines += [
            dataclasses.replace(
                line,
                text=m.prefix + line.text,
                cards=tuple(f"{m.id}/{c}" for c in line.cards),
                map_id=m.id,
            )
            for line in sub.lines
        ]
    return dataclasses.replace(top, cards=cards, lines=tuple(lines))


def with_claims_of(card: Component, mapping: dict[str, str]) -> Component:
    """This function renames the claims of one component through the module mapping."""
    return dataclasses.replace(
        card, implemented_by=tuple(_mapped(p, mapping) for p in card.implemented_by)
    )
