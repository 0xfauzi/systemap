# Layers: the standard readings, then the model's own

A layer is one reading of the map: the page shows one at a time, and each
answers a question. Most are derived; you declare only the ones the
repository's own vocabulary supports.

## The two derived layers

Nothing in the model produces these; the renderer computes them from the
topology.

- **Structure**: every component inside its region and container, no
  edges. The component view. Question: "What are the parts, and where does
  each sit?" The page opens here.
- **System context**: the actors outside the package and every edge that
  crosses the package boundary (an actor at either end), drawn in one hue;
  internal edges dimmed. The system-context view. Question: "Who and what
  is outside, and how does it reach in?"

## The two standard kinds

Every flow has a kind. Two kinds are standard, need no declaring, and every
model uses them:

- `data`: an artifact moves. A file, a record, a message, a response, a
  request. Layer "Data flow". Question: "What moves, and where does it go?"
  Verbs: hands to / receives from.
- `control`: one part invokes, schedules or drives another. A call, a
  command, an event, a scheduled run. Layer "Control flow". Question: "Who
  drives whom?" Verbs: drives / is driven by.

How to choose: name the artifact first. If the sentence is "A gives B an
X", the kind is data and X is the artifact. If the sentence is "A makes B
run" and no artifact of note travels, the kind is control and the artifact
is the call or the command. When both are true (A calls B with a request),
prefer data when the reader needs to know what travels and control when the
reader needs to know who is in charge; one flow, one kind. A model with no
control flow at all gets a judgement line asking whether one was missed.

## A kind of your own

When the repository's vocabulary has a reading of its own (`measure`,
`feedback`, `record`), declare the kind in `flow_kinds`, give it a `Layer`
in `Meaning.layers` written as the question it answers, and map it in
`layer_of_kind`. Give it a verb pair in `verbs`. Move a single edge to
another layer with `layer_overrides` when its kind's layer is the wrong
reading for that one edge. Custom layers follow the standard ones in the
page order and take the theme's palette in turn.

Page order: Structure, System context, Data flow, Control flow, then
Agents, Context and Tools when the model has an agent, then the model's
own layers, then All.

## Agentic systems

When a part of the system runs a model and acts on its output, the map
needs to show the agents, what enters their windows, and what they can
do. Three component kinds and two flow kinds exist for that.

- `kind="agent"`: a part that runs a model and acts on its output. Find
  them by the call: the facts record each module's third-party imports
  under `external`, and `systemap judgement` prints `model sdk: module X
  imports <sdk> and its component P is not an agent` for a built-in list
  of model SDKs and agent frameworks (extend it with `[facts] model_sdks`
  in `systemap.toml`). A module that calls a coding-agent CLI through a
  subprocess is found by reading it. Drawn with an inner ring.
- `kind="context"`: a store whose content enters an agent's window: a
  system prompt, a prompt template, a memory file, retrieved knowledge,
  injected facts, a conversation log. Find them by what is read before or
  during a turn: prompt files and the modules that render them, memory,
  retrieval, anything assembled into the window. Drawn dotted.
- `kind="tool"`: a capability an agent invokes with arguments: a shell,
  an API, a search, a file editor, a test runner. Find them by what the
  agent calls with arguments and reads the result of. Drawn with a
  notched corner.
- `Flow(src, dst, artifact, "context")`: content entering an agent's
  window. `src` is the source of the content, `dst` the agent. The check
  refuses a context flow whose destination is not an agent. Layer
  "Context": "What enters each agent's window, and from where?"
- `Flow(src, dst, artifact, "tool")`: an agent invoking a tool. `src` is
  the agent, `dst` the tool; the artifact is the call or its result. The
  check refuses a tool flow whose source is not an agent. Layer "Tools":
  "What can each agent do, and through what?"

The Agents layer appears with the first agent: every agent card and every
edge that touches an agent, in one hue. Question: "Which parts run a model,
and what do they reach?"

An agent, a tool and a context card are code in the tree like any other
component: each names its modules and an entry they define. A tool that is
genuinely outside the package (a remote service the agent calls) is an
actor, and the flow to it is still a tool flow. Write one journey per
agent's turn: what enters the window, what the model returns, what the
agent invokes, what it writes back.
