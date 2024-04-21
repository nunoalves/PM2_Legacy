"""
Dynamic Font Display from PM2 VGA Files using Pygame

This script dynamically displays text using custom fonts loaded from the 
Premier Manager 2 VGA files. The script reads VGA files and an associated 
palette file to render the fonts correctly. It uses Pygame to create a graphical 
window where users can type, and their input is displayed using the fonts from 
the specified VGA file.

Command Line Arguments:
    1. filename: Specifies the path to the VGA file containing the font graphics.
    2. palette_filename: Specifies the path to the VGA file containing the color 
       palette.
    3. --scale (optional): An integer scale factor to enlarge the font display. 
       Default is 1 (no scaling).

Usage Examples:
    Basic usage with default scaling:
    $ python3 dynamicFontDisplay.py ../assets/font16c.vga ../assets/paldata.vga

    With scaling factor to enlarge the font size:
    $ python3 dynamicFontDisplay.py ../assets/font16c.vga ../assets/paldata.vga --scale 10
"""

import pygame
import sys
import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description="Dynamic PM2 Font Display from VGA")
    parser.add_argument("filename", help="Path to the VGA file")
    parser.add_argument("palette_filename", help="Path to the palette file")
    parser.add_argument("--scale", type=int, default=1, help="Scale factor for the character size")
    return parser.parse_args()

def read_rgb_palette_from_file(file_path, palette_adjustment=4):
    try:
        with open(file_path, 'rb') as file:
            file.seek(0x100)  # Skip to the palette data
            palette_data = file.read()
            palette = []
            for i in range(0, len(palette_data), 3):
                if i + 2 < len(palette_data):
                    rgb = tuple(min(255, byte * palette_adjustment) for byte in palette_data[i:i+3])
                    palette.append(rgb)
    except FileNotFoundError:
        print(f"Error: The palette file {file_path} was not found.")
        sys.exit(1)
    return palette

def extract_images_from_vga(filename, palette, scale):
    try:
        with open(filename, 'rb') as file:
            raw_data = file.read()
    except FileNotFoundError:
        print(f"Error: The VGA file {filename} was not found.")
        sys.exit(1)

    y_size = int.from_bytes(raw_data[4:6], 'little')
    x_size = int.from_bytes(raw_data[6:8], 'little')
    image_and_metadata_size = x_size * y_size + 8
    number_images = len(raw_data) // image_and_metadata_size

    images = []
    for image_id in range(number_images):
        data_start_index = image_id * image_and_metadata_size + 8
        image_data = raw_data[data_start_index:data_start_index + x_size * y_size]
        
        image = pygame.Surface((x_size, y_size))
        for i in range(y_size):
            for j in range(x_size):
                color_index = image_data[i * x_size + j]
                color = palette[color_index] if 0 <= color_index < len(palette) else (255, 255, 255)
                image.set_at((j, i), color)
        if scale > 1:
            image = pygame.transform.scale(image, (x_size * scale, y_size * scale))
        images.append(image)
    
    return images, x_size * scale, y_size * scale

def main():
    args = parse_arguments()
    title = f"Dynamic Font Display - File: {args.filename}, Palette: {args.palette_filename}, Scale: {args.scale}"

    pygame.init()
    screen_width, screen_height = 800, 600
    screen = pygame.display.set_mode((screen_width, screen_height))
    pygame.display.set_caption(title)

    palette = read_rgb_palette_from_file(args.palette_filename)
    images, char_width, char_height = extract_images_from_vga(args.filename, palette, args.scale)

    running = True
    text = []
    cursor_x, cursor_y = 0, 0

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_BACKSPACE and text:
                    text.pop()
                    cursor_x -= char_width
                    if cursor_x < 0:
                        cursor_x = screen_width - char_width
                        cursor_y -= char_height
                elif event.unicode.isprintable():
                    if cursor_x >= screen_width - char_width:
                        cursor_x = 0
                        cursor_y += char_height
                    text.append((event.unicode, cursor_x, cursor_y))
                    cursor_x += char_width

        screen.fill((255, 255, 255))  # White background

        for char, x, y in text:
            index = ord(char) - 32
            if 0 <= index < len(images):
                screen.blit(images[index], (x, y))
            else:
                print(f"Character '{char}' out of index range.")

        pygame.display.flip()

    pygame.quit()
    sys.exit()

if __name__ == '__main__':
    main()
