#!/usr/bin/env python

"""merge_all_publications.py: Merges multiple HTML files exported from Adobe InDesign into a single scrollable document with CSS namespacing to prevent conflicts."""

__author__      = "Ed Watson"
__copyright__   = "CC-BY-SA-4.0 license"
__version__     = "2.9.0"
__comments__    = "03/17/26 EW: 2.9.0 Updates - Fixed interactive button bug by namespacing element IDs to prevent conflicts between collections (InDesign exports use same ID patterns like _idContainer000); Also fixed JS reference bug to only add script tags when idGeneratedScript.js exists; 01/14/26 EW: 2.8.0 Updates - Fixed font path resolution in CSS and added automatic short-name font file normalization (e.g., calibril.ttf → Calibri-Light.ttf); 01/13/26 EW: 2.7.0v Updates - Implemented CSS namespacing to prevent style conflicts between collections; 01/13/26 EW: 2.5.3-debug Updates - Added comprehensive debug logging; 12/15/25 EW: 2.5.2v Updates - fixed base64 image handling and improved output"

import os
import re
import shutil
import sys
import argparse
import base64
from bs4 import BeautifulSoup

# Global debug flag - will be set by command-line argument
DEBUG = False

# Global flag to show/hide page navigation features (current page display and jump-to-page)
# Set to True to show these features, False to hide them
SHOW_PAGE_NAVIGATION = False

def log_debug(message):
    """Print debug message if DEBUG is enabled."""
    if DEBUG:
        print(message)

def print_progress_bar(iteration, total, prefix='', suffix='', length=50, fill='█'):
    """
    Print a progress bar to the console.
    
    Args:
        iteration (int): Current iteration (0-indexed)
        total (int): Total iterations
        prefix (str): Prefix string
        suffix (str): Suffix string
        length (int): Character length of bar
        fill (str): Bar fill character
    """
    percent = f"{100 * (iteration / float(total)):.1f}"
    filled_length = int(length * iteration // total)
    bar = fill * filled_length + '-' * (length - filled_length)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent}% {suffix}')
    sys.stdout.flush()
    if iteration == total:
        print()  # New line on completion

def extract_page_number_from_filename(filename):
    """Extract page number from publication filename."""
    numbered_pattern = re.compile(r'publication-(\d+)\.html$')
    match = numbered_pattern.search(filename)
    if match:
        return int(match.group(1))
    if filename == 'publication.html':
        return 0
    return None

