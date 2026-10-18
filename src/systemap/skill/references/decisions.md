# Decisions: examine the claims of the map

The `systemap decisions` commands give the claims of the map to you, the coding agent.
You examine each claim against the source code in your current session.
Then systemap examines your verdicts and records the correct verdicts.
The commands send no request to a model and send no question to a person.

## Decision requests

A decision request is one claim that you must examine. Each decision request has one of these types:

| type | claim | result of `supported` |
|---|---|---|
| `judgement` | An open judgement line. | systemap adds an exact answer to `[judgement] answered`, with your citations. |
| `source_review` | A component with a missing or stale source review. | systemap records the current `source_review` digest. |
| `flow_review` | A flow with a `review_digest` that is not current. | systemap records the current `review_digest`. |

Each decision request has an `id`. If the claim does not change, the `id` stays the same in a different session.

## Procedure

1. Run `systemap refresh`. The commands reject facts that do not agree with the source code.
2. Run `systemap decisions pending --json`. Read the `claim`, `files`, `blocked`, and `insufficient` fields of each decision request.
3. Read the source files of each claim. Compare the source code with each part of the claim.
4. Select one verdict for each decision request:
   - `supported`: the source code agrees with the full claim.
   - `contradicted`: the source code does not agree with the claim.
   - `insufficient_evidence`: the source code does not give sufficient data for a decision.
5. Write a JSON list with one object for each verdict:

   ```json
   {"request_id": "<id>", "verdict": "supported",
    "citations": [{"file": "pkg/reader.py", "start_line": 1, "end_line": 12, "sha256": "<digest>"}],
    "summary": "<one sentence about the source code>"}
   ```

6. Write the source hash of the full file in `sha256`. The `files` rows of the decision request give it.
7. Run `systemap decisions submit FILE`. If the command rejects one verdict, it writes no file. Correct each error. Then run the command again.
8. If a verdict is `contradicted`, correct the map. Then run `systemap refresh` and do this procedure again.
9. Run `systemap decisions status`. In your report, give each unknown decision request, its CI result, and its verdicts.

## Rules

- With Jev, use the sequence from `systemap judgement --order-by-drift` to select the first stale component, but examine all stale components.
- Do not record `supported` without a citation. A verdict of `supported` must refer to a file of the claim.
  For a flow, the files of the claim are the files of the two endpoint components.
- Refer only to the lines that you read. Do not refer to a file that you did not read.
- A citation can refer to a source file or a test file that the facts list.
- Obey the writing profile in the summary. The summary of a `supported` judgement verdict becomes the recorded answer reason.
- If a decision request has a `blocked` value, do not send `supported`. Do the step in the `blocked` text.
- Stop at `unknown`. An unknown decision request does not show that the claim is correct.
  Do not send a verdict for it. `systemap decisions status` exits 1 while a decision request is unknown.
- The CI result of an unknown decision request is in its `CI:` row and its `open_lines`.
  An open judgement line of the claim stays open. Thus `systemap judgement --strict` exits 1.
  If the claim has no open judgement line, `systemap judgement --strict` does not exit 1 because of the claim.
- After one `insufficient_evidence` verdict, you can send one more verdict for the decision request.
  Before it, examine more of the source, for example other files.
  After 2 verdicts of `insufficient_evidence` for the same target, the decision request becomes `unknown`.
- After `[decisions] max_contradicted` verdicts of `contradicted` for the same target, the decision request becomes `unknown`. The default is 3.
  A change of the map claim does not set the count to zero.
- If a source file of the target changes, the decision request becomes pending again, with zero `contradicted` and zero `insufficient_evidence` verdicts.
- The limits stop work that occurs again and again. They do not stop an agent that sends `supported` for a claim that it wrote.
  Thus the decision store keeps each verdict, and `systemap decisions status` shows each verdict.
- systemap rejects `supported` for the source review of a component if a flow of that component is `contradicted` or `unknown`. Correct the flow first.

## Decision store

systemap records the verdicts in the decision store, `.systemap/decisions.json`. Git does not record this file.
`supported` in `systemap decisions status` counts the `supported` verdicts of the current claims.
`supported_records` counts all `supported` verdicts in the decision store, also for claims that are not current.
To start new counts, remove the file.

If the file does not contain correct JSON, or has a different version or form, the commands stop with exit 1. The error gives the path and the cause.
Then remove the file.

## Assurance level

`systemap judgement --json` gives each claim an assurance level in `assurance`. The page gives it in the panel.

- `established`: the facts show the full claim. Only an import rule with the result `pass` gets this level.
- `examined`: a current source review or a current flow review records that an agent or a person examined the claim against citations. A `supported` verdict writes this source review. The facts do not show the claim.
- `unknown`: the facts and the source reviews do not show the claim. Do not count it as the result `pass`.

The freshness is a different value: `current`, `earlier`, `stale`, or `missing`. A stale source review gives `unknown`.
In a report, do not write "verified" or "proven" for an `examined` claim. Write "examined".
