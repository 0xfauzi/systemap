from systemap.model import Component, Container, Meaning, Model, Region

CONTAINERS = (Container(id="system", label="SYSTEM", box=(20, 20, 600, 300), tone="server"),)

REGIONS = (
    Region(id="application", label="APPLICATION", box=(40, 60, 560, 220), container="system"),
)

COMPONENTS = (
    Component(
        id="Application",
        does="Serves a user through the command line and web view.",
        implemented_by=(
            "acme.web.cli",
            "acme.web.client",
            "acme.web.index",
            "acme.web.service",
            "acme.web.view",
        ),
        entry="serve",
        region="application",
        x=220,
        y=120,
    ),
)

MODEL = Model(
    canvas=(640, 340),
    containers=CONTAINERS,
    regions=REGIONS,
    components=COMPONENTS,
    flows=(),
    flow_kinds=(),
    invariants=(),
)

MEANING = Meaning(plain={"Application": "the application"})
