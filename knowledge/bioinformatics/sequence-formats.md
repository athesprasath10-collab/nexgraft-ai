# Common bioinformatics file formats

## FASTA
Text format for nucleotide or protein sequences. Each record starts with a header line beginning with ">" followed by an identifier and optional description; the following lines hold the sequence. Extensions: .fasta, .fa, .fna (nucleotide), .faa (protein).

## FASTQ
Stores sequencing reads with per-base quality. Four lines per record: "@" + read ID, the sequence, a "+" separator line, and a quality string of the same length as the sequence. Qualities are Phred scores, Q = −10·log10(P_error); Q30 means a 1 in 1000 chance of an incorrect base call. Modern Illumina data uses Phred+33 encoding (ASCII character code minus 33).

## SAM / BAM / CRAM
Sequence Alignment/Map format stores read alignments to a reference: header lines start with "@", followed by 11 mandatory tab-separated fields (QNAME, FLAG, RNAME, POS, MAPQ, CIGAR, RNEXT, PNEXT, TLEN, SEQ, QUAL). BAM is the compressed binary version; CRAM compresses further using the reference. SAMtools sorts, indexes and filters these files.

## VCF
Variant Call Format lists variants against a reference: CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO, then FORMAT and per-sample genotype columns. bcftools manipulates VCF/BCF files.

## GFF3 / GTF / BED
Annotation formats. GFF3 and GTF describe genes, transcripts and exons with 1-based, inclusive coordinates. BED uses 0-based, half-open coordinates (start is 0-based, end is exclusive) — a frequent source of off-by-one errors.

## GenBank
Rich annotated record format from NCBI with a header (LOCUS, DEFINITION, ACCESSION, VERSION), a FEATURES table and the ORIGIN sequence. Biopython reads it with SeqIO.parse(path, "genbank").

## PDB / mmCIF
Macromolecular 3D structure formats from the Protein Data Bank. mmCIF is the current standard archive format; legacy PDB format has fixed-width columns and size limits. Used for structural analysis and docking preparation.
