#!/usr/bin/env python3
"""
gnd2bmp.py  –  decode Premier Manager 2 *.gnd RLE streams and write a BMP.
usage: python gnd2bmp.py picture.gnd paldata.vga [options]

Options
-------
--out FILE        output BMP name        (default out.bmp)
--trace FILE      command trace          (default out.trace.txt)
--max-out PIX     stop after PIX pixels
--max-in  BYTES   stop after BYTES source bytes

"""

import struct, argparse
from collections import deque
from pathlib import Path
from palette_vga import load_vga_palette
import math, struct
from pathlib import Path

WIDTH = 320
WIN   = 4096                    

SHORT_REPEAT_LITERAL_BIAS = 3
LONG_REPEAT_LITERAL_BIAS = 36
COPY_2_BIAS = 2
COPY_3_BIAS = 3

def write_bmp(dst: Path, width: int, pixels: bytes,
              palette_bgra: bytes, scale: int = 1):
    """
    • one output row every <width> decoded indices
    • pads the final row with fully-transparent pixels (alpha=0)
    • enlarges each pixel by integer *scale* (default 1)
    • writes a 32-bit BGRA top-down BMP (no colour table needed)
    """
    assert scale >= 1
    height    = math.ceil(len(pixels) / width)
    row_pad   = 0                           # 32-bit rows already dword aligned
    out_w     = width  * scale
    out_h     = height * scale
    need      = height * width

    # ---------------------------------------------------------------- image ↑
    # build the enlarged BGRA buffer once
    def expand_row(src_row: bytes) -> bytes:
        # map indices → palette BGRA, then replicate horizontally
        row32 = bytearray()
        for idx in src_row:
            b, g, r, a = palette_bgra[idx*4: idx*4+4]
            row32 += bytes([b, g, r, 255]) * scale
        return row32

    transparent_px = bytes([255, 255, 255, 255]) * scale

    out = bytearray()
    for y in range(height):
        row = pixels[y*width : (y+1)*width]
        if len(row) < width:                      # tail line padding
            row += b'\x00' * (width - len(row))
        big = expand_row(row)
        out.extend(big + b'\x00'*row_pad)
        # replicate vertically
        for _ in range(scale-1):
            out.extend(big + b'\x00'*row_pad)

    # if decode stopped early and produced <need bytes>, add transparent rows
    while len(out) < out_w * out_h * 4:
        out.extend(transparent_px * width)

    # ------------------------------------------------------------- BMP ↓
    img_size = len(out)
    off_bits = 14 + 40                    # no palette
    hdr = struct.pack('<2sIHHI', b'BM', off_bits + img_size, 0, 0, off_bits)
    dib = struct.pack('<IiiHHIIiiII',
                      40, out_w, -out_h,   # signed height negative = top-down
                      1, 32, 0,            # 32-bit, BI_RGB
                      img_size,
                      2835, 2835,          # 72 dpi
                      0, 0)

    with dst.open('wb') as f:
        f.write(hdr + dib + out)

# --------------------------------------------------------------- op-code funcs
def op_literal(cmd, src, pos, hist):
    n   = cmd
    dat = src[pos+1:pos+1+n]
    hist.extend(dat);  return pos+1+n, dat, f'LIT {n}'

def op_short_repeat_literal(cmd, src, pos, hist):
    n = (cmd & 0x3F) + SHORT_REPEAT_LITERAL_BIAS; val = src[pos+1]
    dat = bytes([val]) * n
    hist.extend(dat);  return pos+2, dat, f'R_SHRT_LIT {n}×{val:02X}'

def op_copy2(cmd, src, pos, hist):
    dist = (cmd & 0x1F) + COPY_2_BIAS
    if len(hist) < dist:
        raise ValueError(f'op_copy2 dist {dist} before buffer filled')

    payload = bytes(hist[-dist + i] for i in range(2))
    hist.extend(payload)
    note = f'SHRT_CPY2 off={dist}'
    return pos + 1, payload, note

def op_long_repeat_literal(cmd, src, pos, hist):
    n = ((cmd & 0x1F) << 8) + src[pos+1] + LONG_REPEAT_LITERAL_BIAS; val = src[pos+2]
    dat = bytes([val]) * n
    hist.extend(dat);  return pos+3, dat, f'R_LONG_LIT {n}×{val:02X}'

def op_copy3(cmd, src, pos, hist):
    dist = (cmd & 0x1F) + COPY_3_BIAS
    if len(hist) < dist:
        raise ValueError(f'op_copy3 dist {dist} before buffer filled')

    payload = bytes(hist[-dist + i] for i in range(3))
    hist.extend(payload)
    note = f'SHRT_CPY3 off={dist}'
    return pos + 1, payload, note


def long_op_copy(cmd, src, pos, hist):
    """
    Handle any Cx–Fx two-byte “copy” opcode.
      cmd = 0xC0…0xFF
      src = the full input bytearray
      pos = current index into src (pointing at cmd)
      hist = bytearray of already-decoded output

    Returns:
      new_pos, payload_bytes, note_str
    """
    # 1) compute copy length
    #    high nibble: 0xC→4, 0xD→8, 0xE→12, 0xF→16
    group = (cmd >> 4) - 0xC
    base  = 4 * group + 4            # 4, 8, 12 or 16
    extra = (cmd >> 2) & 0x3         # bits 3–2 add 0–3
    length = base + extra            # final copy length (4…19)

    # 2) BIAS = length
    bias = length

    # 3) reconstruct offset
    lo = src[pos + 1]
    hi = cmd & 0x3                   # low bit of cmd is the 9th bit
    offset = (hi << 8) | lo          # 0…511
    dist = offset + bias             # back-reference distance

    if len(hist) < dist:
        raise ValueError(f'op_copy: need {dist} bytes in history, have {len(hist)}')

    # 4) copy from history
    payload = bytes(hist[-dist + i] for i in range(length))
    hist.extend(payload)

    note = f'COPY{length} off={dist}'
    return pos + 2, payload, note

