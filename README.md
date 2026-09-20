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

Your coding agent writes faster than you read. You review the diff, you merge
it, and the picture you had of how the system fits together quietly stops
matching the system.

**systemap keeps that picture. Your agent draws the map out of your code, a
checker refuses to let it be incomplete or older than the tree, and every pull
request says what it did to the shape of the system before you merge it.** It
reads Python and only Python, and it has no dependencies.

<p align="center">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/screenshots/tour.gif" alt="the map: switching readings, clicking a component to light what it reaches, stepping a journey" width="100%">
</p>

<p align="center">
  <a href="https://0xfauzi.github.io/systemap/map/"><b>Open the live map</b></a>, which is
  systemap's map of itself.
</p>

## Start

    uv tool install systemap        # or: uv add --dev systemap
    systemap init                   # --no-ci to skip the workflow

`init` writes the configuration, a starter model, the agent's skill under
`.claude/skills/systemap/`, and a CI workflow. Then it prints the one sentence
you give your agent:

> Map this repository with systemap. Follow the systemap skill.

That is your side of it. The agent reads the facts, drafts the model, lays it
out, runs the check until every module is mapped and the layout passes, and
then goes round again looking for what it missed. When it stops, you read its
answers, correct what you disagree with, and commit `docs/map/`.

Using Claude Code? The repository is its own plugin marketplace:

    /plugin marketplace add 0xfauzi/systemap
    /plugin install systemap@systemap

Any agent that reads a skill directory and runs a command works the same way.

## Why an agent, and not a script

A map takes two kinds of knowledge. The mechanical kind is which modules
exist, what each exports, which tests import it: a script reads that out of
the syntax tree in a second and never gets it wrong. The other kind is
judgement. Which modules together make one thing a reader would point at and
name? What does the line between two parts mean?

A script has none of that, so its map is complete and meaningless. A person
has it, but rarely the patience to keep it true through every refactor. An
agent has both, once it follows a written procedure and something refuses its
output when a module is mapped by nobody or the page is older than the model.
systemap is that procedure and that checker.

## One model, several ways to read it

<p align="center">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/map/figures/structure.svg" alt="systemap's map of itself: the Structure reading, every part in its region, no edges" width="100%">
</p>

One committed model, drawn several ways. Above is Structure: every part in its
place, not one arrow. Switch and the edges arrive, for what crosses the
boundary, what moves, and who drives whom. Click a part and its neighbours
light up, each spoke carrying the verb for that direction. Step a journey and
the map walks you along it. Past forty cards, a card can hold a map of its own.

Every edge says whether the code backs it: solid where an import joins the two
ends, dashed where nothing in the facts does. A picture somebody wished were
true looks different from one the code agrees with. Three colour schemes ship,
and the header remembers the one you chose.

<p align="center">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/screenshots/warm.png" alt="the warm scheme" width="32%">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/screenshots/graphite.png" alt="the graphite scheme" width="32%">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/screenshots/paper.png" alt="the paper scheme" width="32%">
</p>

## What stops it lying

`systemap check` runs eleven rules and exits 1 naming the fix. It refuses a
module no component claims, an entry naming something the code does not
define, a route through a card it does not connect, a label that touches
another, and a page older than the model.

The check catches contradictions, not omissions, so `systemap judgement` goes
looking for those: a component claiming one module, an entry point no journey
covers, an import crossing two cards with nothing drawn between them. Each
line is acted on or answered with a reason in `systemap.toml`, so nobody is
asked the same question twice.

    systemap check && systemap judgement --strict

Six repositories have been mapped this way end to end, four of them somebody
else's, each finishing unattended with both commands clean
([docs/benchmarks.md](docs/benchmarks.md)).

## What this pull request did to the system

Git says which lines changed. `systemap delta --base main` says what changed
in the system, from the facts at both commits, one line per thing, each with
its fix:

    moved: pkg.old -> pkg.new (same content); Gateway names pkg.old in
      implemented_by: rename it in map/model.py
    added: pkg.thing, claimed by no card
    entry vanished: Gateway names entry serve, which its modules no longer define

The workflow `init` writes posts that as one comment per pull request and
keeps it updated, so review starts with what the change did to the system
rather than with 400 lines of diff. It exits 1 when something needs a
decision, so CI holds the line while you are not looking.

Your agent then acts on those lines alone instead of redrawing the map. On
three real merged pull requests that path cost 2.31, 4.39 and 2.50 dollars,
against between 3 and 26 dollars for a first map of a whole repository
([docs/benchmarks.md](docs/benchmarks.md)).

## The rest, briefly

- **It teaches while it refuses.** Under the first line of each kind, `check`,
  `judgement` and `delta` say why it matters and what to do. `--brief` turns
  that off; `systemap explain "<kind>"` prints one in full.
- **`systemap journeys`** has an agent write the walk through the system for a
  way in that no journey starts from, and checks every step against the map
  before writing it.
- **`systemap history --since "1 year ago"`** samples the tree back through
  time and says what moved in each window, with the commits that moved it.
- **`systemap plan "<task>"`** names the cards a piece of work will most
  likely change, and afterwards compares that with the cards it did change.
- **`systemap audit`** and **`triage`** ask TypeSafe's Jev model the questions
  a name-and-import checker cannot answer. They need `TYPESAFE_API_KEY`;
  `check` and `judgement` never ask, so CI stays offline unless you hand it
  the key.

Every threshold in those was measured before the feature was built, and the
features that failed their bar were recorded rather than shipped
([bench/jev](bench/jev)). `systemap --help` lists every command;
[docs/reference.md](docs/reference.md) has every option, rule and key.

## What it is not

It reads Python and only Python. It is not a call graph: the map draws the
flows the agent declared, not every call. It is not a dependency visualiser:
modules are not cards, components are. It is not a UML tool: one diagram, one
layout, and no notation beyond card, line, label and a mark per kind.

## Development

    uv sync
    uv run pytest -q
    uv run systemap check && uv run systemap judgement --strict

The workflow runs the suite, the types and the linter on Linux, macOS and
Windows with Python 3.11 and 3.13, and installs the built wheel into an empty
environment on each to run the commands against a copy of this repository's
own map.

MIT licensed.

Map something with it, and whatever gets in your way is worth an issue. Every
version so far was written from somebody's log of where they got stuck, most
of them an agent's.
