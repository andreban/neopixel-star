# AGENTS.md

Guidance for AI agents (and humans) changing this project. See [README.md](README.md) for what the board
is and how to order it, and [PLAN.md](PLAN.md) for why it is designed this way.

## Prerequisites

- **KiCad 10.** The build uses these parts of the installation:
  - `kicad-cli`, for ERC, DRC, zone filling, Gerber/drill/position exports and renders;
  - KiCad's bundled Python, which provides `pcbnew`;
  - the stock symbol, footprint and 3D-model libraries, copied into the project libraries.
- **Finding KiCad.** `scripts/common/config.py` looks in KiCad 10's standard install locations for Windows,
  macOS and Linux. If KiCad is installed elsewhere, set the `KICAD_DIR` environment variable to the
  installation directory: the folder containing `bin/` and `share/` on Windows and Linux,
  `KiCad.app/Contents` on macOS. Never hardcode a machine-specific path in the repo.
- **Python 3** for `build_all.py` and `build_schematic.py`. No third-party packages are needed.

## Variants

The same scripts build four boards, registered in `scripts/common/variants.py`:

| Variant | Outputs | Scripts |
|---|---|---|
| `smd` | `smd/kicad/`, `smd/fab/`, `smd/easyeda/`, `smd/docs/` | `scripts/smd/` |
| `hotplate/v1` | `hotplate/v1/kicad/`, `hotplate/v1/fab/`, `hotplate/v1/easyeda/`, `hotplate/v1/docs/` | `scripts/hotplate/v1/` |
| `hotplate/v2` | `hotplate/v2/kicad/`, `hotplate/v2/fab/`, `hotplate/v2/easyeda/`, `hotplate/v2/docs/` | `scripts/hotplate/v2/` |
| `tht` | `tht/kicad/`, `tht/fab/`, `tht/easyeda/`, `tht/docs/` | `scripts/tht/` |

Each variant's scripts are `parts.py` (the single source of truth for its parts, nets and BOM data),
`layout.py` (placement and routing) and `schematic.py` (the sheet). Everything else is shared, in
`scripts/common/`. A change to shared code must leave **all** variants clean. A change to one
variant must not alter the other's outputs.

## Everything is generated

`smd/`, `hotplate/v1/`, `hotplate/v2/` and `tht/` hold **build outputs**, except their `README.md` files. Never hand-edit them: the
next build overwrites the changes. Make changes in `scripts/`, then rebuild:

```sh
python scripts/build_all.py          # all variants
python scripts/build_all.py tht      # one variant (or prefix): smd, hotplate, hotplate/v1, hotplate/v2 or tht
```

A change is done only when this build finishes. It runs ERC, DRC and schematic parity, and **exits on
any violation**, including warnings. Don't suppress or exclude checks to get it to pass.

Commit the regenerated outputs together with the script change that produced them.

## Where things live

| File | Role |
|---|---|
| `scripts/build_all.py` | Entry point: generate → check → export, per variant |
| `scripts/build_schematic.py` | Entry point: writes `.kicad_sch` + project symbol library. Plain Python |
| `scripts/build_board.py` | Entry point: writes `.kicad_pcb` + project footprint library. **Must run under KiCad's bundled Python** (`<KiCad>/bin/python.exe`), because it imports `pcbnew` |
| `scripts/common/variants.py` | Variant registry: project name, output folder, star size, pour clearance, front silkscreen policy |
| `scripts/common/config.py` | Design rules, LED ring angles, sheet placement, repo root, KiCad install detection |
| `scripts/common/parts.py` | The `Part` type, `uid()` and `board_net()` |
| `scripts/common/board.py` | Board machinery: the `Board` helper, outline, project footprint library, artwork, stackup |
| `scripts/common/schematic.py` | Schematic machinery: symbol extraction/correction, the `Sheet` writer |
| `scripts/common/geometry.py` | Star outline parsed from the SVG path (lines + cubic Béziers), no deps |
| `scripts/common/logo.py` | Logo polygons from `reference/mwg-logo.svg` |
| `scripts/common/assembly.py` | Assembly drawings (`docs/assembly-*.svg`): parts, pin 1 and references per side, read from the saved `.kicad_pcb`. Plain Python |
| `scripts/common/model_jst.py` | Generated VRML model for the SMD J1 (KiCad ships none) |
| `scripts/<variant>/parts.py` | That variant's parts: footprints, pin→net maps, values, LCSC/MPN, datasheets |
| `scripts/<variant>/layout.py` | That variant's LED radii, placement, routing and artwork positions |
| `scripts/<variant>/schematic.py` | That variant's schematic sheet |

Coordinates in the layouts are mm relative to the star centre, y pointing down, angles
counter-clockwise on screen from east. `common.board.local(x, y, rot, u, v)` maps footprint-local
offsets (`+v` = clockwise side of an LED) to board coordinates.

## Constraints that aren't obvious (SMD)

- **Size.** The layout (LED radii, via slots, hop waypoints, back-side placement) is tuned for
  a 50 mm star (`star_width` in `variants.py`). The LEDs alone need ≥ 44.5 mm. After changing the size, expect to rework the
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

## Constraints that aren't obvious (hot-plate)

- **The point of the variant:** everything that needs paste is on the front; the back holds only
  iron-solderable parts (`J1` and `U1` on `hotplate/v1`; `J1` alone on `hotplate/v2`). Don't add
  paste parts to the back.
- **Vias beside the LEDs, not under them.** A 3535 body has no room for two vias. DIN sits on the
  LED's counter-clockwise side, DOUT and GND on its clockwise side. The space under each LED stays
  free on the back so the GND pour flows through, and the ring of hops doesn't create islands.
- **Hops run inward along the LED's side** before crossing to the notch. Cutting straight from a
  long-point LED toward the notch passes too close to the edge.
- **No per-LED capacitors** (`WS2812B-MINI-V3/W` and `WS2812B-MINI-V6` datasheets). On `v1`, `U1`
  stays because V3/W needs $0.63 \times V_{DD}$ on `DIN`; on `v2`, V6 lowers $V_{IH}$ to
  $0.55 \times V_{DD}$ ($2.75\text{ V}$ at $5\text{ V}$), so `U1`, `C2` and `R2` are omitted.
- **Title and gold logo on the front**, below the centre LED; credit and pin labels on the back.
  The artwork helpers in `common/board.py` (`title`, `logo`, `credit`, `pin_labels`) take a side;
  `artwork()` is the standard all-on-the-back arrangement used by the other variants.

## Constraints that aren't obvious (through-hole)

- **LED symbol.** KiCad's `APA-106-F5` symbol is 1 DO, 2 GND, 3 VDD, 4 DI. The WS2812D-F5 is 1 DOUT,
  **2 VDD, 3 GND**, 4 DIN (datasheet). `scripts/tht/parts.py` makes a corrected copy (`symbol_name`,
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
wrong before (a 2-pin JST number was nearly used for the 3-pin part). Change it in the variant's `parts.py`: the
BOMs and schematic/footprint fields are derived from it. The parts table in that variant's README is
written by hand, so update it too.
