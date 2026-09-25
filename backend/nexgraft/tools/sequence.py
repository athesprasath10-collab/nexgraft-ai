"""Sequence toolkit for the Bioinformatics workspace (pure Python + Biopython).

These functions compute exact values so the language model never has to guess
GC content, translations or ORFs.
"""

from __future__ import annotations

import re
from collections import Counter

from .base import Param, ToolInputError, ToolSpec, result

# Standard genetic code (NCBI table 1), codons ordered by TCAG x TCAG x TCAG.
_BASES = "TCAG"
_AMINO = "FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
CODON_TABLE = {
    a + b + c: _AMINO[16 * i + 4 * j + k]
    for i, a in enumerate(_BASES)
    for j, b in enumerate(_BASES)
    for k, c in enumerate(_BASES)
}
STOP_CODONS = {c for c, aa in CODON_TABLE.items() if aa == "*"}

_COMPLEMENT = str.maketrans("ACGTUNRYSWKMBDHVacgtunryswkmbdhv", "TGCAANYRSWMKVHDBtgcaanyrswmkvhdb")

# Average amino-acid residue masses (Da) and Kyte-Doolittle hydropathy.
_RESIDUE_MASS = {
    "A": 71.0788, "R": 156.1875, "N": 114.1038, "D": 115.0886, "C": 103.1388,
    "E": 129.1155, "Q": 128.1307, "G": 57.0519, "H": 137.1411, "I": 113.1594,
    "L": 113.1594, "K": 128.1741, "M": 131.1926, "F": 147.1766, "P": 97.1167,
    "S": 87.0782, "T": 101.1051, "W": 186.2132, "Y": 163.1760, "V": 99.1326,
}
_KYTE_DOOLITTLE = {
    "A": 1.8, "R": -4.5, "N": -3.5, "D": -3.5, "C": 2.5, "Q": -3.5, "E": -3.5,
    "G": -0.4, "H": -3.2, "I": 4.5, "L": 3.8, "K": -3.9, "M": 1.9, "F": 2.8,
    "P": -1.6, "S": -0.8, "T": -0.7, "W": -0.9, "Y": -1.3, "V": 4.2,
}
_DNA_IUPAC = set("ACGTNRYSWKMBDHV")
_PROTEIN = set("ACDEFGHIKLMNPQRSTVWYBJZXUO*")

# Raw nucleotide runs worth analysing when they appear inside free text.
_RAW_SEQ_RE = re.compile(r"(?<![A-Za-z])[ACGTUNacgtun]{20,}(?![A-Za-z])")


def parse_sequences(text: str) -> list[tuple[str, str]]:
    """Parse FASTA (one or more records) or a single raw sequence."""
    text = text.strip()
    if not text:
        return []
    if text.lstrip().startswith(">"):
        records: list[tuple[str, str]] = []
        name, parts = None, []
        for line in text.splitlines():
            line = line.strip()
            if line.startswith(">"):
                if name is not None:
                    records.append((name, "".join(parts)))
                name, parts = line[1:].strip() or f"seq{len(records) + 1}", []
            elif line and not line.startswith(";"):
                parts.append(re.sub(r"[^A-Za-z*\-]", "", line))
        if name is not None:
            records.append((name, "".join(parts)))
        return [(n, s.upper()) for n, s in records if s]
    seq = re.sub(r"[^A-Za-z*\-]", "", text).upper()
    return [("sequence", seq)] if seq else []


def find_sequences_in_text(text: str, limit: int = 3) -> list[tuple[str, str]]:
    """Detect FASTA blocks or long nucleotide runs embedded in a user message."""
    found: list[tuple[str, str]] = []
    fasta = re.search(r"(^|\n)>[^\n]*\n[A-Za-z*\-\n\r ]{10,}", text)
    if fasta:
        found.extend(parse_sequences(text[fasta.start():]))
    else:
        for i, m in enumerate(_RAW_SEQ_RE.finditer(text)):
            found.append((f"sequence_{i + 1}", m.group(0).upper()))
    return found[:limit]


