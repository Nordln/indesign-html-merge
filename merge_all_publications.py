#!/usr/bin/env python

"""merge_all_publications.py: Merges multiple HTML files exported from Adobe InDesign into a single scrollable document with navigation between pages."""

__author__      = "Ed Watson"
__copyright__   = "CC-BY-SA-4.0 license"
__version__     = "2.2"
__comments__    = "11/21/24 EW: 2.2v Updates - Copy resources to common location in collections mode; 2.1v - Auto-detect publication.html; 2.0v - Added collections.txt support"

import os
import re
import shutil
from bs4 import BeautifulSoup

def extract_page_number_from_filename(filename):
    """
    Extract page number from publication filename.
    Handles both 'publication-X.html' and 'publication.html' formats.
    
    Args:
        filename (str): The filename to extract page number from
        
    Returns:
        int or None: Page number if found, None otherwise
    """
    # Check for numbered format: publication-X.html
    numbered_pattern = re.compile(r'publication-(\d+)\.html$')
    match = numbered_pattern.search(filename)
    if match:
        return int(match.group(1))
    
    # Check for unnumbered format: publication.html (treat as page 0)
    if filename == 'publication.html':
        return 0
    
    return None

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

def find_publication_files(directory=None):
    """
    Find all HTML files in the specified directory that match publication patterns
    and sort them by page number. Handles both 'publication-X.html' and 'publication.html' formats.
    If both 'publication.html' and 'publication-0.html' exist, prioritizes the numbered version.
    
    Args:
        directory (str): Directory to search in. If None, uses current directory.
    
    Returns:
        list: Sorted list of publication file paths
    """
    search_dir = directory if directory else os.getcwd()
    publication_files = []
    page_numbers_found = set()
    
    # Find all matching files
    if os.path.exists(search_dir):
        for filename in os.listdir(search_dir):
            page_number = extract_page_number_from_filename(filename)
            
            if page_number is not None:
                file_path = os.path.join(search_dir, filename)
                
                # If this is page 0, check if we already have publication-0.html
                if page_number == 0 and filename == 'publication.html':
                    # Only add publication.html if publication-0.html doesn't exist
                    if 0 not in page_numbers_found:
                        publication_files.append((page_number, file_path))
                        page_numbers_found.add(page_number)
                else:
                    # For numbered files, always add (and replace publication.html if it was added for page 0)
                    if page_number == 0 and page_number in page_numbers_found:
                        # Remove publication.html entry and add publication-0.html
                        publication_files = [(pn, fp) for pn, fp in publication_files if pn != 0]
                    publication_files.append((page_number, file_path))
                    page_numbers_found.add(page_number)
    
    # Sort files by page number
    publication_files.sort(key=lambda x: x[0])
    
    # Return just the file paths in sorted order
    return [file_path for _, file_path in publication_files]

def collect_all_publication_files_from_collections(collections):
    """
    Collect all publication files from multiple collections in the order specified.
    Each collection should have the structure: collection_name/InDesign_master/publication-web-resources/html/
    
    Args:
        collections (list): List of collection directory names
        
    Returns:
        list: Sorted list of all publication file paths from all collections
    """
    all_files = []
    
    for collection in collections:
        # Build path to the html directory within the collection
        html_dir = os.path.join(collection, 'InDesign_master', 'publication-web-resources', 'html')
        
        if not os.path.exists(html_dir):
            print(f"Warning: Collection directory not found: {html_dir}")
            continue
        
        # Find publication files in this collection
        collection_files = find_publication_files(html_dir)
        
        if collection_files:
            print(f"Found {len(collection_files)} files in collection: {collection}")
            all_files.extend(collection_files)
        else:
            print(f"Warning: No publication files found in collection: {collection}")
    
    return all_files

