# Molecular docking workflow (user-executed)

Docking predicts how a small molecule (ligand) binds to a protein target. NEXGRAFT prepares the workflow, scripts and parameters; the user runs the docking software and interprets the results.

## 1. Target preparation
- Obtain a structure from the PDB (experimental) or a predicted model (e.g. AlphaFold DB). Prefer high-resolution experimental structures with a bound ligand in the site of interest.
- Remove waters and unrelated heteroatoms (keep essential cofactors or metal ions), add hydrogens, assign charges and check protonation states. Tools: PDBFixer/OpenMM, AutoDockTools or Meeko, Open Babel, UCSF ChimeraX.

## 2. Ligand preparation
- Start from SMILES or SDF (e.g. PubChem, ChEMBL). Generate 3D conformers and protonation states at physiological pH using RDKit or Open Babel.
- Convert to the docking program's format (for AutoDock Vina: PDBQT, prepared with Meeko or Open Babel).

## 3. Define the search space
Centre a grid box on the known binding site (co-crystallised ligand, literature residues, or pocket detection such as fpocket or P2Rank). Box sizes around 20–25 Å per side are typical for a single pocket.

## 4. Run docking
AutoDock Vina example: vina --receptor protein.pdbqt --ligand ligand.pdbqt --center_x X --center_y Y --center_z Z --size_x 22 --size_y 22 --size_z 22 --exhaustiveness 16 --num_modes 9 --out docked.pdbqt. Alternatives include smina, GNINA (CNN rescoring), and commercial tools such as Glide.

## 5. Analyse and validate
- Vina reports predicted binding affinities in kcal/mol (more negative = stronger predicted binding). These scores are approximate and not experimental affinities.
- Inspect poses and interactions (hydrogen bonds, hydrophobic contacts) in PyMOL, ChimeraX or PLIP.
- Validate the protocol by redocking the co-crystallised ligand; a pose RMSD below about 2 Å is a common success threshold.
- Consider molecular dynamics (GROMACS, OpenMM) and experimental assays for confirmation.
