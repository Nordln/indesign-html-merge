# Indesign HTML5 Merging and Optimisation Workflow

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
3. **Optimise base64-encoded content** (images and audio) to reduce file size
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

### 3. Optimise Base64 Content (Images and Audio)

```bash
python optimise_base64_image_audio.py merged-embedded.html -i 75 -a 32 -w -v
```

This script:
- Processes the embedded HTML file to optimise all base64-encoded content
- Optimises images with 75% quality and converts to WebP when beneficial
- Optimises audio files with 32kbps bitrate
- Uses more efficient encoding techniques
- Provides verbose output with detailed statistics
- Outputs the optimised file as `merged-embedded-optimized.html`

> **Note:** The older separate scripts `optimise_base64.py` (audio only) and `optimise_base64_former.py` (images only) are still available but the combined script is recommended.

### 4. Convert PNGs to JPEGs

```bash
python png_to_jpeg_optimiser.py merged-embedded-optimized.html -j 25 -e iVBORw0KGgoAAAANSUhEUgAABG iVBORw0KGgoAAAANSUhEUgAACO iVBORw0KGgoAAAANSUhEUgAAAC iVBORw0KGgoAAAANSUhEUgAAAY
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

### optimise_base64_image_audio.py

Optimises all base64-encoded content in HTML files, combining image and audio optimization in a single script.

**Features:**
- Optimizes JPG/PNG images by reducing quality and converting to WebP when beneficial
- Handles SVG files with text-based optimization
- Optimizes audio files by reducing bitrate while maintaining compatibility
- Uses Base85 encoding for images (more efficient than Base64)
- Maintains Base64 encoding for audio files to ensure compatibility
- Adds client-side JavaScript for handling optimised content
- Provides detailed statistics for both image and audio optimization

**Options:**
- `-i/--image-quality`: Image quality (1-100, default: 80)
- `-a/--audio-bitrate`: Audio bitrate in kbps (default: 128) - requires FFmpeg
- `-w/--webp`: Convert images to WebP format when beneficial
- `-d/--max-dimension`: Maximum image dimension for resizing
- `-m/--min-size`: Minimum size to consider for optimisation
- `-r/--min-ratio`: Minimum compression ratio to apply changes
- `-85/--base85`: Use Base85 encoding for images
- `-c/--chunks`: Process file in chunks (for very large files)
- `-v/--verbose`: Print detailed output for debugging

**Example Use Case:**
```bash
python optimise_base64_image_audio.py merged-embedded.html -i 75 -a 32 -w -v
```
This command will:
- Process `merged-embedded.html` and create `merged-embedded-optimized.html`
- Optimize images with 75% quality and convert to WebP when beneficial
- Optimize audio files with 32kbps bitrate
- Print verbose output with detailed statistics

**Requirements:**
1. For image optimization: Pillow library must be installed
2. For audio optimization: FFmpeg must be installed and available in the PATH
3. The HTML must contain elements with base64-encoded data URIs
4. The optimized content must be at least 5% smaller than the original (configurable with `-r` option)

### optimise_base64.py (Legacy - Audio Only)

Optimises base64-encoded audio content in HTML files.

**Features:**
- Optimises audio files by reducing bitrate (requires FFmpeg)
- Adds client-side JavaScript for handling optimised content

**Options:**
- `-b/--bitrate`: Audio bitrate in kbps (default: 128) - requires FFmpeg to be installed
- `-m/--min-size`: Minimum size to consider for optimisation
- `-c/--chunks`: Process file in chunks (for very large files)
- `-v/--verbose`: Print verbose output for debugging

**Note on Audio Optimisation:**
The audio bitrate optimisation has several requirements to work properly:
1. FFmpeg must be installed on your system and available in the PATH
2. The HTML must contain audio elements with base64-encoded data URIs
3. The optimised audio must be at least 5% smaller than the original
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
