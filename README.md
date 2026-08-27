<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/0xfauzi/systemap/main/assets/hero.svg">
    <source media="(prefers-color-scheme: light)" srcset="https://raw.githubusercontent.com/0xfauzi/systemap/main/assets/hero-light.svg">
    <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/assets/hero.svg" alt="systemap: the map your coding agent draws of your system" width="100%">
  </picture>
</p>

<p align="center">
  <a href="https://pypi.org/project/systemap/"><img alt="the version on PyPI" src="https://img.shields.io/pypi/v/systemap?label=PyPI&color=e0a458&labelColor=121417"></a>
  <a href="https://pypi.org/project/systemap/"><img alt="the Python versions it runs on" src="https://img.shields.io/pypi/pyversions/systemap?color=b3b1aa&labelColor=121417"></a>
  <a href="LICENSE"><img alt="the licence" src="https://img.shields.io/pypi/l/systemap?color=8fbfa6&labelColor=121417"></a>
  <img alt="how many dependencies it has" src="https://img.shields.io/badge/dependencies-none-b3b1aa?labelColor=121417">
</p>

If you have a coding agent working in your repository, you have probably
noticed the thing nobody warns you about. It writes faster than you read. You
review the diff in front of you, you merge it, and somewhere along the way the
picture you had of how the system fits together stopped matching the system.

**systemap keeps that picture. Your agent draws the map out of your code, a
checker refuses to let it be incomplete or older than the tree, and every pull
request says what it did to the shape of the system before you merge it.** The
map lives beside the code, so seeing what your agents have built is one page
rather than an afternoon of reading. It is not an import graph with a language
model on top: an import graph knows that one module imports another, and not
that three of them together are the Router, that the Router owns one job, or
that a journey is meant to cross it in a particular order. It reads Python and
only Python.

<p align="center">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/screenshots/tour.gif" alt="the map: switching readings, clicking a component to light what it reaches, stepping a journey" width="100%">
</p>

<p align="center">
  <a href="https://0xfauzi.github.io/systemap/map/"><b>Open the live map</b></a>, which is
  systemap's map of itself, drawn by the command you are about to run.
</p>

## Why the agent draws it

You could draw this yourself. The reason not to is the same reason the picture
went stale: a map takes two kinds of knowledge, and they do not come from the
same place.

The first is mechanical: which modules exist, what each one exports, which
tests import it, where a run starts. A script reads that out of the syntax tree
in a second and never gets it wrong.

The second is judgement. Which modules together make one thing a reader would
point at and name? What does the line between two parts actually mean? Which
question does a reading answer? No script has that, and the person who does
rarely has the patience to keep it true through every refactor. So you end up
with one of two maps: a script's, which is complete and meaningless because a
module is not a part, or a person's, which is meaningful and drifting, because
nothing announces that a part moved.

An agent has both kinds, once two things are true. It follows a written
procedure, so the same judgement is applied the same way every time. And
something refuses its output when a module is mapped by nobody, when a route
crosses a card it does not connect, or when the page is older than the model.
systemap is that procedure and that checker. The agent does the work, and hands
you back a short list of the calls it had to make, each with its answer.

## Start

    uv tool install systemap        # or: uv add --dev systemap
    systemap init                   # --no-ci to skip the workflow

`init` writes the configuration, an empty starter model, the agent's skill
under `.claude/skills/systemap/`, and a CI workflow. Then it prints the one
sentence you give your agent:

> Map this repository with systemap. Follow the systemap skill.

That is the whole of your side. The agent reads the facts, drafts the model,
lays it out, runs the check until every module is mapped and the layout passes,
renders, and then goes round again looking for what it missed. When it stops,
you read its answers, correct what you disagree with, commit `docs/map/`, and
turn on GitHub Pages from the `docs/` directory.

Using Claude Code? The repository is also a plugin and its own marketplace, so
you can skip `init` for the skill:

    /plugin marketplace add 0xfauzi/systemap
    /plugin install systemap@systemap

Any agent that reads a skill directory and runs a command works the same way.
The skill is plain text in the Agent Skills format, with nothing
vendor-specific in it.

## What this pull request did to the system

Git tells you what changed in the code. systemap tells you what changed in the
system.

Reading a diff tells you which lines changed. It does not tell you that a
module moved out of the part that owned it, that a new import now crosses two
components with nothing between them on the map, or that the entry point a card
names has quietly gone.

`systemap delta --base main` reads the facts at both commits out of git and
says exactly that, in the map's own terms, one line per thing, each with its
fix:

    moved: pkg.old -> pkg.new (same content); Gateway names pkg.old in
      implemented_by: rename it in map/model.py
    added: pkg.thing, claimed by no card
    entry vanished: Gateway names entry serve, which its modules no longer define
    evidence lost: Emitter -> Contracts (slide tree) was observed at the base
      and nothing backs it now

The workflow `init` writes posts that report as one comment on every pull
request and keeps it updated as you push, so the review you do on your agent's
work starts with what the change did to the system rather than with 400 lines
of diff. It exits 0 when nothing needs a person and 1 when something does, so
CI can hold the line while you are not looking.

