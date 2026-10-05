"""The explanations for diagnostic lines give their meaning, their importance, and the
necessary action.

The diagnostic line is an identifier for exact answers. This module does not change the
identifier. `systemap explain KIND` prints the full explanation. The `--brief` option
omits the explanation rows.
"""

from __future__ import annotations

from dataclasses import dataclass

INDENT = "      "


@dataclass(frozen=True)
class Lesson:
    """An explanation gives the meaning, importance, and action for one diagnostic kind."""

    means: str
    why: str
    do: str

    def rows(self, indent: str = INDENT) -> list[str]:
        return [f"{indent}why: {self.why}", f"{indent}do:  {self.do}"]


# ---- the lines `systemap judgement` prints ----------------------------------------

JUDGEMENT = {
    "single module": Lesson(
        means="A component contains one module.",
        why=("A component for each file gives no information that the file tree does not give."),
        do=(
            "Keep the component if it has a different task. Otherwise, put the module in "
            "the component for its task."
        ),
    ),
    "possible mis-fold": Lesson(
        means=(
            "The module and its component have no same word. The other modules of the "
            "component are in different packages."
        ),
        why=(
            "A component has one task. A module with a different task can make the "
            "component description incorrect."
        ),
        do=(
            "Read the module. Put it in the component for its task, or record the "
            "reason for its component at this snapshot."
        ),
    ),
    "no sentence": Lesson(
        means="A flow connects two components, but it has no description.",
        why=("A flow without a description does not tell the reader which data moves or why."),
        do=(
            "Write a sentence about the source component. Give the artifact name and the "
            "reason that the destination component uses it."
        ),
    ),
    "thin layer": Lesson(
        means="A layer has less than two components.",
        why=(
            "A layer with one component gives little information about the connections in "
            "the system."
        ),
        do=("Add the flows for this layer, or give the reason that this layer is not necessary."),
    ),
    "entry point": Lesson(
        means="An entry point has no sequence.",
        why=(
            "An entry point starts a system operation. Without a sequence, the map does "
            "not give the steps of this operation."
        ),
        do=(
            "Write the sequence from the entry point to the result. Or give the reason "
            "that no sequence is necessary."
        ),
    ),
    "journey start": Lesson(
        means="A sequence starts at an entry point that the facts do not contain.",
        why=(
            "An incorrect entry point name prevents the map from showing which entry "
            "points have sequences."
        ),
        do=(
            "Use the entry point name from `systemap facts --entry-points`, or leave "
            "`starts` empty."
        ),
    ),
    "drafted journey": Lesson(
        means=(
            "`systemap journeys` wrote this sequence, but the sequence must have a source review."
        ),
        why=(
            "A coding agent wrote the sequence from the code. The maintainer must make "
            "sure that the sequence is correct."
        ),
        do=(
            "Compare the sequence with the code. Correct the errors. Then set "
            "`drafted=False`, or answer the line with your source review."
        ),
    ),
    "crossing import": Lesson(
        means=(
            "A module of one component imports a module of another component. No flow "
            "connects these components."
        ),
        why=(
            "The code has a connection that the map does not show. This connection can "
            "affect a change to the system."
        ),
        do=(
            "Add the flow and its description. Or put the modules in one component, or "
            "record why the import does not make a flow necessary."
        ),
    ),
    "declared flow": Lesson(
        means=("A flow has no import evidence. Its description has no specified mechanism."),
        why=("Without evidence, the reader cannot know if the flow is correct."),
        do=(
            "Find the source code. Or give the mechanism in the description and in "
            "`[flows] observed_by`. Otherwise, remove the flow."
        ),
    ),
    "flow review": Lesson(
        means="A flow has an import, a shared module, or a specified mechanism word.",
        why=(
            "This structure does not give evidence of the direction, data, or runtime "
            "behavior. Source references must agree with the source and claim."
        ),
        do=(
            "Read the source. Record the source references with correct digests. If the "
            "claim is incorrect, change the flow."
        ),
    ),
    "model sdk": Lesson(
        means="A module imports a model SDK, but its component has no model-call marker.",
        why=("The map must show model calls. These calls can have a cost, a delay, and errors."),
        do=(
            "Set the component kind to `agent` or set `calls_model`. Add the model flow, "
            "or record the applicable repository rule."
        ),
    ),
    "unknown surface": Lesson(
        means=("The TypeScript parser could not identify a module or package target."),
        why=(
            "If the facts omit an export or import, the public interface or its "
            "connections can be incorrect."
        ),
        do=(
            "Read the source excerpt. Add parser support for the syntax, or remove "
            "unrelated files from the source roots."
        ),
    ),
}

