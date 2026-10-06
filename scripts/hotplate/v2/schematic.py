"""Hot-plate v2 schematic sheet."""
from common.schematic import power_flags, led_grid

G = 2.54


def draw(sh):
    sh.text("Input: 5V / DIN / GND. WS2812B-MINI-V6 accepts 3.3 V or 5 V data directly (VIH = 0.55 x VDD).",
            20 * G, 12 * G)
    sh.part("J1", 22 * G, 22 * G)
    power_flags(sh, G)
    sh.part("R1", 36 * G, 22 * G)
    sh.part("C1", 46 * G, 22 * G)
    led_grid(sh, G, caps=False)
