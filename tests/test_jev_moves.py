"""`delta --jev`'s first half: the new module a module that disappeared became.

delta pairs a module that moved by its source, its public names, or a file
name that reads the same with most of the same names. A module renamed and
rewritten in one commit answers none of the three; Jev is asked about those
alone, and its pick counts at MOVE_AT confidence or more.
"""

from __future__ import annotations

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
    recording = Recording("jev_moves")
    client = jev.Jev(recording.send)
    moves = jev_cli.jev_moves({"components": BASE}, {"components": HEAD}, client)
    assert list(moves) == ["pkg.ledger"]
    new, how = moves["pkg.ledger"]
    assert new == "pkg.accounts.book"
    assert how.startswith("read as the same module by Jev, confidence ")
    # the module delta pairs itself is never asked about
    asked = [path for method, path in recording.sent if method == "POST"]
    assert len(asked) == 2


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
