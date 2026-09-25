from nexgraft.agents.base import PluginSpec

PLUGIN = PluginSpec(
    id="biomedical",
    agent="hardware",
    name="Biomedical Engineering",
    description="Wearables, biosignal acquisition, medical-device safety and standards.",
    icon="heart-pulse",
    order=1,
    keywords={
        "biomedical": 3.0, "wearable": 3.0, "ecg": 3.0, "eeg": 3.0, "emg": 3.0, "ppg": 3.0, "spo2": 3.0,
        "pulse oximeter": 3.0, "physiological": 2.5, "biosignal": 3.0, "medical device": 3.0, "patient monitor": 3.0,
        "heart rate": 2.5, "implant": 2.5, "prosthetic": 2.5, "glucose monitor": 3.0, "electrode": 2.5,
    },
    prompt=(
        "Active domain plugin: Biomedical Engineering. Consider biosignal characteristics, analog front ends, "
        "sampling, motion artefacts, power budget, patient safety (isolation, leakage), biocompatibility and the "
        "relevant standards (IEC 60601 family, ISO 14971, ISO 10993, IEC 62304) and regulation (CDSCO in India)."
    ),
    knowledge_collection="hardware-biomedical",
    tools=["battery_life", "biosignal_sampling", "adc_resolution"],
    examples=["What sensors and hardware considerations should I evaluate for a wearable that monitors physiological parameters?"],
)
