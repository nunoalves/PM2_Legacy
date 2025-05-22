#!/usr/bin/env python3
"""
gnd2bmp.py – Decode Premier Manager 2 *.gnd files into 32-bit BMPs
             (with optional single-step visualisation).

Opcode key
----------
LIT  N              – copy N literal bytes that follow
RPTm×VV             – write m copies of byte 0xVV
CPYk off=D          – copy k bytes from D positions back in the history

CPY lengths
  CPY2  : A0–BF
  CPY3  : 80–9F
  CPY4-19: C0–FF  (length = base{4,8,12,16} + extra{0-3})

Usage
-----
python gnd2bmp.py PICTURE.gnd PALETTE.vga [--out OUT.bmp] [--scale N] [--step]

Options
-------
--out FILE        output BMP name        (default out.bmp)
--trace FILE      command trace          (default out.trace.txt)
--max-out PIX     stop after PIX pixels
--max-in  BYTES   stop after BYTES source bytes
--step            print each opcode & dump step_XXXX.bmp
"""

from __future__ import annotations
import argparse, math, struct
from collections import deque
from pathlib import Path
from palette_vga import load_vga_palette

WIDTH, WIN = 320, 4096

# -------------------------------------------------------------------- helpers
def write_bmp(dst: Path, w: int, pixels: bytes, pal: bytes, scale: int = 1):
    h = math.ceil(len(pixels) / w)
    out_w, out_h = w * scale, h * scale

    def row_expand(raw: bytes) -> bytes:
        buf = bytearray()
        for idx in raw:
            b, g, r, _ = pal[idx*4 : idx*4+4]
            buf += bytes([b, g, r, 255]) * scale
        return buf

    out = bytearray()
    for y in range(h):
        line = pixels[y*w : (y+1)*w].ljust(w, b'\0')
        big = row_expand(line)
        out += big * scale

    img_sz, off_bits = len(out), 54
    hdr = struct.pack('<2sIHHI', b'BM', off_bits + img_sz, 0, 0, off_bits)
    dib = struct.pack('<IiiHHIIiiII',
                      40, out_w, -out_h, 1, 32, 0,
                      img_sz, 2835, 2835, 0, 0)
    dst.write_bytes(hdr + dib + out)

# ------------------------------------------------------------- opcode decoders
def op_literal(cmd, src, pos, hist):
    n = cmd
    payload = src[pos+1 : pos+1+n]
    hist.extend(payload)
    return pos+1+n, payload, f'LIT {n}'

def op_short_rpt(cmd, src, pos, hist):
    n   = (cmd & 0x3F) + 3
    val = src[pos+1]
    payload = bytes([val]) * n
    hist.extend(payload)
    return pos+2, payload, f'RPT{n}×{val:02X}'

def op_long_rpt(cmd, src, pos, hist):
    n   = ((cmd & 0x1F) << 8) + src[pos+1] + 36
    val = src[pos+2]
    payload = bytes([val]) * n
    hist.extend(payload)
    return pos+3, payload, f'RPT{n}×{val:02X}'

def op_copy2(cmd, src, pos, hist):
    dist = (cmd & 0x1F) + 2
    payload = bytes(hist[-dist + i] for i in range(2))
    hist.extend(payload)
    return pos+1, payload, f'CPY2 off={dist}'

def op_copy3(cmd, src, pos, hist):
    dist = (cmd & 0x1F) + 3
    payload = bytes(hist[-dist + i] for i in range(3))
    hist.extend(payload)
    return pos+1, payload, f'CPY3 off={dist}'

# ---- your original long-distance copy (unchanged) --------------------------
def op_copy_long(cmd, src, pos, hist):
    group  = (cmd >> 4) - 0xC
    base   = group * 4 + 4
    extra  = (cmd >> 2) & 0x3
    length = base + extra
    bias   = length

    lo  = src[pos+1]
    hi  = cmd & 0x03                 # 2 bits → 0,1,2,3
    offset = (hi << 8) | lo          # 0…0x3FF
    dist = offset + bias

    if len(hist) < dist:
        raise ValueError(f'CPY{length} needs hist {dist}, has {len(hist)}')

    payload = bytes(hist[-dist + i] for i in range(length))
    hist.extend(payload)
    return pos+2, payload, f'CPY{length} off={dist}'
# ---------------------------------------------------------------------------

HANDLERS = (
    (lambda c: 0x01 <= c <= 0x1F, op_literal),
    (lambda c: 0x40 <= c <= 0x5F, op_short_rpt),
    (lambda c: 0x60 <= c <= 0x7F, op_long_rpt),
    (lambda c: 0x80 <= c <= 0x9F, op_copy2),
    (lambda c: 0xA0 <= c <= 0xBF, op_copy3),
    (lambda c: 0xC0 <= c <= 0xFF, op_copy_long),
)

# ------------------------------------------------------------------ decoder
def decode(stream: bytes, *, step=False, save_frame_cb=None) -> bytes:
    pos, out = 0, bytearray()
    hist = deque([0]*WIN, maxlen=WIN)
    frame = 0

    while pos < len(stream) and stream[pos] != 0x00:
        for cond, fn in HANDLERS:
            if cond(stream[pos]):
                nxt, payload, note = fn(stream[pos], stream, pos, hist)

                if step:
                    frame += 1
                    raw = stream[pos:nxt].hex(' ').upper()
                    print(f'#{frame:04d}  @0x{pos:06X}  {raw:<11}  {note}')
                    if save_frame_cb:
                        save_frame_cb(frame, bytes(out + payload))

                out.extend(payload)
                pos = nxt
                break
        else:
            raise ValueError(f'Unknown opcode 0x{stream[pos]:02X} at 0x{pos:X}')
    return bytes(out)

# --------------------------------------------------------------------- CLI
def main() -> None:
    ap = argparse.ArgumentParser(description='Convert *.gnd → BMP')
    ap.add_argument('gnd')
    ap.add_argument('palette')
    ap.add_argument('--out', default='out.bmp')
    ap.add_argument('--scale', type=int, default=1)
    ap.add_argument('--step', action='store_true',
                    help='print each opcode & dump step_XXXX.bmp')
    args = ap.parse_args()

    gnd_bytes = Path(args.gnd).read_bytes()
    palette   = load_vga_palette(args.palette)

    save_cb = None
    if args.step:
        step_dir = Path(args.out).with_suffix('')
        step_dir.mkdir(exist_ok=True)

        def save_cb(n: int, pix: bytes):
            write_bmp(step_dir / f'step_{n:04d}.bmp', WIDTH, pix, palette,
                      scale=args.scale)

    pixels = decode(gnd_bytes, step=args.step, save_frame_cb=save_cb)
    write_bmp(Path(args.out), WIDTH, pixels, palette, args.scale)
    print('BMP: ', args.out)
    if args.step:
        print('Directory where frames are located:', step_dir)

if __name__ == '__main__':
    main()
