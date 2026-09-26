# AGENTS.md

Guidance for AI agents (and humans) changing this project. See [README.md](README.md) for what the board
is and how to order it, and [PLAN.md](PLAN.md) for why it is designed this way.

## Prerequisites

- **KiCad 10.** The build uses these parts of the installation:
  - `kicad-cli`, for ERC, DRC, zone filling, Gerber/drill/position exports and renders;
  - KiCad's bundled Python, which provides `pcbnew`;
  - the stock symbol, footprint and 3D-model libraries, copied into the project libraries.
- **Finding KiCad.** `scripts/config.py` looks in KiCad 10's standard install locations for Windows,
  macOS and Linux. If KiCad is installed elsewhere, set the `KICAD_DIR` environment variable to the
  installation directory: the folder containing `bin/` and `share/` on Windows and Linux,
  `KiCad.app/Contents` on macOS. Never hardcode a machine-specific path in the repo.
- **Python 3** for `build_all.py` and `build_schematic.py`. No third-party packages are needed.

## Two variants

The same scripts build two boards, registered in `scripts/variants.py`:

| Variant | Outputs | Parts | Layout |
|---|---|---|---|
| `smd` | repo root: `kicad/`, `fab/`, `easyeda/`, `docs/` | `parts.py` | `build_board.py` |
| `tht` | `tht/kicad/`, `tht/fab/`, `tht/easyeda/`, `tht/docs/` | `parts_tht.py` | `build_board_tht.py` |

Shared code (outline, artwork, stackup, footprint loading, the `Board` helper) lives in
`build_board.py` and `build_schematic.py`. A change to shared code must leave **both** variants clean.
A change to one variant must not alter the other's outputs.

## Everything is generated

`kicad/`, `fab/`, `easyeda/`, `docs/` and everything under `tht/` except `tht/README.md` are **build
outputs**. Never hand-edit them: the next build overwrites the changes. Make changes in `scripts/`,
then rebuild:

```sh
python scripts/build_all.py          # both variants
python scripts/build_all.py tht      # one variant: smd or tht
```

A change is done only when this build finishes. It runs ERC, DRC and schematic parity, and **exits on
any violation**, including warnings. Don't suppress or exclude checks to get it to pass.

Commit the regenerated outputs together with the script change that produced them.

## Where things live

| File | Role |
|---|---|
| `scripts/parts.py` | SMD parts: footprints, pin→net maps, values, LCSC/MPN, datasheets. Also the `Part` type, `uid()` and `board_net()` |
| `scripts/parts_tht.py` | Through-hole parts, same structure |
| `scripts/variants.py` | Variant registry: project name, output folder, parts table, star size |
| `scripts/config.py` | SMD star size and LED radii, design rules, logo size, KiCad install detection |
| `scripts/geometry.py` | Star outline parsed from the SVG path (lines + cubic Béziers), no deps |
| `scripts/logo.py` | Logo polygons from `reference/mwg-logo.svg` |
| `scripts/build_schematic.py` | Writes `.kicad_sch` + project symbol library. Plain Python |
| `scripts/build_board.py` | Writes `.kicad_pcb` + project footprint library; shared machinery and the SMD layout. **Must run under KiCad's bundled Python** (`<KiCad>/bin/python.exe`), because it imports `pcbnew` |
| `scripts/build_board_tht.py` | Through-hole layout (radii, hops, placement), called by `build_board.py tht` |
| `scripts/model_jst.py` | Generated VRML model for J1 (KiCad ships none) |
| `scripts/build_all.py` | Orchestrates generate → check → export |

Coordinates in `build_board.py` are mm relative to the star centre, y pointing down, angles
counter-clockwise on screen from east. `local(x, y, rot, u, v)` maps footprint-local offsets
(`+v` = clockwise side of an LED) to board coordinates.

## Constraints that aren't obvious (SMD)

