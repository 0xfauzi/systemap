"""Pointing and selecting on the atlas page, in a browser (docs/design/atlas.md, stage 2).

The test drives real atlas pages in the Chromium of Playwright (tests/atlas_point.js): the
map of this repository, and the fixture of tests/test_canvas_page.py, which has the nested
map Gateway. The test skips when Node or the Playwright package is not there, except when
SYSTEMAP_BROWSER_TESTS is "required". Then it fails. The test of axe-core skips when
axe-core is not on NODE_PATH, with the same exception.

The card of the self-map is the card that is not an actor with the most flows in the first
layer of the top map.

Acceptance values, written before the first run on 2026-11-18:

1. A mouse move onto the card lights the flows of the card in the layer, and no other flow.
   The ends of the lit flows and the card are the lit cards. Each lit line has the color of
   the kind of its flow, a wire of 2 px or less that is wider than the wire at rest, and a
   casing that is wider than the wire.
2. Each lit line draws one time in the direction of the flow: the drawn part grows from
   less than 1 to 1 in 900 ms, and it never goes down. While the part is less than 1, the
   dash of the line starts at the first point of the line, which is the source dot. The
   canvas has the color of the kind (a sum of the channel differences of 60 or less) at
   one point or more of each lit line after the draw.
3. Each lit line has one label, and no two labels of lit lines cover each other.
4. The reading line is a polite live region. For the card it gives the name and the
   counts of the flows that it receives and gives. A move to empty space removes the light
   and the reading line.
5. A move onto a lit line lights only that flow. The reading line gives the source, the
   target, the artifact and the relation sentence of the flow. A click pins the line: it
   stays lit after the pointer goes. Esc removes the pin.
6. A card with no flow in the layer has no light that makes the map go back: the light has
   no flow and the value DIM is 0.
7. A click selects the card: after 1.6 s the details are open at the right, 380 px wide,
   with the name of the card. The frame of the map is fully at the left of the details and
   under the header. The selection ring is drawn. The details have one row for each flow
   of the card in the layer, with its relation sentence and its evidence state, and the
   sections Sequences and Rules, and Source modules for a card with modules.
8. A pointer on a row lights the flow of that row only. A click on the row selects the card
   at the other end of the flow. Esc closes the details: no card is selected, and the frame
   of the map uses the full width again.
9. On a phone of 390 x 844 px, a tap selects the card. The details are a sheet at the
   bottom, and the box of the card is fully between the headline and the top of the sheet.
   The page has no horizontal scroll.
10. Tab moves the keyboard focus through the cards and the lines of the current map in the
    order of `tabOrder`, which has each card and each line of the layer one time. The focused
    item is lit, and the reading line gives its place in the order. Enter on the card selects
    it and opens the details. Esc closes the details and gives the keyboard focus back to the
    card. F fits the map.
11. With the reduced motion of the device, and after a click on the Reduce motion button,
    each lit line is fully drawn 50 ms after the move, and DIM is 1. Without reduced motion,
    the lines are not fully drawn after 50 ms. The button has aria-pressed true, and the page
    has data-reduce-motion true.
12. Nested maps: the card Gateway has a second edge and a small picture. Its details have
    the button "See its 2 parts". A click on that button goes into Gateway, the details
    close, and the headline has the path with a button for the top map. A neighbour in
    Gateway gives "outside Gateway" in the reading line, and a click on it goes out to the
    top map and selects the same card there. A double-click goes into Gateway, and Esc goes
    out one level.
13. The page has no script error in each run. axe-core finds no serious or critical
    violation with the details open, in the light and the dark scheme, at 1440 x 900 and at
    390 x 844.

Acceptance values added on 2026-11-18 after an independent review, before the first run of
the new checks:

14. Direction. In one frame with a drawn part from 0.3 to 0.65, the dash of each such line
    has an "on" length of the full line or more and an offset of less than that length, and
    the canvas color near the start of the line (6 %, 12 % and 18 % of its length) is
    nearer to the color of the kind than the color near its end (82 %, 88 % and 94 %), by a
    sum of the channel differences of 60 or more.
15. The other cards and lines go back. With the full light, each line that is not lit has
    0.3 times its alpha at rest or less, each card that is not lit has 0.5 times its alpha
    at rest or less, and each lit card keeps its alpha at rest.
16. Layer All of the self-map: for each card that is not an actor, no lit label that draws
    over the cards covers the box of a card. A label that has no free place draws below the
    cards.
17. The details give the description, the assurance level and the freshness of the card in
    the head, the source records, one entry for each sequence that uses the card with the
    numbers of its steps, and the text of each rule that names the card, as on the canvas
    page (an import rule with no source is under each card).
    Changed on 2026-11-20 in the final repair, before the run: the head gives the level and
    the freshness in the words of the study, for example "Claims examined against the
    source, current".
18. The keyboard. Tab moves through the full order, and one more Tab leaves the canvas.
    Enter on a focused line pins it. Enter on a card gives the keyboard focus to the heading
    of the details, and 3 Tab presses or less give it to the first flow row, which lights its
    flow. Esc with the keyboard focus in the details closes them. Esc and F operate while a
    button of the page has the keyboard focus.
19. Reduced motion also applies to the details and the camera: 50 ms after a click, the
    details are open and the camera is at its end. Without reduced motion, the camera is not
    at its end after 50 ms.
20. On a phone, a tap on a line pins it, and the reading line gives it.
21. Nested maps: after a double-click on the pointed card, after a zoom of the camera into
    the map while the pointer stays on the card, and after Shift+Enter on the focused card,
    the camera is in the map and the reading line is empty. A click on the path of the
    headline goes out to the top map.

Acceptance values added on 2026-11-18 after a second independent review, before the first
run of the new checks:

22. The rules of the map stay available. The details of a card have the entry "All rules
    of this map (N)", where N is the count of the invariants and the import rules of the
    map, and the text of each invariant and each import rule of the map. In a map with an
    invariant that names no card, the details of each card give the text of that
    invariant. In a map with no rules, the details give "The model has no rules for this
    map."
23. On the phone sheet after a resize: with the details open at 1440 x 900, a change of
    the window to 390 x 844 moves the box of the selected card fully between the headline
    and the top of the sheet.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from conftest import write_tree
from test_atlas_browser import nested_page, self_page  # noqa: F401  (fixtures)
from test_canvas_access import no_axe
from test_canvas_browser import browser
from test_nest_join import CONFIG, NESTED, SOURCE, TOP

from systemap import atlas_data, config, facts_file, nest
from systemap.cli import main

ROOT = Path(__file__).resolve().parent
DRIVER = ROOT / "atlas_point.js"


def _drive(mode: str, page: Path, *rest: str) -> dict[str, Any]:
    proc = subprocess.run(
        [browser(), str(DRIVER), mode, str(page), *rest],
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr
    out = dict(json.loads(proc.stdout))
    assert out.get("errors", []) == [], out.get("errors")
    return out


def _card(data: dict[str, Any]) -> str:
    top = data["maps"][0]
    edges = top["layers"][0]["e"]
    count: dict[str, int] = {}
    for i in edges:
        for end in ("s", "t"):
            count[top["flows"][i][end]] = count.get(top["flows"][i][end], 0) + 1
    cards = [c["id"] for c in top["cards"] if c["k"] != "actor"]
    return max(cards, key=lambda c: (count.get(c, 0), c))


def _layer_flows(data: dict[str, Any], card: str) -> list[int]:
    top = data["maps"][0]
    return sorted(
        i for i in top["layers"][0]["e"] if card in (top["flows"][i]["s"], top["flows"][i]["t"])
    )


@pytest.fixture(scope="module")
def card(self_page: tuple[Path, dict[str, Any]]) -> str:  # noqa: F811
    return _card(self_page[1])


@pytest.fixture(scope="module")
def point_run(self_page: tuple[Path, dict[str, Any]], card: str) -> dict[str, Any]:  # noqa: F811
    return _drive("--point", self_page[0], card)


def _rgb(hex_color: str) -> list[int]:
    h = hex_color.lstrip("#")
    return [int(h[i : i + 2], 16) for i in (0, 2, 4)]


KIND = {"data": "--data", "control": "--control", "judge": "--judge", "context": "--context"}


def test_pointing_at_a_card_lights_its_flows(
    self_page: tuple[Path, dict[str, Any]],  # noqa: F811
    card: str,
    point_run: dict[str, Any],
) -> None:
    """Acceptance 1."""
    top = self_page[1]["maps"][0]
    want = _layer_flows(self_page[1], card)
    lit = point_run["state"]["lit"]
    assert want and lit["flows"] == want and lit["focus"] is True
    ends = {top["flows"][i][e] for i in want for e in ("s", "t")} | {card}
    assert set(lit["cards"]) == ends
    marks = point_run["drawn"]["marks"]
    rest = {m["f"]: m for m in marks if m["t"] == "line"}
    lines = [m for m in marks if m["t"] == "lit"]
    assert sorted(m["f"] for m in lines) == want
    for m in lines:
        assert m["k"] == top["flows"][m["f"]]["k"]
        assert rest[m["f"]]["wire"] < m["wire"] <= 2 < m["casing"]


def test_a_lit_line_draws_one_time_from_its_source(point_run: dict[str, Any]) -> None:
    """Acceptance 2."""
    parts: dict[int, list[float]] = {}
    for frame in point_run["frames"]:
        for m in frame:
            if m["t"] != "lit":
                continue
            parts.setdefault(m["f"], []).append(m["part"])
            if m["part"] < 1:
                assert m["dash"] is not None and m["dash"][1] > 0
    for f, seq in parts.items():
        assert seq[0] < 1 and seq[-1] == 1, (f, seq)
        assert all(a <= b for a, b in zip(seq, seq[1:], strict=False)), (f, seq)
    kinds = point_run["kinds"]
    for line in point_run["colors"]:
        want = _rgb(kinds[KIND.get(line["k"], "--ink-2")])
        best = min(sum(abs(a - b) for a, b in zip(c, want, strict=True)) for c in line["colors"])
        assert best <= 60, (line["f"], line["k"], best)


def test_the_labels_of_lit_lines_cover_no_other_label(point_run: dict[str, Any]) -> None:
    """Acceptance 3."""
    marks = point_run["drawn"]["marks"]
    labels = [m for m in marks if m["t"] == "litLabel"]
    assert sorted(m["f"] for m in labels) == sorted(m["f"] for m in marks if m["t"] == "lit")
    texts = point_run["drawn"]["texts"]

    def box(label: dict[str, Any]) -> list[float]:
        mine = [t for t in texts if t["s"] == label["s"] and t["weight"] == 500]
        near = min(mine, key=lambda t: abs(t["box"][0] + t["box"][2] - 2 * label["x"]))
        return list(near["box"])

    boxes = [box(m) for m in labels]
    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            assert not (a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]), (a, b)


def test_the_reading_line_gives_the_card(card: str, point_run: dict[str, Any]) -> None:
    """Acceptance 4."""
    say = point_run["state"]["say"]
    assert say["live"] == "polite" and say["on"] is True
    assert say["text"].startswith(card) and "receives " in say["text"] and "gives " in say["text"]
    away = point_run["away"]
    assert away["say"]["on"] is False and away["lit"]["key"] == "" and away["lit"]["dim"] == 0


def test_pointing_at_a_line_lights_that_flow(
    self_page: tuple[Path, dict[str, Any]],  # noqa: F811
    point_run: dict[str, Any],
) -> None:
    """Acceptance 5."""
    line = point_run["line"]
    f = self_page[1]["maps"][0]["flows"][line["f"]]
    assert line["state"]["lit"]["flows"] == [line["f"]]
    text = line["state"]["say"]["text"]
    assert text.startswith(f["s"] + "→ to " + f["t"]) and f["a"] in text and f["y"] in text
    assert point_run["pinned"]["lit"]["pin"] == line["f"]
    assert point_run["pinned"]["lit"]["flows"] == [line["f"]]
    assert point_run["unpinned"]["lit"]["pin"] is None


def test_a_lit_line_draws_from_its_source(point_run: dict[str, Any]) -> None:
    """Acceptance 14."""
    middle = point_run["middle"]
    assert middle
    kinds = point_run["kinds"]
    for line in middle:
        on, offset = line["dash"]
        assert 0 < offset < on and 0.3 <= line["part"] <= 0.65
        want = _rgb(kinds[KIND.get(line["k"], "--ink-2")])

        def near(colors: list[list[int]], want: list[int] = want) -> int:
            return min(sum(abs(a - b) for a, b in zip(c, want, strict=True)) for c in colors)

        assert near(line["start"]) + 60 <= near(line["end"]), line


def test_the_other_cards_and_lines_go_back(point_run: dict[str, Any]) -> None:
    """Acceptance 15."""
    lit = point_run["state"]["lit"]
    assert lit["dim"] == 1
    rest = {(m["t"], m.get("f", m.get("id"))): m["alpha"] for m in point_run["restMarks"]}
    marks = point_run["drawn"]["marks"]
    lines = [m for m in marks if m["t"] == "line"]
    cards = [m for m in marks if m["t"] == "card" and m["map"] == ""]
    assert lines and cards
    for m in lines:
        if m["f"] not in lit["flows"]:
            assert m["alpha"] <= 0.3 * rest[("line", m["f"])] + 1e-9, m["f"]
    for m in cards:
        was = rest[("card", m["id"])]
        if m["id"] in lit["cards"]:
            assert m["alpha"] == pytest.approx(was), m["id"]
        else:
            assert m["alpha"] <= 0.5 * was, m["id"]


def test_a_lit_label_covers_no_card_name(self_page: tuple[Path, dict[str, Any]]) -> None:  # noqa: F811
    """Acceptance 16."""
    out = _drive("--labels", self_page[0])
    checked = 0
    for run in out["runs"]:
        boxes = [
            [c["b"][0], c["b"][1], c["b"][0] + c["b"][2], c["b"][1] + c["b"][3]]
            for c in run["cards"]
        ]
        for label in run["labels"]:
            if label["under"]:
                continue
            mine = [t for t in run["texts"] if t["s"] == label["s"]]
            near = min(
                mine,
                key=lambda t: (
                    abs(t["box"][0] + t["box"][2] - 2 * label["x"])
                    + abs(t["box"][1] + t["box"][3] - 2 * label["y"])
                ),
            )["box"]
            checked += 1
            for b in boxes:
                assert not (
                    near[0] < b[2] and near[2] > b[0] and near[1] < b[3] and near[3] > b[1]
                ), (
                    run["id"],
                    label["s"],
                )
    assert checked > 0


def test_a_card_with_no_flow_does_not_dim_the_map(point_run: dict[str, Any]) -> None:
    """Acceptance 6."""
    quiet = point_run["quiet"]
    assert quiet["state"]["lit"]["flows"] == [] and quiet["state"]["lit"]["dim"] == 0
    assert quiet["state"]["say"]["text"].startswith(quiet["id"])


@pytest.fixture(scope="module")
def select_run(self_page: tuple[Path, dict[str, Any]], card: str) -> dict[str, Any]:  # noqa: F811
    return _drive("--select", self_page[0], card)


def test_a_click_selects_the_card_and_opens_the_details(
    self_page: tuple[Path, dict[str, Any]],  # noqa: F811
    card: str,
    select_run: dict[str, Any],
) -> None:
    """Acceptance 7."""
    side = select_run["state"]["side"]
    assert side["on"] is True and side["sel"] == {"map": "", "id": card}
    assert side["box"][0] == pytest.approx(1440 - 380) and side["box"][2] == pytest.approx(380)
    frame = select_run["frame"]
    assert frame[0] >= 0 and frame[0] + frame[2] <= 1440 - 380 and frame[1] >= 48
    assert [m["id"] for m in select_run["marks"]] == [card]
    details = select_run["details"]
    assert details["title"] == card
    top = self_page[1]["maps"][0]
    rows = details["rows"]
    assert sorted(r["f"] for r in rows) == _layer_flows(self_page[1], card)
    for r in rows:
        assert top["flows"][r["f"]].get("y", "") in r["text"] and "Evidence: " in r["text"]
    assert {"Sequences", "Rules"} <= set(details["heads"])
    has_modules = any(c.get("m") for c in top["cards"] if c["id"] == card)
    assert ("Source modules" in details["heads"]) is has_modules


_CLAIMS = {
    "established": "Claims established from the source facts",
    "examined": "Claims examined against the source",
    "unknown": "Claims not examined",
}


def _level(o: dict[str, Any]) -> str:
    return f"{_CLAIMS[o['as'][0]]}, {o['as'][1]}" if o.get("as") else ""


def test_the_details_keep_the_content_of_the_canvas_page(
    self_page: tuple[Path, dict[str, Any]],  # noqa: F811
    card: str,
    select_run: dict[str, Any],
) -> None:
    """Acceptance 17."""
    top = self_page[1]["maps"][0]
    c = next(x for x in top["cards"] if x["id"] == card)
    details = select_run["details"]
    assert details["short"] == c.get("p", "")
    assert details["state"] == _level(c)
    if c.get("d"):
        assert details["about"] == c["d"]
    assert "Source records" in details["summaries"]
    assert "Module claims in the model: " in details["records"]
    want = []
    for q in top.get("sq", []):
        at = []
        for k, step in enumerate(q["s"]):
            f = top["flows"][step["f"]] if step.get("f", -1) >= 0 else None
            if (
                (f and card in (f["s"], f["t"]))
                or card in step.get("a", [])
                or card in step.get("me", [])
            ):
                at.append(k + 1)
        if at:
            word = "step " if len(at) == 1 else "steps "
            want.append(f"{q['n']}: {word}{', '.join(map(str, at))}.")
    assert details["sequences"] == want
    rules = details["rules"]
    for r in top.get("iv", []):
        if card in r.get("g", []):
            assert f"Invariant {r['n']}. {r['t']}" in rules
    for r in top.get("ir", []):
        if not r.get("s") or card in r.get("s", []) or card in r.get("t", []):
            assert f"Import rule {r['id']}." in rules
    _all_rules(top, rules)


def _all_rules(top: dict[str, Any], rules: str) -> None:
    """Acceptance 22: the details have the full list of the rules of the map."""
    count = len(top.get("iv", [])) + len(top.get("ir", []))
    assert count, "the map of the test has no rules"
    assert f"All rules of this map ({count})" in rules
    for r in top.get("iv", []):
        assert f"Invariant {r['n']}. {r['t']}" in rules
    for r in top.get("ir", []):
        assert f"Import rule {r['id']}. Kind: {r['k']}." in rules


RULES_TOP = TOP.replace(
    "from systemap import Component,", "from systemap import Component, Invariant,"
).replace(
    "flow_kinds=())",
    'flow_kinds=(), invariants=(Invariant(1, "The auth gives each token.", '
    'governs=("Auth",)), Invariant(2, "Each request has a record.")))',
)


@pytest.fixture(scope="module")
def rules_page(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, dict[str, Any]]:
    root = tmp_path_factory.mktemp("rules")
    files = {
        "systemap.toml": CONFIG + '[render]\npage = "atlas"\n',
        "map/model.py": RULES_TOP,
        "map/gateway.py": NESTED,
        **SOURCE,
    }
    write_tree(root, files)
    for command in ("place", "extract", "render"):
        assert main(["--root", str(root), command]) == 0
    cfg = config.load(root)
    tree = nest.load(cfg)
    data = atlas_data.build(cfg, tree, facts_file.read_facts(cfg.facts_path, cfg.root))
    return root / "docs" / "map" / "index.html", data


def test_an_invariant_that_names_no_card_is_in_the_details(
    rules_page: tuple[Path, dict[str, Any]],
) -> None:
    """Acceptance 22, with an invariant that names no card."""
    top = rules_page[1]["maps"][0]
    assert any(not r.get("g") for r in top["iv"])
    for card in ("Store", "Auth"):
        rules = _drive("--select", rules_page[0], card)["details"]["rules"]
        _all_rules(top, rules)
        if card == "Store":
            assert "No rule of the model names this card." in rules
        else:
            assert "Invariant 1. The auth gives each token." in rules.split("All rules")[0]


def test_a_row_lights_its_flow_and_esc_closes_the_details(
    self_page: tuple[Path, dict[str, Any]],  # noqa: F811
    card: str,
    select_run: dict[str, Any],
) -> None:
    """Acceptance 8."""
    first = select_run["details"]["rows"][0]["f"]
    assert select_run["row"]["lit"]["flows"] == [first]
    f = self_page[1]["maps"][0]["flows"][first]
    other = f["t"] if f["s"] == card else f["s"]
    assert select_run["rowClick"]["side"]["sel"] == {"map": "", "id": other}
    closed = select_run["closed"]
    assert closed["state"]["side"]["sel"] is None and closed["state"]["side"]["on"] is False
    assert closed["frame"][0] + closed["frame"][2] > 1440 - 380


def test_a_phone_has_the_details_as_a_sheet(
    self_page: tuple[Path, dict[str, Any]],  # noqa: F811
    card: str,
) -> None:
    """Acceptance 9."""
    out = _drive("--phone", self_page[0], card)
    side, box = out["state"]["side"], out["box"]
    assert side["sel"] == {"map": "", "id": card}
    assert side["box"][0] == 0 and side["box"][2] == 390 and side["top"] > 844 / 3
    assert box[1] >= out["head"] and box[1] + box[3] <= side["top"]
    assert out["scroll"] == 390
    # Acceptance 20.
    tap = out["tapLine"]
    f = self_page[1]["maps"][0]["flows"][tap["f"]]
    assert tap["state"]["lit"]["pin"] == tap["f"] and tap["state"]["lit"]["flows"] == [tap["f"]]
    assert tap["state"]["say"]["on"] is True and f["a"] in tap["state"]["say"]["text"]


def test_a_resize_to_a_phone_moves_the_card_above_the_sheet(
    self_page: tuple[Path, dict[str, Any]],  # noqa: F811
    card: str,
) -> None:
    """Acceptance 23."""
    out = _drive("--resize", self_page[0], card)
    side, box = out["state"]["side"], out["box"]
    assert side["sel"] == {"map": "", "id": card}
    assert side["box"][2] == 390
    assert box[1] >= out["head"] and box[1] + box[3] <= side["top"]


@pytest.fixture(scope="module")
def keys_run(self_page: tuple[Path, dict[str, Any]], card: str) -> dict[str, Any]:  # noqa: F811
    return _drive("--keys", self_page[0], card)


def test_the_keyboard_moves_through_cards_and_lines(
    self_page: tuple[Path, dict[str, Any]],  # noqa: F811
    card: str,
    keys_run: dict[str, Any],
) -> None:
    """Acceptance 10 and the full order of acceptance 18."""
    out = keys_run
    top = self_page[1]["maps"][0]
    order = out["order"]
    assert sorted(x["id"] for x in order if "id" in x) == sorted(c["id"] for c in top["cards"])
    assert sorted(x["f"] for x in order if "f" in x) == sorted(top["layers"][0]["e"])
    assert len(out["steps"]) == len(order)
    for i, step in enumerate(out["steps"]):
        want = order[i]
        focus = step["keys"]["focus"]
        assert focus == (
            {"map": "", "id": want["id"]} if "id" in want else {"map": "", "f": want["f"]}
        )
        assert step["lit"]["hot"] == want.get("id", want.get("f")) and step["lit"]["from"] == "key"
        assert step["say"]["text"].startswith(
            ("Card " if "id" in want else "Line ") + f"{i + 1} of {len(order)}."
        )
    assert out["after"]["keys"]["focus"] is None and out["after"]["active"] != "canvas"
    assert out["onCard"]["keys"]["focus"] == {"map": "", "id": card}
    assert out["entered"]["side"]["sel"] == {"map": "", "id": card}
    assert out["escaped"]["side"]["sel"] is None and out["escaped"]["keys"]["focus"] == {
        "map": "",
        "id": card,
    }
    assert out["escaped"]["active"] == "canvas"
    fit, cam = out["fitted"]["fit"], out["fitted"]["camera"]
    assert cam["k"] == pytest.approx(fit["k"]) and cam["x"] == pytest.approx(fit["x"])


def test_the_keyboard_reaches_the_details_and_the_buttons(keys_run: dict[str, Any]) -> None:
    """Acceptance 18."""
    out = keys_run
    first = next(x["f"] for x in out["order"] if "f" in x)
    assert out["pinned"]["lit"]["pin"] == first and out["pinned"]["lit"]["flows"] == [first]
    assert out["entered"]["active"] == "atlas-side-h"
    row = out["onRow"]
    assert row["tabs"] <= 3
    assert row["state"]["lit"]["flows"] == [row["f"]] and row["state"]["lit"]["from"] == "row"
    button = out["button"]
    assert button["before"]["side"]["on"] is True and button["before"]["active"] == "atlas-motion"
    assert button["after"]["side"]["on"] is False and button["after"]["side"]["sel"] is None
    fit, cam = button["fitted"]["fit"], button["fitted"]["camera"]
    assert button["fitted"]["active"] == "atlas-zf"
    assert cam["k"] == pytest.approx(fit["k"]) and cam["x"] == pytest.approx(fit["x"])


def test_reduced_motion_draws_no_line(
    self_page: tuple[Path, dict[str, Any]],  # noqa: F811
    card: str,
) -> None:
    """Acceptance 11."""
    out = _drive("--motion", self_page[0], card)
    for run in (out["device"], out["button"]):
        assert run["light"]["parts"] and all(p == 1 for p in run["light"]["parts"])
        assert run["light"]["lit"]["dim"] == 1
    assert any(p < 1 for p in out["plain"]["light"]["parts"])
    assert out["button"]["pressed"] == "true" and out["button"]["attr"] == "true"
    # Acceptance 19.
    for run in (out["device"], out["button"]):
        soon, late = run["select"]["soon"], run["select"]["late"]
        assert soon["side"]["on"] is True and soon["shown"] is True
        assert soon["camera"] == pytest.approx(late["camera"])
    plain = out["plain"]["select"]
    assert plain["soon"]["camera"] != pytest.approx(plain["late"]["camera"])
    assert plain["late"]["side"]["on"] is True


def test_the_nested_map_affordances(nested_page: Path) -> None:  # noqa: F811
    """Acceptance 12."""
    out = _drive("--nested", nested_page, "Gateway", "Gateway")
    card = next(m for m in out["marks"] if m["t"] == "card")
    assert card["under"] is True and any(m["t"] == "map" for m in out["marks"])
    assert out["details"]["enter"] == "See its 2 parts"
    # Acceptance 22: the fixture has no rules.
    assert "The model has no rules for this map." in out["details"]["rules"]
    inside = out["inside"]
    assert inside["state"]["chain"] == ["Gateway"] and inside["state"]["side"]["sel"] is None
    assert inside["path"] == ["join"]
    nb = out["neighbour"]
    assert nb and "outside Gateway" in out["neighbourSay"]["text"]
    assert out["out"]["current"] == "" and out["out"]["side"]["sel"] == {"map": "", "id": nb}
    assert out["esc"]["before"]["chain"] == ["Gateway"] and out["esc"]["after"]["chain"] == []
    # Acceptance 21.
    assert out["pointed"]["say"]["on"] is True and out["pointed"]["chain"] == []
    assert out["keyed"]["say"]["text"].startswith("Card ")
    for name in ("dblSay", "zoomSay", "shiftEnter"):
        assert out[name]["chain"] == ["Gateway"], name
        assert out[name]["say"] == {"on": False, "text": "", "live": "polite"}, name
        assert out[name]["lit"]["hot"] is None, name
    assert out["pathOut"]["chain"] == [] and out["pathOut"]["current"] == ""


def test_axe_finds_no_violation_with_the_details_open(
    self_page: tuple[Path, dict[str, Any]],  # noqa: F811
    card: str,
) -> None:
    """Acceptance 13."""
    runs = _drive("--axe", self_page[0], card)["runs"]
    if any(r["axe"] is None for r in runs):
        no_axe("the test needs axe-core on NODE_PATH")
    for r in runs:
        assert r["errors"] == [], r
        assert r["axe"]["violations"] == [], r
