# Wearable monitoring of physiological parameters (research overview)

## Commonly monitored parameters
- Heart rate: from ECG (electrical activity) or PPG (optical blood-volume changes). A commonly cited normal resting range for adults is 60–100 beats per minute.
- Heart rate variability (HRV): variation in beat-to-beat intervals. Time-domain measures include SDNN and RMSSD; frequency-domain measures include LF (0.04–0.15 Hz) and HF (0.15–0.4 Hz) power. HRV reflects autonomic nervous system activity and is sensitive to recording conditions.
- Rhythm: single-lead ECG wearables and PPG-based algorithms are widely studied for atrial fibrillation screening; several consumer devices have regulatory clearance for AF notification features.
- Blood oxygen saturation (SpO2): pulse oximetry compares absorption of red (~660 nm) and infrared (~940 nm) light. Healthy adults at sea level typically read about 95–100%. Studies have shown pulse oximeters can overestimate saturation in people with darker skin pigmentation, an important equity consideration.
- Respiratory rate: typically 12–20 breaths per minute in resting adults; can be derived from chest impedance, accelerometry or PPG/ECG modulation.
- Skin or body temperature: skin temperature differs from core temperature and is affected by environment.
- Blood pressure: cuffless estimation from pulse transit/arrival time or PPG morphology is an active research area; accuracy, calibration drift and validation (e.g. IEEE 1708, ISO 81060-2 for cuff devices) remain challenges.
- Activity and posture: inertial measurement units (accelerometer, gyroscope).
- Electrodermal activity (EDA): sweat-gland activity related to sympathetic arousal.

## Research challenges
Motion artefacts, sensor–skin contact, inter-individual variability (skin tone, BMI, age), battery life versus sampling rate, data privacy, algorithm validation against reference standards, and the difference between consumer wellness devices and regulated medical devices.

## Typical study designs
Validation studies compare the wearable against a reference (e.g. 12-lead ECG, Holter, arterial blood gas, polysomnography) using Bland–Altman analysis, mean absolute error and correlation. Real-world studies examine adherence, usability and clinical outcomes.

Reference ranges vary by source and population; this note is for research orientation, not clinical interpretation.
