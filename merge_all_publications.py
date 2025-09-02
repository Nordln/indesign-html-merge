#!/usr/bin/env python

"""merge_all_publications.py: Merges multiple HTML files exported from Adobe InDesign into a single scrollable document with navigation between pages."""

__author__      = "Ed Watson"
__copyright__   = "CC-BY-SA-4.0 license"

import os
import re
from bs4 import BeautifulSoup

def find_publication_files():
    """
    Find all HTML files in the current directory that match the pattern "-[number].html"
    and sort them by page number.
    
    Returns:
        list: Sorted list of publication file paths
    """
    current_dir = os.getcwd()
    publication_files = []
    
    # Regular expression to match files with pattern "-[number].html"
    pattern = re.compile(r'publication-(\d+)\.html$')
    
    # Find all matching files
    for filename in os.listdir(current_dir):
        match = pattern.search(filename)
        if match:
            page_number = int(match.group(1))
            file_path = os.path.join(current_dir, filename)
            publication_files.append((page_number, file_path))
    
    # Sort files by page number
    publication_files.sort(key=lambda x: x[0])
    
    # Return just the file paths in sorted order
    return [file_path for _, file_path in publication_files]

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
    <link href="../css/idGeneratedStyles.css" rel="stylesheet" type="text/css" />
    <script src="../script/idGeneratedScript.js" type="text/javascript"></script>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: black;
        }
        .container {
            width: 840px;
            margin: 0 auto;
            overflow-y: auto;
        }
        .publication {
            width: 840px;
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
            background-color: #007bff;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
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
        }
        .goto-input {
            width: 50px;
            padding: 6px;
            border: 1px solid #ccc;
            border-radius: 4px;
            text-align: center;
            font-size: 14px;
        }
        
        /* Floating Zoom-Out Button Styles */
        .zoom-out-button {
            position: fixed;
            top: 20px;
            right: 20px;
            width: 50px;
            height: 50px;
            background-color: rgba(0, 0, 0, 0.8);
            border: 2px solid rgba(255, 255, 255, 0.9);
            border-radius: 50%;
            cursor: pointer;
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
            transition: all 0.2s ease;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
            -webkit-tap-highlight-color: transparent;
        }
        
        .zoom-out-button:hover {
            background-color: rgba(0, 0, 0, 0.9);
            border-color: rgba(255, 255, 255, 1);
            transform: scale(1.05);
        }
        
        .zoom-out-button:active {
            transform: scale(0.95);
            background-color: rgba(50, 50, 50, 0.9);
        }
        
        .zoom-out-button svg {
            width: 24px;
            height: 24px;
            fill: white;
            stroke: white;
            stroke-width: 1;
        }
        
        /* Animation for button press feedback */
        .zoom-out-button.pressed {
            animation: zoomButtonPress 0.15s ease;
        }
        
        @keyframes zoomButtonPress {
            0% { transform: scale(1); }
            50% { transform: scale(0.9); background-color: rgba(0, 123, 255, 0.9); }
            100% { transform: scale(1); }
        }
        
        /* Ensure button is accessible on all screen sizes */
        @media (max-width: 480px) {
            .zoom-out-button {
                top: 15px;
                right: 15px;
                width: 48px;
                height: 48px;
            }
        }
    </style>
    <script type="text/javascript">
        function scrollToPage(pageId) {
            const element = document.getElementById(pageId);
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
                scrollToPage('publication-' + prevPageNumber);
            }
        }
        
        function navigateToNextPage(currentPageNumber, totalPages) {
            const nextPageNumber = currentPageNumber + 1;
            if (nextPageNumber <= totalPages) {
                scrollToPage('publication-' + nextPageNumber);
            }
        }
        
        function goToSpecificPage(inputId, totalPages) {
            const input = document.getElementById(inputId);
            const pageNumber = parseInt(input.value);
            
            if (isNaN(pageNumber) || pageNumber < 1 || pageNumber > totalPages) {
                alert('Please enter a valid page number between 1 and ' + totalPages);
                input.value = '';
                return;
            }
            
            scrollToPage('publication-' + pageNumber);
            input.value = '';
        }
        
        // Floating Zoom-Out Button Functionality
        function resetBrowserZoom() {
            try {
                // Method 1: Direct zoom reset (Chrome/WebKit)
                if (document.body.style.zoom !== undefined) {
                    document.body.style.zoom = '1';
                }
                
                // Method 2: CSS transform reset
                if (document.body.style.transform !== undefined) {
                    document.body.style.transform = 'scale(1)';
                }
                
                // Method 3: Viewport meta tag manipulation (Safari fallback)
                let viewport = document.querySelector('meta[name="viewport"]');
                if (!viewport) {
                    viewport = document.createElement('meta');
                    viewport.name = 'viewport';
                    document.head.appendChild(viewport);
                }
                viewport.content = 'width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no';
                
                // Method 4: Force viewport reset by temporarily changing content
                setTimeout(function() {
                    viewport.content = 'width=device-width, initial-scale=1.0, maximum-scale=10.0, user-scalable=yes';
                }, 100);
                
                // Method 5: Reset scroll position to top
                window.scrollTo(0, 0);
                
                // Visual feedback
                const button = document.getElementById('zoom-out-btn');
                if (button) {
                    button.classList.add('pressed');
                    setTimeout(function() {
                        button.classList.remove('pressed');
                    }, 150);
                }
                
                return true;
            } catch (error) {
                console.warn('Zoom reset failed:', error);
                return false;
            }
        }
        
        function initializeZoomButton() {
            const button = document.getElementById('zoom-out-btn');
            if (button) {
                // Touch events for mobile
                button.addEventListener('touchstart', function(e) {
                    e.preventDefault();
                    resetBrowserZoom();
                }, { passive: false });
                
                // Click events for desktop
                button.addEventListener('click', function(e) {
                    e.preventDefault();
                    resetBrowserZoom();
                });
                
                // Prevent context menu on long press
                button.addEventListener('contextmenu', function(e) {
                    e.preventDefault();
                });
            }
        }
        
        // Register interactive handlers from original script and add our navigation
        function initializeNavigation() {
            if (typeof RegisterInteractiveHandlers === 'function') {
                RegisterInteractiveHandlers();
            }
            
            // Initialize zoom button after DOM is ready
            initializeZoomButton();
        }
    </script>
