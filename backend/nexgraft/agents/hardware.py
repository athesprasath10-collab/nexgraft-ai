from __future__ import annotations

from .base import AgentSpec, Preparation, TaskContext
from .grounding import add_knowledge
from .schematic import add_schematic


async def prepare(ctx: TaskContext) -> Preparation:
    from .registry import registry  # local import: registry imports this module

    prep = Preparation()
    await add_schematic(ctx, prep)
    all_collections = [p.knowledge_collection for p in registry.plugins_for("hardware")]
    plugin = registry.plugins.get(ctx.plugin_id or "")
    if plugin:
        # Search the active domain plugin first; fall back to other engineering domains.
        await add_knowledge(ctx, prep, [plugin.knowledge_collection], k=3)
        if len(prep.sources) < 2:
            others = [c for c in all_collections if c != plugin.knowledge_collection]
            await add_knowledge(ctx, prep, others, k=2)
    else:
        await add_knowledge(ctx, prep, all_collections, k=4)
    return prep


AGENT = AgentSpec(
    id="hardware",
    name="Hardware Design AI",
    short_name="Hardware Design",
    tagline="Engineering guidance through domain plugins",
    description="An engineering workspace with domain plugins (biomedical, electronics, mechanical, civil, electrical) for components, materials, calculations and design considerations.",
    color="#ffb547",
    icon="cpu",
    workspace="engineering",
    order=4,
    system_prompt=(
        "You are NEXGRAFT Hardware Design AI, an engineering design assistant. You provide technical information, design "
        "considerations, component and material guidance, calculations and design methodologies.\n"
        "Structure answers as: ## Requirements, ## Components & materials (use a comparison table), ## Design "
        "considerations, ## Calculations (formulas with units, when relevant), ## Standards & references, "
        "## Next steps (user-controlled: simulation, prototyping, testing, validation).\n"
        "Only name specific part numbers you are confident exist, and tell the user to check datasheets. If verified "
        "calculator results are provided, use those exact values. You give guidance; the user controls the actual design, "
        "simulation, fabrication and validation. Never claim a design is validated, certified or safe to deploy."
    ),
    capabilities=["Component & sensor selection", "Circuit schematics", "Materials", "Engineering calculations", "Design considerations", "Standards & references"],
    keywords={
        "hardware": 3.0, "sensor": 2.5, "sensors": 2.5, "circuit": 3.0, "circuits": 3.0, "pcb": 3.5, "microcontroller": 3.0,
        "arduino": 3.0, "esp32": 3.0, "raspberry pi": 3.0, "stm32": 3.0, "component": 1.5, "components": 1.5,
        "design": 0.8, "device": 1.5, "prototype": 1.5, "wearable": 2.0, "battery": 2.0, "voltage": 2.5, "current": 1.0,
        "resistor": 3.0, "capacitor": 3.0, "amplifier": 2.5, "adc": 2.5, "embedded": 2.5, "firmware": 2.0, "enclosure": 2.5,
        "material": 1.5, "materials": 1.5, "beam": 2.5, "load": 1.0, "stress": 1.0, "torque": 3.0, "gear": 3.0,
        "mechanical": 2.5, "civil": 3.0, "concrete": 3.0, "bridge": 2.5, "foundation": 2.0, "structural": 2.5,
        "electrical": 2.5, "motor": 2.5, "transformer": 3.0, "wiring": 3.0, "power supply": 3.0, "engineering": 1.5,
        "electronics": 3.0, "biomedical device": 3.0, "biomedical engineering": 2.5, "cad": 2.0, "3d print": 2.5,
        "fabrication": 2.0, "actuator": 3.0, "robot": 2.5, "solar": 2.0, "inverter": 3.0,
        "biomedical": 1.5, "monitoring device": 2.0, "system design": 1.5,
    },
    knowledge_collections=["hardware-biomedical", "hardware-electronics", "hardware-mechanical", "hardware-civil", "hardware-electrical"],
    user_controls=["Final design decisions", "Simulation and analysis", "Fabrication and assembly", "Testing, certification and validation"],
    examples=[
        "What sensors and hardware considerations should I evaluate for a wearable biomedical device?",
        "Design considerations for a 5 V to 3.3 V power supply for an ESP32 sensor node.",
        "Draw a circuit to switch a 12 V relay from an ESP32 pin.",
        "Select a beam section for a 3 m aluminium frame carrying 500 N at mid-span.",
    ],
    prepare=prepare,
    subtask_title="Hardware & sensor design",
    subtask_instruction="Recommend hardware: sensors, components, materials and design considerations for this request: {message}",
    uses_plugins=True,
    temperature=0.3,
    boundary="Provides engineering information and design guidance. Design, simulation, fabrication and validation stay user-controlled.",
)
