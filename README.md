# NeoPixel Star

A 50 mm, star-shaped NeoPixel board in the spirit of the Adafruit Jewel. The outline is the exact
yellow sparkle from the [Modern Web Guidance logo](reference/mwg-logo.svg), uniformly scaled.

| Front | Back |
|---|---|
| ![front](docs/front.png) | ![back](docs/back.png) |
| ![front, angled](docs/angle-front.png) | ![back, angled](docs/angle-back.png) |

- 9 × WS2812B (5050): one in the centre, one in each of the 8 points
- 100 nF decoupling cap per LED, 10 µF bulk cap
- On-board **74AHCT1G125 level shifter**, so 3.3 V microcontrollers (Pico, ESP32, …) drive it reliably
- JST-PH 2.0 mm 3-pin connector on the back, cable exits toward the top point
- Yellow solder mask, black silkscreen, ENIG, with the MWG logo in exposed gold on the back
- 2 layers, 1.6 mm. Front is a solid 5 V pour, back a solid GND pour

Schematic: [docs/schematic.pdf](docs/schematic.pdf)

**Prefer through-hole?** There's a hand-solderable version with 5 mm LEDs:
[tht/README.md](tht/README.md).

> **Status:** the design passes KiCad ERC and DRC, including a check that the board matches the schematic,
> but it has not been manufactured or tested yet. Treat the first order as a prototype run.

## Wiring

| J1 pin | Signal | Connect to |
|---|---|---|
| 1 | 5V | MCU board's 5 V / VBUS / USB pin, or an external 5 V supply |
| 2 | DIN | Any GPIO (3.3 V or 5 V logic) |
| 3 | GND | GND |

Pins are labelled on the back, next to the connector. The data chain is: LED1 in the centre,
then the top point, then clockwise (index 0 = centre, 1 = top, 2 = top-right, … 8 = top-left).

