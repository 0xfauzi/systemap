# Map a large system in nested parts: the design

Status: a proposal, revision 2. Nothing in this design is built or measured. All paths are relative to `src/systemap/`, unless a different path is shown. Line references are to `origin/main` on 2026-11-04.

Revision 2 applies the 20 corrections of the design critique. The section "Changes from revision 1" at the end lists them.

Language status: `~/.claude/WRITING.md` is not on this machine. The official ASD-STE100 dictionary was not available. Thus this document gives no ASD-STE100 acceptance result for its text or for the proposed skill text. Before a commit, a maintainer must examine each word and each new glossary term against the official reference (`skill/references/language.md`).

Short forms in this document: "part" means a nested part (see the glossary rows). "Join" means Phase C. The proposed skill text does not use these short forms.

## Summary

systemap can map a large repository today with nested maps. But it does not support work by more than one agent. These are the problems:

- One broken or missing child file stops every command (nest.py:133-143, 238-244).
- Shared files have no lock (answer_write.py:207-234, decisions_store.py:85-91).
- Few commands operate on one map only. Today `--map` exists only on `figure` (cli.py:1102-1110) and `review` (review.py:329-334), and `review --map` loads the full tree (review.py:146-150).
- Nothing examines the boundary between a parent card and its nested map. `check_nesting` examines only actor IDs and module claims (check.py:253-297).

This design adds one procedure, with three phases:

1. **Contract first.** One main agent writes the top map. The top map claims every module and has 40 cards or fewer. The main agent also fixes the shared words (layers, flow artifacts, naming rules) and writes boundary import rules in the parent contract. Then it writes a stub for each nested map before it sets `map=`. This commit is the contract commit.
2. **Parts.** For each nested map, a part agent maps the inside of one card. If the coding agent can start sub-agents, the part agents work at the same time, each in its own Git worktree. If not, one agent does the parts in sequence, with one commit after each part. Both modes use the same message, the same commands, and the same result file.
3. **Join as a check.** The main agent examines the write set of each part against a commit. It submits the decisions of each part one at a time, then runs the full-tree checks. The checks include two new judgement kinds: `boundary flow` and `boundary import`. The main agent sends a part back for rework one time at most. After that, the main agent corrects the remaining lines itself.

The code changes are:
- one shared function for nested-map file names, used by suggest.py and `parts`,
- a reentrant lock for shared files, a lock for each model file, and a safe restore,
- `--map` with a scoped load on more commands,
- a `systemap parts` command with `--stub`,
- the module `nest_join.py`.

The visual design replaces the iframe overlay with linked pages. It adds:
- a full path of links,
- a map tree,
- search across maps,
- a roll-up of changes, with a "boundary changes" row,
- labels for neighbour cards,
- ports on the frame of a nested map.

## Goals and non-goals

### Goals

- A repository that one readable map cannot show can be mapped as a tree of nested maps. Each map has about 40 components or fewer (`CARDS_PER_MAP`, nest.py:23). Each card has 10 modules or fewer where possible (`MODULES_PER_CARD`, nest.py:26).
- The procedure works with sub-agents and without sub-agents. The result does not depend on the mode.
- Each part result can be examined alone: `systemap check --map ID` and `systemap judgement --map ID`.
- The join can be examined with these checks:
  - top coverage (check.py:779, `coverage=m.top`),
  - exact claims (check.py:278-297),
  - parent crossing imports (`crossing_pairs`, judgement.py:204-221, and the line text at judgement.py:230),
  - the new boundary kinds.
- Parallel agents cannot lose each other's writes without notice. A second writer stops with an error.
- All load limits stay unchanged. These are the limits for each map load: 512 KB, 100,000 values, 16 files, and a syntax depth of 32 (model_load.py:45-48). The nesting limit is 16 levels (`MAX_NESTING`, nest.py:30).
- A reader always knows which map is open, where it is in the tree, and which flows cross its frame.

### Non-goals

- No merge of maps into one model. The tree stays a tree of model files, as Structurizr keeps one model with many views.
- No new uniqueness rule for component or sequence IDs across maps. IDs are unique in one model (model.py:386-388, sequence_ids.py:17-24). The map ID path makes each card unique (nest.py:121-122).
- No change to the identifiers of current findings. The `crossing import` line form stays the same. So `answer_migrations.py` needs no change.
- No automatic choice of part boundaries by a model. The plan gives facts. The main agent decides.
- No in-place semantic zoom in one canvas (Proposal 4). It stays an option for later, after the measurements in this design.
- No recommended number of agents or part size before the measurements in this design.

## The process

### Roles

| Role | Who | Write set | Must not run |
|---|---|---|---|
| main agent | The coding agent of the user, one session | the top model and contract, `systemap.toml`, `.systemap/decisions.json`, the facts file, `docs/map/`, `map/parts/plan.json`, all stub files, all `map=` fields | nothing is excluded |
| part agent | A sub-agent, or the main agent in a later step | its model file, its contract file, new model files whose names start with `<stem>_`, its result file `map/parts/<stem>.json` | `extract`, `refresh`, `render`, `init`, `decisions submit`, `triage`, `place` without `--map`, and `review`, `describe`, or `journeys` without `--map` |

"Write set" is the set of files that one agent can change. The design does not use "owner" for this meaning, because the glossary gives "owner, ownership" only the meaning "the component assignment of a source module" (skill/references/language.md:284).

The write sets of part agents do not intersect, for these reasons:
- Only one component can open a given model file (nest.py:248-260).
- Each map has its own contract file (contract.py:73-77).
- The plan refuses two file prefixes when one prefix starts with the other (see "File names").
- `check` and `judgement` read the facts. They do not write them.

### Phase A: the main agent writes the contract (always one agent)

A1. Run `systemap extract` and `systemap suggest`. `suggest` gives package groups and the crossing imports between them (suggest.py:133-171). It also names maps above 40 cards and cards above 10 modules (suggest.py:174-217).

A2. Write the top map.
- Use 40 cards or fewer.
- Claim every module. Coverage counts only on the top map (check.py:779), and a nested map gets `NOT_COUNTED` (check.py:749).
- Write the shared words in the top `MEANING`: the layer IDs and questions, the regions, and the artifact names of the flows between top cards.

The theme is resolved for each map from its own layers (nest.py:146-150). Thus colors stay the same across levels only if all maps use the same layer IDs. The visual change in this design (V9) makes inheritance explicit.

A3. Fix the boundaries from facts.
- For each `crossing import` line between top cards (judgement.py:230), write a flow with an artifact, or record an answer. These flows are the boundary flows.
- For each card that becomes a part, write one `allow_imports` rule in `map/contract.py`. Its `src` is the card, and its `dst` is the cards that the card imports at this commit (model.py:184-199). The reason cites the commit. The reason must say that the rule records the current imports, and that it does not show that the boundary is correct.
- The rule must be in the parent contract. The owner table of an import rule contains only the claims of that model (import_rules.py:93-98), and nested actors have no claims. Thus a nested contract cannot state a rule about a sibling part.

A4. Select the parts.
- A part is one top card that will open a nested map. A card above 10 modules is a candidate.
- The main agent maps the small cards itself.
- A part with more than 400 modules is a level-2 part. 400 is 40 cards multiplied by 10 modules, a value from two constants. It is not a measurement of readability.

