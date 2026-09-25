# Electronic component selection

## Passive components
- Resistors: standard E-series values (E12 for 10%, E24 for 5%, E96 for 1%). Check tolerance, temperature coefficient and power rating; derate to about 50% of rated power.
- Capacitors: C0G/NP0 ceramics are stable (filters, timing). X7R/X5R ceramics lose significant capacitance under DC bias and temperature — check the DC-bias curve. Electrolytic and tantalum parts provide bulk capacitance; observe voltage derating.
- Decoupling: place a 100 nF ceramic capacitor close to every IC supply pin, plus bulk capacitance (1–10 µF or more) per power rail.

## Power supply
- LDO regulators are simple and quiet but dissipate (Vin − Vout) × I as heat.
- Switching regulators (buck, boost, buck-boost) are efficient but need careful layout and filtering for noise-sensitive analog circuits.
- For battery devices, check quiescent current, dropout voltage and efficiency at light load.

## Microcontrollers
Choose by peripherals (ADC resolution, timers, DMA), communication (I2C, SPI, UART, USB, CAN, BLE/Wi-Fi), memory, power modes, toolchain and community support. Common families: STM32 (ARM Cortex-M), Nordic nRF52/nRF53 (BLE), ESP32 (Wi-Fi + BLE), RP2040, and AVR/ATmega for simple tasks.

## Interfaces
- I2C: two wires, addressable devices, typically 100/400 kHz (1 MHz Fast-mode Plus); needs pull-up resistors.
- SPI: faster, full-duplex, one chip-select per device.
- UART: simple asynchronous serial.
Check logic voltage levels (1.8 V / 3.3 V / 5 V) and use level shifters when mixing.

## Protection
ESD protection (TVS diodes) on connectors, reverse-polarity protection, fuses or polyfuses, and current limiting on outputs.

## Sourcing
Prefer parts in active production with multiple distributors (and second sources), check lifecycle status (NRND/EOL), and confirm packages you can assemble.
