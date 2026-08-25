# kstrl, mapped with systemap

The first and fullest model: `atlas/model.py` holds kstrl's 54 components,
60 flows, 7 layers, 4 journeys and 15 invariants, converted from the
`logical_model.py` and `relations.py` that kstrl's atlas tooling used.
`systemap.toml` shows every configuration key in use, and its `[theme]`
table carries kstrl's own tokens (the package default is a neutral dark
scheme).

`docs/atlas/atlas.json` is the facts file kstrl committed, so the map can
be checked and rendered from this directory without the kstrl tree:

    cd examples/kstrl
    uv run systemap check
    uv run systemap render
    open docs/atlas/index.html

`systemap extract` needs the kstrl source, so run it from a kstrl checkout
with these two files copied to its root.