A5. Write the stubs, then set `map=`. If a parent has `map=` and the file is missing, every command fails (nest.py:238-244). Thus, for each part:
1. Run `systemap parts --stub CARD`. The command writes a stub model file with:
   - one internal component for each `suggest` group in the card modules,
   - one internal component `<Card>Other` for the modules that `suggest.proposals` puts in its `alone` list (suggest.py:123-129), if that list is not empty,
   - the symbol claims of the card, unchanged,
   - actors for the parent components that have a boundary flow or a crossing import with the card. At level 2, the actors must be components of the direct parent map (check.py:265-275). See "Level-2 parts".
   - positions from the same placement as `place --map`, so that the stub has no "has no position" problem (model.py:418),
   - no flows,
   - the `MODEL` and `MEANING` exports (config.py:791-796).
   The command refuses to write a file that exists. It refuses a group ID or the `<Card>Other` ID if it is the same as an actor ID (model.py:386-387). Then the main agent selects a different ID. A stub must pass `check_nesting` and the model problems of `check` (check.py:740-748).
2. Set `map="<file>"` on the card. The path is relative to the parent model file (nest.py:222). The file name comes from the shared function `parts.file_name` (see "File names").
3. Run `systemap refresh` and `systemap check`. Both must exit 0.
4. Commit. This commit is the contract commit.

File names: all model files stay in the folder of the top model. A model file can import sibling files only from its own folder (model_load.py:145-161). The stem of a map is the map ID in lower case, with `_` in place of `/`. For example, the map `Gateway/Routes` has the stem `gateway_routes` and the file `map/gateway_routes.py`. The function `parts.file_name(map_id)` gives this name, and `suggest` and `parts --stub` both use it. The plan refuses a card ID if its stem:
- is `model`, `contract`, or `plan`,
- ends in `_contract`, because contract.py:73-77 adds that suffix,
- is the same as a different stem in the plan,
- gives a prefix `<stem>_` that is the start of a different stem in the plan, or the reverse.

All comparisons use the lower-case form, because a file system can ignore case.

A6. Run `systemap parts --json`. The command writes `map/parts/plan.json`. The `map/parts/` folder is tracked by Git, so the plan and the result files are in the branch of each worktree and in each merge. The final join commit removes `map/parts/`. A later `systemap parts` makes the plan again.

### The part plan (`systemap parts`)

The command reads the tree and the stored facts. It writes only `map/parts/plan.json`, and with `--stub` the stub file. It does not decide boundaries. It computes facts for the boundaries that the main agent made.

```json
{
  "base_commit": "<facts built_at_commit>",
  "facts_digest": "<digest of the facts file>",
  "contract_digest": "<digest of the top model, the top contract, and the claims and flows of each opening card>",
  "vocabulary": {"layers": ["..."], "regions": ["..."], "flow_artifacts": ["..."]},
  "shared_files": ["systemap.toml", ".systemap/decisions.json", "map/model.py",
                   "map/contract.py", "map/parts/plan.json", "docs/map/"],
  "parts": [{
    "map": "Gateway",
    "card": "Gateway",
    "stem": "gateway",
    "model_file": "map/gateway.py",
    "contract_file": "map/gateway_contract.py",
    "file_prefix": "map/gateway_",
    "result_file": "map/parts/gateway.json",
    "modules": ["..."], "module_count": 37, "source_bytes": 412000,
    "groups": [{"id": "...", "modules": ["..."]}],
    "alone": ["..."],
    "actors": [{"id": "Auth", "because": ["flow token", "crossing import"]}],
    "boundary_flows": [{"src": "Gateway", "dst": "Auth", "artifact": "token"}],
    "boundary_imports": [{"module": "app.gateway.routes", "imports": "app.auth.jwt", "card": "Auth"}],
    "import_rules": ["gateway-imports"],
    "entry_points": ["<entry identities in these modules>"],
    "state": "stub",
    "level_2": false
  }],
  "order": ["Gateway", "Store"]
}
```

Where each field comes from:
- `modules`: `claimed(card, components)` without empty markers, as in check.py:278-280.
- `groups` and `alone`: `suggest.proposals`, limited to the modules of the card (suggest.py:110-130).
- `actors` and `boundary_imports`: the parent flows, and the pair index of `crossing_pairs` with the parent owner table (judgement.py:204-221).
- `entry_points`: each entry goes to the deepest map that claims its module (judgement.py:507-508, journey_coverage.py:35-45). Entry coverage is global (judgement.py:510). Thus one assignment for each entry prevents two parts from writing a sequence for the same entry. It also prevents gaps.
- `state`: `stub` while the map has only the stub components. Otherwise `mapped`.
- `level_2`: true if `module_count` is more than 400.
- `order`: the largest `module_count` first, so that the longest parts start first.
- `facts_digest` and `contract_digest`: `parts` and the join refuse a plan if either digest is different from the current tree. They stop with the message "The plan is stale. Do systemap parts again." `check --map` gives this text as a warning and does not change its exit code. If no plan exists, `check --map` says nothing about a plan, so a user who does not use parts sees no change.

The text form prints one line for each part. For example: `Gateway (map/gateway.py): 37 modules, 3 entry points, actors Auth, Store`.

### Phase B: the part agents