def detect_type(seq: str) -> str:
    letters = [c for c in seq.upper() if c.isalpha()]
    if not letters:
        raise ToolInputError("No sequence letters found.")
    counts = Counter(letters)
    nucleotide = sum(counts[c] for c in "ACGTUN")
    if nucleotide / len(letters) >= 0.9:
        if counts["U"] and not counts["T"]:
            return "RNA"
        if set(counts) <= _DNA_IUPAC | {"U"}:
            return "DNA"
    if set(counts) <= _PROTEIN:
        return "protein"
    raise ToolInputError("Could not recognise this as DNA, RNA or protein.")


def reverse_complement(seq: str) -> str:
    return seq.translate(_COMPLEMENT)[::-1]


def translate(seq: str, frame: int = 1, to_stop: bool = False) -> str:
    dna = seq.upper().replace("U", "T")
    protein = []
    for i in range(frame - 1, len(dna) - 2, 3):
        aa = CODON_TABLE.get(dna[i:i + 3], "X")
        if to_stop and aa == "*":
            break
        protein.append(aa)
    return "".join(protein)


def find_orfs(seq: str, min_aa: int = 30) -> list[dict]:
    """ATG..stop ORFs on all six frames (standard code), longest first."""
    dna = seq.upper().replace("U", "T")
    n = len(dna)
    orfs = []
    for strand, s in (("+", dna), ("-", reverse_complement(dna))):
        for frame in range(3):
            i = frame
            while i < n - 2:
                if s[i:i + 3] == "ATG":
                    for j in range(i, n - 2, 3):
                        if s[j:j + 3] in STOP_CODONS:
                            aa_len = (j - i) // 3
                            if aa_len >= min_aa:
                                if strand == "+":
                                    start, end = i + 1, j + 3
                                else:
                                    start, end = n - (j + 3) + 1, n - i
                                orfs.append({
                                    "strand": strand,
                                    "frame": frame + 1,
                                    "start": start,
                                    "end": end,
                                    "length_nt": j + 3 - i,
                                    "length_aa": aa_len,
                                    "protein": translate(s[i:j], 1),
                                })
                            i = j  # continue scanning after this ORF
                            break
                    else:
                        break  # no stop codon downstream in this frame
                i += 3
    return sorted(orfs, key=lambda o: o["length_aa"], reverse=True)


def _preview(seq: str, width: int = 120) -> str:
    return seq if len(seq) <= width else f"{seq[:width]}… ({len(seq)} total)"


def _nucleotide_stats(name: str, seq: str, kind: str) -> dict:
    s = seq.upper()
    counts = Counter(s)
    acgt = sum(counts[c] for c in "ACGTU")
    gc = counts["G"] + counts["C"]
    gc_pct = 100 * gc / acgt if acgt else 0.0
    t_or_u = "U" if kind == "RNA" else "T"
    rows = [
        ("Type", kind, ""),
        ("Length", len(s), "nt"),
        ("GC content", gc_pct, "%"),
        ("AT/AU content", 100 - gc_pct if acgt else 0.0, "%"),
        ("A / C / G / " + t_or_u, f"{counts['A']} / {counts['C']} / {counts['G']} / {counts[t_or_u]}", ""),
    ]
    ambiguous = len(s) - acgt
    if ambiguous:
        rows.append(("Ambiguous bases (N etc.)", ambiguous, ""))
    if kind == "DNA" and acgt:
        # Oligo molecular weight (anhydrous, 5'-OH) and basic melting-temperature formulas.
        mw = counts["A"] * 313.21 + counts["T"] * 304.2 + counts["C"] * 289.18 + counts["G"] * 329.21 - 61.96
        rows.append(("Molecular weight (ssDNA, approx.)", mw, "g/mol"))
        at = counts["A"] + counts["T"]
        if acgt < 14:
            rows.append(("Tm (Wallace rule 2·AT + 4·GC)", 2 * at + 4 * gc, "°C"))
        else:
            rows.append(("Tm (basic: 64.9 + 41·(GC−16.4)/N)", 64.9 + 41 * (gc - 16.4) / acgt, "°C"))
    orfs = find_orfs(s, min_aa=30 if len(s) > 300 else 10)
    if orfs:
        top = orfs[0]
        rows.append(("Longest ORF", f"{top['length_aa']} aa ({top['strand']} strand, frame {top['frame']}, {top['start']}–{top['end']})", ""))
    else:
        rows.append(("Longest ORF", "none found (ATG…stop)", ""))
    extra = {
        "sequence_preview": _preview(s),
        "translation_frame1": _preview(translate(s, 1)),
    }
    if kind == "DNA":
        extra["reverse_complement"] = _preview(reverse_complement(s))
    summary = f"{name}: {kind}, {len(s)} nt, GC {gc_pct:.2f}%"
    return result(summary, rows, **extra, orfs=orfs[:5])


