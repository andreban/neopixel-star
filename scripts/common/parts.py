"""Component data type and naming helpers shared by both variants. Each
variant's parts table is in <variant>/parts.py."""
from dataclasses import dataclass, field


@dataclass
class Part:
    lib: str                 # stock KiCad footprint library it was copied from
    footprint: str
    value: str
    symbol: str              # stock KiCad symbol, "Lib:Name"
    pins: dict               # pad/pin number -> net name (None = unconnected)
    lcsc: str
    mpn: str
    manufacturer: str
    description: str = ""
    datasheet: str = ""
    # When the stock symbol's pin numbering doesn't match the part: the name
    # of the corrected copy in the project library, and stock -> real pin number.
    symbol_name: str = ""
    pin_numbers: dict = field(default_factory=dict)
    nc_pin_name: str = "DOUT"   # symbol pin name of the unconnected pin (LED9's data out)
    # Symbol pin names by pin number, for parts with several unconnected pins.
    pin_names: dict = field(default_factory=dict)

    def pin_name(self, pad):
        return self.pin_names.get(pad, self.nc_pin_name)


def board_net(net, ref=None, pad=None, pin_name=None):
    """PCB net name as KiCad derives it from the schematic. Power symbols and
    global labels give plain names; a no-connect pin gets a net of its own."""
    if net is None:
        return f"unconnected-({ref}-{pin_name or pad}-Pad{pad})"
    return net


def uid(name, ns=""):
    """Stable UUID so schematic symbols and PCB footprints link up (and the
    generated files don't churn between runs). `ns` separates variants."""
    import uuid
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "neopixel-star/" + ns + name))

