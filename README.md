# HTML Publication Optimisation Workflow

This repository contains a set of Python scripts designed to prepare and optimise HTML files exported from Adobe InDesign for web publication. The workflow processes raw HTML exports, merges them into a single file, and applies various optimisation techniques to reduce file size while maintaining quality.

## Use Case

This workflow is designed for preparing Adobe InDesign HTML exports for web publication. The process significantly reduces file size while maintaining content quality, making it suitable for sharing interactive learning content for consumpion from the general public. By following this optimisation workflow, the designer can convert multiple large HTML exports into a single, optimised file suitable for web hosting and distribution.

## Prerequisites

- Python 3.6+
- Required Python packages (install via `pip install -r requirements.txt`):
  - BeautifulSoup4
  - Pillow (PIL)
- External tool:
  - [Monolith](https://github.com/Y2Z/monolith) - A command-line tool for saving web pages as a single HTML file

## Workflow Overview

The optimisation process consists of four sequential steps:

1. **Merge multiple HTML files** into a single scrollable document
2. **Embed all resources** (CSS, images, etc.) into a single self-contained HTML file
3. **Optimise base64-encoded content** to reduce file size
4. **Convert PNG images to JPEG** for further size reduction

## Step-by-Step Process

### 1. Merge Publications

```bash
python merge_all_publications.py
```

This script:
- Finds all HTML files in the current directory matching the pattern `publication-[number].html`
- Sorts them by page number
- Merges them into a single scrollable HTML page with navigation between sections
- Outputs the merged file as `merged-publication.html`

### 2. Embed Resources with Monolith

```bash
monolith merged-publication.html -o merged-embedded.html --no-frames
```

This command:
- Uses the Monolith tool to process the merged HTML file
- Embeds all external resources (CSS, JavaScript, images) directly into the HTML
- Creates a self-contained HTML file with no external dependencies
- The `--no-frames` option prevents the creation of frames

### 3. Audio optimise Base64 Content

```bash
python optimise_base64.py merged-embedded.html -q 25
```

This script:
- Processes the embedded HTML file to optimise base64-encoded content
- Optimises audio files
- Uses more efficient encoding techniques
- Outputs the optimised file as `merged-embedded-audio_optimised.html`

### 4. Convert PNGs to JPEGs

```bash
python png_to_jpeg_optimiser.py merged-embedded-audio_optimised.html -j 25 -e iVBORw0KGgoAAAANSUhEUgAABG iVBORw0KGgoAAAANSUhEUgAACO
```

This script:
- Further optimises the HTML by converting PNG images to JPEG format
- Sets JPEG quality to 25% (adjustable via the `-j` parameter)
- Excludes specific PNG images from conversion using the base64 prefix (`-e` parameter)
- The example excludes PNGs starting with iVBORw0KGgoAAAANSUhEUgAABG and iVBORw0KGgoAAAANSUhEUgAACO. Useful to retain images with transparencies.
- Outputs the final optimised file as `merged-embedded-optimised-jpeg_converted.html`

## Script Details

### merge_all_publications.py

Merges multiple HTML files exported from Adobe InDesign into a single scrollable document with navigation between pages.

**Features:**
- Automatically finds and sorts publication files by page number
- Creates a clean, navigable interface between pages
- Preserves original content and styling
- Adds JavaScript for smooth scrolling between sections

### optimise_base64.py

Optimises base64-encoded content in HTML files, focusing on reducing the size of embedded media.

**Features:**
- Reduces image quality while maintaining acceptable visual appearance
- Converts images to WebP format when beneficial
- Optimises SVG files with text-based minification
- Can use Base85 encoding instead of Base64 for better compression
- Adds client-side JavaScript for handling optimised content
- Optimises audio files by reducing bitrate (requires FFmpeg)

**Options:**
- `-b/--bitrate`: Audio bitrate in kbps (default: 128) - requires FFmpeg to be installed
- `-d/--max-dimension`: Maximum image dimension for resizing
- `-m/--min-size`: Minimum size to consider for optimisation
- `-r/--min-ratio`: Minimum compression ratio to apply changes
- `-85/--base85`: Use Base85 encoding
- `-c/--chunks`: Process file in chunks (for very large files)

**Note on Audio Optimisation:**
The audio bitrate optimisation has several requirements to work properly:
1. FFmpeg must be installed on your system and available in the PATH
2. The HTML must contain audio elements with base64-encoded data URIs
3. The optimised audio must be at least 5% smaller than the original (configurable with `-r` option)
4. The audio content must have a MIME type that starts with 'audio/'

### png_to_jpeg_optimiser.py

Specifically focuses on converting PNG images to JPEG format for further size reduction.

**Features:**
- Identifies PNG images in base64-encoded data URIs
- Converts PNGs to JPEGs with configurable quality
- Handles transparency by replacing with white background
- Allows excluding specific PNGs from conversion
- Adds client-side JavaScript for handling optimised content

**Options:**
- `-j/--jpeg-quality`: JPEG quality for PNG conversion (1-100, default: 75)
- `-m/--min-size`: Minimum size to consider for optimisation
- `-r/--min-ratio`: Minimum compression ratio to apply changes
- `-c/--chunks`: Process file in chunks (for very large files)
- `-e/--exclude`: List of base64 prefixes to exclude from conversion
