"""Hot-plate variant components. Same structure as smd/parts.py.

Everything small is on the front, so the front can be reflowed on a hot plate
with the back still bare; only J1 and U1 go on the back, soldered afterwards
with an iron. WS2812B-MINI-V3/W (3535) LEDs: same pinout as the 5050 WS2812B,
and their datasheet calls for no per-LED capacitor. Their input threshold is
0.63 x VDD (3.15 V at 5 V), so U1 still level-shifts 3.3 V data.
"""
from common.parts import Part


def led_nets(i):
    """WS2812B-Mini pins: 1 VDD, 2 DOUT, 3 VSS, 4 DIN. LED(i+1) is chain position i."""
    return {"1": "+5V", "2": f"D{i + 1}" if i < 8 else None, "3": "GND",
            "4": "LED_DIN" if i == 0 else f"D{i}"}


LED = dict(lib="LED_SMD", footprint="LED_WS2812B-Mini_PLCC4_3.5x3.5mm", value="WS2812B-Mini",
           symbol="LED:WS2812B", lcsc="C527089", mpn="WS2812B-MINI-V3/W", manufacturer="Worldsemi",
           description="Addressable RGB LED, 3535",
           datasheet="https://www.lcsc.com/datasheet/C527089.pdf")
RES_0603 = dict(lib="Resistor_SMD", footprint="R_0603_1608Metric", symbol="Device:R",
                manufacturer="UNI-ROYAL")

PARTS = {f"LED{i + 1}": Part(pins=led_nets(i), **LED) for i in range(9)}
PARTS.update({
    "C1": Part("Capacitor_SMD", "C_0603_1608Metric", "10u", "Device:C", {"1": "+5V", "2": "GND"},
               "C19702", "CL10A106KP8NNNC", "Samsung", "10 uF 10 V X5R 0603, bulk"),
    "C2": Part("Capacitor_SMD", "C_0603_1608Metric", "100n", "Device:C", {"1": "+5V", "2": "GND"},
               "C14663", "CC0603KRX7R9BB104", "YAGEO", "100 nF 50 V X7R 0603, U1 decoupling"),
    "R1": Part(value="330", pins={"1": "DIN_5V", "2": "LED_DIN"}, lcsc="C23138",
               mpn="0603WAF3300T5E", description="330 R 1% 0603, data series resistor", **RES_0603),
    "R2": Part(value="100k", pins={"1": "DIN", "2": "GND"}, lcsc="C25803",
               mpn="0603WAF1003T5E", description="100 k 1% 0603, DIN pull-down", **RES_0603),
    # Back side, soldered with an iron after the front is reflowed.
    "U1": Part("Package_TO_SOT_SMD", "SOT-23-5", "74AHCT1G125", "74xGxx:74AHCT1G125",
               {"1": "GND", "2": "DIN", "3": "GND", "4": "DIN_5V", "5": "+5V"},
               "C7484", "SN74AHCT1G125DBVR", "Texas Instruments", "Level shifter / buffer, SOT-23-5",
               "https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf"),
    "J1": Part("Connector_JST", "JST_PH_S3B-PH-SM4-TB_1x03-1MP_P2.00mm_Horizontal", "JST-PH 3p",
               "Connector_Generic_MountingPin:Conn_01x03_MountingPin",
               {"1": "+5V", "2": "DIN", "3": "GND", "MP": "GND"},
               "C265101", "S3B-PH-SM4-TB(LF)(SN)", "JST", "JST PH 2.0 mm 3-pin, SMD side entry"),
})