# -------------------------------------------------------------- command table
HANDLERS = (
    (lambda c: 0x01 <= c <= 0x1F, op_literal), #fully decoded
    (lambda c: 0x40 <= c <= 0x5F, op_short_repeat_literal), #fully decoded
    (lambda c: 0x60 <= c <= 0x7F, op_long_repeat_literal), #fully decoded    
    (lambda c: 0x80 <= c <= 0x9F, op_copy2), #fully decoded
    (lambda c: 0xA0 <= c <= 0xBF, op_copy3), #fully decoded
    (lambda c: 0xC0 <= c <= 0xFF, long_op_copy),
)

# ------------------------------------------------------------------- decoder
def decode(stream: bytes, stop_pix=None, stop_src=None, *,
           step=False, save_frame_cb=None):
    pos, out = 0, bytearray()
    hist     = deque([0]*WIN, maxlen=WIN)
    trace    = []
    frame = 0                      # track how many ops we’ve executed

    while pos < len(stream):
        if stream[pos] == 0x00:
            trace.append((pos, b'\x00', 'TERM', b''));  break
        if stop_src and pos >= stop_src:  break
        if stop_pix and len(out) >= stop_pix: break

        for cond, fn in HANDLERS:
            if cond(stream[pos]):
                nxt, payload, note = fn(stream[pos], stream, pos, hist)

                if step:
                    print(f'frame #{frame+1:4} [src 0x{pos:02X} cmd 0x{stream[pos]:06X}] {note}  '
                          f'(wrote {len(payload)} bytes, out={len(out)+len(payload)})')

                trace.append((pos, stream[pos:nxt], note, payload))
                out.extend(payload);  pos = nxt
                
                if step and save_frame_cb:
                    frame += 1
                    save_frame_cb(frame, bytes(out))   

                break
        else:   # unknown byte
            trace.append((pos, bytes([stream[pos]]), 'UNK', b''))
            pos += 1
    return bytes(out), trace

# ---------------------------------------------------------------------- main
def main() -> None:
    import argparse
    from pathlib import Path

    p = argparse.ArgumentParser(
        description='Decode a *.gnd file into a 32-bit BMP (VGA palette).')
    p.add_argument('gnd',                 help='input *.gnd file')
    p.add_argument('palette',             help='VGA palette (.vga)')
    p.add_argument('--out',   default='out.bmp',
                   help='final BMP filename           (default: %(default)s)')
    p.add_argument('--trace', default='out.trace.txt',
                   help='opcode trace log             (default: %(default)s)')
    p.add_argument('--max-out', type=int, metavar='PIX',
                   help='stop after PIX output pixels')
    p.add_argument('--max-in',  type=int, metavar='BYTES',
                   help='stop after BYTES input bytes')
    p.add_argument('--scale', type=int, default=1,
                   help='integer zoom factor ≥1        (default: %(default)s)')
    p.add_argument('--step', action='store_true',
                   help='single-step mode: pause after each opcode, '
                        'dump incremental BMPs')

    args = p.parse_args()

    # -------------------------------------------------- load input & palette
    gnd_bytes = Path(args.gnd).read_bytes()
    palette   = load_vga_palette(args.palette)

    # ------------------------------------------- prepare stepping, if any
    step_dir: Path | None = None
    if args.step:
        # Save incremental frames next to --out:  “out/step_0001.bmp”, …
        step_dir = Path(args.out).with_suffix('')  # strip extension
        step_dir.mkdir(parents=True, exist_ok=True)

        def save_frame(frame_no: int, pixels_so_far: bytes) -> None:
            """Write an interim BMP for frame <frame_no>."""
            bmp_name = step_dir / f'step_{frame_no:04d}.bmp'
            write_bmp(bmp_name, WIDTH, pixels_so_far,
                      palette_bgra=palette, scale=args.scale)
    else:
        save_frame = None  # type: ignore[arg-type]

    # ----------------------------------------------------------- decode
    pixels, trace = decode(
        gnd_bytes,
        stop_pix=args.max_out,
        stop_src=args.max_in,
        step=args.step,
        save_frame_cb=save_frame,
    )

    # -------------------------------------------------------- final BMP
    write_bmp(Path(args.out), WIDTH, pixels, palette, scale=args.scale)

    # ------------------------------------------------------- trace log
    with Path(args.trace).open('w') as f:
        for ofs, raw, note, payload in trace:
            f.write(f'{ofs:06X}  {raw.hex(" ").upper():<11}  '
                    f'{note:<18} {payload[:16].hex(" ")}'
                    f'{" ..." if len(payload) > 16 else ""}\n')

    # ---------------------------------------------------------- console
    print('BMP   →', args.out)
    print('Trace →', args.trace)
    if args.step:
        print('Step  →', step_dir / 'step_0001.bmp', '(and subsequent frames)')

if __name__ == '__main__':
    main()
