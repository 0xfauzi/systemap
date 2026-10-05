# ruff: noqa: E501
"""The sequences in the systemap map.

`map/model.py` imports JOURNEYS from this file. Each step gives active
components, measurement components, one flow and an explanation.
`systemap check` rejects a step whose flow is missing from the model."""

from __future__ import annotations

from systemap import Journey, Step  # type: ignore[import-not-found, unused-ignore]

JOURNEYS = (
    Journey(
        id="over-time",
        label="Read the change history",
        starts="systemap history (subcommand)",
        covers=('["subcommand","systemap.cli","systemap","history"]',),
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The user runs systemap history with a start date and a sample interval.",
            ),
            Step(
                acts=("ChangeDetector",),
                measures=(),
                edge=("CLI", "ChangeDetector"),
                say="The change detector selects one commit per interval from git, in date order. Each interval has the same weight.",
            ),
            Step(
                acts=("FactsExtractor",),
                measures=(),
                edge=("FactsExtractor", "ChangeDetector"),
                say="The extractor reads facts from each git revision. It does not read the working tree. The cache stores facts in .systemap/facts.",
            ),
            Step(
                acts=("ChangeDetector",),
                measures=("Model",),
                edge=("Model", "ChangeDetector"),
                say="The comparison uses the components in the model for all samples. Each component has module claims for its function.",
            ),
            Step(
                acts=("ChangeDetector",),
                measures=(),
                edge=("ChangeDetector", "Agent"),
                say="The report shows the largest changes first: component size, imports between components and commits that added modules.",
            ),
        ),
    ),
    Journey(
        id="plan-then-check",
        label="Compare a plan with source changes",
        starts="plan (subcommand in systemap.jev_cli)",
        covers=('["subcommand","systemap.jev_cli","","plan"]',),
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="Before source changes, the agent or maintainer runs systemap plan with a task description.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=(),
                edge=("Model", "SecondOpinion"),
                say="The plan projection reads component functions from the model. Its question uses the model component names.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=(),
                edge=("SecondOpinion", "TypeSafe"),
                say="Jev receives a question about the probability of a change in each component for this task.",
            ),
            Step(
                acts=("TypeSafe",),
                measures=(),
                edge=("TypeSafe", "SecondOpinion"),
                say="Jev gives a weight for each component. The projection selects components at or above the measured threshold.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=(),
                edge=("SecondOpinion", "Agent"),
                say="The report shows flows, sequences and rules for each selected component. The command writes the projection in .systemap/plans.",
            ),
            Step(
                acts=("ChangeDetector",),
                measures=("SecondOpinion",),
                edge=("FactsExtractor", "ChangeDetector"),
                say="After source changes, systemap plan --check compares the initial facts with the new facts. It identifies changed components outside the plan.",
            ),
        ),
    ),
    Journey(
        id="second-opinion",
        label="Get an audit or issue assessment",
        covers=(
            '["subcommand","systemap.jev_cli","","audit"]',
            '["subcommand","systemap.jev_cli","","triage"]',
        ),
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="With a Jev key and no open judgement findings, the agent runs systemap audit. For an issue, the maintainer runs systemap triage.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=(),
                edge=("Model", "SecondOpinion"),
                say="The second-opinion process reads components, explanations, flows, invariants and facts. It makes a different question for each claim.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=(),
                edge=("SecondOpinion", "TypeSafe"),
                say="The command sends questions without cached answers to Jev through HTTPS. audit --dry-run shows the data before transmission.",
            ),
            Step(
                acts=("TypeSafe",),
                measures=(),
                edge=("TypeSafe", "SecondOpinion"),
                say="Jev gives a probability or choice. The cache stores each answer by model release.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=("Agent",),
                edge=("SecondOpinion", "Agent"),
                say="The report shows Jev findings that are different from map claims, or three components with the largest probabilities for triage. The agent corrects or answers findings.",
            ),
        ),
    ),
    Journey(
        id="first-map",
        label="Make the initial map",
        covers=(
            '["console_script","systemap.cli","main","systemap"]',
            '["subcommand","systemap.cli","systemap","init"]',
            '["subcommand","systemap.cli","systemap","extract"]',
            '["subcommand","systemap.cli","systemap","suggest"]',
            '["subcommand","systemap.cli","systemap","place"]',
            '["subcommand","systemap.cli","systemap","check"]',
            '["subcommand","systemap.cli","systemap","skill"]',
        ),
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent runs systemap init. The command writes the configuration, initial model and workflow.",
            ),
            Step(
                acts=("CLI",),
                measures=(),
                edge=("CLI", "Skill"),
                say="init installs the skill directory in the project. systemap skill installs it again on request.",
            ),
            Step(
                acts=("Skill",),
                measures=(),
                edge=("Skill", "Agent"),
                say="The skill gives the procedure: extraction, model draft, check, judgement, render and second examination.",
            ),
            Step(
                acts=("FactsExtractor",),
                measures=(),
                edge=("CLI", "FactsExtractor"),
                say="systemap extract reads modules, public names, imports and entry points from the source tree.",
            ),
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "Model"),
                say="The agent runs systemap suggest for initial module groups. Then the agent writes components, flows, explanations and sequences in map/model.py, without positions.",
            ),
            Step(
                acts=("Placer",),
                measures=(),
                edge=("Placer", "Model"),
                say="systemap place sets regions and component cards on a grid. It keeps spaces between regions and writes positions in the model file.",
            ),
            Step(
                acts=("Check",),
                measures=("Check",),
                edge=("Check", "Agent"),
                say="systemap check gives each error and necessary action. The agent makes changes until module coverage is N/N and layout checks give no errors.",
            ),
        ),
    ),
    Journey(
        id="second-pass",
        label="Examine the model and refresh the map",
        covers=(
            '["subcommand","systemap.cli","systemap","judgement"]',
            '["subcommand","systemap.cli","systemap","refresh"]',
            '["subcommand","systemap.cli","systemap","describe"]',
            '["subcommand","systemap.cli","systemap","serve"]',
        ),
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
                say="Judgement examines fact imports for connections without model flows. It finds entry points without sequences.",
            ),
            Step(
                acts=("Judgement",),
                measures=("Judgement",),
                edge=("Judgement", "Agent"),
                say="Findings identify imports between components, entry points without sequence coverage and layers with few flows. The agent corrects or answers each finding.",
            ),
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "Model"),
                say="The agent adds missing flows and corrects module groups. The agent does the check again. If a full examination finds no necessary changes, stop.",
            ),
            Step(
                acts=("Page",),
                measures=(),
                edge=("CLI", "Page"),
                say="systemap refresh renders the page and figures. systemap describe gives diagram measurements. systemap serve opens the page for examination.",
            ),
            Step(
                acts=("Judgement",),
                measures=("Maintainer",),
                edge=("Judgement", "Maintainer"),
                say="The agent records judgement answers in systemap.toml. judgement --strict must give exit code 0. The maintainer examines the answers and writes docs/map in a Git commit.",
            ),
        ),
    ),
    Journey(
        id="refactor",
        label="Update the map after a module move",
        covers=('["subcommand","systemap.cli","systemap","delta"]',),
        steps=(
            Step(
                acts=("CI",),
                measures=(),
                edge=("CI", "CLI"),
                say="A pull request moves a module. The workflow runs systemap delta --base with the base branch. It posts a map-change report.",
            ),
            Step(
                acts=("ChangeDetector",),
                measures=(),
                edge=("CLI", "ChangeDetector"),
                say="The detector reads facts from both git revisions. It identifies old module claims and the renames that correct them.",
            ),
            Step(
                acts=("Check",),
                measures=("CI",),
                edge=("Check", "CI"),
                say="The CI job rejects the change if a finding has no decision. The comment gives necessary actions for the map.",
            ),
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent examines delta findings and changed component source. The agent records review digests. The agent runs refresh, check and judgement --strict, then writes docs/map in a Git commit.",
            ),
            Step(
                acts=("Page",),
                measures=("Maintainer",),
                edge=("Page", "Maintainer"),
                say="The maintainer reads the page. The changed component shows the new source location.",
            ),
        ),
    ),
    Journey(
        id="read-facts",
        label="Read stored source facts",
        covers=('["subcommand","systemap.cli","systemap","facts"]',),
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent runs systemap facts with --module or --entry-points. The command reads stored facts and prints the selected record.",
            ),
        ),
    ),
    Journey(
        id="render-page",
        label="Render the map page",
        covers=('["subcommand","systemap.cli","systemap","render"]',),
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent runs systemap render to make the page from stored facts and the model.",
            ),
            Step(
                acts=("Page",),
                measures=(),
                edge=("CLI", "Page"),
                say="The command gives stored facts, the model and the selected theme to the page generator.",
            ),
            Step(
                acts=("Schematic",),
                measures=(),
                edge=("Schematic", "Page"),
                say="The page contains the schematic SVG and detail data for its controls.",
            ),
            Step(
                acts=("Maintainer",),
                measures=(),
                edge=("Page", "Maintainer"),
                say="The maintainer opens the page to examine components, flows and sequences.",
            ),
        ),
    ),
    Journey(
        id="draw-figure",
        label="Make a map figure",
        covers=('["subcommand","systemap.cli","systemap","figure"]',),
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent runs systemap figure. The command can use a selected mode and output path.",
            ),
            Step(
                acts=("Figures",),
                measures=(),
                edge=("CLI", "Figures"),
                say="The command tells the figure generator to make one diagram from stored facts and the model.",
            ),
            Step(
                acts=("Schematic",),
                measures=(),
                edge=("Schematic", "Figures"),
                say="The figure uses the schematic SVG, alone or in an HTML figure element.",
            ),
        ),
    ),
    Journey(
        id="explain-line",
        label="Read a finding explanation",
        covers=('["subcommand","systemap.cli","systemap","explain"]',),
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent runs systemap explain with a finding kind. The command gives the explanation, cause and necessary action.",
            ),
        ),
    ),
    Journey(
        id="write-journey",
        label="Write a sequence for an entry point",
        covers=('["subcommand","systemap.jev_cli","","journeys"]',),
        steps=(
            Step(
                acts=("Agent",),
                measures=(),
                edge=("Agent", "CLI"),
                say="The agent runs systemap journeys for an entry point without a sequence with source review.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=(),
                edge=("CLI", "SecondOpinion"),
                say="The command groups entry points without sequences by component. It tells the configured coding agent to read the source for one group.",
            ),
            Step(
                acts=("SecondOpinion",),
                measures=(),
                edge=("SecondOpinion", "Agent"),
                say="The command validates the sequence draft against model components and flows. Then it writes the draft for the maintainer to examine.",
            ),
        ),
    ),
)
