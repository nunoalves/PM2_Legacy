"""
File Hash Verification Script (Python 3.12.2)

This script verifies the integrity of files located in a specified directory by 
comparing their calculated hash values with expected hash values listed in a 
separate text file. It supports various hash functions (e.g., MD5, SHA-1, 
SHA-256) as specified by the user.

Usage:
- Set the `assets_location` variable to the path of the directory containing the 
  files to be verified.
- Set the `hash_list_file` variable to the name of the text file containing the 
  expected hashes and file names.
- Optionally, change the `hash_name` variable to use a different hash function 
  (default is 'md5').

Note:
The expected hash list file format should not include headers or comments, and 
each line should follow the format: "<expected_hash> <file_name>".
"""

import hashlib
import os

def calculate_file_hash(file_path, hash_name='md5'):
    # Ensure the hash function is supported to avoid AttributeError
    try:
        hash_func = hashlib.new(hash_name)
    except ValueError:
        print(f"Unsupported hash type: {hash_name}")
        return None
    
    try:
        with open(file_path, 'rb') as file:
            while chunk := file.read(8192):
                hash_func.update(chunk)
        return hash_func.hexdigest()
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return None
    except IOError as e:
        print(f"Error opening file {file_path}: {e}")
        return None

def verify_file_hashes(assets_location, hash_list_file, hash_name='md5'):
    hash_list_path = os.path.join(assets_location, hash_list_file)
    try:
        with open(hash_list_path, 'r') as file:
            for line in file:
                if line.startswith('#') or not line.strip():
                    continue  # Skip comment lines and empty lines
                expected_hash, file_path = line.strip().split()
                full_file_path = os.path.join(assets_location, file_path)
                if not os.path.exists(full_file_path):
                    print(f"{full_file_path:40}: FILE NOT FOUND")
                    continue
                calculated_hash = calculate_file_hash(full_file_path, hash_name)
                if calculated_hash == expected_hash:
                    print(f"{full_file_path:40}: PASS")
                else:
                    print(f"{full_file_path:40}: FAIL (Calculated: {calculated_hash})")
    except FileNotFoundError:
        print(f"Hash list file not found: {hash_list_path}")
    except IOError as e:
        print(f"Error opening hash list {hash_list_path}: {e}")

# Entry point
assets_location = "../assets/"  # Location of the assets
hash_list_file = 'assets_hash_list.txt'  # File with expected hashes and file names
hash_name = 'md5' # Hash type

verify_file_hashes(assets_location, hash_list_file, hash_name)
