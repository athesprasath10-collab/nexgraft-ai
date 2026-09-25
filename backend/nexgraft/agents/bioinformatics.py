from __future__ import annotations

from ..tools import TOOL_REGISTRY, ToolInputError, to_markdown
from ..tools.sequence import find_sequences_in_text
from .base import AgentSpec, Preparation, TaskContext
from .grounding import add_knowledge

_SEQUENCE_ATTACHMENT_EXT = (".fasta", ".fa", ".fna", ".faa", ".ffn", ".txt", ".seq")


async def prepare(ctx: TaskContext) -> Preparation:
    """Detect sequences in the request or attached FASTA files and compute exact statistics."""
    prep = Preparation()
    candidates = find_sequences_in_text(ctx.message)
    for att in ctx.attachments:
        if att.get("kind") == "document" and att.get("name", "").lower().endswith(_SEQUENCE_ATTACHMENT_EXT):
            candidates.extend(find_sequences_in_text(att.get("text", "")[:200_000]))
    tool = TOOL_REGISTRY["sequence_stats"]
    for name, seq in candidates[:3]:
        try:
            output = await tool.execute({"sequence": f">{name}\n{seq}"})
        except ToolInputError:
            continue
        prep.tool_calls.append({"tool": tool.id, "name": tool.name, "input": {"sequence": seq[:80] + ("…" if len(seq) > 80 else "")}, "output": output})
        prep.context_blocks.append(
            "Verified tool results (computed by the NEXGRAFT sequence toolkit — use these exact values):\n"
            + to_markdown(tool.name, output)
        )
    await add_knowledge(ctx, prep, ["bioinformatics"], k=4)
    return prep


AGENT = AgentSpec(
    id="bioinformatics",
    name="Bioinformatics AI",
    short_name="Bioinformatics",
    tagline="Sequence analysis, code and workflows — you stay in control of execution",
    description="An AI-powered bioinformatics coding and workflow environment: describe a biological or computational task and get code, workflows, parameters and explanations.",
    color="#2dd4a0",
    icon="dna",
    workspace="code",
    order=2,
    system_prompt=(
        "You are NEXGRAFT Bioinformatics AI, a computational biology assistant that works like a coding and workflow "
        "environment. For each request:\n"
        "1. State the approach briefly.\n"
        "2. When code helps, give ONE complete, runnable Python 3 script in a ```python block. Prefer the standard "
        "library and Biopython (Bio.SeqIO, Bio.Seq, Bio.SeqUtils.gc_fraction, Bio.Align.PairwiseAligner). Never use "
        "the removed Bio.SeqUtils.GC. Print results clearly. For plots use matplotlib and plt.savefig('plot.png') "
        "instead of plt.show(). If the user attached files, read them by their exact file name.\n"
        "3. Explain the code and the biology behind it.\n"
        "4. Explain how to run it and what output to expect.\n"
        "5. For steps that need external software (BLAST, BWA, STAR, GATK, AutoDock Vina, PyMOL…), give the workflow, "
        "commands and parameters, and state that the user runs them.\n"
        "Never claim that you executed code or external tools. If verified tool results are provided, use those exact values."
    ),
    capabilities=["Sequence analysis", "Python/Biopython code", "NGS workflows", "Alignment & phylogenetics", "Docking workflow guidance", "Biological databases"],
    keywords={
        "dna": 2.5, "rna": 2.5, "protein sequence": 3.0, "sequence": 1.5, "sequences": 1.5, "genome": 2.5,
        "genomic": 2.5, "genomics": 2.5, "gene": 1.5, "genes": 1.5, "gc content": 3.0, "fasta": 3.0, "fastq": 3.0,
        "alignment": 2.0, "align": 1.5, "blast": 3.0, "phylogenetic": 3.0, "phylogeny": 3.0, "mutation": 1.5,
        "variant calling": 3.0, "snp": 2.0, "rna-seq": 3.0, "rnaseq": 3.0, "ngs": 3.0, "sequencing": 2.0,
        "bioinformatics": 3.5, "biopython": 3.5, "codon": 2.5, "orf": 2.5, "primer": 2.0, "transcriptome": 2.5,
        "proteomics": 2.0, "docking": 3.0, "molecular docking": 3.5, "ligand": 2.0, "pdb": 2.0, "autodock": 3.5,
        "motif": 1.5, "k-mer": 2.5, "kmer": 2.5, "biological data": 2.5, "expression data": 2.0, "microbiome": 2.0,
        "crispr": 2.0, "plasmid": 2.0, "reverse complement": 3.0, "translation": 1.0, "amino acid": 2.0,
        "uniprot": 3.0, "ncbi": 2.5, "genbank": 3.0, "vcf": 3.0, "bam": 2.5, "sam file": 2.5,
    },
    knowledge_collections=["bioinformatics"],
    user_controls=["Running generated code (with the Run button or on your own machine)", "External tools such as BLAST, aligners and docking software", "Experiments and interpretation of results"],
    examples=[
        "Generate Python code to analyze a DNA sequence and calculate GC content.",
        "Create a workflow for sequence alignment and downstream analysis.",
        "Explain the steps for docking a ligand to a protein with AutoDock Vina.",
    ],
    tools=["sequence_stats", "translate", "orf_finder", "pairwise_align"],
    prepare=prepare,
    subtask_title="Biological data analysis",
    subtask_instruction="Describe the biological data analysis approach for this request, with a Python script or workflow where useful: {message}",
    temperature=0.2,
    boundary="Generates code, workflows and guidance. External execution (e.g. molecular docking) stays user-controlled.",
)
