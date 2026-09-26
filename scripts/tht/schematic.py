"""Through-hole schematic sheet."""
from common.schematic import power_flags, led_grid

G = 2.54


def draw(sh):
    sh.text("Input: 5V / DIN / GND. WS2812D-F5 accepts 3.3 V or 5 V data directly (VIH = 2.7 V).",
            20 * G, 12 * G)
    sh.part("J1", 22 * G, 22 * G)
    power_flags(sh, G)
    sh.part("R1", 34 * G, 22 * G)
    sh.part("C1", 44 * G, 22 * G)
    led_grid(sh, G, caps=False)