A new sub-agent starts "with a fresh, isolated context window. It doesn't see your conversation history, the skills you've already invoked, or the files Claude has already read" (Claude Code sub-agent documentation, https://code.claude.com/docs/en/sub-agents, read 2026-11-04). Thus the message must be complete. The template is in `references/parts.md`:

```
Read <skill>/SKILL.md, <skill>/references/parts.md, and <skill>/references/language.md.
The writing profile is <profile>.
Map the nested part <MAP ID>. Get its record with: systemap parts --map <MAP ID> --json
Write only these files: <model_file>, <contract_file>, <result_file>,
  and new model files whose names start with <file_prefix>.
Do not run: systemap extract, refresh, render, init, triage, or decisions submit.
Use systemap place, review, describe, and journeys only with --map <MAP ID>.
Use only these layer IDs: <layers>. Use these artifacts for flows to actors: <boundary_flows>.
Record answers only in the forms item and items.
If a module claim or a boundary flow must change, do not change it.
  Write a boundary request in the result file.
Done when:
  - systemap check --map <MAP ID> exits 0.
  - Each line of systemap judgement --map <MAP ID> has a verdict or an answer in the result file.
  - No nested component has more than ten modules, or the result file gives the reason.
  - Each boundary flow has a nested end, or a boundary request.
Then write the result file and commit it with your model files.
Give a summary of five lines or fewer.
```

The short summary limits the text that goes back into the context of the main agent. Anthropic describes a design in which "subagent outputs can bypass the main coordinator" and go to a file system (https://www.anthropic.com/engineering/multi-agent-research-system, 2025-06-13). Thus the files are the result, and the summary is only a pointer to them.

The part procedure is the normal SKILL.md loop, done on one map:
1. Replace the stub groups with task components of 3 to 10 modules each.
2. Write the flows, which include the flows to actors with the fixed artifacts.
3. Write the sequences for the assigned `entry_points` only.
4. Write the invariants and the internal import rules in the contract file of the part. These rules can name only internal components (import_rules.py:93-98).
5. Run `place --map`, `check --map`, and `judgement --map`.
6. Run `decisions list --map` and write the verdicts in the result file.
7. Examine its own names and sentences against the language policy.

The result file is `map/parts/<stem>.json`.

```json
{
  "map": "Gateway",
  "base_commit": "...",
  "facts_digest": "...",
  "contract_digest": "...",
  "files": ["map/gateway.py", "map/gateway_contract.py"],
  "check_exit": 0,
  "open_lines": ["Gateway: ..."],
  "verdicts": ["<rows in the format of systemap decisions submit FILE>"],
  "answers": [{"line": "Gateway: ...", "form": "item", "reason": "..."}],
  "proposed_answers": [{"form": "kind", "value": "...", "reason": "..."}],
  "boundary_requests": [{"kind": "move_module | add_flow | remove_flow | artifact",
                         "subject": "...", "reason": "...", "source_refs": ["..."]}],
  "questions": ["..."]
}
```

A part agent records answers only in the forms `item` and `items`. The other forms in `config.ANSWER_FORMS` (config.py:85) are `crossing`, `crossing_into`, `crossing_from`, `kind`, and `module_sdk`. They apply across maps (second-pass.md:102-111). A part agent can propose one under `proposed_answers`. Only the main agent records it. The join refuses a result file that has a different form under `answers`.

**Without sub-agents.** One agent does Phase A, then each part in `order`, then Phase C. It uses the template message as its own task text. It writes the result file and makes one commit after each part. A context that becomes full can start again from the plan and the result files.

**Level-2 parts.** The part agent does Phases A to C inside its part, with these changes:
- Its map is the frozen parent. Its stubs use its file prefix. It writes `map/parts/<stem>_plan.json` for its sub-parts with `systemap parts --map <MAP ID> --json`.
- In step A5, it runs `systemap check --map <MAP ID>` in place of `refresh` and `check`. The full refresh is for the main agent at the join.
- The actors of a sub-part must be components of its direct parent map (check.py:265-275). If a sub-part imports a module that a top card claims, the level-1 map must have an actor for that top card first. The level-2 stub then uses that actor. `parts --stub` refuses a level-2 stub that needs an actor that the level-1 map does not have.
- It writes its boundary rules in its own contract, where its cards claim the modules.
- It does not write the shared files. It puts the verdicts and answers of its sub-parts in its own result file.
- If its agent cannot start sub-agents at that depth, it does the sub-parts in sequence. Claude Code permits sub-agents "up to three layers below the main conversation" by default, and `CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH` changes this (https://code.claude.com/docs/en/sub-agents, read 2026-11-04). Other agents can have a different limit. The sequential fallback does not depend on the limit.

### Phase C: the join

**Barrier.** The main agent starts Phase C only after each part agent has stopped and has committed. During Phase C, no part agent runs, except in the rework round of step 7. During the rework round, the main agent does no full-tree write.

For each part, in `order`:
1. Parallel mode: merge the worktree branch of the part. Sequential mode: the part commit is already on the branch.
2. Examine the write set. `git diff --name-only <commit before the part> <part commit>` must show only files in the write set of the part. In parallel mode, the commit before the part is the contract commit. In sequential mode, it is the commit of the previous part. If a file is outside the write set, reject the part: run `git revert --no-edit <part commit>` (or do not merge the worktree branch), and send the part back. The other parts do not change, because each part has its own commits.
3. If the `facts_digest` or the `contract_digest` of the result file is different from the plan, send the part back.
4. `systemap check --map <ID>` must exit 0.

Then for the full tree:

5. **Decisions of the parts that no boundary request touches.** For each such result file, run `systemap decisions submit <verdict file>`. Then record the exact answers. The answers keep the map prefix (judgement.py:9-11). The submit writes review digests into the model file of that map (decisions_submit.py:430-438, review.py:117-145). The request ID of a card or a flow contains a digest of its claims (decisions.py:214-218), and `submit` writes nothing if one result is not a current request (decisions_submit.py:175-182, 316-322). Thus this step must come before any boundary edit.
6. **Boundary requests.** The main agent decides each request. If it accepts a request, it edits the top model or the top contract. Then it runs `systemap parts --json` again, because the `contract_digest` changes. A module move changes two parts. The main agent sends both parts back with the request in the message, and with this note: "Make the verdict file again. The verdicts of the earlier file are not current." A part never makes a boundary change itself.
7. **One rework round.** Send each part that has open lines, or that step 6 touched, back once, with the lines in the message. The barrier applies again. After that round, the main agent does steps 1 to 5 for the reworked parts and corrects the remaining lines itself. This rule stops a loop that has no end.
8. **Full checks.** Run `systemap place --map <ID>` for each part, then `systemap refresh`, `systemap check`, `systemap rules`, and `systemap judgement`. `rules` gives the parent `allow_imports` results for each part. The full-tree run is the authoritative result. A run with `--map` is not.
9. **One language pass.** One agent examines all new names and sentences in the tree, so the words agree across parts.
10. **Final commit.** Remove `map/parts/` and commit.

### Join checks (new judgement kinds)

The join checks are judgement lines, not check failures. An agent can answer them, and current trees must not start to fail `check`. The logic goes in a new module, `nest_join.py`, because check.py has 794 lines and judgement.py has 795 lines. `judgement.run_tree` calls it with one or two lines (judgement.py:499-526).

| Kind | Line (identity only) | Rule |
|---|---|---|
| `boundary flow` | `Gateway: boundary flow: Routes sends to actor Auth, and the parent map has no flow from Gateway to Auth` | A nested flow from an internal component to actor X needs a parent flow from the card to X, in the same direction. Also for the opposite direction. |
| `boundary flow` | `Gateway: boundary flow: the parent flow from Gateway to Auth has no nested flow to actor Auth` | A parent flow between the card and X needs at least one nested flow with actor X, in the same direction. |
| `boundary import` | `Gateway: boundary import: Routes imports Auth, and Auth is not an actor of the map inside Gateway` | A module of a nested component imports a module that X owns, and X is not an actor of the nested map. |
| `boundary import` | `Gateway: boundary import: Routes imports Auth, and no flow connects Routes and actor Auth` | The same import exists, and X is an actor, but no nested flow connects the two. |

The owner X of an imported module: find the nearest ancestor map in which a component claims the module. If that component is the opening card of the current map or one of its ancestors' opening cards, the import is internal and gives no line. Otherwise, X is the actor of the current map that stands for that component, or for the component of the direct parent map that contains it. This rule works at level 2: a module of `Gateway/Routes` that imports a module of the top card `Auth` has the owner `Auth` through the actor `Auth` of the map `Gateway`.

Evidence for each kind. Exact answers need an evidence digest (judgement.py:5-7), and a request with no digest is blocked (decisions.py:417-420). The current evidence is the claims of the named components and the crossing imports (judgement_evidence.py:1-21). In a nested map, an actor has no claims. Thus the new kinds need their own evidence:
- `boundary flow`: the claims of the opening card and of the component that X stands for, the parent flow record (if it exists), and the nested flows with actor X.
- `boundary import`: the same claims, and the import pairs of the line.

A change to the parent flow, to the claims, or to the import pairs makes an exact answer stale.

Rules for the lines:
- A line contains only the prefix, the kind, the component names, and the fixed text. It has no count, module, or line number.
- The import count and the module pairs go in a row below the line, as `crossing_counts` does (judgement.py:263-270). They also go in `judgement --json` fields: `map_id`, `parent_flow`, `nested_flows`, `import_pairs`.
- Both kinds go in `config.LINE_KINDS` (config.py:88-106), so `kind = "boundary flow"` answers are accepted.
- `explain.py` gets a `Lesson` for each kind (explain.py:124), with three sentences: what the finding tells the reader, why it is important to the map, and what the reader must do.
- The kinds are new, so no migration is necessary.
- Parent-level `crossing import` lines stay the same (second-pass.md:109-110). The nested owner table does not change. Thus the open-line count of current users does not change for current kinds. Current trees with nested maps can get new lines of the new kinds. The release note must say this.

Why the checks are necessary today:
- `check_nesting` compares only actors and claims (check.py:253-297).
- A flow to an actor gets the state EXTERNAL, so imports do not examine it (evidence.py:364-372).
- A part agent that maps only a child does not see its boundary imports.

Entry coverage: the plan assigns each entry to one map. A `repeated cover` kind (one entry covered in two maps) is an open question, because the assignment in the plan can be enough. M8 decides this.

### Shared files

The rule: only the main agent writes shared files, and only in Phase A and Phase C.

| File | Writer | Part agents |
|---|---|---|
| `map/model.py`, `map/contract.py`, all `map=` fields | main agent | read only |
| `map/<stem>.py`, `map/<stem>_contract.py`, `map/<stem>_*.py`, `map/parts/<stem>.json` | the part agent of that map | only that agent |
| `systemap.toml`, `.systemap/decisions.json` | main agent, one submit at a time | never write |
| facts file, `docs/map/**` | main agent (`extract`, `refresh`) | never write |
| `map/parts/plan.json` | main agent (`parts`) | read only |

The rule is not enough alone, because agents do not always obey prose. Thus the code adds a safety: locks. A lock stops a second writer with an error. It does not merge, and it does not wait. This obeys AGENTS.md: "If a command cannot do the specified work, show the failure and stop."

The verified faults:
- `answer_write.add` reads, edits, and writes the file with no lock (answer_write.py:207-234).
- `_write_answers` writes its `before` bytes back after a load failure (decisions_submit.py:362-372). That write can delete the answers of a different writer.
- `decisions_store.save` replaces the full store (decisions_store.py:85-91). The records come from a snapshot that the command read at its start (decisions_submit.py:78). Thus the last writer wins.
- `place` writes every model file of the tree (cli.py:817-829). `review` also writes model files (review.py:144).

**Worktrees.** Parallel mode requires a Git worktree for each part agent, for example `isolation: worktree` in Claude Code. In a shared checkout, `git status` shows the changes of all parts together, and the join cannot know which part changed a file. Sequential mode uses the one checkout, with one commit after each part. Both modes examine the write set against commits, as step 2 of Phase C says.

### Checks for each mode

| Check | When | Who |
|---|---|---|
| `check --map ID`, `judgement --map ID`, `decisions list --map ID` | during the part loop | part agent |
| Each stub passes `check_nesting` and the model problems of `check` | before `map=` | `parts --stub` and its test |
| The write set examination against commits | at the join, for each part | main agent |
| `check`, `rules`, `judgement` on the full tree | at the join | main agent |
| `boundary flow`, `boundary import` | at the join (full tree) and in `--map` runs | both |
| `suggest` shows no card above 10 modules (suggest.py:174-217) | completion | main agent |

With `--map`, the global entry coverage and the top coverage are not complete. The output of a scoped run says "entry coverage: not examined in a run with --map" and does not give entry lines. Unknown is never a pass.

### Maintenance after a source change

1. The main agent runs `systemap extract` and `systemap delta --base <ref> --json`. Each delta line has a `map_id`, and cards have the form `mapid/card` (delta.py:80-88, 700-709).
2. The main agent first does the contract lines:
   - lines with an empty `map_id`,
   - new modules with no claim (top coverage),
   - `rules` failures of the parent boundary rules,
   - parent `crossing import` lines.

   It assigns each new module to a top card. A new module in card X then gives the line "has no claim for M" in the map of X (check.py:296). That line is the task for the part.

   A new import across parts makes the parent `allow_imports` rule fail, and `check` and `refresh` then exit 1 (cli.py:411-416, 525-528). The main agent examines the import. If the import is correct, it adds the card to the `dst` of the boundary rule, with a reason that cites the commit (SKILL.md:170). The pull request summary shows this change in the "boundary changes" row (V8), so a reviewer can accept or refuse it.
3. The main agent groups the other lines by `map_id`. A module that moves between parts changes two maps. `compute_tree` already compares each child against the modules that its card claims at each commit (delta.py:670-711). The "boundary changes" row connects the change to the parent claims with the two nested map changes.
4. For each affected part, use the Phase B message with its delta lines added. If two or fewer parts are affected, the main agent does them in sequence. Anthropic reports that "multi-agent systems use about 15x more tokens than chats" in its research system (https://www.anthropic.com/engineering/multi-agent-research-system, 2025-06-13). That value is for a different task. For map maintenance, the number of parts at which sub-agents cost less is not known (M9).
5. The one-third rule of maintenance.md applies to each part. If more than one third of the components of a part change, the part gets a full remap.
6. A card that grows above 10 modules becomes a new part with `parts --stub`.
7. Do Phase C, steps 2 to 10.

## Skill changes

### SKILL.md: replace lines 173-179

SKILL.md has 240 lines, which is the limit. Lines 173-179 are seven lines (five text lines and two empty lines). The replacement is also seven lines. It joins lines 173 and 174 into one line, so the new reference row (below) has space. The `map="gateway.py"` example moves to layout.md, where layout.md:66-67 already shows it.

```
Select the region for each component. Use `systemap place` for positions. A route must not cross an unrelated region. Use `pinned=True` only for a position that must stay fixed.

A component with more than ten modules can have a nested map. Maps with more than forty components also receive a nested-map suggestion.
Write the nested model file before you set `map=` on the component. Its internal components must cover all of the parent's module claims, without additions. Its actors represent adjacent components.
If the map needs two or more nested maps, read `references/parts.md`. If your agent can start sub-agents, give each sub-agent one nested part. If it cannot, do each nested part in sequence.
Only the agent of the parent map writes `systemap.toml`, the parent model, and the output. Commands without `--map` examine every nested map. Only a run without `--map` gives the result for completion.
```

Add this row to the References list, after the `maintenance.md` row:

```
- `references/parts.md`: nested parts, sub-agents, and the examination of their results. Read it when the map needs two or more nested maps.
```

The terms "nested part" and "sub-agent" are defined in the glossary of `references/language.md`, which SKILL.md tells the agent to read before each text change (SKILL.md:231). The total stays at 240 lines. Make the same change in `skills/systemap/SKILL.md` and `.claude/skills/systemap/SKILL.md`. The three directories are identical today and must stay identical.

### New file `references/parts.md` (target 160 lines or fewer)

1. **Contents.**
2. **When to use this procedure.** Use it when the map needs two or more nested maps. Below that, do not divide the work. The steps and the checks are the same with or without sub-agents.
3. **Terms.** main agent, nested part, part agent, part plan, result file, write set, boundary flow, boundary import, contract commit, stub.
4. **Step 1. Write the top map.** Claim each module. Use forty components or fewer. Write the layer IDs, the regions, and the flow artifacts. Part agents must use these names.
5. **Step 2. Write the boundary rules.** One `allow_imports` rule for each nested part in `map/contract.py`. The reason gives the commit and says that the rule records the current imports.
6. **Step 3. Write the stubs.** `systemap parts --stub CARD`, then `map=`, then `refresh` and `check`, then a commit.
7. **Step 4. Start the part agents.** The message template. Give each part agent its own Git worktree. "Start five part agents or fewer at one time" is a temporary value until M8 gives a better one.
8. **Rules for a part agent.** The write set, the prohibited commands, the permitted answer forms (`item` and `items` only), and the boundary requests. "If a different command holds `.systemap/write.lock`, stop and tell the main agent. Do not remove the lock."
9. **The result file.** The JSON form.
10. **Step 5. Examine the nested parts together.** The steps of Phase C, with the action for each new kind. Submit the verdicts of the nested parts that no boundary request touches first. After a boundary change, the touched nested parts must make their verdict files again. Do one rework round, then correct the remaining lines yourself.
11. **Nested parts inside a nested part.** The level-2 procedure.
12. **Without sub-agents.** Do one nested part at a time. Write the result file and commit after each nested part.
13. **After a source change.** The maintenance steps, with the boundary rule update.
14. **Completion conditions.** The second-pass.md conditions apply to the full tree. No line of the new kinds is open without an answer, no nested component has more than ten modules, and no result file has an open question.

The text of parts.md uses "write a stub" and "examine the nested parts together", not the verbs "seed" and "join". "Merge" occurs only as the Git command. See the glossary rows.

### Other skill files (all three copies)

- `references/layout.md:61-83`, step 4: "If the map has two or more nested maps, read `references/parts.md`." Keep the `map="gateway.py"` example there.
- `references/second-pass.md:102-111`: the two new kinds, and the agent that answers each kind (`boundary flow`: the main agent. `boundary import`: the part agent first).
- `references/maintenance.md`: "Group the delta lines by `map_id`. Do the lines without a map ID first. If a boundary rule fails, examine the import, then change the rule with a reason."
- `references/decisions.md`: "Use `systemap decisions list --map ID` for one nested map. Only the main agent runs `systemap decisions submit`."
- `references/language.md` glossary. Each new row needs a category (language.md:452-453). The proposed category for each noun is 19 (technical names). A maintainer must examine this value and each word against the official dictionary. The rows:
  - **sub-agent** (19): an agent that a different agent starts for one task, with its own context.
  - **main agent** (19): the agent that writes the top map, divides the work, and examines the results together.
  - **nested part** (19): one nested map, its contract file, and the model files with its file prefix. The design does not add "part" alone, because it is an ordinary dictionary word (language.md:150).
  - **part agent** (19): the agent that maps one nested part.
  - **part plan** (19): the output of `systemap parts`.
  - **result file** (19): the file in which a part agent records its verdicts, answers, boundary requests, and questions.
  - **write set** (19): the files that one agent can change.
  - **boundary flow** (19): a flow between a card that opens a map and an adjacent component of the parent map.
  - **stub** (19): a nested model file that has only the components from `systemap parts --stub`.
  - **lock file** (19): a file that permits only one command at a time to write shared files.
- Technical verbs (language.md:405-430): add **merge** with the meaning "combine two Git branches with `git merge`" only. The design adds no other verb.

"Owner" keeps only its current meaning. The current glossary term "port" (language.md:286) is used in the visual design.

## systemap code changes

The sizes are estimates of new or changed lines. They are not measurements.

1. **One function for nested-map file names.** `parts.file_name(map_id)` gives the lower-case stem with `_` in place of `/`, plus `.py`, beside the top model. suggest.py:194-197 prints `map="<that name>"` in place of `map="map/<card>.py"`. Today that text gives `map/map/<card>.py` with the default model `map/model.py` (config.py:195), because the path is relative to the parent model (nest.py:222). A test proves that `suggest` and `parts --stub` give the same path and that the path loads. About 20 lines.
2. **Locks.**
   - `file_write.exclusive(root, command)` is a context manager. It makes `.systemap/write.lock` with `os.open(O_CREAT | O_EXCL)`. The file holds the process ID, the command, and the time. The context is reentrant in one process: an inner writer that runs in the same command finds the held lock and continues. A second process stops with an error that gives the path and the holder. The lock is never removed automatically. The error tells how to remove a lock that a stopped command left.
   - Use the shared lock at the command level in `decisions submit` (from the store read to `decisions_store.save`, with the nested `answer_write.add`), `audit` and other commands that call `answer_write.add`, and the facts and page writes of `extract`, `refresh`, and `render` (cli.py:532-538).
   - Model files get a lock for each file, `<model file>.lock`, in the model writer. Thus `place --map` and `review --map` on different nested parts do not stop each other. Full-tree `place` takes the lock of each model file that it writes.
   About 90 lines, plus about 20 lines of call sites.
3. **Store merge and safe restore.**
   - `decisions_store.save` reads the store again under the lock and merges the records by key before the write.
   - `decisions_submit._write_answers` (decisions_submit.py:362-372) writes `before` back only if the file still has the bytes that this command wrote. If not, it stops with an error that gives both states.
   About 40 lines.
4. **Scoped load.** `nest.load(cfg, only=None)` (nest.py has 290 lines). With a map ID, it loads the ancestors, that map, and the descendants. It does not read sibling files. `"."` selects the top map, because `.` cannot be a card ID (nest.py:116-118). `Tree.partial` tells callers that the tree is not complete. About 40 lines.
5. **`--map ID` with the scoped load on `check`, `judgement`, `rules`, `place`, `decisions list`, `review`, `describe`, and `journeys`.** These commands report only that map.
   - `check --map` does not examine page staleness. It warns about a stale plan (see the plan fields).
   - `judgement --map` says that entry coverage is not examined.
   - `place --map` writes only that model file.
   - `decisions list --map` keeps the requests with `request.map == ID` (decisions.py:99, 441-455). Its request IDs must be the same as the IDs of the full-tree snapshot that `decisions submit` uses (decisions_submit.py:78-80).
   - `review --map` already exists (review.py:329-334), but it loads the full tree (review.py:146-150). It changes to the scoped load.
   - `refresh`, `extract`, and `decisions submit` refuse `--map`.
   cli.py has 1388 lines, so the handlers go in a new module `cli_scope.py`. About 150 lines.
6. **`systemap parts [--map ID] [--json] [--stub CARD]`.** New module `parts.py`, with the plan fields above. It reuses `suggest.proposals`, `judgement.crossing_pairs`, and `journey_coverage.outside_map`. `--stub` writes a stub with positions and refuses a file that exists. The plan refuses reserved stems, prefixes that overlap, and stale digests. The join refuses a result file with an answer form other than `item` or `items`. The subcommand is registered in `cli_scope.py`. About 300 lines.
7. **New judgement kinds.** New module `nest_join.py` with `boundary flow` and `boundary import`, called from `judgement.run_tree`. It also needs:
   - the evidence for each kind (see "Join checks"),
   - the two kinds in `config.LINE_KINDS`,
   - a `Lesson` for each kind in `explain.py`,
   - the rows and fields in `judgement_json.py`.
   About 250 lines.
8. **Boundary changes in the pull request summary.** `pr_summary.py` gives changes for each map separately (pr_summary.py:129-160). Add one "boundary changes" row that connects a change to the claims of an opening card with the changes in the nested maps, and that lists each change to a boundary rule. About 60 lines.
9. **The self-map.** Add `parts.py`, `nest_join.py`, `cli_scope.py`, and the new page modules to components in `map/` (AGENTS.md).
10. **Tests**, with recorded answers and injected agents only. No test calls Jev or a coding agent.
    - `test_parts.py`: the plan fields, `level_2`, the entry assignment, the `alone` modules in a stub, the symbol claims in a stub, a group ID that is the same as an actor ID, a stub that passes `check`, the refusal of a file that exists, the reserved stems (`model`, `contract`, `plan`, `*_contract`, case), prefixes that overlap, a stale `facts_digest`, a stale `contract_digest`, the warning of `check --map`, and no warning when no plan exists.
    - `test_parts.py`: `suggest` and `parts --stub` give the same file name.
    - `test_nest_join.py`: each form of each kind, lines that do not change when counts change, and an exact answer that becomes stale when the parent flow changes.
    - `test_lock.py`: two writer processes. The store merge keeps the records of two maps. The restore does not delete the answers of a different writer. A nested lock in one process continues. Two `place --map` processes on different model files both succeed.
    - A scoped-load test with a broken sibling file, for each command with `--map`.
    - A test that `decisions list --map` and the full-tree snapshot give the same request IDs for one map.
    - A fixture with 3 levels and at least 10 maps. Today tests stop at 2 levels (nest.py:27-29). It includes a level-2 nested part that imports a module of a top sibling card.
    - A worktree round trip: a part commit on a worktree branch, a merge, and a join that reads its result file.
    - A delta test with a module that moves between two parts.
    About 700 lines.
11. **Documentation.** `docs/reference.md:587-645` gets a section about the parts procedure, the locks, `--map`, and the new kinds.

## Visual design of nested maps

Principles:
- Overview first (Shneiderman).
- A title with scope and a legend (C4 notation checklist).
- Known positions do not move (Misue et al.).
- Marks are never color only (theme.py:22-24).
- The page does not draw a relation between levels that no check confirms (issue #106: unknown is never a pass).

### V1. Each map is a linked page, and the overlay goes away

Today "Open map" shows the child in an iframe dialog (page.py:365-377, page_script.py:247-273). The top URL does not change, so a reader cannot bookmark or share a nested view, and Back does not work. At level 3 there is an iframe inside an iframe. Escape is caught only by the parent document (page_script.py:392).

Change:
- "Open map" becomes an `<a href>`. A double-click and a second Enter set `location.href` (schematic_relations.py:604-609).
- In Changes mode, the link adds `#changes` (nest.py:275 has no fragment).
- Each page already reads the theme and the motion setting from localStorage (page.py:488-503). So the frame copy (page_script.py:300-312) is not necessary.
- After the change, the CSP can use `frame-src 'none'` in place of `frame-src 'self'` (page_csp.py:91).

### V2. A full path and a title with scope

- The header becomes `<nav aria-label="Map path"><ol>` with one link for each ancestor (`../` repeated k times, then `index.html`). The current map has `aria-current="page"`. Today the header shows only the parent (page.py:251-256).
- One separator, "/", with `aria-hidden="true"`.
- The h1 shows the last segment, so the phone ellipsis does not hide the current name (page_phone.py:22-23).
- `<title>` becomes "<name> system map: Gateway/Routes (level 2)" (page.py:490).
- The data comes from `Map.id` alone (nest.py:116-122).

### V3. Neighbour cards and the parent context

- In a nested map, an actor that is an internal parent component gets the state label "in the parent map" and a corner notch. Today all actors have a dashed border and "outside" (schematic.py:421-437, 525-526). An actor that is also an actor in the parent keeps "outside".
- The inspector of a neighbour card shows:
  - the parent boundary flow,
  - the link "Show in the parent map" (`../index.html#Auth`),
  - the link "Open the map inside Auth" if that card opens a map.
- The phone "OUTSIDE" column (page_phone.py:386-399) divides into "Parent map" and "Outside".
- A small parent context mark shows at the left of the canvas: the parent cards as plain rectangles (about 40 elements), the opening card filled, and the neighbours dashed. The full mark is one link to `../index.html#<card>`. It is not shown on a phone.
  The mark has its own row below the map, above the legend, so it does not cover a card or a flow at a zoom or a position of the map (correction of 2026-11-05).

### V4. The frame and the ports

- On a nested page, a frame with the label "Inside Gateway" goes around the internal components. The actors stay outside the frame.
- Each crossing point of a flow on the frame is a port. The glossary already defines "port" (language.md:286).
- New module `place_nested.py`: `place` puts each neighbour actor in the band (top, right, bottom, left) that faces its direction from the opening card in the parent layout. In each band, the actors keep their parent order. Pinned positions win. The parent placement must exist first. The scoped load has the ancestors, so `place --map` can do this.
- A flow with an open `boundary flow` or `boundary import` line shows the line text in its inspector, and a dotted port with the text "No flow in the parent map", "No flow inside", or "Import with no flow". A port that has no open line shows no join state. The page never says "verified". The evidence state stays EXTERNAL (evidence.py:364-372).

### V5. The card that opens a map

- The stacked second card stays (schematic.py:450-457).
- A text badge "12 inside" goes in the lower-right corner.
- The `node__map` group gets `aria-hidden="true"`. The card aria-label (schematic.py:446-448) adds "opens the map Gateway with 12 components". Today the label on the `<g>` has no role, and `_no_tooltips` removes its `<title>` (page.py:514-521).
- The inspector preview (schematic_relations.py:456-466) becomes a compact silhouette: one rectangle for each nested card, plus stubs at the frame for the boundary flows. Today page.py:123-127, 637 embeds one full preview SVG for each child.
- The parent flow label gets "(3 inside)" when the nested map has more than one flow for it. The flow inspector lists the nested flows as links to `Gateway/index.html#Routes`.

### V6. The map tree

- A "Map tree" panel on every page replaces the one-level "Child maps" list (page.py:601-609). It is a nested `<ul>` of links (not `role="tree"`, so that normal link keys work).
- Each item shows the card ID, the component count, "changed" when the subtree changed, and "N findings" from the same check run.
- If the render has no finding counts, for example in `check` and `stale` renders (check.py:621-630), the item shows "not examined", not zero.
- The data is one compact list in each page: map ID, parent ID, card count, change flag, finding count.

### V7. Search across maps

- Each page embeds a search index: map ID, component ID, kind, and `plain` text cut to 60 characters. Today Find indexes only the current page (page_palette.py:151-155).
- Results from the current map come first. The other results are in "Other maps", with the hint "in Gateway/Routes".
- The key is the map ID plus the component ID, because IDs are unique only in one model (model.py:386-388). Neighbour rows come after internal rows.
- Each page embeds its own copy of the index. The static page policy has no `connect-src`, and pages open from `file://` (page_csp.py:83-95). The `live` page adds `connect-src 'self'` (page_csp.py:110-126), but the index must also work on static pages.

### V8. Changes go up the tree

- After `compared[m.id]` exists for all maps (live_render.py:70-84), the render makes one roll-up record for each map: counts of added, removed, and changed components, flows, and sequences, and a flag for a changed descendant.
- An opening card in Changes mode gets the mark "changed inside": a second outline on the back card, plus text.
- The change panel gets the section "Changes in nested maps", with one link for each map to `<path>/index.html#changes`.
- The change panel and the pull request summary get one "boundary changes" row. It connects a change to the claims of an opening card (for example, a module that moved between two nested parts) with the two nested map changes, and lists each change to a boundary rule with its reason. A reviewer accepts or refuses the boundary change from this row.
- The top summary counts all maps, with one row for each map. This agrees with pr_summary.py:129-160.
- The roll-up counts only the model change data of each map, so a source change is not counted two times.

### V9. Colors, keys, phone, and motion

- **Colors.** A nested map gets the parent color for each layer ID that the parent has. A new layer gets a color after the parent colors. This changes `nest._theme` (nest.py:146-150, 194) and `theme.resolve`. All new text marks use the current text tokens (4.5:1, theme.py:17-19).
- **Keys.** `u` goes to the parent map with the fragment of the opening card. `t` opens the Map tree. Neither key operates while focus is in a text field (page_motion.py:254). A key review is necessary before these keys are fixed. The keys sheet (page_motion.py:215-226) and the sr-only hint (page.py:592-596) change.
- **Phone.** The header shows "< Gateway" and the last segment. The Map tree is a full-height sheet. A grid row shows "Opens a map: 12 components".
- **Motion.** The design adds no animation. A later transition must stop when the reader setting is on (page_assets.py:221).
- **Page size.** The repeated inline code is about 415 KB of the 919,206-byte page of this repository (Proposal 5 measured this in the design workflow. The value is not in `bench/jev/README.md` yet, so M11 must record it again). Inline code stays for now. A shared script file needs a CSP decision.

The new code goes in new modules (`page_tree.py`, `page_context.py`, `page_phone_nest.py`, `place_nested.py`). page.py has 669 lines, schematic.py has 745, schematic_relations.py has 710, and page_phone.py has 697.

## Measurements

Each experiment writes its acceptance value in its docstring before the run. A test with people (M13, M17, M18) has no docstring. For those tests, a written protocol with the acceptance values goes in `bench/jev/README.md` before the first session. All results go in `bench/jev/README.md`, including failures. No value below is measured now. The acceptance values are targets that the maintainer can change before a run, not after it.

| ID | What | Acceptance value |
|---|---|---|
| M1 | Full-tree `check`, `judgement`, `refresh` on big5 (about 4,250 modules) divided into 10, 25, and 50 nested maps on 3 levels | Time at most 1.5 times the same commands on the unsplit fixture (a baseline for `check` is necessary. `extract` is 45 to 51 s today). Peak RSS at most 600 MB. |
| M2 | `check --map ID` with the scoped load on the 50-map tree | Time at most 0.5 times the full-tree `check`. A syntax error in a sibling model file does not change the exit code. |
| M3 | `systemap parts --json` on big5 | At most 10 s and 50 MB peak RSS above the facts read. Output at most 50 MB. |
| M4 | Size of a nested model with 40 components, flows, sequences, and positions | At most 256 KB and 50,000 values (50 percent of model_load.py:45-46). If not, `parts` must use a lower component limit. |
| M5 | Join round trip: divide the self-map (178 modules) into parts that copy its current cards and flows | 0 `boundary flow` lines, 0 `boundary import` lines, and the same `check` and `rules` results as before the division. |
| M6 | Locks: 100 runs of two `decisions submit` processes at the same time with different verdict files, and 100 runs of two `place --map` processes on different nested parts | 0 lost answer rows, 0 lost store records, each refused `submit` run exits non-zero with the lock error, and 100 percent of the `place --map` runs exit 0. |
| M7 | Part size for one part agent: 50, 100, 200, and 400 modules | Complete (check exit 0, all lines with a verdict or an answer, no card above 10 modules) with no context compaction in at least 4 of 5 runs. Record the largest size that passes. |
| M8 | Process quality: this repository mapped by one agent, by the sequential parts procedure, and by 3 and 5 parallel part agents | After the join, `check` exits 0. Open judgement lines are at most 1.1 times the one-agent count. At least 90 percent of the top flows of the one-agent map are in the parts map. Parallel wall time is at most 0.6 times sequential. Total tokens are at most 2 times the one-agent run. |
| M9 | Maintenance threshold: the number of affected parts at which sub-agents use fewer tokens than one agent, on 3 deltas | The threshold differs by at most 1 part across the 3 deltas. Only then does the skill get a threshold. |
| M10 | Three levels: the 3-level fixture | `check`, `judgement`, `refresh`, `place`, and `delta` exit 0. Pass or fail. |
| M11 | Page size for 50 maps on 3 levels, 40 cards at most | Each page at most 1.5 MB. Tree and search index at most 150 KB for each page. Parent context mark and compact preview at most 8 KB each. Full output at most 75 MB. |
| M12 | Page load to an interactive map, 40-card nested page, Playwright on CI | At most 1.5 s in Chromium and Firefox. |
| M13 | Accessibility: axe-core on a level-3 page in Ink and Paper, NVDA with Firefox, and VoiceOver with Safari | 0 serious or critical issues. A tester reaches the path, the Map tree, and Back with keys only. |
| M14 | Contrast of the new text marks in Ink and Paper (tests/test_theme.py) | At least 4.5:1 for text and 3:1 for lines. |
| M15 | Phone at 360 x 740 px on a level-3 page | No horizontal scroll. Tap targets 44 px or more. The last segment of the path is not cut. |
| M16 | Same-side rule on the fixture | 100 percent of neighbour actors are in the band that agrees with the parent direction. |
| M17 | Reviewer test: a PR with one planted boundary change in a level-2 or level-3 map | At least 8 of 10 reviewers find it from the top page in Changes mode. Median time at most 2 minutes. |
| M18 | Comprehension test, current overlay against linked pages, 3-level tree | At least 8 of 10 participants complete each task (name the level, name the parent of a neighbour, find a component in a different map, go back to the top). Median at most 60 s for each task. |
| M19 | `extract` and full-tree `check` on a fixture with more than 10,000 source files (issue #92) | `extract` at most 5 minutes and 2 GB peak RSS. Full-tree `check` at most 2 minutes. If not, Phase A cannot be recommended for that size, and the skill says so. |

## Risks and open questions

- **Different decisions in each part.** Part agents can use different naming styles or detail levels inside the fixed words (Cognition). The join checks find structural disagreement, but they do not find word meanings. The final language pass and a person must examine the text. The quality that remains is not measured (M8).
- **A wrong contract.** If the top map is wrong, the part agents find the errors late. A module move makes two parts start again, and their verdict files must be made again. Many boundary requests remove the gain of parallel work.
- **A large first step.** For about 4,250 modules, Phase A is a large step for one agent. Its cost is not measured. Above 10,000 files, the extract and check cost is not measured (M19, issue #92).
- **Boundary rules record bad imports.** The rules describe the source at the contract commit. They do not show that the boundary is correct. The reasons must say this. Each later change to a rule shows in the "boundary changes" row for a reviewer.
- **Results of a scoped run.** A run with `--map` does not have the global entry coverage or the top coverage. The skill and the output must say that only the full-tree run is authoritative.
- **A lock that stays.** A stopped command can leave a lock file. Only a person removes it. The error gives the path, the process ID, and the time.
- **Write sets are not enforced.** The examination with Git finds files outside the write set after the work. It does not prevent the change. A rejected part is reverted by its commit.
- **Worktrees are necessary for parallel mode.** An agent that cannot make a worktree for each sub-agent must use sequential mode. Some agent platforms can share one checkout among sub-agents by default. This statement is not verified for any named platform, and the design does not use it to select a default.
- **Partial adoption.** A portable skill can ask for sub-agents only in prose (the Agent Skills specification has no field for this). Some agents ignore the request. The sequential path must give the same result.
- **Token cost.** For small trees, sub-agents can cost more than they save. The skill must not recommend sub-agents for two or fewer parts until M8 and M9 show a gain.
- **Many boundary lines.** `boundary flow` can give lines for a parent flow that is a summary with no single inside end. The answers are then necessary. The rate of such lines is not known.
- **Visual changes for current users.**
  - Layer color inheritance changes colors on current nested pages.
  - The removal of the overlay removes the feel of opening a map in place. If M18 fails, the overlay must not come back unless the URL, Back, and Escape problems are corrected.
- **Page weight.** Each of 50 pages embeds the indexes and about 415 KB of repeated code. A shared script needs a CSP decision and can fail on `file://`.
- **Open questions.**
  - Is a `repeated cover` kind necessary, or is the entry assignment of the plan enough? M8 decides.
  - Can a sibling import give `Layer` values from a shared module under the default reader? A test is necessary before the design uses a `map/shared.py`. Until then, the words go in the top `MEANING` and in the plan.
  - Which value replaces the temporary limit of five parallel part agents? M8 decides.
  - Is category 19 correct for the new glossary nouns, and is "nested part" permitted? A maintainer with the official dictionary decides.
  - The in-place zoom of Proposal 4 stays an option. It needs proof that the hidden-iframe loader works from `file://` in Chrome, Firefox, and Safari.

## Rollout in steps

Each step is a separate pull request. Each pull request passes the required checks of AGENTS.md: `uv run pytest`, `uv run pre-commit run --all-files`, `uv run mypy src --strict`, `uv run systemap refresh`, `uv run systemap check`, and `uv run systemap judgement`.

1. **Corrections and write safety.** `parts.file_name` and the suggest.py:194-197 text, the reentrant lock (`file_write.exclusive`), the locks for each model file, the store merge, the safe restore, and `test_lock.py`. Then run M6. This step is useful without the rest of the design.
2. **A fixture with 3 levels and scoped commands.** The 3-level fixture with 10 or more maps, `nest.load(only=)`, `--map` on `check`, `judgement`, `rules`, `place`, `decisions list`, `review`, `describe`, and `journeys`, and `cli_scope.py`. Then run M1, M2, M10, and M19.
3. **The part plan.** `parts.py` with `--json`, `--map`, and `--stub`, reserved stems, prefix overlap, the two digests, the result-file validation, `test_parts.py`, the worktree round trip test, and the self-map update. Then run M3 and M4.
4. **The new judgement kinds.** `nest_join.py`, the evidence for each kind, `config.LINE_KINDS`, the `explain.py` lessons, `judgement_json.py`, and `test_nest_join.py`. Then run M5. Add a release note, because current trees with nested maps can get new lines.
5. **Skill and documentation.** The SKILL.md lines and the References row, `references/parts.md`, the pointers in layout.md, second-pass.md, maintenance.md, and decisions.md, the glossary rows and the technical verb, and `docs/reference.md`, in all three skill directories. A maintainer examines the language before the merge.
6. **Visual step 1: navigation.** Linked pages in place of the overlay, the full path, the title with scope, `#changes` links, the aria-label correction, the phone header, and the keys. Then run M12, M13, and M15.
7. **Visual step 2: boundaries.** Neighbour labels, the parent context mark, the frame and ports with the lines of the new kinds, `place_nested.py`, the "N inside" badge, compact previews, and layer color inheritance. Then run M14 and M16.
8. **Visual step 3: the tree.** The Map tree panel with finding counts, search across maps, the roll-up of changes, and the "boundary changes" row in the page and in `pr_summary.py`. Then run M11 and M17.
9. **The process experiments.** The bench experiments M7, M8, M9, and M18 with real agents (not in tests). Their acceptance values are in the docstrings or the written protocols before the runs, and all results, including failures, go in `bench/jev/README.md`. Change the temporary values in `parts.md` only after these results.

## Changes from revision 1

| # | Problem in revision 1 | Correction |
|---|---|---|
| 1 | The plan and the result files were in the Git-ignored `.systemap/` folder (file_write.py:245-269), so a worktree merge lost them. | They are in the tracked folder `map/parts/`. The final join commit removes it. A worktree round trip test. |
| 2 | In a shared checkout, the write-set examination could not tell which part changed a file. | Parallel mode requires worktrees. Sequential mode commits after each part. The examination compares commits. A rejected part is reverted by its commit. |
| 3 | A full-tree `place` or `submit` could run while parts were in rework. | A barrier. `place --map` for each part at the join. The rework round comes before the full checks. |
| 4 | A stub failed `check`: it had no positions and no component for `alone` modules. | `--stub` gives positions, a `<Card>Other` component, unchanged symbol claims, and refuses an ID that is the same as an actor ID. |
| 5 | The lock was not reentrant, so `decisions submit` refused itself, and parallel `place --map` runs stopped each other. | A reentrant lock at the command level, and a lock for each model file. Tests for both. |
| 6 | The import rule did not work at level 2, and level-2 actors must be direct-parent components. | The owner is the nearest ancestor component, mapped to an actor of the current map. The level-1 map must have that actor first. A 3-level test. |
| 7 | The new kinds had no evidence digest, no `LINE_KINDS` entry, and no `Lesson`. | Evidence for each kind, both kinds in `LINE_KINDS`, a `Lesson` for each, a staleness test. |
| 8 | The reserved names did not include `contract` or `plan`, did not compare case, and the prefixes could overlap. | Reserved stems `model`, `contract`, `plan`, `*_contract`. Lower-case comparison. The prefix `<stem>_`, with an overlap examination. |
| 9 | Boundary edits came before the submit, which made the verdict files not current (decisions.py:214-218). | Submit the untouched parts first. Touched parts make their verdict files again. |
| 10 | `review`, `describe`, and `journeys` loaded the full tree. | They get `--map` with the scoped load. `triage` is prohibited for part agents. A request ID test. |
| 11 | The plan digest did not find a change to the contract, and `check --map` failed on a stale plan. | `contract_digest`. Only `parts` and the join refuse. `check --map` warns, and says nothing if no plan exists. |
| 12 | A level-2 part agent could not run `refresh`. The SKILL line said "main agent". | Level 2 uses `check --map`. The SKILL line says "the agent of the parent map". The depth claim now has a source. |
| 13 | The SKILL text "Commands examine every nested map" became false, and the References list had no row for parts.md. | "Commands without `--map` examine every nested map." Lines 173 and 174 join to give space for the References row. The total stays at 240 lines. |
| 14 | The glossary rows had no category, "part" is an ordinary word, unapproved verbs, a semicolon. | Category 19 (to be examined), "nested part", "write a stub" and `--stub` in place of "seed", "merge" as a technical verb for Git only, no semicolon. |
| 15 | M8, M9, M13, M17, and M18 had no acceptance value or protocol. Nothing above 10,000 files. | Token and threshold values. Written protocols for the tests with people. M19 for issue #92. |
| 16 | The suggest.py text did not agree with the file-name rule. | One function `parts.file_name` for both, and a test. |
| 17 | The prohibited answer forms did not include `crossing_into` and `crossing_from`. | Part agents use only `item` and `items`. The join refuses other forms. |
| 18 | A new cross-part import made CI fail, with no step for a reviewer. | Maintenance step 2 updates the boundary rule with a reason. A "boundary changes" row in the page and in `pr_summary.py`. |
| 19 | Wrong citations. | model_load.py:45-48, nest.py:23 and 26, check.py:779, check.py:253-297, cli.py:1102-1110 and review.py:329-334, language.md:286, judgement.py:204-221 and 230, page_csp.py:110-126. These were examined against `origin/main` on 2026-11-04. |
| 20 | Statements about agent platforms had no source. | The Claude Code depth limit and context isolation and the Anthropic token value now have URLs and dates. The "subagent output to a filesystem" quote was not in the article, so it is replaced by the article's own words. The Cursor and Codex statements are removed, and no default depends on them. |
