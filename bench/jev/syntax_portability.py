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

from systemap import syntax_text

root = Path.cwd()

result = {"canonical": {}, "baseline": {}, "formatting_mismatches": 0}
for path in sorted((root / "src/systemap").glob("*.py")):
    raw = path.read_text()
    name = path.relative_to(root).as_posix()
    canonical = syntax_text.text(ast.parse(raw))
    result["canonical"][name] = hashlib.sha256(canonical.encode()).hexdigest()
    result["baseline"][name] = hashlib.sha256(
        ast.dump(ast.parse(raw), include_attributes=False).encode()
    ).hexdigest()
    formatted = syntax_text.text(ast.parse("# formatting control\n" + raw + "\n"))
    result["formatting_mismatches"] += canonical != formatted
result["body_edit_detected"] = syntax_text.text(
    ast.parse("def f():\n return 1\n")
) != syntax_text.text(ast.parse("def f():\n return 2\n"))
print(json.dumps(result))
