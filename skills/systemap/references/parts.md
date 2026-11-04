# Map a large system in nested parts

## Contents

- When to use this procedure
- Terms
- Step 1. Write the top map
- Step 2. Write the boundary rules
- Step 3. Write the stubs
- Step 4. Start the part agents
- Rules for a part agent
- The result file
- Step 5. Examine the nested parts together
- Nested parts inside a nested part
- Without sub-agents
- After a source change
- Completion conditions

## When to use this procedure

Use this procedure when the map needs two or more nested maps. For one nested map, do not divide the work.
The steps and the checks are the same with sub-agents and without sub-agents.

## Terms

The glossary in `references/language.md` gives the meaning of these terms:
main agent, sub-agent, nested map, nested part, part agent, part plan, result file, write set, stem, file prefix,
map prefix, boundary flow, boundary import, boundary request, contract commit, stub, and Git worktree.
Without sub-agents, the main agent is also the part agent of each nested part.
The plan of the top map is `map/parts/plan.json`.

The stem of a nested map is its map ID in lower case, with `_` in place of each `/`. For example, the map `Gateway/Routes` has the model file `map/gateway_routes.py`.
`systemap parts --map ID --json` gives the model file, the contract file, the file prefix, and the result file of each nested part.

## Step 1. Write the top map

The main agent does steps 1, 2, and 3 alone.

1. Run `systemap extract` and `systemap suggest`. `suggest` gives package groups, the crossing imports between them, and the components above ten modules.
2. Write the top map with forty components or fewer. Give each module a component assignment on the top map. Coverage counts only on the top map.
3. In the top `MEANING`, write the layer IDs and questions, the regions, and the flow artifacts between top components.
   Part agents must use these names. Use the same layer IDs in all maps, so that the colors stay the same.
4. For each `crossing import` line between top components, write a flow with an artifact, or record an answer. These flows are the boundary flows.
5. Select the nested parts. A component with more than ten modules is a candidate. Do not make nested parts for the small components.

## Step 2. Write the boundary rules

For each nested part, write one `allow_imports` rule in `map/contract.py`.
Its `src` is the component that opens the nested map. Its `dst` gives the components that this component imports at this commit.
The reason gives the commit. It must also say that the rule records the current imports and does not show that the boundary is correct.
Write the rule in the parent contract. A nested contract cannot give a rule about a sibling nested part, because its actors have no module claims.

## Step 3. Write the stubs

If a component has `map=` and its file is missing, every command fails. Thus do these steps in this sequence for each nested part:

1. Run `systemap parts --stub CARD`. CARD is the component that opens the nested map.
   The stub has one component for each `suggest` group and a component `<CARD>Other` for the modules alone in their package.
   It also has the symbol claims of the card, the actors, and positions.
   The command does not write over a file. If the stub has a problem, the command writes no file and gives the problem.
   For example, a group ID can be the same as an actor ID. Then write the stub yourself with a different ID.
2. Set `map="<file>"` on the component, with the value that the command gives.
3. Run `systemap refresh` and `systemap check`. Both must exit 0.

Then run `systemap parts`. It writes the part plan. Commit the top map, the contract, the stubs, the `map=` fields, and `map/parts/`. This commit is the contract commit.

## Step 4. Start the part agents

Give each part agent its own Git worktree from the contract commit. In one shared folder, the main agent cannot find in step 5 which agent changed a file.
Git does not track `.systemap/`. Thus copy `.systemap/decisions.json` into each worktree before its part agent starts.
The lock `.systemap/write.lock` stops a second writer only in the same folder.
Start five part agents or fewer at one time. This limit is temporary. A measurement is necessary to replace it.
A sub-agent starts without the text of your session. Thus give it this full message, with the values from `systemap parts --map <MAP ID> --json`:

```text
Read <skill>/SKILL.md, <skill>/references/parts.md, and <skill>/references/language.md.
The writing profile is <profile>.
Map the nested part <MAP ID>. Get its record with: systemap parts --map <MAP ID> --json
Write only these files: <model_file>, <contract_file>, <result_file>,
  and new model files whose names start with <file_prefix>.
  If your record has level_2 true, also the JSON files in map/parts/ whose names start with <stem>_.
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

The files are the result. The summary only tells the main agent where to read.

## Rules for a part agent

- Change only the files of your write set. Do not write `systemap.toml`, `.systemap/decisions.json`, the parent model, the parent contract, the plan, or `docs/map/`.
- Do the loop in SKILL.md on your map only:
  1. Replace the stub components with components for tasks, with 3 to 10 modules each.
  2. Write the flows. Use the given artifacts for the flows to actors.
  3. Write the sequences only for the `entry_points` of your record.
  4. Write the invariants and the internal import rules in your contract file. These rules can refer only to internal components.
  5. Run `systemap place --map ID`, `systemap check --map ID`, and `systemap judgement --map ID`.
  6. Run `systemap decisions pending --map ID --json`. Write your verdicts in the result file.
  7. Examine your names and sentences against `references/language.md`.
- Record answers only in the forms `item` and `items`. The other forms apply across maps. Put such an answer under `proposed_answers`.
- If a different command holds `.systemap/write.lock`, stop and tell the main agent. Do not remove the lock.

## The result file

The result file is `map/parts/<stem>.json`. Copy `base_commit`, `facts_digest`, and `contract_digest` from the plan.

```json
{"map": "Gateway", "base_commit": "...", "facts_digest": "...", "contract_digest": "...",
 "files": ["map/gateway.py", "map/gateway_contract.py"], "check_exit": 0, "open_lines": ["Gateway: ..."],
 "verdicts": ["<rows in the form of systemap decisions submit FILE>"],
 "answers": [{"line": "Gateway: ...", "form": "item", "reason": "..."}],
 "proposed_answers": [{"form": "kind", "value": "...", "reason": "..."}],
 "boundary_requests": [{"kind": "move_module", "subject": "...", "reason": "...", "source_refs": ["..."]}],
 "questions": ["..."]}
