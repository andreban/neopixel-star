# AGENTS.md

Guidance for AI agents (and humans) changing this project. See [README.md](README.md) for what the board
is and how to order it, and [PLAN.md](PLAN.md) for why it is designed this way.

## Prerequisites

- **KiCad 10.** The build uses these parts of the installation:
  - `kicad-cli`, for ERC, DRC, zone filling, Gerber/drill/position exports and renders;
  - KiCad's bundled Python, which provides `pcbnew`;
  - the stock symbol, footprint and 3D-model libraries, copied into the project libraries.
- **`KICAD_10` in `scripts/config.py`** must point at the KiCad 10 installation directory (the folder
  containing `bin/` and `share/`). Set it for your machine before building. The build fails if it
  is wrong.
- **Python 3** for `build_all.py` and `build_schematic.py`. No third-party packages are needed.

## Everything is generated

`kicad/`, `fab/`, `easyeda/` and `docs/` are **build outputs**. Never hand-edit them: the next build
overwrites the changes. Make changes in `scripts/`, then rebuild:

```sh
python scripts/build_all.py
```

A change is done only when this build finishes. It runs ERC, DRC and schematic parity, and **exits on
any violation**, including warnings. Don't suppress or exclude checks to get it to pass.

Commit the regenerated outputs together with the script change that produced them.

## Where things live

| File | Role |
|---|---|
| `scripts/parts.py` | Single source of truth: footprints, pin→net maps, values, LCSC/MPN, datasheets |
| `scripts/config.py` | Star size, LED radii, design rules, logo size, **KiCad install path** |
| `scripts/geometry.py` | Star outline parsed from the SVG path (lines + cubic Béziers), no deps |
| `scripts/logo.py` | Logo polygons from `reference/mwg-logo.svg` |
| `scripts/build_schematic.py` | Writes `.kicad_sch` + project symbol library. Plain Python |
| `scripts/build_board.py` | Writes `.kicad_pcb` + project footprint library. **Must run under KiCad's bundled Python** (`<KiCad>/bin/python.exe`), because it imports `pcbnew` |
| `scripts/model_jst.py` | Generated VRML model for J1 (KiCad ships none) |
| `scripts/build_all.py` | Orchestrates generate → check → export |

Coordinates in `build_board.py` are mm relative to the star centre, y pointing down, angles
counter-clockwise on screen from east. `local(x, y, rot, u, v)` maps footprint-local offsets
(`+v` = clockwise side of an LED) to board coordinates.

## Constraints that aren't obvious

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