- **Size.** The layout (LED radii, via slots, hop waypoints, back-side placement) is tuned for
  `STAR_WIDTH = 50`. The LEDs alone need ≥ 44.5 mm. After changing the size, expect to rework the
  placement.
- **Pours.** The front is a solid +5V pour and the back a solid GND pour. Anything that splits a pour
  into islands shows up as unconnected pads in DRC. In particular:
  - Data hops on the back must leave and enter the under-LED vias **sideways** (see `side()` in
    `data_chain`). A hop that approaches along the LED axis chokes the gap between the two vias.
  - Keep vias (e.g. cap GND vias) **out of the gold logo's outline**. The logo interior is isolated
    copper, so a via there ends up on an island.
- **Gold artwork** is copper with **no net** on B.Cu plus a matching B.Mask opening. It must not touch
  routing, and it is mirrored in x because it is read from the back. Back-side text is mirrored too.
- **Nets.** The schematic uses **global labels**, so net names are plain (`D1`, not `/D1`). Local
  labels break EasyEDA's netlist comparison. PCB net names must match `parts.board_net()`.
- **LED9 DOUT** is intentionally unconnected (no-connect in the schematic).
- **Front stays clean.** The project footprint library moves LED and passive silkscreen to F.Fab.
  Only J1 and U1 keep silkscreen. Don't add front silkscreen.
- **Vias** are 0.3 mm drill / 0.6 mm pad. Both fabs make these at standard price. Enlarging them
  blocks the pour between the bottom LED's vias.

## Constraints that aren't obvious (through-hole)

- **LED symbol.** KiCad's `APA-106-F5` symbol is 1 DO, 2 GND, 3 VDD, 4 DI. The WS2812D-F5 is 1 DOUT,
  **2 VDD, 3 GND**, 4 DIN (datasheet). `parts_tht.py` makes a corrected copy (`symbol_name`,
  `pin_numbers`). Never use the stock symbol as-is for this part.
- **Size 55 mm.** At 50 mm the staggered pads only fit with the LEDs pulled in so far that the top
  LED's leads land under J1's housing (the top LED must be ≥ 13.6 mm from the centre).
- **Staggered footprint with 1.5 mm pads.** Inline pads at 1.27 mm pitch give a 0.085 mm annular ring,
  which is too thin. The stock staggered footprint's 1.8 mm pads seal each point's tip, so the pours
  can't reach the LED pads there. 1.5 mm pads plus a 0.25 mm pour clearance (THT only) let them through.
- **Data hops on the back.** The staggered pins put VDD in each LED's outer row. Hops on the front
  would cut every VDD pad off from the +5V pour. On the back they only cut off GND-free tips.
- **Long-point LEDs at 14.0 mm**, not their 15.3 mm maximum: further out, the point is too narrow for
  the pour to get around the pad row.
- **Front silkscreen** is kept (it's hand-assembled): a short flat-side line per LED, clear of the
  pads, plus the stock C1/R1 marks. The full LED outline is on F.Fab (the stock arcs overlap the pads).

## KiCad Python gotchas

- Load footprints through the single module-level `_IO` plugin. Calling `pcbnew.FootprintLoad()`
  repeatedly can hand back freed SWIG objects.
- Don't remove items from a footprint while iterating it; change their layer instead.
- `ZONE_FILLER` from Python can leave a pour empty. Zones are filled by
  `kicad-cli pcb drc --refill-zones --save-board` in `build_all.py`.
- The board stackup (yellow mask, black silk, ENIG) isn't exposed to Python. It is written into the
  saved file by `write_stackup()`.
- `swig/python detected a memory leak` messages on exit are harmless noise.

## Part numbers

When changing a part, verify the LCSC number on lcsc.com. Numbers recalled from memory have been
wrong before (a 2-pin JST number was nearly used for the 3-pin part). Change it in `parts.py`: the
BOMs and schematic/footprint fields are derived from it. The parts table in the README is written by
hand, so update it too.
