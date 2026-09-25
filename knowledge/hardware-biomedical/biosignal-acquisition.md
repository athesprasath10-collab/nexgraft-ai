# Biosignal acquisition fundamentals

## Typical signal characteristics
| Signal | Amplitude | Bandwidth of interest |
|---|---|---|
| ECG | ~0.5–4 mV | 0.5–40 Hz (monitoring), 0.05–150 Hz (diagnostic) |
| EEG | ~10–100 µV at the scalp | ~0.5–100 Hz (most clinical content below ~40 Hz) |
| Surface EMG | up to a few mV | ~20–500 Hz |
| PPG | pulsatile AC is a small fraction of the DC level | ~0.5–5 Hz for pulse; wider for morphology |
| Respiration (impedance) | small impedance changes (ohms) | ~0.1–1 Hz |

## Analog front end
- Instrumentation amplifier with high common-mode rejection (CMRR) and high input impedance; right-leg drive (driven common electrode) further reduces common-mode interference.
- Electrode DC offsets can reach hundreds of millivolts (ECG standards commonly require tolerating ±300 mV), so early-stage gain must not saturate; AC coupling or high-resolution ΔΣ ADCs with modest gain help.
- High-pass filtering removes baseline wander; low-pass anti-aliasing filters must cut off below half the sampling rate.
- Mains interference: 50 Hz in India and Europe (60 Hz in the Americas). Notch filters help but distort nearby frequencies; good shielding and layout come first.
- Integrated ECG AFEs (e.g. ADS129x, MAX30003) combine PGA, 24-bit ΔΣ ADC, lead-off detection and right-leg drive.

## Digital processing
Band-pass filtering, QRS detection (e.g. Pan–Tompkins algorithm), motion-artefact handling with accelerometer reference, signal-quality indices, and feature extraction (heart rate, HRV, SpO2 ratio-of-ratios).

## Sampling and data rate
Nyquist requires sampling above twice the highest frequency of interest; in practice 2.5–5× plus a proper anti-aliasing filter. Data rate = sampling rate × channels × bytes per sample.
