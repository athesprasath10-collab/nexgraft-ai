from nexgraft.agents.base import PluginSpec

PLUGIN = PluginSpec(
    id="mechanical",
    agent="hardware",
    name="Mechanical Engineering",
    description="Materials, stress and deflection, mechanisms, tolerances and manufacturing.",
    icon="cog",
    order=3,
    keywords={
        "mechanical": 3.0, "gear": 3.0, "shaft": 3.0, "bearing": 3.0, "torque": 3.0, "beam": 2.0, "stress": 2.5,
        "strain": 2.5, "deflection": 2.5, "fatigue": 3.0, "tolerance": 2.5, "cad": 2.0, "3d print": 2.5,
        "machining": 3.0, "welding": 3.0, "spring": 2.5, "linkage": 3.0, "mechanism": 3.0, "thermal": 1.5,
        "enclosure": 2.0, "aluminium": 2.0, "aluminum": 2.0, "steel": 1.5, "fea": 3.0,
    },
    prompt=(
        "Active domain plugin: Mechanical Engineering. Consider loads, materials, stress, deflection, factor of "
        "safety, fatigue, tolerances and fits, manufacturing process and assembly. Show formulas with units and "
        "recommend FEA or physical testing where appropriate."
    ),
    knowledge_collection="hardware-mechanical",
    tools=["beam_point_load", "axial_stress"],
    examples=["Select a beam section for a 1 m aluminium frame carrying 500 N at mid-span."],
)
