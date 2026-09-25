# Mechanical design basics

## Material properties (typical room-temperature values)
| Material | Young's modulus E | Yield strength |
|---|---|---|
| Structural steel (IS 2062 E250 / S275) | ~200–210 GPa | 250–275 MPa |
| Stainless steel 304 (annealed) | ~193 GPa | ~215 MPa |
| Aluminium 6061-T6 | ~69 GPa | ~276 MPa |
| Titanium Ti-6Al-4V | ~114 GPa | ~880 MPa |
| ABS | ~2.0–2.4 GPa | ~40 MPa |
| PLA (3D printing filament, bulk) | ~3.5 GPa | ~50–60 MPa |
| PEEK | ~3.6 GPa | ~90–100 MPa |
Values vary by grade, temper and process; 3D-printed parts are anisotropic and weaker between layers.

## Stress, strain and safety factor
Normal stress σ = F/A; strain ε = ΔL/L; Hooke's law σ = E·ε in the elastic range. Factor of safety = allowable (e.g. yield) / working stress. Typical values: about 1.5–2 for well-characterised static loads, higher for uncertain loads, fatigue or safety-critical parts.

## Beams
Second moment of area for a rectangle: I = b·h³/12. Bending stress σ = M·c/I with c = h/2. Point load at the centre of a simply supported beam: δ = F·L³/(48·E·I), Mmax = F·L/4. Cantilever with end load: δ = F·L³/(3·E·I), Mmax = F·L.

## Fits and tolerances
ISO 286 hole-basis fits: H7/g6 (sliding clearance), H7/h6 (locational clearance), H7/k6 (transition), H7/p6 (locational interference). Specify only the tolerances function requires; tight tolerances raise cost.

## Design for manufacture
Match the design to the process: uniform wall thickness and draft for injection moulding, minimum wall and overhang limits for 3D printing, standard tool radii and hole sizes for machining, and standard fasteners.

## Tools
CAD: SolidWorks, Autodesk Fusion, Onshape, FreeCAD. Simulation (FEA): ANSYS, SolidWorks Simulation, CalculiX. FEA results need mesh-convergence checks and validation by testing.
