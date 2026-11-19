"""The renderer script of the atlas page: the parts of the script in their order.

The atlas page (`atlas_page`) has one script element with `SCRIPT`. It joins the scene part
(`atlas_scene`), the view part (`atlas_view`), the lines part (`atlas_lines`), the drawing
part (`atlas_draw`), the marks part (`atlas_marks`), the lit part (`atlas_lit`), the image part (`atlas_image`), the inside part (`atlas_inside`), the tree
part (`atlas_tree`), the keyboard part (`atlas_keys`), the details part (`atlas_details`), the tools part
(`atlas_tools`), the Find part (`atlas_find`),
the Sequences part and its diagram part (`atlas_sequences`), the States part
(`atlas_states`), the Focus part (`atlas_focus`), the History part (`atlas_history`) and
the input part (`atlas_input`). The parts are a fork of the
renderer of the canvas page (`page_canvas`) with the look of docs/design/atlas.md. The page
policy (`page_csp`) gets the digest of the element.
"""

from __future__ import annotations

from systemap.atlas_details import DETAILS
from systemap.atlas_draw import DRAW
from systemap.atlas_find import FIND
from systemap.atlas_focus import FOCUS
from systemap.atlas_history import HISTORY
from systemap.atlas_image import IMAGE
from systemap.atlas_input import INPUT
from systemap.atlas_inside import INSIDE
from systemap.atlas_keys import KEYS
from systemap.atlas_lines import LINES
from systemap.atlas_lit import LIT
from systemap.atlas_marks import MARKS
from systemap.atlas_scene import SCENE
from systemap.atlas_sequences import BOARD, SEQ
from systemap.atlas_states import STATES
from systemap.atlas_tools import TOOLS
from systemap.atlas_tree import TREE
from systemap.atlas_view import VIEW_PART

SCRIPT = (
    "(function(){\n'use strict';\n"
    + SCENE
    + VIEW_PART
    + LINES
    + DRAW
    + MARKS
    + LIT
    + IMAGE
    + INSIDE
    + TREE
    + KEYS
    + DETAILS
    + TOOLS
    + FIND
    + SEQ
    + BOARD
    + STATES
    + FOCUS
    + HISTORY
    + INPUT
    + "})();\n"
)

# The page embeds the script in a script element. "</" would end the element.
if "</" in SCRIPT:  # pragma: no cover - a guard for a change of the script text
    raise ValueError("The atlas script must not contain the text </.")
