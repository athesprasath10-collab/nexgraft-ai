# Sensors and electronics for biomedical wearables

## Sensing options (examples — verify availability and datasheets)
| Parameter | Common approach | Example parts |
|---|---|---|
| Heart rate, SpO2 | PPG (red/IR/green LEDs + photodiode) | MAX30102, MAX30101, MAX86150 (PPG + ECG) |
| ECG | Biopotential analog front end | AD8232 (single-lead, prototyping), MAX30003 (single-channel ECG AFE), ADS1292R (2-ch, 24-bit, with respiration), ADS1298 (8-ch, 24-bit) |
| Skin/body temperature | Digital temperature sensor | MAX30205 (±0.1 °C from 37–39 °C), TMP117 (±0.1 °C from −20–50 °C) |
| Motion, activity | IMU (accelerometer + gyroscope) | BMI270, LSM6DSO/LSM6DSOX; MPU-6050 is a legacy hobby part |
| EDA / bioimpedance | Impedance analog front end | AD5940/AD5941 |

## Processing and connectivity
- Bluetooth Low Energy SoCs: Nordic nRF52832, nRF52840, nRF5340; ST STM32WB. ESP32 variants add Wi-Fi but draw more power.
- Low-power MCUs without radio: STM32L4/U5 series.
- Consider on-device processing (filtering, feature extraction) to reduce radio time and save energy.

## Power
- Small Li-Po cells (e.g. 100–500 mAh) with a charger IC (MCP73831, BQ25100 for small cells) and optionally a fuel gauge (MAX17048).
- Use ultra-low-quiescent-current regulators (e.g. TPS7A02 LDO, TPS62840 buck) and duty-cycle sensors and radio aggressively.
- Battery safety for portable equipment: IEC 62133.

## Design considerations
- Signal quality: motion artefacts, skin contact pressure, ambient light for PPG, electrode type (wet Ag/AgCl vs dry or textile electrodes).
- Sampling: ECG 250–500 Hz for monitoring (higher for detailed morphology), PPG 25–100 Hz for heart rate (higher for HRV/morphology), IMU 25–100 Hz for activity.
- Mechanical: enclosure sealing (IP rating), biocompatible skin-contact materials (e.g. medical-grade silicone), comfort, weight and strap design.
- Data: secure BLE pairing, encryption, privacy of health data.
- Patient safety: electrical isolation, leakage current limits, no mains connection while worn and charging unless designed for it.
- Regulatory path: whether the device is a wellness product or a medical device changes the required standards and testing.
