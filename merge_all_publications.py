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
        .current-page-display {
            margin-left: 20px;
            font-size: 16px;
            font-weight: bold;
            color: #333;
            display: flex;
            align-items: center;
        }
        .current-page-display {
            margin-left: 20px;
            font-size: 16px;
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
            background-color: #28a745;
            font-size: 12px;
            padding: 6px 12px;
        }
        .print-button:hover {
            background-color: #218838;
        }
        
        /* Print media queries */
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
                alert('Please enter a valid page number between 1 and ' + totalPages);
                input.value = '';
                return;
            }
            
            scrollToPage(pageNumber);
            input.value = '';
        }
        
        function printCurrentPage() {
            // Get the currently visible page
            const currentPageNumber = getCurrentVisiblePage();
            printSpecificPage(currentPageNumber);
        }

        function printSpecificPage(pageNumber) {
            console.log('Printing page:', pageNumber);
            
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
                alert('Could not find page to print. Available pages: ' +
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
        }
    </script>
</head>
<body onload="initializeNavigation();">
    <div class="container">
"""
    
    # Process each publication file
    for index, file_path in enumerate(publication_files, 1):
        # Extract page number from filename for the ID (0-based from filename)
        file_page_number = os.path.basename(file_path).split('-')[1].split('.')[0]
        
        # Use 1-based page numbering for user display
        display_page_number = index
        
        # Read the HTML file
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        
        # Extract the main content div
        soup = BeautifulSoup(content, 'html.parser')
        main_content = soup.select_one('div[style*="position:absolute;overflow:hidden"]')
        
        if main_content:
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
                
                merged_html += f'''<div class="separator">
                    <button class="nav-button" {prev_disabled} onclick="{prev_onclick}">Previous Page</button>
                    <div class="goto-container">
                        <span>Go to page:</span>
                        <input type="number" class="goto-input" id="{input_id}" min="1" max="{total_pages}" placeholder="1-{total_pages}">
                        <button class="nav-button" onclick="{goto_onclick}">Go</button>
                    </div>
                    <div class="print-container">
                        <button class="nav-button print-button" onclick="printCurrentPage()">Print Current Page</button>
                    </div>
                    <div class="current-page-display">
                        Page {display_page_number} of {total_pages}
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
