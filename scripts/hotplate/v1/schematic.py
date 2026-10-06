"""Hot-plate schematic sheet."""
from common.schematic import power_flags, led_grid

G = 2.54


def draw(sh):
    sh.text("Input: 5V / DIN / GND. U1 (AHCT, TTL input) accepts 3.3 V or 5 V data.", 20 * G, 12 * G)
    sh.part("J1", 22 * G, 22 * G)
    power_flags(sh, G)
    sh.part("R2", 32 * G, 24 * G)
    sh.part("U1", 44 * G, 22 * G)
    sh.part("C2", 56 * G, 22 * G)
    sh.part("R1", 64 * G, 22 * G)
    sh.part("C1", 72 * G, 22 * G)
    led_grid(sh, G, caps=False)
