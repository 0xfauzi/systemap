"""The state machines of the map of this repository."""

from systemap import State, StateMachine, Transition

MACHINES = (
    StateMachine(
        id="source-review",
        label="Source review of a component",
        of="Model",
        start=("missing",),
        states=(
            State(
                "missing",
                "systemap.card_review.MISSING",
                "The component has no source_review value.",
            ),
            State(
                "current",
                "systemap.card_review.CURRENT",
                "The source_review value is the current digest.",
            ),
            State(
                "stale",
                "systemap.card_review.STALE",
                "The source_review value is not the current digest.",
            ),
        ),
        transitions=(
            Transition(
                "missing",
                "current",
                "review",
                cause="systemap review COMPONENT writes the current digest in the model file.",
                flow="Agent->CLI",
                journey="record-review",
                source="systemap.card_review.state",
            ),
            Transition(
                "current",
                "stale",
                "source or claims change",
                cause="The source or the claims of the component change. Then the digest is different.",
                flow="Agent->Model",
                source="systemap.card_review.state",
            ),
            Transition(
                "stale",
                "current",
                "review",
                cause="A person or an agent examines the claims again. Then systemap review writes the current digest.",
                flow="Agent->CLI",
                journey="record-review",
                source="systemap.card_review.state",
            ),
        ),
    ),
    StateMachine(
        id="flow-review",
        label="Review of a flow",
        of="Model",
        start=("missing",),
        states=(
            State(
                "missing",
                "systemap.flow_review.MISSING",
                "The flow has no source records or no review digest.",
            ),
            State(
                "current",
                "systemap.flow_review.CURRENT",
                "The review digest agrees with the claim and the cited source.",
            ),
            State(
                "stale",
                "systemap.flow_review.STALE",
                "The cited source or the flow changed after the review.",
            ),
            State(
                "earlier",
                "systemap.flow_review.EARLIER",
                "The review is earlier than source tracking. Its digest does not identify the examined source.",
            ),
        ),
        transitions=(
            Transition(
                "missing",
                "current",
                "review --flow",
                cause="systemap review --flow writes the review digest of the flow.",
                flow="Agent->CLI",
                journey="record-review",
                source="systemap.flow_review.form",
            ),
            Transition(
                "current",
                "stale",
                "cited source or flow changes",
                cause="The cited source or the flow claim changes. Then the digest is different.",
                flow="Agent->Model",
                source="systemap.flow_review.form",
            ),
            Transition(
                "stale",
                "current",
                "review --flow",
                cause="A person or an agent examines the flow claim again.",
                flow="Agent->CLI",
                journey="record-review",
                source="systemap.flow_review.form",
            ),
            Transition(
                "earlier",
                "current",
                "review --flow",
                cause="A new review identifies the examined source.",
                flow="Agent->CLI",
                journey="record-review",
                source="systemap.flow_review.form",
            ),
        ),
    ),
)
