"""Design parameters shared by the generator scripts. All dimensions in mm."""

PROJECT = "neopixel-star"

STAR_WIDTH = 50.0          # tip-to-tip; LEDs need >= ~44.5 mm, extra room is for caps + routing
CENTER = (100.0, 100.0)    # board centre on the KiCad sheet
BOARD_THICKNESS = 1.6

# LED ring. Angles are counter-clockwise on screen from east; order is the
# data chain: centre, then clockwise starting at the top point.
R_AXIS = 13.4              # N/E/S/W LEDs, pushed out into the long points
R_DIAG = 10.4              # diagonal LEDs, pushed out into the short points
LED_ANGLES = [90, 45, 0, -45, -90, -135, 180, 135]

# Design rules (safe for both JLCPCB and PCBWay standard 2-layer service)
TRACK = 0.25
POWER_TRACK = 0.5
CLEARANCE = 0.2
VIA_DIA, VIA_DRILL = 0.6, 0.3
EDGE_CLEARANCE = 0.4

# Back artwork
LOGO_WIDTH = 4.2          # gold logo on the back, between the text and the bottom LED
LOGO_TOP = 6.35
KICAD_10 = "C:/Users/andre/AppData/Local/Programs/KiCad/10.0"
FP_LIB = KICAD_10 + "/share/kicad/footprints"