def copy_collection_resources(collections, output_dir):
    """
    Copy CSS, JavaScript, and other resources from all collections to a common location.
    
    Args:
        collections (list): List of collection directory names
        output_dir (str): Directory where merged-publication.html will be created
        
    Returns:
        str: Path to the common resources directory
    """
    # Create publication-web-resources directory structure
    resources_dir = os.path.join(output_dir, 'publication-web-resources')
    css_dir = os.path.join(resources_dir, 'css')
    script_dir = os.path.join(resources_dir, 'script')
    image_dir = os.path.join(resources_dir, 'image')
    
    # Create directories if they don't exist
    os.makedirs(css_dir, exist_ok=True)
    os.makedirs(script_dir, exist_ok=True)
    os.makedirs(image_dir, exist_ok=True)
    
    print("\nCopying resources from collections...")
    
    for collection in collections:
        collection_resources = os.path.join(collection, 'InDesign_master', 'publication-web-resources')
        
        if not os.path.exists(collection_resources):
            print(f"Warning: Resources directory not found for collection: {collection}")
            continue
        
        # Copy CSS files
        collection_css = os.path.join(collection_resources, 'css')
        if os.path.exists(collection_css):
            for item in os.listdir(collection_css):
                src = os.path.join(collection_css, item)
                dst = os.path.join(css_dir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                    print(f"  Copied CSS: {item}")
        
        # Copy JavaScript files
        collection_script = os.path.join(collection_resources, 'script')
        if os.path.exists(collection_script):
            for item in os.listdir(collection_script):
                src = os.path.join(collection_script, item)
                dst = os.path.join(script_dir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                    print(f"  Copied Script: {item}")
        
        # Copy image files
        collection_image = os.path.join(collection_resources, 'image')
        if os.path.exists(collection_image):
            for item in os.listdir(collection_image):
                src = os.path.join(collection_image, item)
                dst = os.path.join(image_dir, item)
                if os.path.isfile(src):
                    shutil.copy2(src, dst)
                    print(f"  Copied Image: {item}")
    
    print("Resource copying complete.\n")
    return resources_dir

def merge_html_pages(publication_files, output_path):
    """
    Merge multiple HTML pages into a single scrollable page with clickable navigation.
    
    Args:
        publication_files (list): List of paths to the HTML files to merge
        output_path (str): Path where the merged HTML file will be saved
    """
    if not publication_files:
        print("No publication files found to merge.")
        return
    
    # Create a new HTML document with navigation JavaScript
    merged_html = """<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="de-DE">
<head>
    <meta charset="utf-8" />
    <title>HTML5 Publication</title>
    <link href="publication-web-resources/css/idGeneratedStyles.css" rel="stylesheet" type="text/css" />
    <script src="publication-web-resources/script/idGeneratedScript.js" type="text/javascript"></script>
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
            justify-content: center;
            gap: 15px;
            padding: 10px;
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
            /* Hide navigation elements */
            .separator, .nav-button, .goto-container, .current-page-display, .print-container {
                display: none !important;
            }
            
            /* Reset body and container for print */
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
            
            /* Hide all pages by default */
            .publication {
                display: none !important;
                page-break-after: always;
            }
            
            /* Show only the page marked for printing with simple scaling */
            .publication.print-active {
                display: block !important;
                transform: scale(0.85) !important;
                transform-origin: top center !important;
                margin: 20px auto !important;
            }
            
            /* Hide only the specific InDesign interactive elements that should be hidden */
            ._idGenStateHide {
                display: none !important;
            }
            
            /* Hide audio controls */
            audio {
                display: none !important;
            }
        }
    </style>
    <script type="text/javascript">
        function scrollToPage(userPageNumber) {
            // Convert 1-based user page number to 0-based div ID
            const divId = 'publication-' + (userPageNumber - 1);
            const element = document.getElementById(divId);
            if (element) {
                // Get the element's position relative to the viewport
                const rect = element.getBoundingClientRect();
                
                // Calculate the scroll position to place the element at the top
                const scrollTop = window.pageYOffset + rect.top;
                
                // Scroll to the element with smooth animation
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
            // Alert user to enable background printing
            alert('Um eine korrekte Formatierung beim Drucken zu gewährleisten, aktivieren Sie bitte "Hintergrunddruck" in Ihrem Druckerdialog.');
            // Get the currently visible page
            const currentPageNumber = getCurrentVisiblePage();
            printSpecificPage(currentPageNumber);
        }

        function printSpecificPage(pageNumber) {
            console.log('Seite drucken:', pageNumber);
            
            // Remove print-active class from all pages
            document.querySelectorAll('.publication').forEach(pub => {
                pub.classList.remove('print-active');
            });
            
            // Add print-active class to the target page
            const targetPageId = 'publication-' + (pageNumber - 1);
            const targetPage = document.getElementById(targetPageId);
            
            console.log('Target page ID:', targetPageId);
            console.log('Target page element:', targetPage);
            
            if (targetPage) {
                targetPage.classList.add('print-active');
                console.log('Added print-active class to:', targetPage);
                
                // Add a small delay to ensure CSS is applied
                setTimeout(() => {
                    // Trigger print dialog
                    window.print();
                    
                    // Clean up after print dialog closes
                    setTimeout(() => {
                        targetPage.classList.remove('print-active');
                        console.log('Removed print-active class');
                    }, 1000);
                }, 100);
            } else {
                console.error('Could not find page element with ID:', targetPageId);
                alert('Die zu druckende Seite konnte nicht gefunden werden. Verfügbare Seiten: ' +
                      Array.from(document.querySelectorAll('.publication')).map(p => p.id).join(', '));
            }
        }

        function getCurrentVisiblePage() {
            // Find which page is currently most visible in viewport
            const publications = document.querySelectorAll('.publication');
            let mostVisiblePage = 1;
            let maxVisibleArea = 0;
            
            publications.forEach((pub, index) => {
                const rect = pub.getBoundingClientRect();
                const visibleHeight = Math.min(rect.bottom, window.innerHeight) - Math.max(rect.top, 0);
                const visibleArea = Math.max(0, visibleHeight) * rect.width;
                
                if (visibleArea > maxVisibleArea) {
                    maxVisibleArea = visibleArea;
                    mostVisiblePage = index + 1; // Convert to 1-based
                }
            });
            
            return mostVisiblePage;
        }

        
        // Register interactive handlers from original script and add our navigation
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
</head>
<body onload="initializeNavigation();">
    <div class="container">
"""
    
    # Process each publication file
    for index, file_path in enumerate(publication_files, 1):
        # Extract page number from filename for the ID (0-based from filename)
        filename = os.path.basename(file_path)
        file_page_number = extract_page_number_from_filename(filename)
        
        # Use 1-based page numbering for user display
        display_page_number = index
        
        # Read the HTML file
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Extract the main content div
        soup = BeautifulSoup(content, 'html.parser')
        main_content = soup.select_one('div[style*="position:absolute;overflow:hidden"]')
        
        if main_content:
            # Update image paths in the content to point to the common resources directory
            # Find all img tags and update their src attributes
            for img in main_content.find_all('img'):
                if img.get('src'):
                    src = img['src']
                    # If it's a relative path starting with ../image/
                    if src.startswith('../image/'):
                        img['src'] = 'publication-web-resources/image/' + src.replace('../image/', '')
                    # If it's just image/
                    elif src.startswith('image/'):
                        img['src'] = 'publication-web-resources/' + src
            
            # Find all object/embed tags (for SVG) and update their data/src attributes
            for obj in main_content.find_all(['object', 'embed']):
                if obj.get('data'):
                    data = obj['data']
                    if data.startswith('../image/'):
                        obj['data'] = 'publication-web-resources/image/' + data.replace('../image/', '')
                    elif data.startswith('image/'):
                        obj['data'] = 'publication-web-resources/' + data
                if obj.get('src'):
                    src = obj['src']
                    if src.startswith('../image/'):
                        obj['src'] = 'publication-web-resources/image/' + src.replace('../image/', '')
                    elif src.startswith('image/'):
                        obj['src'] = 'publication-web-resources/' + src
            
            # Keep div ID matching the original filename (0-based)
            merged_html += f'<div class="publication" id="publication-{file_page_number}">\n'
            merged_html += str(main_content)
            merged_html += '\n</div>\n'
            
            # Add navigation buttons between publications (except after the last one)
            if index < len(publication_files):
                total_pages = len(publication_files)
                
                # Previous page button (using 1-based display numbering)
                prev_disabled = 'disabled' if display_page_number == 1 else ''
                prev_onclick = f"navigateToPreviousPage({display_page_number})" if display_page_number > 1 else ""
                
                # Next page button (using 1-based display numbering)
                next_disabled = 'disabled' if display_page_number == total_pages else ''
                next_onclick = f"navigateToNextPage({display_page_number}, {total_pages})" if display_page_number < total_pages else ""
                
                # Go to page input
                input_id = f"goto-input-{display_page_number}"
                goto_onclick = f"goToSpecificPage('{input_id}', {total_pages})"
                
                merged_html += f'''<div class="separator" data-total-pages="{total_pages}">
                    <button class="nav-button" {prev_disabled} onclick="{prev_onclick}">Vorherige Seite</button>
                    <div class="goto-container">
                        <span>Geh zu Seite</span>
                        <input type="number" class="goto-input" id="{input_id}" min="1" max="{total_pages}" placeholder="1-{total_pages}">
                        <button class="nav-button" onclick="{goto_onclick}">Geh</button>
                    </div>
                    <div class="print-container">
                        <button class="nav-button print-button" onclick="printCurrentPage()">Aktuelle Seite drucken</button>
                    </div>
                    <div class="current-page-display">
                        Seite {display_page_number} von {total_pages}
                    </div>
                    <button class="nav-button" {next_disabled} onclick="{next_onclick}">Nächste Seite</button>
                </div>
'''
    
    # Close the container and body tags
    merged_html += """    </div>
</body>
</html>"""
    
    # Write the merged HTML to the output file
    with open(output_path, 'w', encoding='utf-8') as file:
        file.write(merged_html)
    
    print(f"Merged HTML file created at: {output_path}")
    print(f"Total publications merged: {len(publication_files)}")

def main():
    # Define output path
    current_dir = os.getcwd()
    output_path = os.path.join(current_dir, 'merged-publication.html')
    
    # Check if collections.txt exists
    collections_file = os.path.join(current_dir, 'collections.txt')
    collections = read_collections_file(collections_file)
    
    if collections:
        # Collections mode: merge files from multiple collections
        print(f"Collections mode: Found {len(collections)} collections in collections.txt")
        print("Collections to process:")
        for collection in collections:
            print(f"  - {collection}")
        
        # Copy resources from all collections to common location
        copy_collection_resources(collections, current_dir)
        
        publication_files = collect_all_publication_files_from_collections(collections)
        
        if publication_files:
            print(f"Total publications to merge: {len(publication_files)}")
            
            # Merge the HTML pages
            merge_html_pages(publication_files, output_path)
        else:
            print("No publication files found in any of the specified collections")
    else:
        # Original mode: find files in current directory
        print("Original mode: Searching for publication files in current directory")
        publication_files = find_publication_files()
        
        if publication_files:
            print(f"Found {len(publication_files)} publication files to merge:")
            for file_path in publication_files:
                print(f"  - {os.path.basename(file_path)}")
            
            # Merge the HTML pages
            merge_html_pages(publication_files, output_path)
        else:
            print("No publication files found matching the pattern 'publication-[number].html'")

if __name__ == "__main__":
    main()
