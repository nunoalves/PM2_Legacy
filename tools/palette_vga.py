# palette_vga.py
# --------------- read a PM2 .vga or .pal file and return a 1024-byte BGRA table

from pathlib import Path

def load_vga_palette(path: str, offset: int = 0x100) -> bytes:
    """
    Reads 256×RGB bytes starting at *offset* (default 0x100) and
    expands the 6-bit VGA intensities (0-63) to 8-bit (×4).
    Returns 256×BGRA for use in Windows-style indexed BMPs.
    """
    raw = Path(path).read_bytes()[offset : offset + 256 * 3]
    if len(raw) < 256 * 3:
        raise ValueError('Palette data incomplete.')

    bgrx = bytearray()
    for r, g, b in zip(raw[0::3], raw[1::3], raw[2::3]):
        bgrx += bytes((b * 4, g * 4, r * 4, 0))  # BGRA
    return bytes(bgrx)