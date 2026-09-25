from nexgraft.agents.base import PluginSpec

PLUGIN = PluginSpec(
    id="electrical",
    agent="hardware",
    name="Electrical Engineering",
    description="Power systems, wiring, protection, motors and energy.",
    icon="zap",
    order=5,
    keywords={
        "electrical": 3.0, "three phase": 3.0, "three-phase": 3.0, "single phase": 3.0, "motor": 2.5,
        "transformer": 3.0, "wiring": 3.0, "cable": 2.5, "mcb": 3.0, "rccb": 3.0, "earthing": 3.0, "grounding": 2.0,
        "power factor": 3.0, "inverter": 2.5, "solar": 2.5, "grid": 2.0, "switchgear": 3.0, "kw": 1.5, "kva": 3.0,
    },
    prompt=(
        "Active domain plugin: Electrical Engineering. Consider supply characteristics (230 V / 415 V, 50 Hz in India), "
        "load calculations, cable sizing and voltage drop, protection coordination, earthing, efficiency and the "
        "relevant codes (IS 732, IS 3043, National Electrical Code, IEC 60364). Mains work must be done by licensed professionals."
    ),
    knowledge_collection="hardware-electrical",
    tools=["three_phase_power", "voltage_drop"],
    examples=["Size a copper cable for a 16 A, 230 V load 30 m away with under 3% voltage drop."],
)
