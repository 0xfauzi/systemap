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
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_atlas_browser import nested_page, self_page  # noqa: F401  (fixtures)
from test_canvas_access import no_axe
from test_canvas_browser import browser

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
    assert text.startswith(f["s"] + "→" + f["t"]) and f["a"] in text and f["y"] in text
    assert point_run["pinned"]["lit"]["pin"] == line["f"]
    assert point_run["pinned"]["lit"]["flows"] == [line["f"]]
    assert point_run["unpinned"]["lit"]["pin"] is None


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


def test_the_keyboard_moves_through_cards_and_lines(
    self_page: tuple[Path, dict[str, Any]],  # noqa: F811
    card: str,
) -> None:
    """Acceptance 10."""
    out = _drive("--keys", self_page[0], card)
    top = self_page[1]["maps"][0]
    order = out["order"]
    assert sorted(x["id"] for x in order if "id" in x) == sorted(c["id"] for c in top["cards"])
    assert sorted(x["f"] for x in order if "f" in x) == sorted(top["layers"][0]["e"])
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
    assert out["onCard"]["keys"]["focus"] == {"map": "", "id": card}
    assert out["entered"]["side"]["sel"] == {"map": "", "id": card}
    assert out["escaped"]["side"]["sel"] is None and out["escaped"]["keys"]["focus"] == {
        "map": "",
        "id": card,
    }
    assert out["escaped"]["active"] == "canvas"
    fit, cam = out["fitted"]["fit"], out["fitted"]["camera"]
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


def test_the_nested_map_affordances(nested_page: Path) -> None:  # noqa: F811
    """Acceptance 12."""
    out = _drive("--nested", nested_page, "Gateway", "Gateway")
    card = next(m for m in out["marks"] if m["t"] == "card")
    assert card["under"] is True and any(m["t"] == "map" for m in out["marks"])
    assert out["details"]["enter"] == "See its 2 parts"
    inside = out["inside"]
    assert inside["state"]["chain"] == ["Gateway"] and inside["state"]["side"]["sel"] is None
    assert inside["path"] == ["join"]
    nb = out["neighbour"]
    assert nb and "outside Gateway" in out["neighbourSay"]["text"]
    assert out["out"]["current"] == "" and out["out"]["side"]["sel"] == {"map": "", "id": nb}
    assert out["esc"]["before"]["chain"] == ["Gateway"] and out["esc"]["after"]["chain"] == []


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
