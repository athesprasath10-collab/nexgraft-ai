# NGS analysis workflows

## DNA-seq germline variant calling (typical)
1. Quality control: FastQC per sample, MultiQC to summarise.
2. Adapter and quality trimming: fastp or Trimmomatic.
3. Alignment to a reference genome: BWA-MEM (short reads) or minimap2 (long reads).
4. Sort and index: samtools sort, samtools index.
5. Mark duplicates: Picard MarkDuplicates or GATK MarkDuplicatesSpark.
6. Base quality score recalibration (GATK BQSR) when known-sites resources exist.
7. Variant calling: GATK HaplotypeCaller or bcftools mpileup + call; DeepVariant is a deep-learning alternative.
8. Filtering and annotation: GATK VQSR or hard filters, then Ensembl VEP, SnpEff or ANNOVAR.

## RNA-seq differential expression
1. QC and trimming as above.
2. Either splice-aware alignment (STAR, HISAT2) followed by counting (featureCounts, HTSeq), or pseudo-alignment/quantification (Salmon, kallisto).
3. Differential expression in R with DESeq2, edgeR or limma-voom, using biological replicates (at least three per condition is a common minimum).
4. Multiple-testing correction (Benjamini–Hochberg FDR), then functional enrichment (GO, KEGG) with clusterProfiler or g:Profiler.

## Metagenomics (16S / shotgun)
16S amplicon data is commonly processed with QIIME 2 or DADA2 to amplicon sequence variants; shotgun data with Kraken2/Bracken or MetaPhlAn for taxonomy and HUMAnN for function.

## Reproducibility
Use workflow managers (Snakemake, Nextflow), pinned environments (conda/mamba, containers), record tool versions and parameters, and keep raw data read-only.