Minimal Arduino sketch ([Adafruit NeoPixel](https://github.com/adafruit/Adafruit_NeoPixel)):

```cpp
#include <Adafruit_NeoPixel.h>

Adafruit_NeoPixel star(9, /* DIN pin */ 6, NEO_GRB + NEO_KHZ800);

void setup() {
  star.begin();
  star.setBrightness(80);  // keep USB-powered boards within budget, see below
}

void loop() {
  for (int i = 0; i < 9; i++) {          // light each LED in turn, centre first
    star.clear();
    star.setPixelColor(i, star.Color(255, 180, 0));
    star.show();
    delay(200);
  }
}
```

**Power:** at full white the board draws about 540 mA, which is more than many USB ports and cables
supply. When powering from the MCU's USB 5 V pin, cap the brightness in software:

```cpp
strip.setBrightness(80);                        // Adafruit_NeoPixel, 0-255
FastLED.setMaxPowerInVoltsAndMilliamps(5, 400); // FastLED
```

Don't power it from a 3V3 pin. The LEDs need 3.7–5.3 V, and a 3.3 V regulator can't supply the current.

## Ordering

The Gerbers are shared by both fabs. Silkscreen colour is an order option, not part of the files.

**Board options (both fabs):** 2 layers · 1.6 mm FR-4 · **yellow** solder mask · **black** silkscreen ·
**ENIG** surface finish (this is what makes the logo gold) · 1 oz copper.

### JLCPCB

1. Upload `fab/neopixel-star-gerbers.zip`.
2. Choose the options above. If black silkscreen isn't offered with yellow mask, white is the fallback.
   Set *Mark on PCB* to *Remove Mark* (or you get an order number printed on the board).
3. PCB Assembly: **both sides**. Upload `fab/jlcpcb/bom.csv` and `fab/jlcpcb/cpl.csv`.
4. **Check part rotations in JLCPCB's placement preview**, especially the LEDs, U1 and J1.
   KiCad's and JLCPCB's zero orientations don't always agree. Fix any that are off in the
   preview. Pin 1 of each LED should match the notched corner in the preview.

### PCBWay

1. Upload `fab/neopixel-star-gerbers.zip` and choose the options above (black silkscreen on yellow mask).
2. For assembly, upload `fab/pcbway/bom.csv` (manufacturer part numbers, LCSC numbers included
   as a cross-reference) and `fab/pcbway/centroid.csv`. Components are on both sides.

### Parts

| Ref | Part | LCSC |
|---|---|---|
| LED1–LED9 | Worldsemi WS2812B-B/T, 5050 | C2761795 |
| C1–C9, C11 | 100 nF 0402 X7R (Samsung CL05B104KO5NNNC) | C1525 |
| C10 | 10 µF 0805 X5R (Samsung CL21A106KAYNNNC) | C15850 |
| R1 | 330 Ω 0402 (UNI-ROYAL 0402WGF3300TCE) | C25104 |
| R2 | 100 kΩ 0402 (UNI-ROYAL 0402WGF1003TCE) | C25741 |
| U1 | TI SN74AHCT1G125DBVR, SOT-23-5 | C7484 |
| J1 | JST S3B-PH-SM4-TB(LF)(SN) | C265101 |

Check stock and prices when ordering. Any WS2812B/SK6812 in the 4-pin 5050 package with the
same pinout works.

## Opening in KiCad or EasyEDA

- **KiCad 10:** open `kicad/neopixel-star.kicad_pro`. Symbols and footprints come from the project's
  own libraries (`neopixel-star.kicad_sym`, `neopixel-star.pretty`), so no global libraries are needed.
  KiCad ships no 3D model for the SMD JST connector. `neopixel-star.3dshapes/` has a simple generated
  one (housing, opening, leads, tabs), used for the renders.
- **EasyEDA Pro:** *File → Import → KiCad*, then pick `easyeda/neopixel-star-kicad.zip`. After importing:
  - EasyEDA's default via rule asks for a 0.5 mm hole. This board uses 0.3 mm vias, which both fabs
    make at standard price. Set *Design → Design Rules → Via Size* to a minimum inner diameter of
    0.3 mm and a minimum outer diameter of 0.6 mm.
  - EasyEDA rebuilds the copper pours on import, so check the front 5 V and back GND pours.
  - EasyEDA's DRC may also flag the gold artwork (copper deliberately connected to no net) and
    LED9's unused DOUT pin. Both are expected.
- **Anything else:** `easyeda/outline.dxf` is the exact board outline, and the Gerbers work with any viewer.

## Repository layout

| Path | Contents |
|---|---|
| `kicad/` | KiCad 10 project, schematic, board, project symbol/footprint/3D libraries |
| `fab/` | Gerbers + drill (`neopixel-star-gerbers.zip`), `jlcpcb/` and `pcbway/` BOM and placement files |
| `easyeda/` | Zipped KiCad project for EasyEDA Pro, outline DXF |
| `docs/` | Renders and schematic PDF |
| `tht/` | The through-hole version, with the same `kicad/`, `fab/`, `easyeda/` and `docs/` layout |
| `scripts/` | Generators: everything above is built from these |
| `reference/` | The source logo SVG |
| `PLAN.md` | Design decisions and their reasoning |

## Rebuilding

Everything is generated by scripts from [scripts/parts.py](scripts/parts.py) (SMD),
[scripts/parts_tht.py](scripts/parts_tht.py) (through-hole) and [scripts/config.py](scripts/config.py).
KiCad 10 must be installed. It is found in its standard install location, or set `KICAD_DIR` to the
installation directory.

```sh
python scripts/build_all.py          # both versions
python scripts/build_all.py tht      # just one: smd or tht
```

This regenerates the schematic and board, refills the pours with KiCad's zone filler, and runs ERC
and DRC with schematic parity. The build stops on any violation. It then exports Gerbers, the
JLCPCB/PCBWay BOM and placement files, the EasyEDA package and the renders in `docs/` (under
`tht/` for the through-hole version).

To change the size, edit `STAR_WIDTH` in `config.py`. Below about 44.5 mm the 5050 LEDs no longer
fit in the points. The LED radii, routing waypoints and back-side layout are tuned for 50 mm, so
check DRC after changing it.

## Credits

The board outline and back-side artwork use the Modern Web Guidance logo from
[developer.chrome.com](https://developer.chrome.com/). Inspired by the
[Adafruit NeoPixel Jewel](https://www.adafruit.com/product/2226).

## License

[Apache License 2.0](LICENSE).
