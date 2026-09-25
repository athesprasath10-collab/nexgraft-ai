# PCB design guidelines

## Stack-up and grounding
Use a solid ground plane (a 4-layer board with signal–ground–power–signal is a robust default). Avoid splitting the ground plane under high-speed or sensitive signals; keep return paths short.

## Layout
- Place decoupling capacitors as close as possible to IC power pins, with short vias to ground.
- Keep switching regulator loops (input capacitor, switch, diode/FET, inductor) small.
- Separate noisy digital and switching sections from sensitive analog front ends; route analog signals away from clocks.
- Keep antenna areas free of copper as the RF module datasheet specifies.

## Trace width and clearance
Trace width for a given current and temperature rise is estimated from IPC-2221 (or the newer IPC-2152) charts; online calculators implement them. Follow the manufacturer's minimum trace/space and drill capabilities (e.g. 0.15 mm / 0.15 mm is common for low-cost fabs).

## Design for manufacture and test
Add fiducials, test points for power rails and key signals, clear silkscreen with polarity marks, and a programming/debug header (SWD/JTAG). Run DRC and ERC before ordering and review the Gerbers in a viewer.

## Tools
KiCad (free, open source), Altium Designer, Autodesk Fusion Electronics/EAGLE. Simulate analog sections in LTspice or ngspice before layout.
