"""XIAO variant components. Same structure as hotplate/v2/parts.py.

The front is hot-plate v2's: WS2812B-MINI-V6 LEDs (3.3 V data is enough,
VIH = 0.55 x VDD), R1 and C1, all reflowed in one pass. The back holds only a
Seeed Studio XIAO in female headers (soldered with an iron afterwards), so
it can be unplugged.
The XIAO's USB-C powers the LEDs (its 5V pin is USB VBUS) and its D3 drives
the chain. Any XIAO fits: they all share the 14 edge pins.
"""
from common import xiao
from common.parts import Part


def led_nets(i):
    """WS2812B-Mini pins: 1 VDD, 2 DOUT, 3 VSS, 4 DIN. LED(i+1) is chain position i."""
    return {"1": "+5V", "2": f"D{i + 1}" if i < 8 else None, "3": "GND",
            "4": "LED_DIN" if i == 0 else f"D{i}"}


LED = dict(lib="LED_SMD", footprint="LED_WS2812B-Mini_PLCC4_3.5x3.5mm", value="WS2812B-Mini",
           symbol="LED:WS2812B", lcsc="C52941386", mpn="WS2812B-MINI-V6", manufacturer="Worldsemi",
           description="Addressable RGB LED, 3535",
           datasheet="https://www.lcsc.com/datasheet/C52941386.pdf")

# XIAO pins: only 5V (USB VBUS), GND and D3 are used.
XIAO_NETS = {str(n): None for n in range(1, 15)}
XIAO_NETS.update({"4": "DIN", "13": "GND", "14": "+5V"})

PARTS = {f"LED{i + 1}": Part(pins=led_nets(i), **LED) for i in range(9)}
PARTS.update({
    "C1": Part("Capacitor_SMD", "C_0603_1608Metric", "10u", "Device:C", {"1": "+5V", "2": "GND"},
               "C19702", "CL10A106KP8NNNC", "Samsung", "10 uF 10 V X5R 0603, bulk"),
    "R1": Part("Resistor_SMD", "R_0603_1608Metric", "330", "Device:R", {"1": "DIN", "2": "LED_DIN"},
               "C23138", "0603WAF3300T5E", "UNI-ROYAL", "330 R 1% 0603, data series resistor"),
    # Back side, in two 1x7 2.54 mm female headers soldered with an iron after
    # the front is reflowed.
    "U1": Part("generated", xiao.NAME, "XIAO RP2040", "generated:XIAO", XIAO_NETS,
               "C22184628", "102010428", "Seeed Studio",
               "Seeed Studio XIAO RP2040 in 2.54 mm female headers (any XIAO fits)",
               "https://wiki.seeedstudio.com/XIAO-RP2040/",
               pin_names={str(n): name for n, name in xiao.PIN_NAMES.items()}),
})