def _protein_stats(name: str, seq: str) -> dict:
    s = seq.upper().rstrip("*")
    counts = Counter(s)
    standard = [c for c in s if c in _RESIDUE_MASS]
    mw = sum(_RESIDUE_MASS[c] for c in standard) + 18.01528 if standard else 0.0
    gravy = sum(_KYTE_DOOLITTLE[c] for c in standard) / len(standard) if standard else 0.0
    top = ", ".join(f"{aa} {100 * n / len(s):.1f}%" for aa, n in counts.most_common(5))
    rows = [
        ("Type", "protein", ""),
        ("Length", len(s), "aa"),
        ("Molecular weight (average)", mw / 1000, "kDa"),
        ("GRAVY (Kyte–Doolittle)", gravy, ""),
        ("Most frequent residues", top, ""),
    ]
    warnings = []
    if len(standard) != len(s):
        warnings.append(f"{len(s) - len(standard)} non-standard residue(s) excluded from mass/GRAVY.")
    return result(
        f"{name}: protein, {len(s)} aa, ~{mw / 1000:.2f} kDa",
        rows,
        sequence_preview=_preview(s),
        warnings=warnings,
    )


def sequence_stats(sequence: str) -> dict:
    records = parse_sequences(sequence)
    if not records:
        raise ToolInputError("Paste a DNA, RNA or protein sequence (raw or FASTA).")
    if sum(len(s) for _, s in records) > 2_000_000:
        raise ToolInputError("Sequence input is limited to 2 Mb in the local toolkit.")
    outputs = []
    for name, seq in records[:10]:
        kind = detect_type(seq)
        outputs.append(_protein_stats(name, seq) if kind == "protein" else _nucleotide_stats(name, seq, kind))
    if len(outputs) == 1:
        return outputs[0]
    return {
        "summary": f"{len(records)} records" + (" (first 10 analysed)" if len(records) > 10 else ""),
        "results": [{"label": o["summary"].split(":")[0], "value": o["summary"].split(":", 1)[1].strip(), "unit": ""} for o in outputs],
        "records": outputs,
    }


def translate_tool(sequence: str, frame: str = "1", to_stop: bool = False) -> dict:
    records = parse_sequences(sequence)
    if not records:
        raise ToolInputError("Paste a DNA or RNA sequence.")
    name, seq = records[0]
    if detect_type(seq) == "protein":
        raise ToolInputError("This looks like a protein sequence already.")
    f = int(frame.replace("-", "")) if frame.lstrip("-").isdigit() else 1
    source = reverse_complement(seq) if frame.startswith("-") else seq
    protein = translate(source, f, to_stop)
    return result(
        f"{name}: frame {frame} → {len(protein)} aa",
        [("Frame", frame, ""), ("Protein length", len(protein), "aa"), ("Stop codons (*)", protein.count("*"), "")],
        protein=protein,
    )


def orf_tool(sequence: str, min_aa: float = 30) -> dict:
    records = parse_sequences(sequence)
    if not records:
        raise ToolInputError("Paste a DNA or RNA sequence.")
    name, seq = records[0]
    if detect_type(seq) == "protein":
        raise ToolInputError("ORF finding needs a nucleotide sequence.")
    orfs = find_orfs(seq, int(min_aa))
    rows = [
        (f"ORF {i + 1}", f"{o['length_aa']} aa, {o['strand']}{o['frame']}, {o['start']}–{o['end']}", "")
        for i, o in enumerate(orfs[:10])
    ]
    return result(f"{name}: {len(orfs)} ORF(s) ≥ {int(min_aa)} aa on 6 frames", rows, orfs=orfs[:10])


