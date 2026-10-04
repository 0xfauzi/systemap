# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The project instructions identify one person maintaining a view of a system
larger than they can remember. The README describes a developer reviewing code
written by a coding agent. The map supports both learning the system and
reviewing changes to it.

## Product Purpose

systemap generates a readable system map from extracted facts and authored
meaning. Commands help keep the map consistent with the code.

## Operating Context

The agent authors the map, the checker refuses invalid maps, and a person
reviews the result. The generated page can be read locally or shared.

## Capabilities and Constraints

A card is a part whose modules do one job. A flow describes something travelling
between parts. A journey describes an operation step by step. A layer selects
relationships that answer one question.

The page is a stored snapshot. It cannot infer changes after generation.
Imports supply structural evidence, without proving the authored meaning.
Source reviews bind to source bytes and the exact authored claim.
Declared relationships retain their status. External relationships cross the
code boundary. The generated production page fetches nothing and depends on
nothing. Terminal commands are instructions, not actions the page can execute.

## Brand Commitments

The name is systemap. The project requires literal language, short sentences,
no emoji and no em dashes. The user selected the refined spatial-map prototype
and rejected the operations-first layout. DESIGN.md records the implemented
map, inspector, controls and reading alternative.

## Evidence on Hand

README.md, AGENTS.md, map/model.py, docs/map/index.html and docs/map/map.json
provide product descriptions and the system's own map. Existing screenshot
artifacts are kept locally in output/playwright and are excluded from the PR.
Their freshness must be checked against the current page before using them as
current-state evidence.

## Product Principles

- Explain purposes and relationships before quantities of code.
- Keep facts, authored meaning and recorded decisions distinguishable.
- Preserve exact finding identifiers when presenting a judgement.
- Surface missing evidence rather than substituting an answer.

## Open Decisions

An isometric presentation and a dedicated view-sharing control remain optional.
They are not part of the selected production direction.
