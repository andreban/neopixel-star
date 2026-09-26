"""Through-hole variant components. Same structure as smd/parts.py.

WS2812D-F5 LEDs accept 3.3 V data directly (VIH = 2.7 V at VDD = 5 V), and
their datasheet calls for no per-LED capacitor, so the board is just the LEDs,
a bulk capacitor, a series resistor and the connector.
"""
from common.parts import Part


def led_nets(i):
    """WS2812D-F5 pins: 1 DOUT, 2 VDD, 3 GND, 4 DIN. LED(i+1) is chain position i."""
    return {"1": f"D{i + 1}" if i < 8 else None, "2": "+5V", "3": "GND",
            "4": "LED_DIN" if i == 0 else f"D{i}"}


LED = dict(lib="LED_THT", footprint="LED_D5.0mm-4_RGB_Staggered_Pins", value="WS2812D-F5",
           # KiCad's APA-106-F5 symbol is 1 DO, 2 GND, 3 VDD, 4 DI. The
           # WS2812D-F5 swaps the supply pins (2 VDD, 3 GND), so the project
           # library gets a corrected copy.
           symbol="LED:APA-106-F5", symbol_name="WS2812D-F5", pin_numbers={"2": "3", "3": "2"}, nc_pin_name="DO",
           lcsc="C190565", mpn="WS2812D-F5", manufacturer="Worldsemi",
           description="Addressable RGB LED, 5 mm through-hole",
           datasheet="https://www.lcsc.com/datasheet/C190565.pdf")

PARTS = {f"LED{i + 1}": Part(pins=led_nets(i), **LED) for i in range(9)}
PARTS.update({
    "C1": Part("Capacitor_THT", "CP_Radial_D5.0mm_P2.00mm", "10u", "Device:C_Polarized",
               {"1": "+5V", "2": "GND"}, "C43347", "KM106M025D11RR0VH2FP0", "Chengx",
               "10 uF 25 V electrolytic, 5 x 11 mm, bulk"),
    "R1": Part("Resistor_THT", "R_Axial_DIN0207_L6.3mm_D2.5mm_P2.54mm_Vertical", "330", "Device:R",
               {"1": "DIN", "2": "LED_DIN"}, "C119313", "MF1/4W-330R 1%", "CCO",
               "330 R 1/4 W metal film, data series resistor"),
    # Same order as the SMD board and WS2812 strip pigtails: 5V, DIN, GND.
    "J1": Part("Connector_JST", "JST_PH_S3B-PH-K_1x03_P2.00mm_Horizontal", "JST-PH 3p",
               "Connector_Generic:Conn_01x03", {"1": "+5V", "2": "DIN", "3": "GND"},
               "C157929", "S3B-PH-K-S(LF)(SN)", "JST", "JST PH 2.0 mm 3-pin, through-hole side entry"),
})
