"""Measure what ast.parse does with deep and large inputs, for the limits of the safe model reader.

Acceptance (written before the run): each input either parses or raises SyntaxError,
RecursionError, MemoryError or ValueError, and the process does not crash. The peak
memory of a 1 MB worst-case literal file is under 400 MB. If a crash occurs, the safe
loader must refuse the input before ast.parse.

Run: uv run python bench/jev/model_parse_limits.py [BYTES]
"""

import ast
import resource
import sys
import time

CASES = {
    "parens 300": "x = " + "(" * 300 + "1" + ")" * 300,
    "lists 300": "x = " + "[" * 300 + "]" * 300,
    "unary 100000": "x = " + "-" * 100_000 + "1",
    "binop 100000": "x = " + "+".join(["1"] * 100_000),
    "attr 100000": "x = a" + ".b" * 100_000,
    "call chain 50000": "x = f" + "()" * 50_000,
    "not 100000": "x = " + "not " * 100_000 + "1",
}
for name, src in CASES.items():
    t = time.perf_counter()
    try:
        tree = ast.parse(src)
        out = f"parsed, {sum(1 for _ in ast.walk(tree))} nodes"
    except (SyntaxError, RecursionError, MemoryError, ValueError) as exc:
        out = f"{type(exc).__name__}: {str(exc)[:80]}"
    print(f"{name}: {out} ({time.perf_counter() - t:.2f} s)", flush=True)

size = int(sys.argv[1]) if len(sys.argv) > 1 else 1_000_000
src = "x = [" + "1," * (size // 2) + "]"
t = time.perf_counter()
tree = ast.parse(src)
nodes = sum(1 for _ in ast.walk(tree))
peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
print(
    f"flat list {len(src)} bytes: {nodes} nodes, peak {peak:.0f} MB ({time.perf_counter() - t:.2f} s)"
)
