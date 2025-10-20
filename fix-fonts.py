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

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Rename font files from Monolith output to correct names.')
    parser.add_argument('directory', help='Path to the directory containing font files (e.g., ./fonts)')
    
    args = parser.parse_args()
    rename_fonts(args.directory)