Then your agent acts on those lines alone rather than redrawing the map.
Measured on three real merged pull requests, that path cost 2.31, 4.39 and 2.50
dollars, against between 14 and 26 dollars for a first map of a whole
repository. Every run, with the model that produced it, is in
[docs/benchmarks.md](docs/benchmarks.md).

## One model, several ways to read it

<p align="center">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/map/figures/structure.svg" alt="systemap's map of itself: the Structure reading, every part in its region, no edges" width="100%">
</p>

One committed model, drawn several ways, which is how you look at a system
rather than at a file. The one above is Structure, every part in its place and
not one arrow. Switch, and the edges arrive: System
context draws what crosses the boundary, Data flow what moves, Control flow who
drives whom. A repository with agents in it gets three more, for the agents,
what enters their context, and what they can call.

Click a component and its neighbours light up on the reading you are in, each
spoke carrying the verb for that direction, with one sentence saying what the
part you clicked is to it. Step a journey and the map walks you along it one
edge at a time. Past forty cards, a card can hold a map of its own, which opens
in place with a way back.

Every edge also says whether the code backs it. Where an import joins the two
ends the line is solid, and where nothing in the facts does the line is dashed
and the panel says so, so a picture somebody wished were true looks different
from one the code agrees with.

Three colour schemes ship, and the picker in the header remembers the one you
chose.

<p align="center">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/screenshots/warm.png" alt="the warm scheme" width="32%">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/screenshots/graphite.png" alt="the graphite scheme" width="32%">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/screenshots/paper.png" alt="the paper scheme" width="32%">
</p>

## What stops it lying

`systemap check` runs eleven rules and exits 1 on the first failure, naming the
fix. It refuses a module no component claims, an entry or an interface line
naming something the code does not define, a route through a card it does not
connect, a label that touches another, text under 11 px, a map inside a card
that claims the wrong modules, and a page older than the model. The full table
is in [docs/reference.md](docs/reference.md).

The check catches contradictions. It cannot catch omissions, so
`systemap judgement` goes looking for those: a component claiming one module, a
module folded into a part it shares no name with, an entry point no journey
covers, an import crossing two cards with no edge between them. Each line is
either acted on or answered with a reason in `systemap.toml`, so the answers
live in the repository and nobody is asked the same question twice.

An answer can cover a family rather than a line, which is what keeps the list
short on a large map: `crossing_into = "Ledger"` answers every import into that
card at once. It also means the next import into that card arrives without a
question, here and in a delta. So answer a family when the reason is about the
card, and a line when it is about the pair.

`systemap delta` asks these same questions of one change rather than of the
whole map, which is why a pull request's comment carries what that change
introduced instead of everything still open.

    systemap check && systemap judgement --strict

Six repositories have been mapped this way end to end, four of them written by
somebody else, each finishing unattended with both commands clean. The rows are
in [docs/benchmarks.md](docs/benchmarks.md).

## Commands

| command | what it does |
|---|---|
| `systemap init` | the configuration, a starter model, the skill, a workflow |
| `systemap extract` | read the facts out of the tree |
| `systemap facts` | read those facts back, one view at a time |
| `systemap place` | a position for every card, and the region order that draws best |
| `systemap check` | every rule, with the fix named |
| `systemap judgement` | what the check cannot catch: the second-pass list |
| `systemap suggest` | a first grouping to argue with, from the facts alone |
| `systemap refresh` | extract, check, render, and every configured figure |
| `systemap describe` | what a look at the picture would tell an agent that cannot look |
| `systemap delta` | what a change did to the map |
| `systemap figure` | one figure: a reading, a map inside a card, a plan's reach, a change |
| `systemap serve` | serve the page on the loopback address |
| `systemap skill` | reinstall the skill directory |

Every option and every configuration key is in
[docs/reference.md](docs/reference.md).

## What it is not

It reads Python and only Python. No other language is planned, so if your
system is mostly TypeScript, this is not your tool.

It is not a call graph, because the facts hold imports and public surfaces
while the map draws the flows the agent declared rather than every call. It is
not a dependency visualiser, because modules are not cards and components are.
It is not a UML tool, since there is one diagram, one fixed layout, and no
notation beyond card, line, label and a mark per kind.

## Development

    uv sync
    uv run pytest -q
    uv run mypy src --strict
    uv run ruff check .
    uv run systemap check              # this repository's own map must stay current
    uv run systemap judgement --strict

The workflow runs the suite, the types and the linter on Linux, macOS and
Windows with Python 3.11 and 3.13, installs the built wheel into an empty
virtual environment on each of those six and runs `init`, `extract`,
`refresh`, `check` and `judgement` against a copy of this repository's map,
and installs the plugin from the checkout with the Claude Code CLI.
[docs/reference.md](docs/reference.md) has the rest, including how the skill's
two copies are kept identical.

Releases: push a tag that names the version. `.github/workflows/workflow.yml`
builds the package and uploads it through PyPI's trusted publishing, where
GitHub proves the build came from this repository and no long-lived token
exists to be stolen. `scripts/publish.sh` is the manual path for a release
made from a laptop, taking the token from `UV_PUBLISH_TOKEN` or, on macOS,
from the login keychain.

MIT licensed.

Map something with it, and whatever gets in your way is worth an issue. Every
version so far was written from somebody's log of where they got stuck, most of
them an agent's.
