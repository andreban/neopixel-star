"""Hot-plate v2 variant components. Same structure as hotplate/v1/parts.py.

Everything that needs solder paste is on the front, so the front can be
reflowed on a hot plate with the back still bare; only J1 goes on the back,
soldered afterwards with an iron. WS2812B-MINI-V6 (3535) LEDs: same pinout and
package as WS2812B-MINI-V3/W, no per-LED capacitors needed, and their input
threshold is 0.55 x VDD (2.75 V at 5 V), so 3.3 V data drives them directly
without a level shifter.
"""
from common.parts import Part


def led_nets(i):
    """WS2812B-Mini pins: 1 VDD, 2 DOUT, 3 VSS, 4 DIN. LED(i+1) is chain position i."""
    return {"1": "+5V", "2": f"D{i + 1}" if i < 8 else None, "3": "GND",
            "4": "LED_DIN" if i == 0 else f"D{i}"}


LED = dict(lib="LED_SMD", footprint="LED_WS2812B-Mini_PLCC4_3.5x3.5mm", value="WS2812B-Mini",
           symbol="LED:WS2812B", lcsc="C52941386", mpn="WS2812B-MINI-V6", manufacturer="Worldsemi",
           description="Addressable RGB LED, 3535",
           datasheet="https://www.lcsc.com/datasheet/C52941386.pdf")

PARTS = {f"LED{i + 1}": Part(pins=led_nets(i), **LED) for i in range(9)}
PARTS.update({
    "C1": Part("Capacitor_SMD", "C_0603_1608Metric", "10u", "Device:C", {"1": "+5V", "2": "GND"},
               "C19702", "CL10A106KP8NNNC", "Samsung", "10 uF 10 V X5R 0603, bulk"),
    "R1": Part("Resistor_SMD", "R_0603_1608Metric", "330", "Device:R", {"1": "DIN", "2": "LED_DIN"},
               "C23138", "0603WAF3300T5E", "UNI-ROYAL", "330 R 1% 0603, data series resistor"),
    # Back side, soldered with an iron after the front is reflowed.
    "J1": Part("Connector_JST", "JST_PH_S3B-PH-SM4-TB_1x03-1MP_P2.00mm_Horizontal", "JST-PH 3p",
               "Connector_Generic_MountingPin:Conn_01x03_MountingPin",
               {"1": "+5V", "2": "DIN", "3": "GND", "MP": "GND"},
               "C265101", "S3B-PH-SM4-TB(LF)(SN)", "JST", "JST PH 2.0 mm 3-pin, SMD side entry"),
})
