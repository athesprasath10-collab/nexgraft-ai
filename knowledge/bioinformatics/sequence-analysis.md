# Sequence analysis fundamentals

## Basic sequence properties
- GC content = (G + C) / (A + C + G + T) × 100. It affects DNA stability, melting temperature and sequencing bias; it varies widely across genomes.
- Reverse complement: complement each base (A↔T, C↔G) and reverse the order. Needed because DNA is double-stranded and antiparallel.
- Transcription replaces T with U; translation reads codons (triplets) in a reading frame using a genetic code. The standard code (NCBI table 1) has start codon ATG and stop codons TAA, TAG and TGA.
- There are six reading frames: three on the forward strand and three on the reverse complement.
- An open reading frame (ORF) is a stretch from a start codon to an in-frame stop codon; long ORFs are candidate protein-coding regions, but gene prediction in real genomes uses dedicated tools (e.g. Prodigal for prokaryotes, AUGUSTUS for eukaryotes).

## Pairwise alignment
- Global alignment (Needleman–Wunsch) aligns full-length sequences; local alignment (Smith–Waterman) finds the best-matching sub-regions.
- Scoring uses match/mismatch scores for nucleotides and substitution matrices such as BLOSUM62 or PAM250 for proteins, plus affine gap penalties (gap open + gap extend).
- BLAST is a fast heuristic local-alignment search against databases; report E-values, percent identity and query coverage.

## Multiple sequence alignment and phylogenetics
- MSA tools: Clustal Omega, MUSCLE, MAFFT. Inspect and trim alignments (e.g. trimAl) before building trees.
- Tree methods: distance-based (neighbour-joining, UPGMA), maximum likelihood (IQ-TREE, RAxML-NG) and Bayesian (MrBayes, BEAST). Assess support with bootstrap values.

## Protein properties
Molecular weight (sum of residue masses plus one water), isoelectric point, and GRAVY hydropathy (mean Kyte–Doolittle value; positive means hydrophobic on average). Domain and function annotation uses InterProScan, Pfam and UniProt.
