# Premier Manager 2 Legacy

## Prelude
This is my attempt at porting Premier Manager 2, a staple of my childhood, aiming
to revitalize the DOS version of one of the best soccer manager games before
Championship Manager took over in the early 90s. Despite being terrible at this
game, it inspired me to explore hex editors and disassemblers, paving the way
for a lifelong career in tech. This port closely replicates the original
gameplay, requiring the extraction and placement of the original DOS assets into
the assets directory.

## Directory Structure
- `tools` - Various tools used in development, written in Python and C.
- `assets` - Destination for original PM2 files.

## Setup and Operation
- Windows Subsystem for Linux (WSL) is recommended for this project (see
[WSL Installation](https://learn.microsoft.com/en-us/windows/wsl/install)).
- Python 3.10.12 is used for the scripts in the tools directory. Verify your
version using `python3 --version`.
- For new WSL setups, install pip:
  ```
  sudo apt update
  sudo apt install python3-pip
  ```
- Navigate to the tools directory and install all required Python packages:
  ```
  pip install -r requirements.txt
  ```
- To handle assets:
  1. Place original PM2 files in the asset directory.
  2. Verify the assets using `python3 verifyAssets.py`.
  3. Convert VGA files to BMP format by running `python3 vgaToBmp.py`. This
     process will generate several BMP files in the same directory.