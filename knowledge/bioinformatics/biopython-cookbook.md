# Biopython cookbook

Install with: pip install biopython

## Read sequences
from Bio import SeqIO
for record in SeqIO.parse("sequences.fasta", "fasta"):
    print(record.id, len(record.seq))
Use "fastq" for FASTQ files and "genbank" for GenBank. SeqIO.to_dict or SeqIO.index give random access to large files.

## Sequence operations
from Bio.Seq import Seq
s = Seq("ATGGCCATTGTAATGGGCCGCTGA")
s.reverse_complement(); s.transcribe(); s.translate(to_stop=True)

## GC content
from Bio.SeqUtils import gc_fraction
gc_percent = gc_fraction(s) * 100
Note: the old Bio.SeqUtils.GC function was deprecated and removed in recent Biopython releases; use gc_fraction.

## Pairwise alignment
from Bio import Align
from Bio.Align import substitution_matrices
aligner = Align.PairwiseAligner()
aligner.mode = "global"   # or "local"
aligner.substitution_matrix = substitution_matrices.load("BLOSUM62")
aligner.open_gap_score = -10
aligner.extend_gap_score = -0.5
alignment = aligner.align(seq_a, seq_b)[0]
print(alignment.score); print(alignment)
Bio.pairwise2 is deprecated; prefer PairwiseAligner.

## Protein analysis
from Bio.SeqUtils.ProtParam import ProteinAnalysis
pa = ProteinAnalysis("MKTAYIAKQR")
pa.molecular_weight(); pa.isoelectric_point(); pa.gravy()

## NCBI Entrez
from Bio import Entrez
Entrez.email = "you@example.com"   # NCBI requires an email address
handle = Entrez.efetch(db="nucleotide", id="NM_000546", rettype="fasta", retmode="text")
Respect NCBI rate limits (3 requests/second without an API key).

## Plotting
Use matplotlib and save figures with plt.savefig("plot.png", dpi=150) for scripts that run without a display.