# ---- the lines `systemap delta` prints --------------------------------------------

DELTA = {
    "moved": Lesson(
        means="A module has a different path. systemap identified the module at its previous path.",
        why=("A component with the previous path no longer contains the module."),
        do=(
            "Change the module claim to the new name, or put the module in the component "
            "for its task at this snapshot."
        ),
    ),
    "added": Lesson(
        means="The head commit contains a module that the base commit does not contain.",
        why=("Without a component for the module, the map omits part of the system."),
        do=(
            "Add the module to the component for its task, or give a reason to ignore it "
            "in `[coverage]`."
        ),
    ),
    "removed": Lesson(
        means="The map contains a module claim, but the source tree no longer contains the module.",
        why=(
            "A claim for a missing module makes the component description and coverage "
            "count incorrect."
        ),
        do="Remove the module claim. If the component no longer has a task, remove the component.",
    ),
    "next to the change": Lesson(
        means=(
            "These components have a flow to or from the component with the most changed modules."
        ),
        why=(
            "A diff shows changed code. Connected components give context. In 359 pull "
            "requests, the median was 6 components and 72% included a changed component."
        ),
        do=(
            "Use this information as context. If an error occurs after the change, examine "
            "these components first."
        ),
    ),
    "entry vanished": Lesson(
        means="A component specifies an entry that its modules no longer define.",
        why=(
            "The entry tells the reader where to start. A missing entry cannot start the operation."
        ),
        do="Set the entry to a public name in the modules at this snapshot of the component.",
    ),
    "interface vanished": Lesson(
        means="A component specifies an interface that its modules no longer define.",
        why=(
            "Other components can use this interface. A missing interface makes the map incorrect."
        ),
        do=(
            "Set the interface to a public name at this snapshot, or remove the interface "
            "if the component has none."
        ),
    ),
    "new crossing import": Lesson(
        means=(
            "The change added an import across a component boundary. No flow connects "
            "these components."
        ),
        why=("The code now has a connection that the map does not show."),
        do=(
            "If the connection is correct, add the flow and its description. Otherwise, "
            "change the code or record why no flow is necessary."
        ),
    ),
    "evidence lost": Lesson(
        means="An import previously gave evidence for a flow. That import is now missing.",
        why=(
            "The flow can be missing, or it can use a different mechanism that the map "
            "does not show."
        ),
        do=(
            "Remove the flow, or give its mechanism at this snapshot in the "
            "description and in `[flows] observed_by`."
        ),
    ),
    "source review": Lesson(
        means=(
            "The modules of a component changed, or the parsed code of one of its modules changed."
        ),
        why=(
            "Imports and public signatures do not give all behavior changes. The component "
            "description and related claims can now be incorrect."
        ),
        do=(
            "Read the changed source. Correct the claims. Then record the `source_review` "
            "digest as the maintenance guide specifies."
        ),
    ),
    "source evidence lost": Lesson(
        means=(
            "The source review of a flow no longer gives evidence for its claim in this snapshot."
        ),
        why="An import can stay the same when the flow direction or data changes.",
        do="Read the changed source. Correct the flow claims. Then record new source references.",
    ),
    "move candidate": Lesson(
        means=(
            "A removed module and an added module have some of the same public names. "
            "Their identities are not known."
        ),
        why="Names such as `run` can occur in unrelated modules.",
        do="Compare the source. Accept a module move only if the module task stayed the same.",
    ),
    "structural evidence lost": Lesson(
        means="An import, shared module, or specified mechanism for a flow is now missing.",
        why="The claim can still be correct, but its previous structure no longer gives evidence.",
        do="Read the changed source. Then change or remove the flow claim.",
    ),
}

# ---- the lines `systemap audit` prints, from Jev's answers ------------------------

