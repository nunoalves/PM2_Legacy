
"""
PM2 VGA Files To BMP

This script reads the .vga files from the Premier Manager 2 assets and creates
a bmp file. The .vga format is pretty simple. Inside the file, there are a 
bunch of images. Each image starts with an 8-byte metadata that contains the x
and y dimensions of the subsequent image. The image is composed of x*y bytes, 
in which each byte corresponds to a pixel. I still have to understand the 
conversion between this byte value and the color. The metadata format is as
follows:
    - Bytes 0 to 3 are ignored.
    - Bytes 4 and 5 determine the height (y-size) of each image in pixels.
    - Bytes 6 and 7 determine the width (x-size) of the image in pixels.
    
There is also a file containing the palette information for all the images. The 
palette data begins at byte 0x100 and extends for the next 255*3 bytes. Each 
set of three bytes represents an RGB value, effectively mapping a byte (0 to 
0xFF) to an RGB value. However one thing was weird, the RGB value for each
byte seemed really dark. I was able to match the colors from the palette file 
to the game by multiplying each value by 4. This is set on the variable
palette_adjustment. 
"""

from PIL import Image
import os
import sys

def mergeImages(outputBaseFilename, images, images_per_row):
    # Determine the total size of the merged image
    if not images:
        return

    total_width = images[0].width * images_per_row
    total_rows = len(images) // images_per_row + (1 if len(images) % images_per_row else 0)
    total_height = images[0].height * total_rows

    # Create a new image to hold the merged output
    merged_image = Image.new('RGB', (total_width, total_height))

    # Place each image in the correct position
    x_offset, y_offset = 0, 0
    for i, image in enumerate(images):
        merged_image.paste(image, (x_offset, y_offset))
        x_offset += image.width
        if (i + 1) % images_per_row == 0:
            x_offset = 0
            y_offset += image.height

    # Save the merged image
    merged_image.save(f"{outputBaseFilename}_merged.bmp")

def extractSingleImage(y_size, x_size, byte_data, image_id, palette):
    info_start_index = image_id * (8 + x_size * y_size)
    data_start_index = info_start_index + 8

    # Create a new image using palette mode with the calculated dimensions.
    image = Image.new('P', (x_size, y_size))
    
    # Apply the provided palette
    image.putpalette(palette) 

    # Populate the image with pixel data from byte_data.
    x, y = 0, 0
    for i in range(data_start_index,data_start_index + (x_size*y_size)):
        image.putpixel((x, y), byte_data[i])
        x += 1
        if x == x_size:  # Move to the next row after reaching x_size.
            x = 0
            y += 1

    return image
    
def read_rgb_palette_from_file(file_path, print_palette):

    palette_adjustment = 4 
    
    with open(file_path, 'rb') as file:
        # Skip the first 0x100 bytes to reach the palette data
        file.seek(0x100)
        
        # Read the rest of the file
        palette_data = file.read()
        
        # Extract RGB triplets (3 bytes at a time)
        palette = []
        for i in range(0, len(palette_data), 3):
            # Ensure we don't go beyond the file's end
            if i + 2 < len(palette_data):

                rgb = tuple(byte * palette_adjustment for byte in palette_data[i:i+3])
                palette.append(rgb)
                      
        # Print the palette with ID and RGB values
        if (print_palette == True):
            print("Extracted Palette Information")
            print(f"{'ID':<5}: {'RGB'}")  # Adjust the column widths as necessary

            for id, color in enumerate(palette):
                rgb_str = f"({color[0]}, {color[1]}, {color[2]})"  # Format the RGB tuple as a string
                print(f"0x{id:02X} : {rgb_str}")
        
        return create_flat_palette(palette)

def create_flat_palette(palette):
    # Flatten the RGB palette for PIL
    flat_palette = [value for color in palette for value in color]
    
    # PIL's putpalette method expects 768 bytes (256*3)
    # If our palette is shorter, we'll extend it by repeating the last color
    if len(flat_palette) < 768:
        last_color = flat_palette[-3:]
        flat_palette += last_color * ((768 - len(flat_palette)) // 3)
    
    return flat_palette

#===============================================================================
# Entry point
#===============================================================================

# Define a dictionary mapping input file names to their output base file names
files_to_process = {
    r"../assets/fax.vga": "fax",
    r"../assets/font16c.vga": "font16c",
    r"../assets/font55.vga": "font55",
    r"../assets/font57.vga": "font57",
    r"../assets/font57b.vga": "font57b",
    r"../assets/font77.vga": "font77",
    r"../assets/font77b.vga": "font77b",
    r"../assets/font77c.vga": "font77c",
    r"../assets/fontf9.vga": "fontf9",
    r"../assets/gndscore.vga": "gndscore",
    r"../assets/gndseats.vga": "gndseats",
    r"../assets/groundix.vga": "groundix",
    r"../assets/icons.vga": "icons",
    r"../assets/impslbar.vga": "impslbar",
    r"../assets/matball.vga": "matball",
    r"../assets/matbtn.vga": "matbtn",
    r"../assets/matspd.vga": "matspd",
    r"../assets/phone2.vga": "phone2",
    r"../assets/phonem.vga": "phonem",
    r"../assets/pitch.vga": "pitch",
    r"../assets/pitchbit.vga": "pitchbit",
    r"../assets/posgraph.vga": "posgraph",
    r"../assets/report.vga": "report",
    r"../assets/result.vga": "result",
    r"../assets/sec2.vga": "sec2",
    r"../assets/sh.vga": "sh",
    r"../assets/sponsors.vga": "sponsors",
    r"../assets/ticket.vga": "ticket",
    r"../assets/validbtn.vga": "validbtn",
}

paletteFileName =  r"../assets/paldata.vga"

# Check if all files exist
files_to_check = list(files_to_process.keys()) + [paletteFileName]

for fileName in files_to_check:
    if not os.path.exists(fileName):
        print(f"File {fileName} not found. Exiting the program.")
        sys.exit(1)  # Exit the program indicating an error

# If this point is reached, all files exist
print("All files exist. Proceeding with processing.")

# Read the palette
palette = read_rgb_palette_from_file(paletteFileName,False)

# Handle all files
for inputFileName, outputBaseFileName in files_to_process.items():
    # Read the .vga file in binary mode
    with open(inputFileName, 'rb') as file:
        rawData = file.read()

    # Assuming all images inside this file have the same dimensions
    y_size = int.from_bytes(rawData[4:6], 'little')
    x_size = int.from_bytes(rawData[6:8], 'little')
    image_and_metadata_size = x_size * y_size + 8 
    number_images = round(len(rawData) / image_and_metadata_size)

    print("")
    print(f"Processing {inputFileName}")
    print("y_size        =", y_size)
    print("x_size        =", x_size)
    print("number_images =", number_images)

    # Extracts all individual images
    images = []
    for image_id in range(number_images):
        image = extractSingleImage(y_size, x_size, rawData, image_id, palette)
        images.append(image)

    # Determines images per row for merging
    images_per_row = 5
    if number_images < images_per_row: 
        images_per_row = number_images
    
    # And combines them into a single image
    mergeImages(outputBaseFileName, images, images_per_row)