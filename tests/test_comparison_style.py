"""A comparison figure contains the styles that show its hidden flows.

Acceptance (Codex result schematic-4): a comparison SVG that hides a flow with
`display="none"` contains, in its own style element and for its own SVG ID, the rule
that shows that flow and its label when a selection or a preview adds `hot` or `peek`.
The rule must not depend on the page CSS. A figure that is not a comparison does not
contain the rule.
"""

from __future__ import annotations

from conftest import Sample

from systemap.schematic import render as render_schematic


def comparison(sample: Sample, svg_id: str) -> str:
    svg, _detail = render_schematic(
        sample.model,
        sample.meaning,
        sample.theme,
        sample.facts,
        mode="change",
        changed={"Writer"},
        changed_modules={"pkg.writer"},
        svg_id=svg_id,
    )
    return svg


def test_a_comparison_figure_shows_a_selected_hidden_flow(sample: Sample) -> None:
    for svg_id in ("fig-2", "changemap"):
        svg = comparison(sample, svg_id)
        assert 'data-change="rest" display="none"' in svg
        assert (
            f'#{svg_id} :is(.flow,.flowlbl)[data-change="rest"]:is(.hot,.peek){{display:inline}}'
        ) in svg
        assert f'#{svg_id} :is(.flow,.flowlbl)[data-change="lost"].off{{opacity:1;' in svg


def test_a_figure_without_a_comparison_has_no_comparison_rule(sample: Sample) -> None:
    svg, _detail = render_schematic(sample.model, sample.meaning, sample.theme, sample.facts)
    assert 'data-change="rest"' not in svg
