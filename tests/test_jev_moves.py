"""`delta --jev`'s first half: the new module a module that disappeared became.

delta pairs a module that moved by its source, its public names, or a file
name that reads the same with most of the same names. A module renamed and
rewritten in one commit answers none of the three; Jev is asked about those
alone, and its pick counts at MOVE_AT confidence or more.
"""

from __future__ import annotations

from typing import Any

from jev_replay import Recording

from systemap import jev, jev_cli
from systemap.moves import find as find_moves
from systemap.moves import with_told


def record(file: str, sha: str, doc: str, *names: str) -> dict[str, object]:
    return {
        "file": file,
        "sha": sha,
        "docstring": doc,
        "names": [{"name": n, "kind": "function"} for n in names],
        "imports": [],
    }


BASE = {
    "pkg.ledger": record(
        "pkg/ledger.py",
        "a1",
        "The ledger: records each payment against its account and keeps the running balance.",
        "record_payment",
        "balance",
        "Ledger",
    ),
    "pkg.legacy_csv": record(
        "pkg/legacy_csv.py",
        "a2",
        "Reads the CSV export of the old billing system, row by row.",
        "read_rows",
        "parse_row",
    ),
    "pkg.cli": record("pkg/cli.py", "a3", "The command line.", "main"),
}
HEAD = {
    "pkg.accounts.book": record(
        "pkg/accounts/book.py",
        "b1",
        "The account book: posts every payment to its account and answers the balance.",
        "post_payment",
        "balance_of",
        "AccountBook",
    ),
    "pkg.report": record(
        "pkg/report.py",
        "b2",
        "Formats the monthly statement as HTML for email.",
        "render_statement",
    ),
    "pkg.cli": record("pkg/cli.py", "a3", "The command line.", "main"),
}


def test_delta_alone_pairs_neither() -> None:
    gone, new = ["pkg.ledger", "pkg.legacy_csv"], ["pkg.accounts.book", "pkg.report"]
    assert find_moves(BASE, HEAD, gone, new) == {}


def test_jev_names_the_rewritten_module_and_leaves_the_deleted_one() -> None:
    requests = []

    def send(method: str, path: str, body: dict[str, Any] | None) -> dict[str, Any]:
        if path == "/models":
            return {"models": [{"name": "jev-latest", "release_date": "synthetic"}]}
        assert method == "POST" and path == "/systemone" and body is not None
        requests.append(body)
        question = body["questions"]["became"]
        assert question["instructions"] == jev_cli.BECAME_Q
        assert set(question["criteria"]) == {"pkg.accounts.book", "pkg.report", jev_cli.NOT_MOVED}
        assert question["criteria"][jev_cli.NOT_MOVED] == (
            "The removed module was deleted. No new module continues its function."
        )
        old = body["state"]["old_module"]["module"]
        choice = "pkg.accounts.book" if old == "pkg.ledger" else jev_cli.NOT_MOVED
        return {
            "model": "synthetic",
            "usage": {},
            "answers": {"became": {"type": "choice", "choice": choice, "confidence": 0.9}},
        }

    client = jev.Jev(send)
    moves = jev_cli.jev_moves({"components": BASE}, {"components": HEAD}, client)
    assert list(moves) == ["pkg.ledger"]
    new, how = moves["pkg.ledger"]
    assert new == "pkg.accounts.book"
    assert how.startswith("read as the same module by Jev, confidence ")
    # the module delta pairs itself is never asked about
    assert len(requests) == 2
    assert {body["state"]["old_module"]["module"] for body in requests} == {
        "pkg.ledger",
        "pkg.legacy_csv",
    }


# Exact historical request text for the unchanged captured answers.
HISTORICAL_BECAME_Q = "In one commit `old_module` disappeared and the modules in the options appeared. Which new module is the old one, moved or renamed and perhaps edited? If it was deleted, say so."


def test_historical_move_answers_replay_exact_requests() -> None:
    recording = Recording("jev_moves")
    client = jev.Jev(recording.send)
    criteria = {name: jev_cli._brief(HEAD[name]) for name in ("pkg.accounts.book", "pkg.report")}
    criteria[jev_cli.NOT_MOVED] = (
        "The old module was deleted; none of the new modules continues it."
    )
    asks = []
    for old in ("pkg.ledger", "pkg.legacy_csv"):
        current = jev_cli._move_ask(BASE, old, criteria)
        question = {**current.questions["became"], "instructions": HISTORICAL_BECAME_Q}
        assert question["instructions"] != jev_cli.BECAME_Q
        asks.append(jev.Ask(current.key, current.state, {"became": question}))
    answers = client.ask(asks)
    assert answers["pkg.ledger"]["became"]["choice"] == "pkg.accounts.book"
    assert answers["pkg.ledger"]["became"]["confidence"] >= jev_cli.MOVE_AT
    assert answers["pkg.legacy_csv"]["became"]["choice"] == jev_cli.NOT_MOVED
    assert [path for method, path in recording.sent if method == "POST"] == [
        "/systemone",
        "/systemone",
    ]


def test_told_moves_fill_only_what_delta_left_and_take_each_new_module_once() -> None:
    found = {"pkg.a": ("pkg.x", "same content")}
    told = {
        "pkg.a": ("pkg.y", "jev"),  # delta already paired pkg.a
        "pkg.b": ("pkg.x", "jev"),  # pkg.x is taken
        "pkg.c": ("pkg.y", "jev"),
        "pkg.d": ("pkg.y", "jev"),  # pkg.y went to pkg.c, told first
        "pkg.e": ("pkg.z", "jev"),  # pkg.z did not appear
    }
    out = with_told(found, told, ["pkg.a", "pkg.b", "pkg.c", "pkg.d", "pkg.e"], ["pkg.x", "pkg.y"])
    assert out == {"pkg.a": ("pkg.x", "same content"), "pkg.c": ("pkg.y", "jev")}
