"""Each file read or write in src/systemap that does not use a confined function is in a list.

The confined readers are `repo_files.read_text`, `repo_files.read_bytes`, and
`file_write.read_text`. The confined writer is `file_write.write_atomic`. A different read
of a file can read a link out of the repository, or wait on a FIFO. A different write can
write through a link. This test reads the syntax tree of each module. It finds each call
of `read_text`, `read_bytes`, `write_text`, `write_bytes`, or `open` on a value that is not
`repo_files` or `file_write`, each call of the built-in `open`, `json.load`,
`tomllib.load`, `os.replace`, and `tempfile.mkstemp`, and each `shutil.copy*` call.

Acceptance: the found calls are the same as the ALLOWED
list. A new read of this type fails the test until it uses a confined reader, or until its
entry is in the list with its cause. An entry without a call also fails the test.
On the base (origin/main at 2c7b1f8), the same rule found 34 calls. 23 calls are in
the list below. This change repaired the other 11 calls: 10 defects, and the page read
of `render --check`, which `out_paths.checked` confined but which did not refuse a FIFO.
After the write rule was added, the rule found 47 calls on commit e51ab46. This change
repaired the 8 writes that were not in the list: the page and figure writes, the facts
write, the plan save, the decision store, and the `systemap live` page writes. A write
of these went through a link. The list has 39 calls, 23 reads and 16 writes.
Issue 120 removed the two reads of `model_load` from the list (46 calls before, 44
after). The model reader reads each map file through `repo_files`.
"""

from __future__ import annotations

import ast
from pathlib import Path

import systemap

SOURCE = Path(systemap.__file__).parent
CONFINED = frozenset({"repo_files", "file_write"})
READS = frozenset({"read_text", "read_bytes", "open", "write_text", "write_bytes"})
# Writes that do not go through `file_write.write_atomic`.
WRITES = frozenset({("os", "replace"), ("tempfile", "mkstemp")})
LOADS = frozenset({"json", "tomllib"})

MODEL = "a model file of a loaded map: nest.load and config.load_model examined it"

# (module, function, call): the cause that the read is not a defect.
ALLOWED: dict[tuple[str, str, str], str] = {
    # Package data: the installed files of systemap, not a repository file.
    ("agent.py", "<module>", "read_text"): "package data",
    ("skill.py", "files", "read_text"): "package data",
    ("skill.py", "files", "entry.read_text"): "package data",
    # The configuration file. config.load read it before with repo_files.read_text.
    ("answer_write.py", "add", "target.read_bytes"): "the configuration that config.load read",
    ("answer_write.py", "renew_evidence", "target.read_bytes"): (
        "the configuration that config.load read"
    ),
    ("decisions_submit.py", "_write_answers", "target.read_bytes"): "the same configuration",
    # A path that decisions.confined gave: repo_files.checked examined it.
    ("decisions.py", "file_digest", "path.read_bytes"): "a path from decisions.confined",
    ("decisions_submit.py", "_citation_errors", "full.read_bytes"): "a path from confined",
    # The --results option of the person who operates the command, or stdin.
    ("decisions_submit.py", "read_results", "read_text"): "a path from a command option",
    # Writes: os.devnull and the Git blobs that the command writes.
    ("delta_git.py", "write_tree", "open"): "os.devnull for writes",
    ("delta_git.py", "write_tree", "target.open"): "a write of a Git blob",
    # The confined open functions.
    ("file_write.py", "_create", "os.open"): "the lock open that refuses a link and a FIFO",
    ("repo_files.py", "_open", "os.open"): "the confined reader",
    ("repo_files.py", "_open_below", "os.open"): "the confined reader: a file in an open folder",
    ("repo_files.py", "open_folder", "os.open"): "the confined walk: the resolved root",
    ("repo_files.py", "_child", "os.open"): "the confined walk: a folder without a link",
    # The Git shallow file that `git rev-parse --git-path shallow` names: Git metadata.
    ("history.py", "shallow_note", "path.read_text"): "Git metadata, not a repository file",
    # Model files.
    ("jev_cli.py", "_record_journey", "read_text"): MODEL,
    ("judgement_evidence.py", "model_digest", "read_bytes"): MODEL,
    ("judgement_evidence.py", "model_digest", "path.read_bytes"): MODEL,
    ("model_convert.py", "_siblings", "path.read_text"): MODEL,
    ("model_convert.py", "convert", "read_text"): MODEL,
    ("model_write.py", "write_models", "path.read_bytes"): MODEL,
    ("place_source.py", "write", "path.read_bytes"): MODEL,
    ("review.py", "_definition", "path.read_bytes"): MODEL,
    ("review.py", "_same", "shutil.copyfile"): MODEL,
    ("journeys.py", "_proposed_meaning", "shutil.copyfile"): MODEL,
    # ---- writes that do not use file_write.write_atomic ----
    # The confined writer itself.
    ("file_write.py", "write_atomic", "os.replace"): "the confined writer",
    ("file_write.py", "_temporary", "os.open"): "the confined writer: a new temporary file",
    # The configuration file that config.load read with repo_files: a regular file in the
    # repository. The write keeps its bytes, also a byte order mark.
    ("answer_write.py", "_write", "target.write_bytes"): "the configuration that config.load read",
    ("decisions_submit.py", "_write_answers", "target.write_bytes"): "the same configuration",
    # Model files. os.replace replaces a link. The temporary files are in the model folder.
    ("model_convert.py", "_same", "tempfile.mkstemp"): MODEL,
    ("model_write.py", "_replace", "os.replace"): MODEL,
    ("model_write.py", "_restore", "os.replace"): MODEL,
    ("model_write.py", "replace_bytes", "os.replace"): MODEL + ", to restore its bytes",
    ("model_write.py", "_stage", "tempfile.mkstemp"): MODEL,
    # A copy of the model files in a new temporary folder.
    ("review.py", "_same", "write_text"): "a file in a temporary folder of the command",
    # The contract move: the model file and the contract file of a loaded map.
    ("contract_move.py", "_move", "read_bytes"): MODEL,
    ("contract_move.py", "_move", "target.read_bytes"): MODEL,
    ("contract_move.py", "_same", "shutil.copyfile"): MODEL,
    ("contract_move.py", "_same", "write_text"): "a file in a temporary folder of the command",
    # init and skill: each path is examined with repo_files.inside before the write.
    ("scaffold.py", "write", "path.write_text"): "a new file that repo_files.inside examined",
    ("skill.py", "write", "path.write_text"): "a skill file that repo_files.inside examined",
}


