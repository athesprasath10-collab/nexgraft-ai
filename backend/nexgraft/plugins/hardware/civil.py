from nexgraft.agents.base import PluginSpec

PLUGIN = PluginSpec(
    id="civil",
    agent="hardware",
    name="Civil Engineering",
    description="Structural loads, concrete and steel, Indian Standards and serviceability.",
    icon="building",
    order=4,
    keywords={
        "civil": 3.0, "concrete": 3.0, "rcc": 3.0, "slab": 3.0, "column": 2.5, "foundation": 3.0, "footing": 3.0,
        "bridge": 3.0, "building": 2.0, "structural": 2.5, "rebar": 3.0, "reinforcement": 2.5, "soil": 2.5,
        "is 456": 3.5, "load": 1.0, "seismic": 3.0, "earthquake": 2.5, "construction": 2.5, "masonry": 3.0,
        "beam": 2.0, "deflection": 1.5, "span": 2.0,
    },
    prompt=(
        "Active domain plugin: Civil Engineering. Consider load types and combinations, material grades, limit state "
        "design, serviceability (deflection, cracking), durability and the relevant Indian Standards (IS 456, IS 800, "
        "IS 875, IS 1893). State that real structures need design and approval by a qualified structural engineer."
    ),
    knowledge_collection="hardware-civil",
    tools=["udl_beam"],
    examples=["Check a 5 m simply supported RCC beam (230 × 450 mm) under 10 kN/m for deflection."],
)
