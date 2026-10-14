"""The review upgrade records the source records of each flow review from systemap 2.0.0.

systemap 2.0.0 recorded a flow review digest of the flow claim only. Thus a change to the
source records did not make the review stale. This module replaces each such digest one
time with the earlier-review digest (`flow_review.earlier_digest`). That digest contains
the claim and the source records as written now. The review stays current, with the label
"review earlier than source tracking". After the replacement, a change to the source
records makes the review stale.

`systemap refresh` and `systemap extract` do the replacement before they write the facts.
The replacement does not examine claims, and it does not make a review current. It writes
only a digest that the map accepts before the write. It writes the value as literal data
into the file that defines the flow, and it keeps all other text of that file. It writes
the files only if the reader that runs no code gives the same model with only the new
values.
"""

from __future__ import annotations

import ast
import dataclasses
from pathlib import Path

from systemap import config, flow_review, model_edit, model_write, nest, review
from systemap.model import Flow, Meaning, Model


def record(cfg: config.Config, tree: nest.Tree) -> list[str]:
    """Write the earlier-review digest of each flow review from systemap 2.0.0.

    Give one line for each map with written files, and one warning line for each map that
    the command cannot write. A map without such reviews gives no line.
    """
    out: list[str] = []
    for m in tree.maps:
        if not any(flow_review.needs_record(f, m.meaning) for f in m.model.flows):
            continue
        try:
            out += _record_map(cfg, m)
        except (review.ReviewError, OSError, SyntaxError) as exc:
            out.append(
                f"warning: {m.prefix}the command cannot record the source records of the "
                f"flow reviews from systemap 2.0.0: {exc}"
            )
    return out


def _record_map(cfg: config.Config, m: nest.Map) -> list[str]:
    model, meaning = review._data(m)
    chosen = [f for f in model.flows if flow_review.needs_record(f, meaning)]
    if not chosen:
        return []
    edits: dict[Path, tuple[str, list[tuple[ast.Call, str]]]] = {}
    for flow in chosen:
        path, source, call = review._definition(m, review.Target(flow=flow.key, found=flow))
        edits.setdefault(path, (source, []))[1].append(
            (call, flow_review.earlier_digest(flow, meaning))
        )
    texts = {path: _edited(source, calls) for path, (source, calls) in edits.items()}
    expected = _with_digests(model, meaning, chosen)
    review._same(m, texts, expected, meaning)
    model_write.write_models(texts)
    files = ", ".join(sorted(cfg.rel(path) for path in texts))
    return [
        f"review: {m.prefix}the command recorded the source records of {len(chosen)} flow "
        f"reviews from systemap 2.0.0 in {files}. Each review shows the label "
        f'"{flow_review.EARLIER_LABEL}".'
    ]


def _edited(source: str, calls: list[tuple[ast.Call, str]]) -> str:
    """Set the review digest of each call. The last call changes first.

    Thus a change does not move the location of a call that changes after it.
    """
    for call, digest in sorted(calls, key=lambda item: (item[0].lineno, item[0].col_offset))[::-1]:
        source = model_edit.set_keyword(source, call, "review_digest", digest)
    return source


def _with_digests(model: Model, meaning: Meaning, chosen: list[Flow]) -> Model:
    flows = tuple(
        dataclasses.replace(f, review_digest=flow_review.earlier_digest(f, meaning))
        if f in chosen
        else f
        for f in model.flows
    )
    return dataclasses.replace(model, flows=flows)
