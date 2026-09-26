"""SMD variant components: footprints, pin -> net maps and BOM data. The
single source of truth for the board, schematic and BOM/CPL exports."""
from common.parts import Part

LED = dict(lib="LED_SMD", footprint="LED_WS2812B_PLCC4_5.0x5.0mm_P3.2mm", value="WS2812B",
           symbol="LED:WS2812B", lcsc="C2761795", mpn="WS2812B-B/T", manufacturer="Worldsemi",
           description="Addressable RGB LED, 5050",
           datasheet="https://cdn-shop.adafruit.com/datasheets/WS2812B.pdf")
CAP_100N = dict(lib="Capacitor_SMD", footprint="C_0402_1005Metric", value="100n",
                symbol="Device:C", lcsc="C1525", mpn="CL05B104KO5NNNC", manufacturer="Samsung",
                description="100 nF 16 V X7R 0402")
RES_0402 = dict(lib="Resistor_SMD", footprint="R_0402_1005Metric", symbol="Device:R",
                manufacturer="UNI-ROYAL")


def led_nets(i):
    """WS2812B pins: 1 VDD, 2 DOUT, 3 VSS, 4 DIN. LED(i+1) is chain position i."""
    return {"1": "+5V", "2": f"D{i + 1}" if i < 8 else None, "3": "GND",
            "4": "LED_DIN" if i == 0 else f"D{i}"}


PARTS = {}
for _i in range(9):
    PARTS[f"LED{_i + 1}"] = Part(pins=led_nets(_i), **LED)
    PARTS[f"C{_i + 1}"] = Part(pins={"1": "+5V", "2": "GND"}, **CAP_100N)
PARTS.update({
    "C10": Part("Capacitor_SMD", "C_0805_2012Metric", "10u", "Device:C", {"1": "+5V", "2": "GND"},
                "C15850", "CL21A106KAYNNNC", "Samsung", "10 uF 25 V X5R 0805, bulk"),
    "C11": Part(pins={"1": "+5V", "2": "GND"}, **CAP_100N),
    "R1": Part(value="330", pins={"1": "DIN_5V", "2": "LED_DIN"}, lcsc="C25104",
               mpn="0402WGF3300TCE", description="330 R 1% 0402, data series resistor", **RES_0402),
    "R2": Part(value="100k", pins={"1": "DIN", "2": "GND"}, lcsc="C25741",
               mpn="0402WGF1003TCE", description="100 k 1% 0402, DIN pull-down", **RES_0402),
    # SN74AHCT1G125DBV: 1 ~OE, 2 A, 3 GND, 4 Y, 5 VCC. TTL input threshold,
    # so 3.3 V logic drives it reliably from a 5 V supply.
    "U1": Part("Package_TO_SOT_SMD", "SOT-23-5", "74AHCT1G125", "74xGxx:74AHCT1G125",
               {"1": "GND", "2": "DIN", "3": "GND", "4": "DIN_5V", "5": "+5V"},
               "C7484", "SN74AHCT1G125DBVR", "Texas Instruments", "Level shifter / buffer, SOT-23-5",
               "https://www.ti.com/lit/ds/symlink/sn74ahct1g125.pdf"),
    # Same order as WS2812 strip pigtails: 5V, DIN, GND (labelled on the back).
    # Mounting tabs on GND for strength and a better ground.
    "J1": Part("Connector_JST", "JST_PH_S3B-PH-SM4-TB_1x03-1MP_P2.00mm_Horizontal", "JST-PH 3p",
               "Connector_Generic_MountingPin:Conn_01x03_MountingPin",
               {"1": "+5V", "2": "DIN", "3": "GND", "MP": "GND"},
               "C265101", "S3B-PH-SM4-TB(LF)(SN)", "JST", "JST PH 2.0 mm 3-pin, SMD side entry"),
})
