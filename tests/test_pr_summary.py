"""The pull request summary gives the architectural effect of a change in a small number of lines.

The tests give fixtures to the pure functions. They do not call Git, Jev, or an agent.
"""

from __future__ import annotations

from pathlib import Path

from systemap import import_rules, nest, pr_summary
from systemap.assurance import Claim
from systemap.delta_model import EMPTY, NO_MEANING
from systemap.import_rules import Gap, MapOutcomes, Outcome
from systemap.model import Component, Flow, ImportRule, Invariant, Meaning, Model
from systemap.pr_summary import Summary

CHECKOUT = Component("Checkout", "Takes the order.", implemented_by=("shop.checkout",))
LEDGER = Component("Ledger", "Keeps the payments.", implemented_by=("shop.ledger",))
PAYMENT = Flow("Checkout", "Ledger", "payment record", "data")
NO_DB = ImportRule("no-db", "forbid_import", ("Checkout",), ("Ledger",), "The ledger is apart.")


def model(
    components: tuple[Component, ...] = (CHECKOUT, LEDGER),
    flows: tuple[Flow, ...] = (),
    invariants: tuple[Invariant, ...] = (),
    import_rules: tuple[ImportRule, ...] = (),
) -> Model:
    return Model((0, 0), (), (), components, flows, ("data",), invariants, import_rules)


def tree(*maps: tuple[str, Model]) -> nest.Tree:
    return nest.Tree(
        tuple(
            nest.Map(map_id, Path("map/model.py"), "map/model.py", m, Meaning(plain={}), {})
            for map_id, m in maps
        )
    )


def summary(base: Model, head: Model, **fields: object) -> Summary:
    b, h = tree(("", base)), tree(("", head))
    values: dict[str, object] = {
        "claims": (),
        "rules": (),
        "unknown_policy": "warn",
        "open_lines": 0,
        **fields,
    }
    return Summary(
        pr_summary.contract_changes(b, h),
        pr_summary.map_changes(b, h),
        **values,  # type: ignore[arg-type]
    )


def rules(*outcomes: Outcome) -> tuple[MapOutcomes, ...]:
    return (MapOutcomes("", "", "map/model.py", outcomes),)


def test_no_architectural_change_is_one_line() -> None:
    """Acceptance: the same model at the two commits and one rule with the result pass
    give exactly one line, with the rule count."""
    same = model(import_rules=(NO_DB,))
    text = pr_summary.markdown(summary(same, same, rules=rules(Outcome(NO_DB, import_rules.PASS))))
    assert text == (
        "**Architecture:** no change to the contract or the map. "
        "Rules: 1 passed, 0 failed, 0 unknown."
    )
    assert pr_summary.markdown(summary(same, model())).count("\n") > 0
    assert pr_summary.markdown(summary(model(), model())).endswith("Rules: none.")


def test_a_new_flow_gives_its_level_and_its_freshness() -> None:
    """Acceptance: an added flow gives one row with its endpoints, its artifact, its level,
    and the freshness of its flow review. The contract has its own row: no change."""
    claim = Claim("", "flow", PAYMENT.key, "examined", "current", "flow_review_current")
    text = pr_summary.markdown(summary(model(), model(flows=(PAYMENT,)), claims=(claim,)))
    assert text.splitlines()[:5] == [
        "**Architecture**",
        "",
        "- **Contract:** no change",
        "- **Map:** 1 added flow",
        "  - added flow `Checkout` -> `Ledger`, `payment record`: examined, flow review current",
    ]
    assert "- **Rules:** none" in text
    assert text.endswith(pr_summary.LEGEND)


def test_a_contract_change_has_its_own_rows_with_the_changed_fields() -> None:
    """Acceptance: a new reason of an invariant and a new import rule give two contract rows.
    The contract part asks the reviewer for a decision. The map part says no change."""
    old = Invariant(1, "Checkout writes no ledger row.", ("Checkout",))
    new = Invariant(1, "Checkout writes no ledger row.", ("Checkout",), "Audit rule.")
    claims = (
        Claim("", "invariant", "1", "unknown", "stale", "source_review_stale"),
        Claim("", "import_rule", "no-db", "established", "current", "rule_pass"),
    )
    base, head = model(invariants=(old,)), model(invariants=(new,), import_rules=(NO_DB,))
    lines = pr_summary.markdown(summary(base, head, claims=claims)).splitlines()
    assert lines[2:6] == [
        "- **Contract:** 1 changed invariant, 1 added import rule. "
        "Accept or reject each contract change in this review.",
        "  - changed invariant `1` (reason): unknown, source review stale",
        "  - added import rule `no-db`: established from facts",
        "- **Map:** no change",
    ]


def test_the_order_of_the_components_of_a_rule_is_not_a_change() -> None:
    a = Invariant(1, "x", ("Checkout", "Ledger"), "r")
    b = Invariant(1, "x", ("Ledger", "Checkout"), "r")
    assert not summary(model(invariants=(a,)), model(invariants=(b,))).contract