def read_collections_file(collections_file='collections.txt'):
    """Read and parse the collections.txt file."""
    if not os.path.exists(collections_file):
        return None
    
    collections = []
    with open(collections_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                collections.append(line)
    
    return collections if collections else None

def namespace_css(css_content, namespace, collection_name):
    """
    Add namespace prefix to all CSS selectors to prevent conflicts between collections.
    Also updates ID selectors to match the namespaced element IDs in the HTML.
    
    Args:
        css_content (str): The CSS content to namespace
        namespace (str): The namespace prefix (e.g., 'ns-collection4')
        collection_name (str): The collection name for ID prefixing (e.g., 'collection4')
        
    Returns:
        str: The namespaced CSS content
    """
    # Simple regex-based CSS namespacing
    # This handles most common CSS patterns but may not cover all edge cases
    
    # Pattern to match CSS selectors (simplified)
    # Matches: .class, #id, element, [attribute], :pseudo, etc.
    selector_pattern = r'([.#]?[\w-]+(?:\[[\w-]+(?:[~|^$*]?=[\w-]+)?\])?(?::[\w-]+(?:\([^)]*\))?)*(?:\s*[>+~]\s*)?)'
    
    lines = css_content.split('\n')
    namespaced_lines = []
    
    for line in lines:
        # Skip comments and empty lines
        if line.strip().startswith('/*') or line.strip().startswith('*/') or not line.strip():
            namespaced_lines.append(line)
            continue
        
        # Skip other @-rules (like @media, @keyframes) without modification
        if line.strip().startswith('@'):
            namespaced_lines.append(line)
            continue
        
        # Check if line contains a selector (ends with { or contains ,)
        if '{' in line:
            # Split on { to separate selector from properties
            parts = line.split('{', 1)
            selector_part = parts[0].strip()
            
            # Skip if it's already namespaced or is a special selector
            if namespace in selector_part or selector_part.startswith('@'):
                namespaced_lines.append(line)
                continue
            
            # Handle multiple selectors separated by commas
            selectors = [s.strip() for s in selector_part.split(',')]
            namespaced_selectors = []
            
            for selector in selectors:
                # Add namespace prefix
                if selector:
                    # Also namespace ID selectors to match the HTML element IDs
                    # e.g., #_idContainer000 becomes #collection4-_idContainer000
                    selector = re.sub(r'#(_id[A-Za-z]+\d+)', f'#{collection_name}-\\1', selector)
                    namespaced_selector = f'.{namespace} {selector}'
                    namespaced_selectors.append(namespaced_selector)
            
            # Reconstruct the line
            if len(parts) > 1:
                namespaced_line = ', '.join(namespaced_selectors) + ' { ' + parts[1]
            else:
                namespaced_line = ', '.join(namespaced_selectors)
            
            namespaced_lines.append(namespaced_line)
        else:
            # Property line or closing brace
            namespaced_lines.append(line)
    
    return '\n'.join(namespaced_lines)

def fix_font_paths_in_css(css_content):
    """
    Rewrite absolute font paths in CSS to use relative paths.
    Also rewrite font-family names to use non-standard prefixed names to prevent Monolith from resolving them as system fonts.
    Replaces:
      url(/home/font/...) → url("publication-web-resources/font/...")
      url(/font/...) → url("publication-web-resources/font/...")
      font-family: Calibri; → font-family: "Font_Calibri";
      font-family: "Calibri Light"; → font-family: "Font_Calibri-Light";
      font-family: "Minion Pro"; → font-family: "Font_MinionPro-Regular";
      font-family: Calibri-Bold; → font-family: "Font_Calibri-Bold";
      font-family: Calibri-Italic; → font-family: "Font_Calibri-Italic";

      EW 03/26: Now redundant since font changed to Carlito. consider removal
    """
    # Rewrite font paths
    css_content = re.sub(r'url\([\'"]?/home/font/([^\'"]+)[\'"]?\)', r'url("publication-web-resources/font/\1")', css_content)
    css_content = re.sub(r'url\([\'"]?/font/([^\'"]+)[\'"]?\)', r'url("publication-web-resources/font/\1")', css_content)
    
    # Rewrite font-family names to use prefixed non-standard names
    css_content = re.sub(r'font-family:\s*Calibri\s*;', r'font-family: "Font_Calibri";', css_content)
    css_content = re.sub(r'font-family:\s*"Calibri Light"\s*;', r'font-family: "Font_Calibri-Light";', css_content)
    css_content = re.sub(r'font-family:\s*"Minion Pro"\s*;', r'font-family: "Font_MinionPro-Regular";', css_content)
    css_content = re.sub(r'font-family:\s*Calibri-Bold\s*;', r'font-family: "Font_Calibri-Bold";', css_content)
    css_content = re.sub(r'font-family:\s*Calibri-Italic\s*;', r'font-family: "Font_Calibri-Italic";', css_content)
    
    return css_content

def copy_and_namespace_resources(collections, output_dir):
    """
    Copy resources from all collections and namespace the CSS files.
    
    Args:
        collections (list): List of collection directory names
        output_dir (str): Directory where merged-publication.html will be created
        
    Returns:
        dict: Dictionary mapping collection names to their namespaced CSS content
    """
    # Create main publication-web-resources directory
    resources_dir = os.path.join(output_dir, 'publication-web-resources')
    os.makedirs(resources_dir, exist_ok=True)
    
    # Create common directories for shared resources
    common_font_dir = os.path.join(resources_dir, 'font')
    common_image_dir = os.path.join(resources_dir, 'image')
    common_audio_dir = os.path.join(resources_dir, 'audio')
    
    os.makedirs(common_font_dir, exist_ok=True)
    os.makedirs(common_image_dir, exist_ok=True)
    os.makedirs(common_audio_dir, exist_ok=True)
    
    # Dictionary to store collection-specific resource directories and namespaced CSS
    collection_resources_map = {}
    namespaced_css_map = {}
    
    print("\nProcessing collections with CSS namespacing...")
    
    total_collections = len(collections)
    for idx, collection in enumerate(collections, 1):
        collection_name = os.path.basename(collection)
        namespace = f'ns-{collection_name}'
        
        # Show progress
        print_progress_bar(idx - 1, total_collections, prefix='Progress:', suffix=f'Processing {collection_name}', length=40)
        
        # Create collection-specific directories for JS only (CSS will be inlined)
        collection_dir = os.path.join(resources_dir, collection_name)
        script_dir = os.path.join(collection_dir, 'script')
        
        os.makedirs(script_dir, exist_ok=True)
        
        collection_resources_map[collection] = collection_dir
        
        # Source resources directory
        source_resources = os.path.join(collection, 'InDesign_master', 'publication-web-resources')
        
        if not os.path.exists(source_resources):
            print(f"\nError: Resources directory not found for collection: {collection}")
            continue
        
        # Read and namespace CSS files
        source_css = os.path.join(source_resources, 'css', 'idGeneratedStyles.css')
        if os.path.exists(source_css):
            log_debug(f"  Namespacing CSS for {collection_name}...")
            with open(source_css, 'r', encoding='utf-8') as f:
                css_content = f.read()
            
            # First, fix absolute font paths in the source CSS
            css_content = fix_font_paths_in_css(css_content)
            
            # Then namespace the CSS (including ID selectors to match namespaced HTML element IDs)
            namespaced_css = namespace_css(css_content, namespace, collection_name)
            namespaced_css_map[collection_name] = namespaced_css
        
        # Copy JavaScript files
        source_script = os.path.join(source_resources, 'script')
        if os.path.exists(source_script):
            for item in os.listdir(source_script):
                src = os.path.join(source_script, item)
                dst = os.path.join(script_dir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
        
        # Copy image files to common directory
        source_image = os.path.join(source_resources, 'image')
        if os.path.exists(source_image):
            for item in os.listdir(source_image):
                src = os.path.join(source_image, item)
                dst = os.path.join(common_image_dir, item)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
        
        # Copy audio files to common directory
        source_audio = os.path.join(source_resources, 'audio')
        if os.path.exists(source_audio):
            for item in os.listdir(source_audio):
                src = os.path.join(source_audio, item)
                dst = os.path.join(common_audio_dir, item)
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
        
        # Copy font files
        source_font_dir = os.path.join(collection, 'InDesign_master', 'font')
        if os.path.exists(source_font_dir):
            for item in os.listdir(source_font_dir):
                src = os.path.join(source_font_dir, item)
                dst = os.path.join(common_font_dir, item)
                
                if os.path.isfile(src) and not os.path.exists(dst):
                    shutil.copy2(src, dst)
    
    # Complete the progress bar
    print_progress_bar(total_collections, total_collections, prefix='Progress:', suffix='Complete!', length=40)
    print("Resources processed successfully with CSS namespacing.\n")
    
    # Map short-name font files to their expected long-name variants. EW Note: Font changed to Carlito Mar2026. Name issues fixed. 
    # EW 03/26: Calibri remapping now redundant since font changed to Carlito. Consider removal.
    font_name_mappings = {
        'calibrili.ttf': 'Calibri-LightItalic.ttf',
        'calibril.ttf': 'Calibri-Light.ttf',
        'calibriz.ttf': 'Calibri-BoldItalic.ttf',
        'calibri.ttf': 'Calibri.ttf',
        'calibrib.ttf': 'Calibri-Bold.ttf',
        'calibrii.ttf': 'Calibri-Italic.ttf',
        'calibriz.ttf': 'Calibri-BoldItalic.ttf',
        'calibrili.ttf': 'Calibri-LightItalic.ttf',
        'Carlito-Regular.ttf': 'Carlito.ttf'
    }
    # EW 03/26: Added "'Carlito-Regular.ttf': 'Carlito.ttf'" incase an issue arises with Carlito on some docs
    
    # Create copies for missing long-name variants
    for short_name, long_name in font_name_mappings.items():
        short_path = os.path.join(common_font_dir, short_name)
        long_path = os.path.join(common_font_dir, long_name)
        
        if os.path.exists(short_path) and not os.path.exists(long_path):
            shutil.copy2(short_path, long_path)
            log_debug(f"Copied {short_name} → {long_name} for font compatibility")
    
    # Rename Calibri font files to non-standard names to prevent Monolith from resolving them as system fonts instead. Seems different OSs have slightly different Calibri fonts. Embedded Carlito fonts are recommended
    # EW 03/26: Calibri remapping now redundant since font changed to Carlito. Consider removal.
    font_rename_map = {
        'Calibri.ttf': 'Font_Calibri.ttf',
        'Calibri-Bold.ttf': 'Font_Calibri-Bold.ttf',
        'Calibri-Italic.ttf': 'Font_Calibri-Italic.ttf',
        'Calibri-Light.ttf': 'Font_Calibri-Light.ttf',
        'Calibri-LightItalic.ttf': 'Font_Calibri-LightItalic.ttf',
        'Calibri-BoldItalic.ttf': 'Font_Calibri-BoldItalic.ttf',
        'MinionPro-Regular.otf': 'Font_MinionPro-Regular.otf'
    }
    
    for old_name, new_name in font_rename_map.items():
        old_path = os.path.join(common_font_dir, old_name)
        new_path = os.path.join(common_font_dir, new_name)
        
        if os.path.exists(old_path) and not os.path.exists(new_path):
            shutil.move(old_path, new_path)
            log_debug(f"Renamed font: {old_name} → {new_name}")
    
    return collection_resources_map, namespaced_css_map

def find_publication_files(directory=None):
    """Find all HTML files matching publication patterns."""
    search_dir = directory if directory else os.getcwd()
    publication_files = []
    page_numbers_found = set()
    
    if os.path.exists(search_dir):
        for filename in os.listdir(search_dir):
            page_number = extract_page_number_from_filename(filename)
            
            if page_number is not None:
                file_path = os.path.join(search_dir, filename)
                
                if page_number == 0 and filename == 'publication.html':
                    if 0 not in page_numbers_found:
                        publication_files.append((page_number, file_path))
                        page_numbers_found.add(page_number)
                else:
                    if page_number == 0 and page_number in page_numbers_found:
                        publication_files = [(pn, fp) for pn, fp in publication_files if pn != 0]
                    publication_files.append((page_number, file_path))
                    page_numbers_found.add(page_number)
    
    publication_files.sort(key=lambda x: x[0])
    return [file_path for _, file_path in publication_files]

def collect_all_publication_files_from_collections(collections):
    """Collect all publication files from multiple collections."""
    all_files = []
    
    print("\nCollecting publication files from collections...")
    
    for idx, collection in enumerate(collections, 1):
        collection_name = os.path.basename(collection)
        html_dir = os.path.join(collection, 'InDesign_master', 'publication-web-resources', 'html')
        
        if not os.path.exists(html_dir):
            print(f"  [{idx}/{len(collections)}] {collection_name}: Directory not found")
            continue
        
        collection_files = find_publication_files(html_dir)
        
        if collection_files:
            all_files.extend(collection_files)
            print(f"  [{idx}/{len(collections)}] {collection_name}: Found {len(collection_files)} publication(s) (Total: {len(all_files)})")
        else:
            print(f"  [{idx}/{len(collections)}] {collection_name}: No publication files found")
    
    print(f"\nTotal publications collected: {len(all_files)}\n")
    return all_files

def get_font_as_base64(font_path):
    """Read a font file and return its base64-encoded content."""
    with open(font_path, 'rb') as f:
        font_data = f.read()
    return base64.b64encode(font_data).decode('utf-8')

def merge_html_pages(publication_files, output_path, collection_resources_map, namespaced_css_map):
    """
    Merge multiple HTML pages into a single scrollable page with namespaced CSS.
    
    Args:
        publication_files (list): List of paths to the HTML files to merge
        output_path (str): Path where the merged HTML file will be saved
        collection_resources_map (dict): Dictionary mapping collection paths to their resource directories
        namespaced_css_map (dict): Dictionary mapping collection names to their namespaced CSS content
    """
    if not publication_files:
        print("Error: No publication files found to merge.")
        return
    
    # Define required fonts and their paths
    # EW 03/26: Now redundant since font changed to Carlito. Consider removal.
    font_files = {
        'Calibri': os.path.join('publication-web-resources', 'font', 'Calibri.ttf'),
        'Calibri-Bold': os.path.join('publication-web-resources', 'font', 'Calibri-Bold.ttf'),
        'Calibri-Italic': os.path.join('publication-web-resources', 'font', 'Calibri-Italic.ttf'),
        'Calibri-Light': os.path.join('publication-web-resources', 'font', 'Calibri-Light.ttf'),
        'MinionPro-Regular': os.path.join('publication-web-resources', 'font', 'MinionPro-Regular.otf')
    }
    
    # Build base64 @font-face rules
    font_faces = []
    for font_name, font_path in font_files.items():
        if os.path.exists(font_path):
            font_data = get_font_as_base64(font_path)
            mime_type = 'font/otf' if font_path.endswith('.otf') else 'font/ttf'
            font_faces.append(f'''
    @font-face {{
        font-family: "{font_name}";
        src: url(data:{mime_type};base64,{font_data}) format('truetype');
        font-weight: normal;
        font-style: normal;
    }}''')
        else:
            log_debug(f"Warning: Font file not found: {font_path}")
    
    # Join all font-face rules
    embedded_fonts_css = '\n'.join(font_faces)
    
    # Create a new HTML document
    merged_html = """<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="de-DE">
<head>
    <meta charset="utf-8" />
    <title>HTML5 Publication</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: black;
        }
        .container {
            width: 843px;
            margin: 0 auto;
            overflow-y: auto;
        }
        .publication {
            width: 843px;
            height: 600px;
            position: relative;
            margin-bottom: 20px;
        }
        .separator {
            height: 30px;
            background-color: #f0f0f0;
            border-top: 1px solid #ccc;
            border-bottom: 1px solid #ccc;
            margin: 20px 0;
            text-align: center;
            font-family: Arial, sans-serif;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 10px 20px;
        }
        .nav-left, .nav-center, .nav-right {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .nav-left {
            flex: 1;
            justify-content: flex-start;
        }
        .nav-center {
            flex: 0 0 auto;
            justify-content: center;
        }
        .nav-right {
            flex: 1;
            justify-content: flex-end;
        }
        .nav-button {
            background-color: #0083BB;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            font-weight: bold;
            transition: background-color 0.3s;
        }
        .nav-button:hover {
            background-color: #0056b3;
        }
        .nav-button:disabled {
            background-color: #6c757d;
            cursor: not-allowed;
        }
        .goto-container {
            display: flex;
            align-items: center;
            gap: 5px;
            font-size: 12px
        }
        .goto-input {
            width: 50px;
            padding: 6px;
            border: 1px solid #ccc;
            border-radius: 4px;
            text-align: center;
            font-size: 12px;
        }
        .current-page-display {
            margin-left: 20px;
            font-size: 12px;
            font-weight: bold;
            color: #333;
            display: flex;
            align-items: center;
        }
        .print-container {
            display: flex;
            align-items: center;
            gap: 5px;
            margin-left: 15px;
        }
        .print-button {
            background-color: #3FA353;
            font-size: 12px;
        }
        .print-button:hover {
            background-color: #218838;
        }
        
        /* Print media queries */
        @page {
            size: landscape;
        }
        
        @media print {
            .separator, .nav-button, .goto-container, .current-page-display, .print-container, .nav-left, .nav-center, .nav-right {
                display: none !important;
            }
            
            body {
                background-color: white !important;
                margin: 0 !important;
                padding: 0 !important;
            }
            
            .container {
                width: 100% !important;
                margin: 0 auto !important;
                padding: 0 !important;
                text-align: center !important;
            }
            
            .publication {
                display: none !important;
                page-break-after: always;
            }
            
            .publication.print-active {
                display: block !important;
                transform: scale(0.85) !important;
                transform-origin: top center !important;
                margin: 20px auto !important;
            }
            
            ._idGenStateHide {
                display: none !important;
            }
            
            audio {
                display: none !important;
            }
        }
        
        /* Namespaced CSS for each collection will be inserted here */
"""
    
    # Insert namespaced CSS for each collection
    for collection_name, css_content in namespaced_css_map.items():
        merged_html += f"\n        /* Namespaced CSS for {collection_name} */\n"
        merged_html += css_content + "\n"
    
    merged_html += """    </style>
    <script type="text/javascript">
        function scrollToPage(userPageNumber) {
            const divId = 'publication-' + (userPageNumber - 1);
            const element = document.getElementById(divId);
            if (element) {
                const rect = element.getBoundingClientRect();
                const scrollTop = window.pageYOffset + rect.top;
                window.scrollTo({
                    top: scrollTop,
                    behavior: 'smooth'
                });
            }
        }
        
        function navigateToPreviousPage(currentPageNumber) {
            const prevPageNumber = currentPageNumber - 1;
            if (prevPageNumber >= 1) {
                scrollToPage(prevPageNumber);
            }
        }
        
        function navigateToNextPage(currentPageNumber, totalPages) {
            const nextPageNumber = currentPageNumber + 1;
            if (nextPageNumber <= totalPages) {
                scrollToPage(nextPageNumber);
            }
        }
        
        function goToSpecificPage(inputId, totalPages) {
            const input = document.getElementById(inputId);
            const pageNumber = parseInt(input.value);
            
            if (isNaN(pageNumber) || pageNumber < 1 || pageNumber > totalPages) {
                alert('Bitte geben Sie eine gültige Seitenzahl zwischen 1 und ' + totalPages);
                input.value = '';
                return;
            }
            
            scrollToPage(pageNumber);
            input.value = '';
        }
        
        function printCurrentPage() {
            alert('Um eine korrekte Formatierung beim Drucken zu gewährleisten, aktivieren Sie bitte "Hintergrunddruck" in Ihrem Druckerdialog.');
            const currentPageNumber = getCurrentVisiblePage();
            printSpecificPage(currentPageNumber);
        }

        function printSpecificPage(pageNumber) {
            document.querySelectorAll('.publication').forEach(pub => {
                pub.classList.remove('print-active');
            });
            
            const targetPageId = 'publication-' + (pageNumber - 1);
            const targetPage = document.getElementById(targetPageId);
            
            if (targetPage) {
                targetPage.classList.add('print-active');
                setTimeout(() => {
                    window.print();
                    setTimeout(() => {
                        targetPage.classList.remove('print-active');
                    }, 1000);
                }, 100);
            }
        }

        function getCurrentVisiblePage() {
            const publications = document.querySelectorAll('.publication');
            let mostVisiblePage = 1;
            let maxVisibleArea = 0;
            
            publications.forEach((pub, index) => {
                const rect = pub.getBoundingClientRect();
                const visibleHeight = Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0);
                const visibleArea = Math.max(0, visibleHeight) * rect.width;
                
                if (visibleArea > maxVisibleArea) {
                    maxVisibleArea = visibleArea;
                    mostVisiblePage = index + 1;
                }
            });
            
            return mostVisiblePage;
        }
        
        function initializeNavigation() {
            if (typeof RegisterInteractiveHandlers === 'function') {
                RegisterInteractiveHandlers();
            }
        
            document.querySelectorAll('.goto-input').forEach(input => {
                input.addEventListener('keydown', function(event) {
                    if (event.key === 'Enter' || event.keyCode === 13) {
                        event.preventDefault();
                        const separator = this.closest('.separator');
                        const totalPages = parseInt(separator.getAttribute('data-total-pages'));
                        const inputId = this.id;
                        goToSpecificPage(inputId, totalPages);
                    }
                });
            });
        }
    </script>
"""
    
    # Track which collections we've already added JS for
    added_collections = set()
    
    # Add JS references only for collections that have idGeneratedScript.js
    # This fixes the bug where script tags were added for non-existent files,
    # causing 404 errors that broke interactive button functionality
    for collection_path in collection_resources_map.keys():
        collection_name = os.path.basename(collection_path)
        js_file_path = os.path.join('publication-web-resources', collection_name, 'script', 'idGeneratedScript.js')
        
        if os.path.exists(js_file_path) and collection_path not in added_collections:
            js_script = f'<script src="{js_file_path}" type="text/javascript" id="js-{collection_name}"></script>'
            merged_html += f'    {js_script}\n'
            added_collections.add(collection_path)
            log_debug(f"  Added JS reference for {collection_name}: {js_file_path}")
        elif collection_path not in added_collections:
            log_debug(f"  Skipping JS reference for {collection_name}: idGeneratedScript.js not found")
    
    merged_html += """</head>
<body onload="initializeNavigation();">
    <div class="container">
"""

    print(f"\nMerging {len(publication_files)} publications...")
    
    # Process each publication file
    total_files = len(publication_files)
    for index, file_path in enumerate(publication_files, 1):
        # Show progress
        print_progress_bar(index - 1, total_files, prefix='Merging:', suffix=f'Page {index}/{total_files}', length=40)
        
        filename = os.path.basename(file_path)
        file_page_number = extract_page_number_from_filename(filename)
        display_page_number = index
        
        # Determine which collection this file belongs to
        collection_path = None
        for coll in collection_resources_map.keys():
            if coll in file_path:
                collection_path = coll
                break
        
        if not collection_path:
            print(f"Warning: Could not determine collection for file: {file_path}")
            continue
        
        collection_name = os.path.basename(collection_path)
        namespace = f'ns-{collection_name}'
        
        # Read the HTML file
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Extract the main content div
        soup = BeautifulSoup(content, 'html.parser')
        main_content = soup.select_one('div[style*="position:absolute;overflow:hidden"]')
        
        if main_content:
            # Update image paths
            for img in main_content.find_all('img'):
                if img.get('src'):
                    src = img['src']
                    if not src.startswith('data:'):
                        if src.startswith('../image/'):
                            img['src'] = 'publication-web-resources/image/' + src.replace('../image/', '')
                        elif src.startswith('image/'):
                            img['src'] = 'publication-web-resources/image/' + src.replace('image/', '')
            
            # Update object/embed tags
            for obj in main_content.find_all(['object', 'embed']):
                if obj.get('data'):
                    data = obj['data']
                    if not data.startswith('data:'):
                        if data.startswith('../image/'):
                            obj['data'] = 'publication-web-resources/image/' + data.replace('../image/', '')
                        elif data.startswith('image/'):
                            obj['data'] = 'publication-web-resources/image/' + data.replace('image/', '')
                if obj.get('src'):
                    src = obj['src']
                    if not src.startswith('data:'):
                        if src.startswith('../image/'):
                            obj['src'] = 'publication-web-resources/image/' + src.replace('../image/', '')
                        elif src.startswith('image/'):
                            obj['src'] = 'publication-web-resources/image/' + src.replace('image/', '')
            
            # Update audio tags
            for audio in main_content.find_all('audio'):
                if audio.get('src'):
                    src = audio['src']
                    if not src.startswith('data:'):
                        if src.startswith('../audio/'):
                            audio['src'] = 'publication-web-resources/audio/' + src.replace('../audio/', '')
                        elif src.startswith('audio/'):
                            audio['src'] = 'publication-web-resources/audio/' + src.replace('audio/', '')
                
                for source in audio.find_all('source'):
                    if source.get('src'):
                        src = source['src']
                        if not src.startswith('data:'):
                            if src.startswith('../audio/'):
                                source['src'] = 'publication-web-resources/audio/' + src.replace('../audio/', '')
                            elif src.startswith('audio/'):
                                source['src'] = 'publication-web-resources/audio/' + src.replace('audio/', '')
            
            # Update font references
            for element in main_content.find_all(lambda tag: tag.has_attr('style') and 'font-family' in tag['style']):
                style = element['style']
                
                # Rewrite font URLs
                if 'url(' in style and '/font/' in style:
                    if not ('data:' in style and 'base64' in style):
                        style = re.sub(r'url\([\'"]?(?:\.\.)?/font/([^\'"]+)[\'"]?\)',
                                      r'url("publication-web-resources/font/\1")',
                                      style)
                
                # Rewrite font-family names to non-standard names
                style = re.sub(r'font-family:\s*Calibri\s*;', r'font-family: "Font_Calibri";', style)
                style = re.sub(r'font-family:\s*"Calibri Light"\s*;', r'font-family: "Font_Calibri-Light";', style)
                style = re.sub(r'font-family:\s*"Minion Pro"\s*;', r'font-family: "Font_MinionPro-Regular";', style)
                style = re.sub(r'font-family:\s*Calibri-Bold\s*;', r'font-family: "Font_Calibri-Bold";', style)
                style = re.sub(r'font-family:\s*Calibri-Italic\s*;', r'font-family: "Font_Calibri-Italic";', style)
                
                element['style'] = style
            
            # Namespace element IDs to prevent conflicts between collections
            # This is critical because InDesign exports use the same ID patterns (_idContainer000, etc.)
            # across different documents, causing getElementById() to find wrong elements
            id_prefix = f'{collection_name}-'
            
            # Update all element IDs
            for element in main_content.find_all(id=True):
                old_id = element['id']
                new_id = id_prefix + old_id
                element['id'] = new_id
            
            # Update all ID references in data attributes (data-releaseactions, data-clickactions, etc.)
            # These contain JavaScript calls like onShow('_idContainer053') that need updating
            data_attrs_with_ids = ['data-releaseactions', 'data-clickactions', 'data-rolloveractions',
                                   'data-rolloffactions', 'data-animationOnPageLoadActions',
                                   'data-animationOnStateLoadActions', 'data-animationOnSelfClickActions',
                                   'data-animationOnSelfRolloverActions', 'data-animationOnPageClickActions',
                                   'data-mediaOnPageLoadActions']
            
            for attr in data_attrs_with_ids:
                for element in main_content.find_all(attrs={attr: True}):
                    attr_value = element[attr]
                    # Replace ID references in onShow('id'), onHide('id'), onMediaStart('id',...), etc.
                    # Pattern matches: onShow('_idContainer053') or onHide('_idContainer053')
                    attr_value = re.sub(
                        r"(onShow|onHide)\('(_id[^']+)'\)",
                        lambda m: f"{m.group(1)}('{id_prefix}{m.group(2)}')",
                        attr_value
                    )
                    # Also update media control functions: onMediaStart, onMediaStop, onMediaPause, onMediaResume
                    # Pattern matches: onMediaStart('_idAudio000',0.00,0.000)
                    attr_value = re.sub(
                        r"(onMediaStart|onMediaStop|onMediaPause|onMediaResume)\('(_id[^']+)'",
                        lambda m: f"{m.group(1)}('{id_prefix}{m.group(2)}'",
                        attr_value
                    )
                    element[attr] = attr_value
            
            # Add data attribute
            main_content['data-collection'] = collection_name
            
            # Wrap content in namespace div and publication wrapper
            # Use display_page_number (sequential index) for ID to ensure unique IDs across all collections
            merged_html += f'        <div class="publication" id="publication-{display_page_number - 1}">\n'
            merged_html += f'            <div class="{namespace}">\n'
            merged_html += '                ' + str(main_content) + '\n'
            merged_html += '            </div>\n'
            merged_html += '        </div>\n'
            
            # Add navigation buttons
            if index < len(publication_files):
                total_pages = len(publication_files)
                prev_disabled = 'disabled' if display_page_number == 1 else ''
                prev_onclick = f"navigateToPreviousPage({display_page_number})" if display_page_number > 1 else ""
                next_disabled = 'disabled' if display_page_number == total_pages else ''
                next_onclick = f"navigateToNextPage({display_page_number}, {total_pages})" if display_page_number < total_pages else ""
                input_id = f"goto-input-{display_page_number}"
                goto_onclick = f"goToSpecificPage('{input_id}', {total_pages})"
                
                # Build goto-container HTML conditionally based on SHOW_PAGE_NAVIGATION
                goto_container_html = ''
                current_page_display_html = ''
                if SHOW_PAGE_NAVIGATION:
                    goto_container_html = f'''
                <div class="goto-container">
                    <span>Geh zu Seite</span>
                    <input type="number" class="goto-input" id="{input_id}" min="1" max="{total_pages}" placeholder="1-{total_pages}">
                    <button class="nav-button" onclick="{goto_onclick}">Geh</button>
                </div>'''
                    current_page_display_html = f'''
                <div class="current-page-display">
                    Seite {display_page_number} von {total_pages}
                </div>'''
                
                merged_html += f'''        <div class="separator" data-total-pages="{total_pages}">
            <div class="nav-left">
                <button class="nav-button" {prev_disabled} onclick="{prev_onclick}">Vorherige Seite</button>{goto_container_html}
            </div>
            <div class="nav-center">
                <div class="print-container">
                    <button class="nav-button print-button" onclick="printCurrentPage()">Aktuelle Seite drucken</button>
                </div>{current_page_display_html}
            </div>
            <div class="nav-right">
                <button class="nav-button" {next_disabled} onclick="{next_onclick}">Nächste Seite</button>
            </div>
        </div>
'''

    merged_html += """    </div>
</body>
</html>"""

    # Complete the progress bar
    print_progress_bar(total_files, total_files, prefix='Merging:', suffix='Complete!', length=40)
    
    # Write the merged HTML
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(merged_html)
    
    print(f"\nSuccess: Merged HTML file with namespaced CSS created at: {output_path}")
    print(f"Total publications merged: {len(publication_files)}")

def main():
    global DEBUG
    
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Merge multiple HTML files exported from Adobe InDesign into a single scrollable document with CSS namespacing.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  python merge_all_publications_v2.9.py              # Normal mode
  python merge_all_publications_v2.9.py --debug      # Debug mode with detailed logging
  python merge_all_publications_v2.9.py -d           # Debug mode (short form)
        '''
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Enable debug mode with detailed logging'
    )
    
    args = parser.parse_args()
    DEBUG = args.debug
    
    if DEBUG:
        print("Debug mode enabled\n")
    
    current_dir = os.getcwd()
    output_path = os.path.join(current_dir, 'merged-publication.html')
    
    collections_file = os.path.join(current_dir, 'collections.txt')
    collections = read_collections_file(collections_file)
    
    if collections:
        print(f"\nCollections mode: Found {len(collections)} collections in collections.txt")
        print("Collections to process:")
        for collection in collections:
            print(f"  - {collection}")
        
        # Copy resources and namespace CSS
        collection_resources_map, namespaced_css_map = copy_and_namespace_resources(collections, current_dir)
        
        publication_files = collect_all_publication_files_from_collections(collections)
        
        if publication_files:
            merge_html_pages(publication_files, output_path, collection_resources_map, namespaced_css_map)
        else:
            print("Error: No publication files found in any of the specified collections")
    else:
        print("Error: collections.txt not found. This version requires collections mode.")
        print("Please create a collections.txt file with your collection directories.")

if __name__ == "__main__":
    main()