</head>
<body onload="initializeNavigation();">
    <!-- Floating Zoom-Out Button -->
    <button id="zoom-out-btn" class="zoom-out-button" title="Reset Zoom" aria-label="Reset browser zoom to 100%">
        <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <!-- Magnifying glass circle -->
            <circle cx="11" cy="11" r="8" fill="none" stroke="currentColor" stroke-width="2"/>
            <!-- Magnifying glass handle -->
            <path d="m21 21-4.35-4.35" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            <!-- Minus sign inside the magnifying glass -->
            <line x1="8" y1="11" x2="14" y2="11" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
        </svg>
    </button>
    
    <div class="container">
"""
    
    # Process each publication file
    for index, file_path in enumerate(publication_files, 1):
        # Extract page number from filename for the ID
        page_number = os.path.basename(file_path).split('-')[1].split('.')[0]
        
        # Read the HTML file
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Extract the main content div
        soup = BeautifulSoup(content, 'html.parser')
        main_content = soup.select_one('div[style*="position:absolute;overflow:hidden"]')
        
        if main_content:
            merged_html += f'<div class="publication" id="publication-{page_number}">\n'
            merged_html += str(main_content)
            merged_html += '\n</div>\n'
            
            # Add navigation buttons between publications (except after the last one)
            if index < len(publication_files):
                current_page_num = int(page_number)
                total_pages = len(publication_files)
                
                # Previous page button
                prev_disabled = 'disabled' if current_page_num == 1 else ''
                prev_onclick = f"navigateToPreviousPage({current_page_num})" if current_page_num > 1 else ""
                
                # Next page button
                next_disabled = 'disabled' if current_page_num == total_pages else ''
                next_onclick = f"navigateToNextPage({current_page_num}, {total_pages})" if current_page_num < total_pages else ""
                
                # Go to page input
                input_id = f"goto-input-{current_page_num}"
                goto_onclick = f"goToSpecificPage('{input_id}', {total_pages})"
                
                merged_html += f'''<div class="separator">
                    <button class="nav-button" {prev_disabled} onclick="{prev_onclick}">Previous Page</button>
                    <div class="goto-container">
                        <span>Go to page:</span>
                        <input type="number" class="goto-input" id="{input_id}" min="1" max="{total_pages}" placeholder="1-{total_pages}">
                        <button class="nav-button" onclick="{goto_onclick}">Go</button>
                    </div>
                    <button class="nav-button" {next_disabled} onclick="{next_onclick}">Next Page</button>
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
    
    # Find all publication files
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