```

The request kinds are `move_module`, `add_flow`, `remove_flow`, and `artifact`.

## Step 5. Examine the nested parts together

Start this step only after each part agent has stopped and has committed. For each nested part, in the plan `order`:

1. Run `git diff --name-only <commit before the part> <part branch>`. Each file must be in the write set.
   With worktrees, the commit before the part is the contract commit. Without sub-agents, it is the last commit before the nested part.
   If a file is not in the write set, do not merge the branch. Without sub-agents, revert each commit of the nested part with `git revert --no-edit`.
   Then send the nested part back.
2. Merge the worktree branch of the nested part. Without sub-agents, its commits are already on the branch.
3. Run `systemap parts --results`. If it gives a problem for the nested part, send the nested part back.
   After step 6, a nested part that step 5 submitted shows a different `contract_digest`. Do not send it back for this problem.
4. Run `systemap check --map ID`. It must exit 0.

Then for the full tree:

5. For each nested part that no boundary request changes, run `systemap decisions submit FILE` with its verdicts. Then record its answers in `systemap.toml`.
   Do this before a boundary change, because a boundary change makes the verdicts not current.
6. Decide each boundary request. For an accepted request, change the top model or the top contract. Then run `systemap parts` again and commit.
   Send each changed nested part back with the request and this note: "Make the verdict file again. The verdicts of the earlier file are not current."
7. Send each nested part back one time if it has open lines or if step 6 changed it. Put the lines in the message.
   Give each of these nested parts a worktree from the last commit, so that it copies the digests of the new plan.
   Then do items 1 to 5 for these nested parts. After that, correct the lines that stay open yourself.
8. Run `systemap place --map ID` for each nested part. Then run `systemap refresh`, `systemap check`, `systemap rules`, and `systemap judgement`.
   Only this run without `--map` gives the result.
9. Examine all new names and sentences of the tree in one pass. Thus the words agree across the nested parts.
10. Remove `map/parts/` and commit.

| kind | agent that acts first | action |
|---|---|---|
| `boundary flow` | main agent | Add the missing flow in the nested map or in the parent map. Or record why the parent flow has no single nested end. |
| `boundary import` | part agent | Add the actor and a flow with source evidence, or write a boundary request. |

## Nested parts inside a nested part

A nested part with more than 400 modules has `level_2` true in the plan. Its part agent does steps 1 to 5 inside its nested part, with these changes:

- It obeys the rules for a part agent and does not run the commands that its message prohibits. In step 1, it does not run `systemap extract`.
- In step 5, it does not do items 5, 8, and 10. It runs `systemap parts --map ID --results` in place of `systemap parts --results`.
- Its write set also has the plan and the result files of its nested parts: the JSON files in `map/parts/` whose names start with its stem and `_`.
- Its own map is the parent map of its nested parts. It does not change the module claims of that map.
- `systemap parts --map ID` also writes the plan of its nested parts, for example `map/parts/gateway_plan.json`.
- `systemap parts --map ID --stub CARD` writes each stub. Then run `systemap check --map ID` in place of `refresh` and `check`.
- The actors of a nested map must be components of its direct parent map. If a stub needs an actor that its own map does not have, first add that actor to its map.
- It writes its boundary rules in its own contract file. It puts the verdicts and answers of its nested parts in its own result file.
- If it cannot start sub-agents, it does its nested parts in sequence.

## Without sub-agents

Do steps 1 to 3. Then do one nested part at a time, in the plan `order`. Use the message of step 4 as your task.
Write the result file and commit after each nested part.
If you must start again in a new session, read the plan and the result files first.

## After a source change

1. Run `systemap extract` and `systemap delta --base REF`. A line of a nested map starts with its map prefix, for example `Gateway: `.
2. First, do the lines without a map prefix and the `systemap rules` failures.
   Give each new module a component assignment on the top map. The nested map then gives a line for the missing claim.
3. If a boundary rule fails, examine the import. If the import is correct, add the component to `dst`. Give a reason with the commit.
4. A component that gets more than ten modules can become a new nested part. Use step 3 for it.
5. Step 5 removed `map/parts/`. Thus run `systemap parts` again and commit. This commit is the new contract commit.
6. Use the map prefix of each other line to find its nested part. For each nested part with lines, use the message of step 4 with its delta lines.
   If two or fewer nested parts change, do them in sequence.
   If more than one-third of the components of a nested part change, make its nested map again.
7. Do step 5.

## Completion conditions

- The completion conditions of `references/second-pass.md` apply to the full tree.
- No `boundary flow` or `boundary import` line stays without an action or an answer.
- No nested component has more than ten modules, or the result file gives the reason.
- No result file has an open question.
