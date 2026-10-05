# Layers and flow kinds

A layer shows the components and flows that answer one system question.
The page shows one layer at a time.
Use the language policy in `language.md` for new labels and questions.

## Derived layers

The renderer computes these layers from the model:

- **Structure** shows every component in its region and container, without flows.
  The page starts with this layer.
- **System context** shows external actors and flows across the code boundary.
  Internal flows are dimmed.

## Standard flow kinds

Each flow has one kind:

- `data` carries an artifact such as a file, record, request, or response.
- `control` causes another component to execute an operation.

First identify the artifact. Use data when the reader must know what moves.
Use control when the reader must know which component starts an action.
If both apply, select the kind that best answers the reader's question.
Keep one flow per ordered component pair.
A model without control flows receives a finding about possible missing flows.

The standard layers are Data flow and Control flow.
Use literal direction verbs, such as sends to / receives from.
Do not use a physical metaphor for a software action.

## Custom layers

For another question with source evidence, declare a kind in `flow_kinds`.
Add its `Layer` to `Meaning.layers` and its mapping to `layer_of_kind`.
Add its direction verb pair to `verbs`.
Use `layer_overrides` when one flow must use a different layer from its kind.
Custom layers receive palette colors in order.

Page order is Structure, System context, Data flow, and Control flow.
Agents, Context, and Tools follow when the model has a model-calling component.
Custom layers follow those layers. All is the final selection.

## Agentic systems

A model-calling system must show model inputs and tool operations.
Use these component kinds and flags:

- `kind="agent"`: a component that calls a model and acts on its output.
  Its card has an inner ring.
- `calls_model=True`: a component that calls a model without classification as an agent.
  Its context and tool flows are available in those layers.
  The Agents layer does not include it.
- `kind="context"`: stored data that enters a model context window.
  Examples include prompts, memory files, search result records, and conversation logs.
  Its card has a dotted outline.
- `kind="tool"`: a program capability that the agent calls with arguments.
  Examples include a shell, API, file editor, or test runner.
  Its card has a notched corner.

The repository's own agent definition has precedence over an SDK-based suggestion.
A single model call can stay a component with `calls_model=True`.
Read subprocess code to find calls to a coding-agent CLI.

The facts list third-party imports under `external`.
The `model sdk` finding identifies model SDK imports without a model-calling component.
Configure import prefixes under `[facts] model_sdks`.
A prefix also matches framework tool and session modules.
Use a leading minus, such as `"-google.adk"`, to remove a built-in prefix.
Do not classify all framework modules as agents only because of their imports.

Use these flow kinds for model operations:

- `Flow(src, dst, artifact, "context")` supplies data to an agent or `calls_model` component.
  A different destination is invalid.
- `Flow(src, dst, artifact, "tool")` starts a tool operation from an agent or `calls_model` component.
  A different source is invalid.

The Context layer shows context flows and their source components.
The Tools layer shows tool flows and their destinations.
The Agents layer shows components of kind agent and their applicable flows.
The model schema and structural checker keep these endpoint rules consistent.

## Evidence across layers

An import or common module gives structural evidence only.
A configured mechanism in `[flows] observed_by` also gives structural evidence only.
This evidence does not show the direction or artifact.
For `observed`, examine source and record current `source_refs` and `review_digest`.
A declared flow has no structural or examined source evidence.
Layer selection must not change an evidence state or hide its uncertainty.