def _call(node: ast.Call) -> str | None:
    """Give the text of a read call that is not confined, or None for a different call."""
    func = node.func
    if isinstance(func, ast.Name):
        return "open" if func.id == "open" else None
    if not isinstance(func, ast.Attribute):
        return None
    owner = func.value.id if isinstance(func.value, ast.Name) else ""
    if func.attr in READS and owner not in CONFINED:
        return f"{owner}.{func.attr}" if owner else func.attr
    if (owner in LOADS and func.attr == "load") or (owner == "shutil" and "copy" in func.attr):
        return f"{owner}.{func.attr}"
    if (owner, func.attr) in WRITES:
        return f"{owner}.{func.attr}"
    return None


def _found(path: Path) -> set[tuple[str, str, str]]:
    found: set[tuple[str, str, str]] = set()

    def walk(node: ast.AST, function: str) -> None:
        for child in ast.iter_child_nodes(node):
            inner = function
            if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef):
                inner = child.name
            if isinstance(child, ast.Call) and (call := _call(child)):
                found.add((path.name, function, call))
            walk(child, inner)

    walk(ast.parse(path.read_text(encoding="utf-8")), "<module>")
    return found


def test_each_file_read_without_a_confined_reader_is_in_the_list() -> None:
    found = set().union(*(_found(path) for path in sorted(SOURCE.glob("*.py"))))
    new = sorted(found - set(ALLOWED))
    stale = sorted(set(ALLOWED) - found)
    assert new == [], "Use repo_files or file_write, or record the call with its cause."
    assert stale == [], "Remove the entries that have no call."


def test_the_rule_finds_a_read_and_ignores_a_confined_read(tmp_path: Path) -> None:
    module = tmp_path / "sample.py"
    module.write_text(
        "def one(path, root):\n"
        "    path.read_text()\n"
        "    repo_files.read_text(root, 'x')\n"
        "    file_write.read_text(path)\n"
        "    open(path)\n"
        "    json.load(path)\n",
        encoding="utf-8",
    )
    assert _found(module) == {
        ("sample.py", "one", "path.read_text"),
        ("sample.py", "one", "open"),
        ("sample.py", "one", "json.load"),
    }