def align_tool(sequence_a: str, sequence_b: str, mode: str = "global") -> dict:
    try:
        from Bio import Align
        from Bio.Align import substitution_matrices
    except ImportError as exc:  # pragma: no cover - biopython is in requirements
        raise ToolInputError("Alignment needs Biopython: pip install biopython") from exc
    a_rec, b_rec = parse_sequences(sequence_a), parse_sequences(sequence_b)
    if not a_rec or not b_rec:
        raise ToolInputError("Provide two sequences.")
    a, b = a_rec[0][1], b_rec[0][1]
    if max(len(a), len(b)) > 20000:
        raise ToolInputError("Pairwise alignment here is limited to 20 kb per sequence.")
    kind_a, kind_b = detect_type(a), detect_type(b)
    aligner = Align.PairwiseAligner()
    aligner.mode = "local" if mode == "local" else "global"
    if "protein" in (kind_a, kind_b):
        aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
        aligner.open_gap_score, aligner.extend_gap_score = -10, -0.5
        scoring = "BLOSUM62, gap open −10, extend −0.5"
    else:
        aligner.match_score, aligner.mismatch_score = 2, -1
        aligner.open_gap_score, aligner.extend_gap_score = -5, -1
        scoring = "match +2, mismatch −1, gap open −5, extend −1"
    aln = aligner.align(a.replace("U", "T"), b.replace("U", "T"))[0]
    counts = aln.counts()
    aligned_len = aln.shape[1]
    identity = 100 * counts.identities / aligned_len if aligned_len else 0.0
    text = str(aln)
    if len(text) > 4000:
        text = text[:4000] + "\n…(truncated)"
    return result(
        f"{aligner.mode.title()} alignment: score {aln.score:.1f}, identity {identity:.1f}%",
        [
            ("Mode", aligner.mode, ""),
            ("Scoring", scoring, ""),
            ("Score", float(aln.score), ""),
            ("Alignment length", aligned_len, "columns"),
            ("Identity", identity, "%"),
            ("Mismatches", counts.mismatches, ""),
            ("Gaps", counts.gaps, ""),
        ],
        alignment=text,
    )


_SEQ_HELP = "Raw sequence or FASTA. DNA, RNA or protein is detected automatically."

TOOLS = [
    ToolSpec(
        id="sequence_stats",
        name="Sequence statistics",
        description="Type detection, length, GC content, composition, molecular weight, Tm, translation and longest ORF.",
        agent="bioinformatics",
        category="Sequence toolkit",
        params=[Param("sequence", "Sequence", type="text", help=_SEQ_HELP)],
        run=sequence_stats,
    ),
    ToolSpec(
        id="translate",
        name="Translate (standard code)",
        description="Translate DNA/RNA to protein in any of the six reading frames.",
        agent="bioinformatics",
        category="Sequence toolkit",
        params=[
            Param("sequence", "DNA / RNA sequence", type="text"),
            Param("frame", "Reading frame", type="select", default="1", options=["1", "2", "3", "-1", "-2", "-3"]),
            Param("to_stop", "Stop at first stop codon", type="boolean", default=False, required=False),
        ],
        run=translate_tool,
    ),
    ToolSpec(
        id="orf_finder",
        name="ORF finder",
        description="Find ATG→stop open reading frames on all six frames.",
        agent="bioinformatics",
        category="Sequence toolkit",
        params=[
            Param("sequence", "DNA / RNA sequence", type="text"),
            Param("min_aa", "Minimum ORF length", unit="aa", default=30, min=1),
        ],
        run=orf_tool,
    ),
    ToolSpec(
        id="pairwise_align",
        name="Pairwise alignment",
        description="Needleman–Wunsch (global) or Smith–Waterman (local) alignment via Biopython.",
        agent="bioinformatics",
        category="Sequence toolkit",
        params=[
            Param("sequence_a", "Sequence A", type="text"),
            Param("sequence_b", "Sequence B", type="text"),
            Param("mode", "Mode", type="select", default="global", options=["global", "local"]),
        ],
        run=align_tool,
    ),
]
