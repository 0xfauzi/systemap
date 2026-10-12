"""Give colors to the code blocks of the website when the site is built.

The build changes each `<pre><code class="language-NAME">` block. Python, TOML,
JSON and TypeScript blocks get the parts that the Pygments lexers find. A shell
block gets the command, the options, the strings and the comments. A text or
console block is command output: a line that starts with "$ " is a command, and
the words at the start of a systemap line get a color. Each output line is one
span, so that a long line can wrap under its own indent.

The classes are short: k (keyword or command), s (string), f (class, function or
call), n (number or constant), a (argument or option), c (comment), p (punctuation
or operator), and on an output line: l (label), bad, ok, pr (the prompt).
site/site.css gives one color to each class, from the Ink palette, in both themes.
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterator

from pygments.lexers import get_lexer_by_name
from pygments.token import (
    Comment,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
    _TokenType,
)

BLOCK = re.compile(
    r'<pre(?: class="([^"]*)")?><code class="language-([\w+-]+)">(.*?)</code></pre>', re.S
)
LEXERS = {
    "python": "python",
    "py": "python",
    "toml": "toml",
    "json": "json",
    "ts": "typescript",
    "typescript": "typescript",
    "tsx": "tsx",
}
SHELL = frozenset({"sh", "bash", "shell"})
OUTPUT = frozenset({"text", "console", "output"})

# The parts of a shell line, in the order of the test.
SH_PART = re.compile(
    r"(?P<c>(?<!\S)#.*$)"
    r"|(?P<s>'[^']*'|\"[^\"]*\")"
    r"|(?P<o>(?<!\S)--?[A-Za-z][\w-]*)"
    r"|(?P<e>(?<!\S)[A-Z_][A-Z0-9_]*=\S*)"
    r"|(?P<v>\$\{?\w+\}?)"
    r"|(?P<j>&&|\|\||[|;])"
    r"|(?P<w>[^\s'\"|;&]+)"
    r"|(?P<sp>\s+)"
)

# The start of a systemap output line, and its class. Each rule has two groups:
# the indent and the words that get the color. The first rule that agrees with
# the line gives its color.
OUTPUT_RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^()(The map needs an update.*:)$"), "bad"),
    (re.compile(r"^()(No action is necessary.*:)$"), "ok"),
    (
        re.compile(
            r"^(\s*)((?:unmapped|stale|source review|stale source review|no endpoint source"
            r"|missing|single module|crossing import|possible mis-fold|pending answer):)"
        ),
        "bad",
    ),
    (re.compile(r"^(\s*)((?:added|removed|moved):)"), "ok"),
    (re.compile(r"^(\s*)((?:fix|run|hint):)"), "k"),
    (re.compile(r"^(\s*)([a-z][\w .-]*:)(?=\s)"), "l"),
)


def esc(text: str) -> str:
    return html.escape(text, quote=False)


def span(cls: str, text: str) -> str:
    return f'<span class="{cls}">{esc(text)}</span>' if cls and text else esc(text)


def _token_class(kind: _TokenType, after: str, depth: int) -> str:
    """Give the class of one Pygments token. `after` is the next visible character.
    A name before "=" in a call is an argument. In TOML, `depth` is 1, so a key is one also."""
    if kind in Comment:
        return "c"
    if kind in String:
        return "s"
    if kind in Number or kind in Keyword.Constant:
        return "n"
    if kind in Keyword:
        return "k"
    if kind in Name.Decorator or (kind in Name and after == "=" and depth > 0):
        return "a"
    if kind in Name.Class or kind in Name.Function or (kind in Name and after == "("):
        return "f"
    if kind in Operator or kind in Punctuation:
        return "p"
    return ""


def joined(parts: list[tuple[str, str]]) -> str:
    """Give the spans of the parts. Next parts with the same class are one span."""
    out: list[tuple[str, str]] = []
    for cls, text in parts:
        if out and out[-1][0] == cls:
            out[-1] = (cls, out[-1][1] + text)
        else:
            out.append((cls, text))
    return "".join(span(cls, text) for cls, text in out)


def _pygments(code: str, lang: str) -> str:
    tokens = list(get_lexer_by_name(LEXERS[lang]).get_tokens(code))
    parts: list[tuple[str, str]] = []
    depth = 1 if lang == "toml" else 0
    for i, (kind, value) in enumerate(tokens):
        after = next((v.strip()[:1] for _, v in tokens[i + 1 :] if v.strip()), "")
        # Spaces and new lines between parts take the class of the part before them.
        cls = parts[-1][0] if parts and not value.strip() else _token_class(kind, after, depth)
        parts.append((cls, value))
        if kind in Punctuation:
            depth += value.count("(") - value.count(")")
    return joined(parts).rstrip("\n")


def _shell_parts(line: str) -> Iterator[tuple[str, str]]:
    command_next = True
    for match in SH_PART.finditer(line):
        group, text = match.lastgroup or "sp", match.group()
        if group == "w":
            yield ("k" if command_next else ""), text
            command_next = False
        elif group == "j":
            command_next = True
            yield "p", text
        else:
            yield {"c": "c", "s": "s", "o": "a", "e": "f", "v": "f", "sp": ""}[group], text


def shell_line(line: str) -> str:
    return joined(list(_shell_parts(line)))


def _shell(code: str) -> str:
    lines, out, joined = code.rstrip("\n").split("\n"), [], False
    for line in lines:
        out.append(span("", line) if joined else shell_line(line))
        joined = line.endswith("\\")
    return "\n".join(out)


def output_line(line: str) -> str:
    """Give one line of command output, with the color of its first rule."""
    if line.startswith("$ "):
        return span("pr", "$ ") + shell_line(line[2:])
    for rule, cls in OUTPUT_RULES:
        match = rule.match(line)
        if match:
            return esc(match.group(1)) + span(cls, match.group(2)) + esc(line[match.end(2) :])
    return esc(line)


def _output(code: str) -> str:
    rows = []
    for line in code.rstrip("\n").split("\n"):
        indent = len(line) - len(line.lstrip(" "))
        rows.append(f'<span class="ln" style="--i:{indent}">{output_line(line)}</span>')
    return "\n".join(rows)


def highlight(code: str, lang: str) -> str:
    """Give the HTML of one code block. A language without rules keeps its text."""
    if lang in LEXERS:
        return _pygments(code, lang)
    if lang in SHELL:
        return _shell(code)
    if lang in OUTPUT:
        return _output(code)
    return esc(code.rstrip("\n"))


def highlight_blocks(page: str) -> str:
    """Give the page with a color for the parts of each code block with a language."""

    def one(match: re.Match[str]) -> str:
        classes, lang, body = match.group(1) or "", match.group(2), match.group(3)
        kind = "out" if lang in OUTPUT else "code"
        cls = " ".join(c for c in (kind, classes) if c)
        code = highlight(html.unescape(body), lang)
        return f'<pre class="{cls}"><code class="language-{lang}">{code}</code></pre>'

    return BLOCK.sub(one, page)
