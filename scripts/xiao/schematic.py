"""XIAO variant schematic sheet."""
from common.schematic import power_flags, led_grid

G = 2.54


def draw(sh):
    sh.text("USB-C on the XIAO powers the LEDs (5V = USB VBUS); its D3 drives the chain. Any XIAO fits.",
            20 * G, 8 * G)
    sh.text("WS2812B-MINI-V6 accepts 3.3 V data directly (VIH = 0.55 x VDD).", 20 * G, 10 * G)
    sh.part("U1", 26 * G, 22 * G)
    power_flags(sh, G)
    sh.part("R1", 40 * G, 22 * G)
    sh.part("C1", 50 * G, 22 * G)
    led_grid(sh, G, caps=False)
