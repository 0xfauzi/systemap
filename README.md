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

Your coding agent writes code faster than you can read it. You review the
diff, you merge, and one day you notice you are no longer sure how the pieces
of your own Python or TypeScript project fit together.

**systemap gives you one page that shows how they fit.** Your agent draws it
from your code. A checker then refuses to let that page go out of date, and
every pull request tells you which parts and connections it changed before
you merge it.

This page defines the three words the map uses, then shows how to get one,
then shows what stops it going out of date. The words come first because
nothing else here reads without them.

<p align="center">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/screenshots/tour.gif" alt="the map: switching between views, clicking a card to highlight what it connects to, walking a journey step by step" width="100%">
</p>

<p align="center">
  <a href="https://0xfauzi.github.io/systemap/map/"><b>Open the live map</b></a>, which is
  systemap's map of itself.
</p>

## What is a card, a line and a journey?

**A card is one part of your system.** A few modules that together do one job
you would name out loud: the part that reads the code, the part that sends
mail, the part that talks to the database. Not a file and not a folder. A job.

**A line between two cards means something travels between them**, and the
label says what: a request, a recipe, a file on disk.

**A journey is one trip through the system**, step by step. A request arrives
here, is checked there, is written down over there. The page shows one step
at a time.

That is the whole notation. No other symbols to learn.

<p align="center">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/map/figures/structure.svg" alt="systemap's map of itself: every part in its place, no lines" width="100%">
</p>

The picture above is systemap's own map with the lines hidden, so you can see
the parts and how they group. Turn the lines on and you can ask one question
at a time: what crosses the boundary of the system, what data moves, who
calls whom. Click a card and the page highlights only the cards it connects
to, each one labelled with what it does for that card.

The picture tells you one more thing no hand-drawn diagram can. A solid line
means an import in your code really joins those two parts. A dashed line
means no import joins them, so the line is a claim the code does not
support. You can see which is which without reading any code, and so can
your reviewer.

<p align="center">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/screenshots/warm.png" alt="the warm scheme" width="32%">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/screenshots/graphite.png" alt="the graphite scheme" width="32%">
  <img src="https://raw.githubusercontent.com/0xfauzi/systemap/main/docs/screenshots/paper.png" alt="the paper scheme" width="32%">
</p>

## How do you start?

    uv tool install systemap        # or: uv add --dev systemap
    systemap init                   # --no-ci to skip the workflow

For a TypeScript repository, install the parser extra:

    uv tool install 'systemap[typescript]'

The TypeScript adapter reads `.ts` and `.tsx` modules, named and default
exports, local re-exports, imports, and package `bin` and `exports` entries.
It reads JSONC `tsconfig.json` files and inherited path aliases. `outDir` and
`rootDir` map compiled package entries back to source files. A path in an
inherited config that starts with `${configDir}` means the folder of your own
`tsconfig.json`, as it does for `tsc`. Common test names
are recognized by extraction and change analysis; add repository-specific
globs with `test_patterns = ["**/*.check.ts"]`. If no emit directories are
configured, a `dist/`, `distribution/`, `build/` or `lib/` target maps to a
unique matching file under `src/` or `source/` when one exists. If TypeScript
syntax cannot be parsed or a package target cannot be mapped, the facts keep
an explicit unknown. `systemap check` reports unknowns without failing; `systemap
judgement --strict` requires each one to be fixed or answered. A missing npm
package named by `tsconfig.json` `extends` is also reported as unknown, so
extraction can continue without `node_modules`. The current TypeScript grammar
rejects some valid generic call signatures; those modules remain in the facts
with an unknown surface.

By default, TypeScript discovery uses `src/`, then the repository root. In a
monorepo or a repository without `src/`, set `[package_roots]` to the
application packages you want mapped so scripts and fixtures do not become
application modules.

`init` writes a configuration file, an empty map for your agent to fill in,
the instructions your agent will follow, and a CI workflow. Then it prints the
one sentence you hand to your agent:

> Map this repository with systemap. Follow the systemap skill.

That is all you have to do. The agent reads your code, decides which
modules belong to which card, writes the lines between them, runs the checker
until it reports no failures, and then goes round again looking for what it
missed. When it stops, you read the handful of calls it had to make, change
the ones you disagree with, and commit the page.

Using Claude Code? The repository is its own plugin marketplace:

    /plugin marketplace add 0xfauzi/systemap
    /plugin install systemap@systemap

Any agent that can read instructions and run a command works the same way.

## Why let an agent draw it?