def test_a_removed_item_has_no_level() -> None:
    """Acceptance: a removed flow and a removed import rule say "no level". The summary does
    not use a claim of the head commit for them."""
    claim = Claim("", "flow", PAYMENT.key, "examined", "current", "flow_review_current")
    s = summary(model(flows=(PAYMENT,), import_rules=(NO_DB,)), model(), claims=(claim,))
    text = pr_summary.markdown(s)
    assert "  - removed flow `Checkout` -> `Ledger`, `payment record`: no level" in text
    assert "  - removed import rule `no-db`: no level" in text


def test_failed_and_unknown_rules_give_one_row_each_with_the_level() -> None:
    """Acceptance: a failed rule makes the summary long. Each rule with the result fail or
    unknown gives the first import or module and the count of the others. The policy for
    an unknown result is in the rules row."""
    other = ImportRule("plugins", "forbid_import", ("Checkout",), ("Ledger",), "Plugins apart.")
    failed = Outcome(NO_DB, import_rules.FAIL, (("shop.checkout", "shop.ledger"),))
    gaps = (Gap("shop.plugins", "unresolved_imports", "dynamic import"), Gap("b", "c", "d"))
    unknown = Outcome(other, import_rules.UNKNOWN, gaps=gaps)
    claims = (
        Claim("", "import_rule", "no-db", "unknown", "current", "rule_fail"),
        Claim("", "import_rule", "plugins", "unknown", "current", "rule_unknown"),
    )
    same = model(import_rules=(NO_DB, other))
    text = pr_summary.markdown(
        summary(same, same, claims=claims, rules=rules(failed, unknown), unknown_policy="fail")
    )
    assert "- **Rules:** 0 passed, 1 failed, 1 unknown. Policy for an unknown result: fail" in text
    assert (
        "  - fail `no-db`: `shop.checkout` imports `shop.ledger`. "
        "Level: unknown, facts current" in text
    )
    assert (
        "  - unknown `plugins`: `shop.plugins`: dynamic import, and 1 other module. "
        "Level: unknown, facts current" in text
    )


def test_an_unknown_rule_alone_keeps_the_one_line_form() -> None:
    gap = Gap("shop.plugins", "unresolved_imports", "dynamic import")
    same = model(import_rules=(NO_DB,))
    s = summary(same, same, rules=rules(Outcome(NO_DB, import_rules.UNKNOWN, gaps=(gap,))))
    assert pr_summary.markdown(s).endswith("Rules: 0 passed, 0 failed, 1 unknown.")


def test_each_part_gives_at_most_five_rows_and_a_count() -> None:
    """Acceptance: eight added components give five rows and the row "3 more rows"."""
    cards = tuple(Component(f"C{i}", "x") for i in range(8))
    lines = pr_summary.markdown(summary(model(components=()), model(components=cards)))
    rows = [line for line in lines.splitlines() if line.startswith("  - ")]
    assert len(rows) == 6
    assert rows[-1] == "  - 3 more rows"
    assert "- **Map:** 8 added components" in lines


def test_a_necessary_map_update_is_a_row() -> None:
    same = model()
    text = pr_summary.markdown(summary(same, same, open_lines=2))
    assert (
        "- **Map update:** necessary for 2 lines. "
        "The log of the delta job gives the action for each line." in text
    )


def test_a_base_model_that_does_not_load_is_unknown_and_not_no_change() -> None:
    s = Summary((), (), (), (), "warn", 0, "the model at abc1234 does not load: x")
    text = pr_summary.markdown(s)
    assert "- **Contract and map:** unknown. the model at abc1234 does not load: x" in text
    assert "no change" not in text


def test_a_nested_map_gives_its_id_before_each_name() -> None:
    inner = model(flows=(PAYMENT,))
    b = tree(("", model()), ("Shop", model()))
    h = tree(("", model()), ("Shop", inner))
    s = Summary((), pr_summary.map_changes(b, h), (), (), "warn", 0)
    assert "  - added flow `Shop/Checkout` -> `Shop/Ledger`, `payment record`: no level" in (
        pr_summary.markdown(s)
    )
    assert pr_summary.contract_changes(tree(("", EMPTY)), tree(("", EMPTY))) == ()
    assert NO_MEANING.plain == {}


def test_model_text_cannot_add_a_link_a_mention_or_a_marker() -> None:
    """Acceptance: a flow artifact with a backtick, a new line, an @ name, and an HTML
    comment stays in one code span on one row."""
    bad = Flow("Checkout", "Ledger", "a`b\n@team <!-- x -->", "data")
    text = pr_summary.markdown(summary(model(), model(flows=(bad,))))
    row = next(line for line in text.splitlines() if line.startswith("  - added flow"))
    assert "`a'b @team <!-- x -->`" in row