AUDIT = {
    "jev mis-fold": Lesson(
        means="Jev gives a different component for the task of this module.",
        why=(
            "The `possible mis-fold` rule uses names only. Jev reads the code to find "
            "modules in incorrect components."
        ),
        do=(
            "Compare the module with both components. Move it, or record the reason "
            "for its component at this snapshot."
        ),
    ),
    "jev owner": Lesson(
        means="No component contains this module. Jev gives a possible component.",
        why="Without a component for the module, the map omits part of the system.",
        do=(
            "Add the module to the specified component or one of the three nearest "
            "components. Or give a reason to ignore it."
        ),
    ),
    "jev sentence": Lesson(
        means="Jev gives a possible error in the component description.",
        why=(
            "An incorrect component description gives the reader incorrect information "
            "about the modules."
        ),
        do=(
            "Read the modules again. Correct the description, or record the reason that it "
            "is still correct."
        ),
    ),
    "jev flow": Lesson(
        means=("Jev gives a possible difference between the code and the flow claim."),
        why=(
            "An incorrect flow tells the reader that a connection is available when the "
            "code has no such connection."
        ),
        do=(
            "Find the call for the flow. Jev has no instance-call evidence. If the flow "
            "uses an instance call, record that reason."
        ),
    ),
    "jev governs": Lesson(
        means=(
            "Jev gives a component that a rule can affect. The rule does not name that component."
        ),
        why=(
            "A missing component in the rule scope can let a change cause an error without "
            "a notice."
        ),
        do=(
            "If a change to the component can make the rule incorrect, add the component "
            "to `governs`. Otherwise, record the reason."
        ),
    ),
}

# ---- what `systemap check` refuses -------------------------------------------------

CHECK = {
    "coverage": Lesson(
        means="A module has no component, or it has more than one component.",
        why=(
            "Coverage shows which modules the map contains. Multiple claims for one module "
            "make the component sizes incorrect."
        ),
        do=(
            "Add each module to one component, or give a reason to ignore it in "
            "`[coverage]` in `systemap.toml`."
        ),
    ),
    "map layout": Lesson(
        means="A component, label, region, or route does not obey a map rule.",
        why=(
            "Small text or incorrect routes can give the reader incorrect information "
            "about the system."
        ),
        do="After a component change, use `systemap place`. Then correct the reported errors.",
    ),
    "map routes": Lesson(
        means="An edge crosses an unrelated component or region.",
        why=("An edge across an unrelated component can show a connection that does not occur."),
        do=(
            "Move a component to give the route sufficient space, or use `systemap place "
            "--all` to set the positions again."
        ),
    ),
    "nesting": Lesson(
        means="A map inside a component does not contain the same modules as that component.",
        why=(
            "The nested map must give the internal structure of its component. Different "
            "module sets give different descriptions of the same code."
        ),
        do=(
            "Give the nested map the same module set as the component. Use the connected "
            "parent components as its actors."
        ),
    ),
    "entry": Lesson(
        means="A component specifies an entry that its modules do not define.",
        why="The entry tells the reader where to start. The entry must occur in the code.",
        do="Use a public name in one of the modules of the component.",
    ),
    "interface": Lesson(
        means="A component specifies an interface that its modules do not define.",
        why="Other components use the interface. The interface must occur in the code.",
        do="Use a public interface in the modules at this snapshot of the component.",
    ),
    "stale": Lesson(
        means="The page or facts differ from the model or source tree.",
        why="A page without the latest changes can give an incorrect description of the code.",
        do="Use `systemap refresh`. Then commit the output directory.",
    ),
    "source inventory unresolved": Lesson(
        means="The parser could not read all of a source file or test file.",
        why="A missing file can omit ownership, imports, entries, or tests from the facts.",
        do="Use a compatible parser, or correct the source. Then use `systemap refresh`.",
    ),
    "extraction inputs changed": Lesson(
        means="The configuration or parser inputs changed after systemap wrote the facts.",
        why="The same source can now give a different module graph.",
        do="Use `systemap refresh`. Then read the changed facts.",
    ),
    "entry point targets changed": Lesson(
        means="An entry point name now has a different source target.",
        why="A sequence can now start at code that differs from the recorded target.",
        do="Use `systemap refresh`. Then examine entry point coverage.",
    ),
    "derived facts changed": Lesson(
        means="Imports or other extracted facts changed for a module.",
        why="A source hash does not show which map claims changed.",
        do="Use `systemap refresh`. Then examine the related components and flows.",
    ),
}

LESSONS: dict[str, Lesson] = {**JUDGEMENT, **DELTA, **AUDIT, **CHECK}


def lesson(kind: str) -> Lesson | None:
    return LESSONS.get(kind)


def rows(kind: str, indent: str = INDENT) -> list[str]:
    """This function gives the `why` and `do` rows for a known diagnostic kind."""
    found = LESSONS.get(kind)
    return found.rows(indent) if found else []


def whole(kind: str) -> list[str]:
    """This function gives the full explanation for `systemap explain`."""
    found = LESSONS.get(kind)
    if found is None:
        known = ", ".join(sorted(LESSONS))
        return [f"explain: there is no line kind called {kind!r}.", f"  the kinds are: {known}"]
    return [
        f"{kind}",
        f"  meaning: {found.means}",
        f"  importance: {found.why}",
        f"  action: {found.do}",
    ]
