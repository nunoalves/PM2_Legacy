"""
Generate a BMP displaying each color in the Premier Manager 2 (PM2) palette with its index.

Usage:
    python printPalette.py paldata.vga palette.bmp --base 16
"""
import argparse
from PIL import Image, ImageDraw, ImageFont

def load_palette(path, adjust=4):
    """Read 256 RGB triplets from paldata.vga starting at offset 0x100."""
    with open(path, 'rb') as f:
        f.seek(0x100)
        data = f.read(256 * 3)
    palette = []
    for i in range(0, len(data), 3):
        r, g, b = data[i:i+3]
        palette.append((r * adjust, g * adjust, b * adjust))
    return palette

def format_index(value, base):
    """Convert an integer to its string representation in the given base (2-36)."""
    if base < 2 or base > 36:
        raise ValueError("Base must be between 2 and 36")
    digits = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    if value == 0:
        return "0"
    result = ''
    n = value
    while n > 0:
        n, rem = divmod(n, base)
        result = digits[rem] + result
    return result

def create_palette_image(palette, swatch_size=40, columns=16, base=10):
    """Create an RGB image showing each palette entry as a swatch with its index in the specified base."""
    rows = (len(palette) + columns - 1) // columns
    width = columns * swatch_size
    height = rows * swatch_size

    img = Image.new('RGB', (width, height))
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None

    for idx, color in enumerate(palette):
        x = (idx % columns) * swatch_size
        y = (idx // columns) * swatch_size
        draw.rectangle([x, y, x + swatch_size, y + swatch_size], fill=color)
        text = format_index(idx, base)
        # Measure text size
        if font and hasattr(font, 'getbbox'):
            bbox = font.getbbox(text)
        else:
            bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        # Center text in swatch
        tx = x + (swatch_size - tw) / 2
        ty = y + (swatch_size - th) / 2
        draw.text((tx, ty), text, fill=(255, 255, 255), font=font)

    return img

def main():
    parser = argparse.ArgumentParser(description="Generate BMP displaying palette from paldata.vga with index labels in a chosen base")
    parser.add_argument('palette_file', help='Path to paldata.vga')
    parser.add_argument('output_file', help='Output BMP filename')
    parser.add_argument('--swatch-size', type=int, default=40, help='Size of each color swatch')
    parser.add_argument('--columns', type=int, default=16, help='Number of columns per row')
    parser.add_argument('--adjust', type=int, default=4, help='Palette adjustment multiplier')
    parser.add_argument('--base', type=int, default=10, help='Numeral base for index labels (2-36)')
    args = parser.parse_args()

    palette = load_palette(args.palette_file, adjust=args.adjust)
    img = create_palette_image(
        palette,
        swatch_size=args.swatch_size,
        columns=args.columns,
        base=args.base
    )
    img.save(args.output_file, format='BMP')
    print(f"Saved palette image to {args.output_file} with index base {args.base}")

if __name__ == '__main__':
    main()