"""The tsconfig pattern matcher tells if a path agrees with an include or exclude pattern.

The matcher gives the same result as the regular expression that the reader made
before: `**/` is `(?:[^/]+/)*`, a different `**` is `.*`, `*` is `[^/]*`, and `?` is
`[^/]`. A regular expression goes back to try each split of the path between its
wildcards, so a pattern with many wildcards took seconds for each file. The matcher
reads the path one time from start to end, and keeps the set of possible pattern
positions. A pattern with n tokens has 2 * n + 1 positions at most. Thus the cost to
make a matcher is linear in n, and the cost of each path character is linear in n.
"""

from __future__ import annotations

import re

# The kinds of pattern tokens.
LITERAL = 0
ONE = 1  # `?`: one character that is not "/".
SEGMENT = 2  # `*`: zero or more characters that are not "/".
ANY = 3  # `**` without "/" after it: zero or more characters that are not a line feed.
FOLDERS = 4  # `**/`: zero or more folder names, each with "/" after it.
_REPEATS = frozenset({SEGMENT, ANY, FOLDERS})
_RUN = re.compile(r"(\*+)(/?)|(.)", re.DOTALL)
# The number of positions in the cached steps for each pattern. If there are more, the
# cache starts again. Thus a pattern with many tokens does not keep too much memory.
_CACHE_LIMIT = 1 << 16

Token = tuple[int, str]
State = frozenset[int]


def tokens(pattern: str) -> list[Token]:
    """This function divides a pattern into tokens, as the replacements of the earlier
    regular expression did.

    In a run of stars before "/", the last two stars and the "/" are one `**/` token.
    The other stars of a run make `**` tokens from the left, and an odd star is a `*`.
    """
    out: list[Token] = []
    for match in _RUN.finditer(pattern):
        stars, slash, char = match.groups()
        if char is not None:
            out.append((ONE, "") if char == "?" else (LITERAL, char))
            continue
        count = len(stars)
        folders = bool(slash) and count >= 2
        count -= 2 if folders else 0
        out += [(ANY, "")] * (count // 2) + [(SEGMENT, "")] * (count % 2)
        if folders:
            out.append((FOLDERS, ""))
        elif slash:
            out.append((LITERAL, "/"))
    return _collapse(out)


def _collapse(items: list[Token]) -> list[Token]:
    """This function removes a repeated token that follows an equal repeated token.

    Two equal repeated tokens match the same paths as one token. A `**` and a `*` are
    different: `*` matches a line feed, and `**` does not.
    """
    return [
        item
        for index, item in enumerate(items)
        if item[0] not in _REPEATS or index == 0 or items[index - 1] != item
    ]


class GlobPattern:
    """This record matches full paths against one tsconfig pattern.

    A state is a set of numbers. The number 2 * i is the position before token i. The
    number 2 * i + 1 is a position in a folder name of the `**/` token i. The record keeps
    the steps between states, so the same path parts are not calculated again.
    """

    def __init__(self, items: list[Token], folder_suffix: bool) -> None:
        self._items = list(items)
        accept = {2 * len(self._items)}
        if folder_suffix:
            # A folder name also matches the files in the folder: `(?:/.*)?`.
            self._items += [(LITERAL, "/"), (ANY, "")]
            accept.add(2 * len(self._items))
        self._accept = frozenset(accept)
        self._ends = self._closure_ends()
        self._start: State = self._fill({0}, set())
        self._steps: dict[tuple[State, str], State] = {}
        self._cached = 0

    def _closure_ends(self) -> list[int]:
        """Give, for each token index, the last index that the closure reaches.

        The closure of position 2 * i is 2 * i, 2 * (i + 1), ..., 2 * end. Each repeated
        token can match no characters, thus the closure goes past it.
        """
        ends = list(range(len(self._items) + 1))
        for index in range(len(self._items) - 1, -1, -1):
            if self._items[index][0] in _REPEATS:
                ends[index] = ends[index + 1]
        return ends

    def _fill(self, starts: set[int], out: set[int]) -> State:
        """Add the closures of the token indexes in `starts` to `out`.

        The closures of two indexes overlap at their end. Each position is added one time
        only, so the cost is linear in the number of tokens.
        """
        high = 0
        for index in sorted(starts):
            end = self._ends[index]
            out.update(range(2 * max(index, high), 2 * end + 1, 2))
            high = end + 1
        return frozenset(out)

    def fullmatch(self, text: str) -> bool:
        """Tell if the full text matches the pattern."""
        state = self._start
        for char in text:
            following = self._steps.get((state, char))
            if following is None:
                following = self._step(state, char)
                if self._cached >= _CACHE_LIMIT:
                    self._steps.clear()
                    self._cached = 0
                self._steps[(state, char)] = following
                self._cached += len(following) + 1
            if not following:
                return False
            state = following
        return not state.isdisjoint(self._accept)

    def _step(self, state: State, char: str) -> State:
        out: set[int] = set()
        starts: set[int] = set()
        for number in state:
            move = self._next(number, char)
            if move is not None:
                (starts if move[0] else out).add(move[1])
        return self._fill(starts, out)

    def _next(self, number: int, char: str) -> tuple[bool, int] | None:
        """Give the move from one position: (True, i) is the closure of token index i, and
        (False, p) is the position p only.
        """
        index, in_folder = divmod(number, 2)
        if in_folder:
            return (True, index) if char == "/" else (False, number)
        if index == len(self._items):
            return None
        kind, literal = self._items[index]
        if kind == LITERAL:
            matched = char == literal
        else:
            matched = char != ("\n" if kind == ANY else "/")
        if not matched:
            return None
        if kind in (LITERAL, ONE):
            return (True, index + 1)
        return (False, number + 1) if kind == FOLDERS else (True, index)


def compile_glob(pattern: str, folder_suffix: bool) -> GlobPattern:
    """This function makes a matcher for a pattern without "/" at its start or end.

    With `folder_suffix`, the pattern also matches each path below it.
    """
    return GlobPattern(tokens(pattern), folder_suffix)
