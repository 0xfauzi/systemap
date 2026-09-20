# ruff: noqa: E501
"""The journeys of systemap's own map: the walks a reader takes through it.

They live beside the model because the model file is long enough already;
`map/model.py` imports JOURNEYS from here. A step names what acts, what
measures, the flow it traces, and one sentence, and `systemap check` refuses
a step that traces a flow the model does not draw.
"""

from __future__ import annotations

from systemap import Journey, Step  # type: ignore[import-not-found, unused-ignore]

JOURNEYS = (
    Journey(
        id="over-time",
        label="A year of the system: what moved, and what wrote it",
        starts="systemap history (subcommand)",
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="Somebody asks what the last year did to the system: systemap history, since a date, one sample every so many days.",
            ),
            Step(
                acts=("ChangeDetector",),
                measures=(),
                edge=("CLI", "ChangeDetector"),
                say="The change detector picks one commit per window out of git, oldest first, so a busy fortnight and a quiet one weigh the same.",
            ),
            Step(
                acts=("FactsExtractor",),
                measures=(),
                edge=("FactsExtractor", "ChangeDetector"),
                say="The facts at each commit are extracted from the tree git holds, never from the working copy, and kept under .systemap/facts so the second run is quick.",
            ),
            Step(
                acts=("ChangeDetector",),
                measures=("Model",),
                edge=("Model", "ChangeDetector"),
                say="Every sample is read in today's cards, so a module that moved still counts as the card whose job it does.",
            ),
            Step(
                acts=("ChangeDetector",),
                measures=(),
                edge=("ChangeDetector", "Agent"),
                say="The largest windows are printed first: the cards that grew, the imports that began crossing a boundary, and the commits that wrote the modules which appeared.",
            ),
        ),
    ),
    Journey(
        id="plan-then-check",
        label="A plan: the cards the work will touch, then what it actually touched",
        starts="plan (subcommand in systemap.jev_cli)",
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="Before the work, the agent or the maintainer runs systemap plan with the task in plain words.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=(),
                edge=("Model", "SecondOpinion"),
                say="The projection reads every card's purpose out of the model, so the question is asked in the map's own vocabulary.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=(),
                edge=("SecondOpinion", "TypeSafe"),
                say="One question goes to Jev: which component will this work most likely have to change?",
            ),
            Step(
                acts=("TypeSafe",),
                measures=(),
                edge=("TypeSafe", "SecondOpinion"),
                say="Jev answers with a weight for every card, and the cards above the measured cut are the projection.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=(),
                edge=("SecondOpinion", "Agent"),
                say="Around each card named, the map prints the flows, walks and rules it sits in, and the projection is written under .systemap/plans.",
            ),
            Step(
                acts=("ChangeDetector",),
                measures=("SecondOpinion",),
                edge=("FactsExtractor", "ChangeDetector"),
                say="After the work, systemap plan --check reads the facts where the work started and the facts now, and names every card that changed outside the plan.",
            ),
        ),
    ),
    Journey(
        id="second-opinion",
        label="A second opinion: systemap audit, and triage for an issue",
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="With a key set and the judgement clean, the agent runs systemap audit; a maintainer with an issue in hand runs systemap triage.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=(),
                edge=("Model", "SecondOpinion"),
                say="The second opinion reads the cards, sentences, flows and invariants, and the facts behind them, into one narrow question each.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=(),
                edge=("SecondOpinion", "TypeSafe"),
                say="Questions the cache cannot answer go to Jev over HTTPS; audit --dry-run says what would leave the machine first.",
            ),
            Step(
                acts=("TypeSafe",),
                measures=(),
                edge=("TypeSafe", "SecondOpinion"),
                say="Jev answers each with a probability or a choice, and every answer is cached by the model's release.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=("Agent",),
                edge=("SecondOpinion", "Agent"),
                say="A jev line where the answer disagrees with the map, or triage's three likeliest cards; the agent acts on a line or answers it under [judgement].",
            ),
        ),
    ),
    Journey(
        id="first-map",
        label="The first map: systemap init, extract, a draft, check",
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent runs systemap init: configuration, starter model, the workflow.",
            ),
            Step(
                acts=("CLI",),
                measures=(),
                edge=("CLI", "Skill"),
                say="init installs the skill directory beside the project; systemap skill reinstalls it later.",
            ),
            Step(
                acts=("Skill",),
                measures=(),
                edge=("Skill", "Agent"),
                say="The skill gives the agent the loop: extract, draft, check, judgement, render, second pass.",
            ),
            Step(
                acts=("FactsExtractor",),
                measures=(),
                edge=("CLI", "FactsExtractor"),
                say="systemap extract reads every module, its surface, its imports and the entry points out of the tree.",
            ),
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "Model"),
                say="The agent runs systemap suggest for a first grouping to argue with, then writes map/model.py: components, flows, one sentence per edge, a journey per entry point, and no positions.",
            ),
            Step(
                acts=("Placer",),
                measures=(),
                edge=("Placer", "Model"),
                say="systemap place lays the regions out on a grid with corridors between them, puts every card on it, and writes the positions into the file.",
            ),
            Step(
                acts=("Check",),
                measures=("Check",),
                edge=("Check", "Agent"),
                say="systemap check names each failure and its fix; the agent edits until coverage is N/N and the layout is clean.",
            ),
        ),
    ),
    Journey(
        id="second-pass",
        label="The second pass: judgement, then refresh",
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent runs systemap judgement.",
            ),
            Step(
                acts=("Judgement",),
                measures=(),
                edge=("FactsExtractor", "Judgement"),
                say="The judgement walks the imports in the facts for edges the model lacks, and the entry points for journeys it lacks.",
            ),
            Step(
                acts=("Judgement",),
                measures=("Judgement",),
                edge=("Judgement", "Agent"),
                say="One line per crossing import, per entry point without a journey, per thin layer: the agent changes the model or answers the line.",
            ),
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "Model"),
                say="The agent adds the missed edges, regroups what was grouped by directory, and reruns check; a full pass that changes nothing is the stop.",
            ),
            Step(
                acts=("Page",),
                measures=(),
                edge=("CLI", "Page"),
                say="systemap refresh renders the page and every configured figure; systemap describe says what the picture shows, and systemap serve opens the page for anyone who can look.",
            ),
            Step(
                acts=("Judgement",),
                measures=("Maintainer",),
                edge=("Judgement", "Maintainer"),
                say="The agent answers the remaining judgement lines in systemap.toml, under [judgement] answered, singly or by family; judgement --strict exits 0, and the maintainer reads the answers and commits docs/map.",
            ),
        ),
    ),
    Journey(
        id="refactor",
        label="A refactor moves a module: the maintenance path",
        steps=(
            Step(
                acts=("CI",),
                measures=(),
                edge=("CI", "CLI"),
                say="A pull request moves a module; the workflow runs systemap delta --base against the base branch and posts what the change did to the map as one comment.",
            ),
            Step(
                acts=("ChangeDetector",),
                measures=(),
                edge=("CLI", "ChangeDetector"),
                say="The detector reads the facts at both commits out of git, never from the working copy, and names the card that still names the old path, with the rename that fixes it.",
            ),
            Step(
                acts=("Check",),
                measures=("CI",),
                edge=("Check", "CI"),
                say="The job fails while a line needs a decision; the comment names each fix, so the map is maintained in the pull request that changed the code.",
            ),
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent follows the maintenance path: acts on the delta's lines alone, never redrawing the map, then runs refresh, check and judgement --strict, and commits docs/map.",
            ),
            Step(
                acts=("Page",),
                measures=("Maintainer",),
                edge=("Page", "Maintainer"),
                say="The maintainer reads the page: the moved part is where the code now says it is.",
            ),
        ),
    ),
)
