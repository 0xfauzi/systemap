"""Accept only zero canonical hash mismatches across Python 3.11 and 3.13,
zero formatting mismatches, and a changed hash for a function body edit.
Also measure baseline AST dumps on the same modules for comparison.

Issue 136 replaced `_dump_python_syntax` with `syntax_text.text`. The script now uses the
new function, so a new run does not give the recorded hashes.
"""

import ast
import hashlib
import json
from pathlib import Path

from systemap.syntax_text import text as _dump_python_syntax

root = Path.cwd()

result = {"canonical": {}, "baseline": {}, "formatting_mismatches": 0}
for path in sorted((root / "src/systemap").glob("*.py")):
    raw = path.read_text()
    name = path.relative_to(root).as_posix()
    canonical = _dump_python_syntax(ast.parse(raw))
    result["canonical"][name] = hashlib.sha256(canonical.encode()).hexdigest()
    result["baseline"][name] = hashlib.sha256(
        ast.dump(ast.parse(raw), include_attributes=False).encode()
    ).hexdigest()
    formatted = _dump_python_syntax(ast.parse("# formatting control\n" + raw + "\n"))
    result["formatting_mismatches"] += canonical != formatted
result["body_edit_detected"] = _dump_python_syntax(
    ast.parse("def f():\n return 1\n")
) != _dump_python_syntax(ast.parse("def f():\n return 2\n"))
print(json.dumps(result))
