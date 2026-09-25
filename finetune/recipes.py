"""What each workspace learns from, and how the result is evaluated."""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_BASE = "Qwen/Qwen2.5-3B-Instruct"

# Stack Exchange 2025 dump with Markdown threads, one folder per site. Content is CC BY-SA 3.0/4.0.
SE_REPO = "HuggingFaceTB/stackexchange_2025_md"
SE_LICENSE = "CC BY-SA (3.0/4.0, per post)"

# General-knowledge MMLU subset scored before and after, to catch forgetting.
MMLU_CONTROL = "sociology"


@dataclass(frozen=True)
class Source:
    site: str
    files: tuple[str, ...]
    share: float
    # Keep only questions carrying at least one of these tags (empty = every question).
    tags: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Recipe:
    workspace: str
    ollama_name: str
    # Training system prompt. It is the first sentence of the workspace prompt, not the whole prompt:
    # the answers do not follow the app's formatting rules, and training them under those rules would
    # teach the model to ignore them.
    identity: str
    sources: tuple[Source, ...]
    mmlu: tuple[str, ...]
    samples: tuple[str, ...] = field(default=())


BIOLOGY_TAGS = frozenset(
    {
        "bioinformatics", "genetics", "molecular-genetics", "molecular-biology", "genomics", "genome", "dna",
        "rna", "dna-sequencing", "rna-sequencing", "sequence-analysis", "gene-expression", "gene-regulation",
        "gene", "mutations", "pcr", "primer", "crispr", "cloning", "plasmids", "proteins", "protein-structure",
        "proteomics", "structural-biology", "phylogenetics", "molecular-evolution", "population-genetics",
        "epigenetics", "transcription", "translation", "dna-replication", "database", "biochemistry",
    }
)

RECIPES: dict[str, Recipe] = {
    "bioinformatics": Recipe(
        workspace="bioinformatics",
        ollama_name="nexgraft-bioinformatics",
        identity="You are NEXGRAFT Bioinformatics AI, a computational biology assistant that works like a coding and workflow environment.",
        sources=(
            Source("bioinformatics.stackexchange.com", ("bioinformatics.stackexchange.com/train-00000-of-00001.parquet",), 0.7),
            Source("biology.stackexchange.com", ("biology.stackexchange.com/train-00000-of-00001.parquet",), 0.3, BIOLOGY_TAGS),
        ),
        mmlu=("college_biology", "high_school_biology", "medical_genetics"),
        samples=(
            "Generate Python code to analyze a DNA sequence and calculate GC content.",
            "How do I call variants from paired-end Illumina reads against a reference genome?",
            "What is the difference between TPM, FPKM and raw counts for RNA-seq differential expression?",
        ),
    ),
    "hardware": Recipe(
        workspace="hardware",
        ollama_name="nexgraft-hardware",
        identity="You are NEXGRAFT Hardware Design AI, an engineering design assistant.",
        sources=(
            # The site has two ~520 MB shards; one holds plenty of well-scored threads.
            Source("electronics.stackexchange.com", ("electronics.stackexchange.com/train-00000-of-00002.parquet",), 0.65),
            Source("engineering.stackexchange.com", ("engineering.stackexchange.com/train-00000-of-00001.parquet",), 0.35),
        ),
        mmlu=("electrical_engineering", "college_physics", "conceptual_physics"),
        samples=(
            "Design considerations for a 5 V to 3.3 V power supply for an ESP32 sensor node.",
            "How do I choose a pull-up resistor value for an I2C bus?",
            "Select a beam section for a 3 m aluminium frame carrying 500 N at mid-span.",
        ),
    ),
}


def ollama_base_for(hf_base: str) -> str:
    """Maps a Hugging Face Qwen2.5 id to the matching Ollama tag, e.g. Qwen/Qwen2.5-3B-Instruct -> qwen2.5:3b."""
    import re

    m = re.search(r"Qwen2\.5-(Coder-)?([\d.]+)B", hf_base, re.I)
    if not m:
        return "qwen2.5:3b"
    return f"qwen2.5{'-coder' if m.group(1) else ''}:{m.group(2)}b"