Half of a map is mechanical: which modules exist, what each one exports, which
tests cover it. A script reads that out of your code in a second and never
gets it wrong.

The other half is judgement. Which four modules are really one part? What is
the line between two parts actually for? A script cannot answer that. An
import graph lists every import and still does not say which modules form
one part. A person can answer it, but rarely has the patience to keep
answering it through every refactor.

An agent can do both halves, on two conditions. It follows a written
procedure, so it decides the same way every time. And something checks its
work and rejects it when it is wrong. systemap supplies both: the procedure
your agent follows, and the commands that reject a map that does not match
the code.

## How does the map stay true to the code?

Two commands, and your agent runs both until neither reports anything.

**`systemap check` compares the map with the code.** It fails when a module
belongs to no card, when a card points at a function the code no longer has,
when a line runs through a card it does not connect, when two labels overlap,
or when the page is older than the code. Eleven rules, and every failure names
the fix.

**`systemap judgement` prints the questions a rule cannot answer.** This card
holds a single module, so is it really a part of its own? Here is a way into
your system that no journey covers. These two cards import each other and your
map draws no line between them. You either change the map, or write the reason
it is correct as it stands into `systemap.toml`, where it stays, so the same
question is not asked twice.

    systemap check && systemap judgement --strict

Six repositories have been mapped this way from start to finish, four of them
written by somebody else, each finishing unattended with both commands quiet
([docs/benchmarks.md](docs/benchmarks.md)).

## What did this pull request change about your system?

Git tells you which lines of code changed. `systemap delta --base main` tells
you which parts, connections and claims changed, one line per thing, each
with the fix:

    moved: pkg.old -> pkg.new (same content); Gateway names pkg.old in
      implemented_by: rename it in map/model.py
    added: pkg.thing, claimed by no card; name it in a card's implemented_by
    entry vanished: Gateway names entry serve, which its modules no longer define

Gateway is a card. `implemented_by` is the list of modules a card claims, and
`entry` is the one function it tells a newcomer to start reading at.

The workflow `init` writes posts exactly that as one comment on the pull
request and keeps it up to date as you push. So review starts with what the
change did to the parts and their connections, rather than with four hundred
lines of diff, and CI fails while anything on that list still needs a
decision.

Your agent then fixes those lines instead of redrawing the whole map. On
three merged pull requests of one 111-module repository, that path cost 2.31,
4.39 and 2.50 dollars, against between 3 and 26 dollars to map a repository
from scratch. Three pull requests of one repository is a small sample, and
[docs/benchmarks.md](docs/benchmarks.md) has each run.

## What else can it tell you?

- **Ask why.** Every line systemap prints comes with two more: why it matters
  and what to do. `systemap explain "<kind>"` prints any of them in full.
- **Let an agent write a journey** for a way into your system that nobody has
  written one for. Each step is checked against the map before it is kept.
- **See how the system changed over the past year.** `systemap history`
  samples your repository back through time and says which parts grew, and
  which commits grew them.
- **Say what you are about to do.** `systemap plan "<task>"` names the parts
  the work will most likely touch, and afterwards compares that with the parts
  it did touch.
- **Have TypeSafe's Jev model check** the judgement calls a name-and-import
  checker cannot make. It needs `TYPESAFE_API_KEY`. `check` and `judgement`
  make no network requests, so CI runs offline unless you set that variable.

Every threshold in there was measured before the feature was built, and the
features that failed their test were written down rather than shipped
([bench/jev](bench/jev)). `systemap --help` lists every command, and
[docs/reference.md](docs/reference.md) has every option, rule and setting.

## What is systemap not?

It reads Python, TypeScript and TSX. TypeScript support reads exported names,
imports, tests, package binaries, package export roots and configured
`tsconfig.json` path aliases. `delta` and `history` read the same TypeScript
facts from committed trees. Framework-specific routes are not read yet. It is
not a call graph: the map shows the lines your agent declared and defended,
not every function call. It is not a
dependency diagram: modules are not parts, and the map shows parts. It is not
a UML tool: one picture, one layout, and nothing to learn beyond card, line
and journey.

## How do you work on systemap itself?

    uv sync
    uv run pytest -q
    uv run systemap check && uv run systemap judgement --strict

CI runs the tests, the types and the linter on Linux, macOS and Windows with
Python 3.11 and 3.13, and installs the built package into an empty environment
on each one to run the commands against a copy of this repository's own map.

MIT licensed.

Map something with it. If something blocks you, open an issue. Every
version so far came out of somebody's log of where they got stuck, most of
them an agent's.
