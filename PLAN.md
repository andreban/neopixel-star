# NeoPixel Star PCB — Plan

## Goal
A star-shaped PCB, inspired by the Adafruit Jewel, with yellow solder mask. It has 9 addressable RGB LEDs on the
front and a JST connector plus support parts on the back. It ships as a KiCad project that can be
imported into EasyEDA and fabricated (and optionally assembled) by JLCPCB or PCBWay.

## Source shape
- Taken from the yellow `<path>` (`fill="#FBBC04"`) in `reference/mwg-logo.svg`.
- It is an **8-point sparkle**, not a 5-point star: 4 long points (N/E/S/W) and 4 short diagonal points
  (NE/SE/SW/NW), with small fillets at every tip and inner corner. Center + 8 points = **9 LEDs**.
- The bounding box is square (96.19 × 96.19 SVG units). The outline is scaled uniformly, so the only
  free parameter is the physical size.

## LED layout (computed)
- 1 LED in the center. 8 LEDs sit on the arm axes, rotated to follow each arm (0°/45°/90°…), each pushed
  as far out into its point as it fits.
- Assumptions: 0.4 mm LED-to-board-edge clearance and 0.3 mm between LED footprints.
- Minimum star width (tip to tip) that fits all 9:

| LED package | Parts | Min width |
|---|---|---|
| 5050 | WS2812B, SK6812 | ~42 mm |
| 3535 | SK6812-3535 | ~30.5 mm |
| 2020 | WS2812B-2020 | ~19.5 mm |

The long points are narrow triangles, so the LEDs there stop well short of the tips. The tips themselves
will stay dark.

## Electrical (Jewel-style)
- 5 V, GND and DIN in through the JST connector.
- Daisy chain order: center → N → NE → E → … → NW (clockwise). The order is open for discussion.
- 100 nF decoupling capacitor per LED (0402/0603) on the back, directly behind each LED where possible.
- Level shifter on DIN: 74AHCT1G125 (SOT-23-5) powered from 5 V, with its enable pin tied low. Its TTL input
  (VIH ≈ 2 V) accepts 3.3 V or 5 V data and outputs a full 5 V signal. It gets a 100 nF decoupling cap, and a
  weak pull-down on its input so the first LED doesn't pick up noise when nothing is connected.
- ~330 Ω series resistor between the shifter output and the first LED's DIN.
- ~10 µF bulk capacitor at the connector.
- Worst-case current: 9 × 60 mA ≈ 540 mA at full white. Power and ground get wide traces or pours on both layers.
- 2-layer, 1.6 mm FR-4 (or 1.0/1.2 mm), yellow mask, white silkscreen.

## Deliverables
1. `neopixel-star.kicad_pro/.kicad_sch/.kicad_pcb` (KiCad 10 format). The board outline goes on
   Edge.Cuts, generated from the SVG path by a script so it matches exactly.
2. The generator script (Python) that builds the outline and LED placement. This makes size changes cheap.
3. Fab outputs: shared Gerbers + drill files, plus JLCPCB and PCBWay assembly files (see Decisions).
4. README with ordering settings for JLCPCB / PCBWay and EasyEDA import notes.

## Fab notes / risks
- Inner corners: the fab mills the outline with a ~1 mm bit, so inner corners get at least a ~0.5 mm radius.
  The SVG's inner fillets are ~0.45 mm at 42 mm width, so they will be essentially identical. At smaller
  sizes they will be slightly rounder than the SVG.
- Yellow mask is supported by both JLCPCB and PCBWay. It may add cost or lead time, and at JLCPCB it
  can limit which PCBA options are available.
- KiCad is not installed on this machine. Running DRC and exporting Gerbers needs KiCad 9 (`kicad-cli`).

## Decisions
- LEDs: 5050 (WS2812B or SK6812, whichever is stocked at both fabs), star **50 mm** tip to tip (45 mm fits the LEDs alone,
  with no room left for the caps and data routing between them).
- Assembly: fab-assembled (PCBA), double-sided: LEDs + 100 nF caps + R1 (330 R) on the front (no room for R1
  between J1 and U1 on the back); JST, level shifter,
  resistors and bulk cap on the back.
- Fabs: support **both JLCPCB and PCBWay** from one design. Silkscreen color is an order option, not part
  of the files, so the Gerbers are shared. Separate assembly packages:
  - `fab/jlcpcb/`: Gerbers + BOM (LCSC part numbers) + CPL in JLCPCB format. Order with black silkscreen
    if offered for yellow mask, otherwise white.
  - `fab/pcbway/`: Gerbers + BOM (manufacturer part numbers) + centroid file in PCBWay format. Order with
    black silkscreen.
  - Parts are chosen to be available at both (common WS2812B/SK6812, 74AHCT1G125, JST S3B-PH-SM4-TB).
- Connector: JST-PH 2.0 3-pin (5V / DIN / GND), SMD right-angle, on the back.
- On-board 74AHCT1G125 level shifter on DIN, so 3.3 V microcontrollers (Pico, ESP32) work reliably.
- Power: from the microcontroller's 5 V pin (VBUS/5V/USB) or an external 5 V supply. The README will
  recommend a software brightness cap (~400 mA) when powering from USB.
- No DOUT breakout, no mounting holes, no hanging hole. The last LED's DOUT is left unconnected.
- Front: LEDs only, no silkscreen art. The board shape itself is the logo's star. I measured the free
  front space at 45 mm: at most ~5 mm pockets, too small for text.
- Back artwork. Parts cluster in the center, leaving the arms and edges for art:
  - MWG logo, single color (brackets, bar, top loop, star), from `reference/mwg-logo.svg`, ~12–15 mm wide
  - "Modern Web Guidance" under the logo
  - "Created with ✨ by @andreban". The ✨ is drawn as a mini version of the star outline, because the fab
    can't print emoji fonts.
  - Text at least 1 mm tall, 0.15 mm stroke (JLCPCB/PCBWay minimum for legibility)
- Finish: yellow solder mask, **black silkscreen**, **ENIG** surface finish.
  - Logo in exposed gold: a copper shape on B.Cu with a matching B.Mask opening. It's isolated (no net)
    and the back routing keeps clear of it. Logo strokes should be at least 0.2 mm.
  - Text ("Modern Web Guidance", credit line) in black silkscreen on B.Silkscreen.

- Connector orientation: the cable exits toward the **top** point. The connector sits on the back, upper
  center, with its opening facing the top tip. The back artwork goes below and around it.
- Chain order: center (LED1) → top (LED2) → then clockwise NE, E, SE, S, SW, W, NW (LED3–LED9).
- Board: 2-layer, 1.6 mm FR-4.
- Tooling: KiCad 10 (installed via winget), driven headlessly with `kicad-cli` and KiCad's Python API.
  - Python scripts generate the project: the exact SVG outline, placement, footprints, artwork and routing.
  - `kicad-cli pcb drc` and `kicad-cli sch erc` must pass with zero errors.
  - `kicad-cli` exports the Gerbers, drill files, positions/BOM, and front/back renders for review.
  - EasyEDA copy is the KiCad 10 project zipped (EasyEDA's importer docs are dated; the import is untested).
    Fallback: `easyeda/outline.dxf` + Gerbers.

## Status
Built: `python scripts/build_all.py` regenerates everything. ERC, DRC and schematic parity are clean.
Still to verify: the EasyEDA Pro import, and part rotations in the JLCPCB/PCBWay placement previews.
