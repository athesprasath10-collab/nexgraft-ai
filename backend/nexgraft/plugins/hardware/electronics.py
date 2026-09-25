from nexgraft.agents.base import PluginSpec

PLUGIN = PluginSpec(
    id="electronics",
    agent="hardware",
    name="Electronics",
    description="Circuits, components, microcontrollers, power supplies and PCB design.",
    icon="circuit-board",
    order=2,
    keywords={
        "circuit": 3.0, "pcb": 3.0, "resistor": 3.0, "capacitor": 3.0, "microcontroller": 3.0, "arduino": 3.0,
        "esp32": 3.0, "stm32": 3.0, "regulator": 3.0, "ldo": 3.0, "op-amp": 3.0, "opamp": 3.0, "led": 2.0,
        "i2c": 3.0, "spi": 3.0, "uart": 3.0, "adc": 2.0, "transistor": 3.0, "mosfet": 3.0, "electronics": 3.0,
        "embedded": 2.0, "firmware": 2.0, "filter": 1.5, "oscillator": 3.0,
    },
    prompt=(
        "Active domain plugin: Electronics. Consider component ratings and tolerances, power budget, decoupling, "
        "signal integrity, interfaces (I2C/SPI/UART), protection (ESD, reverse polarity), PCB layout and "
        "manufacturability. Show circuit calculations with units."
    ),
    knowledge_collection="hardware-electronics",
    tools=["ohms_law", "voltage_divider", "led_resistor", "rc_filter"],
    examples=["Design considerations for a 5 V to 3.3 V power supply for an ESP32 sensor node."],
)
