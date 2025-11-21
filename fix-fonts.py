import os
import re
import argparse

# Define mapping from Monolith's output names to desired names
FONT_NAME_MAP = {
    'calibrib.ttf': 'Calibri-Bold.ttf',
    'calibrii.ttf': 'Calibri-Italic.ttf',
    'calibribi.ttf': 'Calibri-BoldItalic.ttf',
    'arialbd.ttf': 'Arial-Bold.ttf',
    'ariali.ttf': 'Arial-Italic.ttf',
    'arialbi.ttf': 'Arial-BoldItalic.ttf',
    'timesbd.ttf': 'Times-New-Roman-Bold.ttf',
    'timesi.ttf': 'Times-New-Roman-Italic.ttf',
    'timesbi.ttf': 'Times-New-Roman-BoldItalic.ttf',
    'verdanab.ttf': 'Verdana-Bold.ttf',
    'verdanai.ttf': 'Verdana-Italic.ttf',
    'verdanabi.ttf': 'Verdana-BoldItalic.ttf',
    'georgiabd.ttf': 'Georgia-Bold.ttf',
    'georgiai.ttf': 'Georgia-Italic.ttf',
    'georgiabi.ttf': 'Georgia-BoldItalic.ttf',
}

def read_collections_file(collections_file='collections.txt'):
    """
    Read and parse the collections.txt file to get list of collection directories.
    
    Args:
        collections_file (str): Path to the collections file
        
    Returns:
        list: List of collection directory names (one per line, stripped of whitespace)
    """
    if not os.path.exists(collections_file):
        return None
    
    collections = []
    with open(collections_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip empty lines and comments
            if line and not line.startswith('#'):
                collections.append(line)
    
    return collections if collections else None

def rename_fonts(directory):
    """
    Rename font files in the specified directory based on predefined mapping.
    Only renames if target file does not already exist to avoid overwrites.
    """
    renamed_count = 0
    skipped_count = 0
    
    if not os.path.exists(directory):
        print(f"Error: Directory '{directory}' does not exist.")
        return
    
    if not os.path.isdir(directory):
        print(f"Error: '{directory}' is not a directory.")
        return
    
    for filename in os.listdir(directory):
        if filename.lower().endswith(('.ttf', '.otf')):
            # Normalize to lowercase for lookup
            lower_filename = filename.lower()
            if lower_filename in FONT_NAME_MAP:
                new_name = FONT_NAME_MAP[lower_filename]
                old_path = os.path.join(directory, filename)
                new_path = os.path.join(directory, new_name)
                
                if not os.path.exists(new_path):
                    try:
                        os.rename(old_path, new_path)
                        print(f"Renamed: {filename} → {new_name}")
                        renamed_count += 1
                    except Exception as e:
                        print(f"Failed to rename {filename} → {new_name}: {e}")
                else:
                    print(f"Skipping: {filename} → {new_name} (target already exists)")
                    skipped_count += 1
    
    print(f"\nSummary: {renamed_count} renamed, {skipped_count} skipped")

def process_collections_mode():
    """
    Process font directories from multiple collections listed in collections.txt.
    Each collection should have the structure: collection_name/InDesign_master/font/
    """
    collections_file = 'collections.txt'
    collections = read_collections_file(collections_file)
    
    if not collections:
        print(f"Error: No collections found in {collections_file}")
        return
    
    print(f"Collections mode: Found {len(collections)} collections in {collections_file}")
    print("Collections to process:")
    for collection in collections:
        print(f"  - {collection}")
    print()
    
    total_renamed = 0
    total_skipped = 0
    
    for collection in collections:
        # Build path to the font directory within the collection
        font_dir = os.path.join(collection, 'InDesign_master', 'font')
        
        if not os.path.exists(font_dir):
            print(f"Warning: Font directory not found: {font_dir}")
            print()
            continue
        
        print(f"Processing collection: {collection}")
        print(f"Font directory: {font_dir}")
        
        # Process fonts in this collection
        renamed_count = 0
        skipped_count = 0
        
        for filename in os.listdir(font_dir):
            if filename.lower().endswith(('.ttf', '.otf')):
                # Normalize to lowercase for lookup
                lower_filename = filename.lower()
                if lower_filename in FONT_NAME_MAP:
                    new_name = FONT_NAME_MAP[lower_filename]
                    old_path = os.path.join(font_dir, filename)
                    new_path = os.path.join(font_dir, new_name)
                    
                    if not os.path.exists(new_path):
                        try:
                            os.rename(old_path, new_path)
                            print(f"  Renamed: {filename} → {new_name}")
                            renamed_count += 1
                        except Exception as e:
                            print(f"  Failed to rename {filename} → {new_name}: {e}")
                    else:
                        print(f"  Skipping: {filename} → {new_name} (target already exists)")
                        skipped_count += 1
        
        print(f"  Collection summary: {renamed_count} renamed, {skipped_count} skipped")
        print()
        
        total_renamed += renamed_count
        total_skipped += skipped_count
    
    print(f"Overall summary: {total_renamed} renamed, {total_skipped} skipped across all collections")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Rename font files from Monolith output to correct names. '
                    'Supports both single directory mode and collections mode (using collections.txt).'
    )
    parser.add_argument(
        'directory',
        nargs='?',
        help='Path to the directory containing font files (e.g., ./fonts). '
             'If omitted and collections.txt exists, will process all collections.'
    )
    parser.add_argument(
        '--collections',
        action='store_true',
        help='Force collections mode (read from collections.txt)'
    )
    
    args = parser.parse_args()
    
    # Check if we should use collections mode
    if args.collections or (not args.directory and os.path.exists('collections.txt')):
        process_collections_mode()
    elif args.directory:
        rename_fonts(args.directory)
    else:
        print("Error: No directory specified and collections.txt not found.")
        print("Usage:")
        print("  Single directory mode: python fix-fonts.py <directory>")
        print("  Collections mode: python fix-fonts.py --collections")
        print("  Auto-detect mode: python fix-fonts.py (requires collections.txt)")