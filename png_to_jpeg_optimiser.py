#!/usr/bin/env python

"""png_to_jpeg_optimiser.py: Script to optimize base64 encoded content in HTML files with PNG to JPEG conversion."""

__author__      = "Ed Watson"
__copyright__   = "Unlicense license"

import os
import re
import sys
import base64
import io
from pathlib import Path
import argparse
import mimetypes

# Try to import optional dependencies
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("Error: Pillow library not found. This script requires Pillow for image conversion.")
    print("Install with: pip install Pillow")
    sys.exit(1)

# JavaScript for client-side handling
DECODER_JS = """
<script>
// Process all optimized content when the page loads
document.addEventListener('DOMContentLoaded', function() {
    // Process all elements with data-optimized attributes
    const elements = document.querySelectorAll('[data-optimized-src]');
    
    elements.forEach(function(element) {
        const encodedData = element.getAttribute('data-optimized-src');
        const mimeType = element.getAttribute('data-mime-type');
        
        if (encodedData && mimeType) {
            try {
                // Create data URI
                const dataUri = 'data:' + mimeType + ';base64,' + encodedData;
                
                // Set the appropriate attribute based on element type
                if (element.tagName === 'IMG') {
                    element.src = dataUri;
                } else if (element.tagName === 'SOURCE') {
                    element.srcset = dataUri;
                } else {
                    // For other elements with background images in style
                    element.style.backgroundImage = 'url(' + dataUri + ')';
                }
            } catch (err) {
                console.error('Error processing optimized content:', err);
            }
        }
    });
});
</script>
"""

def convert_png_to_jpeg(image_data, quality=75):
    """
    Convert PNG image to JPEG with specified quality
    
    Args:
        image_data: Binary PNG image data
        quality: JPEG quality (1-100)
        
    Returns:
        tuple: (jpeg_data, success)
    """
    try:
        # Open the image
        img = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if needed (JPEG doesn't support alpha channel)
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            # Create a white background
            background = Image.new('RGB', img.size, (255, 255, 255))
            # Paste the image on the background
            if img.mode == 'RGBA':
                background.paste(img, mask=img.split()[3])  # 3 is the alpha channel
            else:
                background.paste(img, mask=img.convert('RGBA').split()[3])
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        # Save as JPEG
        output = io.BytesIO()
        img.save(output, format="JPEG", quality=quality, optimize=True)
        jpeg_data = output.getvalue()
        
        return jpeg_data, True
    
    except Exception as e:
        print(f"PNG to JPEG conversion error: {e}")
        return image_data, False

def is_valid_base64(s):
    """Check if a string is valid base64"""
    try:
        # Try to decode the base64 string
        decoded = base64.b64decode(s)
        return True
    except Exception:
        return False

def should_exclude(base64_data, excluded_prefixes):
    """
    Check if the base64 data starts with any of the excluded prefixes
    
    Args:
        base64_data: Base64 encoded string
        excluded_prefixes: List of prefixes to exclude
        
    Returns:
        bool: True if should be excluded, False otherwise
    """
    if not excluded_prefixes:
        return False
    
    # Get the first 26 characters (or less if the string is shorter)
    prefix = base64_data[:26]
    
    # Check if the prefix matches any in the excluded list
    for excluded_prefix in excluded_prefixes:
        if prefix.startswith(excluded_prefix):
            return True
    
    return False

def process_data_uri(match, tag_name=None, options=None):
    """Process a data URI match and return optimized version"""
    if options is None:
        options = {}
    
    data_uri = match.group(0)
    
    # Extract mime type and base64 data
    pattern = r'data:([^;]+);base64,([^"\'\s]+)'
    uri_match = re.search(pattern, data_uri)
    
    if not uri_match:
        return data_uri  # Return original if not matching expected format
    
    mime_type = uri_match.group(1)
    base64_data = uri_match.group(2)
    
    # Validate base64 data
    if not is_valid_base64(base64_data):
        print(f"Warning: Invalid base64 data found for {mime_type}")
        return data_uri
    
    try:
        # Decode base64
        binary_data = base64.b64decode(base64_data)
        
        # Skip if data is too small to benefit from optimization
        if len(binary_data) < options.get('min_size', 1024):
            return data_uri
        
        # Process based on content type
        if mime_type == 'image/png' and options.get('png_to_jpeg', False):
            # Check if this PNG should be excluded from conversion
            excluded_prefixes = options.get('excluded_prefixes', [])
            if should_exclude(base64_data, excluded_prefixes):
                if options.get('verbose', False):
                    print(f"Skipping PNG conversion (matched excluded prefix): {base64_data[:26]}...")
                return data_uri
            
            # Convert PNG to JPEG
            jpeg_quality = options.get('jpeg_quality', 75)
            optimized_data, success = convert_png_to_jpeg(binary_data, jpeg_quality)
            
            if success:
                new_mime_type = 'image/jpeg'
                if options.get('verbose', False):
                    print(f"Converted PNG to JPEG (quality: {jpeg_quality})")
                    
                    # Calculate compression ratio
                    compression_ratio = (len(binary_data) - len(optimized_data)) / len(binary_data)
                    print(f"  Original size: {len(binary_data):,} bytes")
                    print(f"  New size: {len(optimized_data):,} bytes")
                    print(f"  Compression ratio: {compression_ratio:.2%}")
            else:
                # Conversion failed, keep original
                optimized_data = binary_data
                new_mime_type = mime_type
        else:
            # Keep original for other types
            optimized_data = binary_data
            new_mime_type = mime_type
        
        # Encode the optimized data
        encoded_data = base64.b64encode(optimized_data).decode('ascii')
        
        # Calculate compression ratio
        original_size = len(base64_data)
        new_size = len(encoded_data)
        compression_ratio = (original_size - new_size) / original_size
        
        # Only use optimized version if it provides significant benefit
        min_ratio = options.get('min_compression_ratio', 0.05)  # 5% minimum improvement
        
        if compression_ratio < min_ratio and mime_type != 'image/png':
            return data_uri
        
        # For img and source tags, replace with data-optimized attributes
        if tag_name in ['img', 'source']:
            return f'data-optimized-src="{encoded_data}" data-mime-type="{new_mime_type}"'
        
        # For CSS background images or other contexts
        return f'data-optimized-src="{encoded_data}" data-mime-type="{new_mime_type}"'
        
    except Exception as e:
        print(f"Error processing data URI: {e}")
        return data_uri  # Return original on error

def optimize_html_file(input_path, output_path, options=None):
    """Optimize base64 content in an HTML file"""
    if options is None:
        options = {}
    
    try:
        # Read the HTML file
        with open(input_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        
        # Track original size
        original_size = len(html_content.encode('utf-8'))
        
        # Process img tags with src attributes
        img_pattern = r'<img[^>]+src=["\'](data:[^;]+;base64,[^"\']+)["\'][^>]*>'
        html_content = re.sub(img_pattern, lambda m: re.sub(r'src=["\'](data:[^;]+;base64,[^"\']+)["\']', 
                                                          lambda n: process_data_uri(n, 'img', options), m.group(0)), html_content)
        
        # Process source tags with srcset attributes
        source_pattern = r'<source[^>]+srcset=["\'](data:[^;]+;base64,[^"\']+)["\'][^>]*>'
        html_content = re.sub(source_pattern, lambda m: re.sub(r'srcset=["\'](data:[^;]+;base64,[^"\']+)["\']', 
                                                             lambda n: process_data_uri(n, 'source', options), m.group(0)), html_content)
        
        # Process CSS background images
        css_pattern = r'background-image:\s*url\(["\']?(data:[^;]+;base64,[^"\')\s]+)["\']?\)'
        html_content = re.sub(css_pattern, lambda m: re.sub(r'url\(["\']?(data:[^;]+;base64,[^"\')\s]+)["\']?\)', 
                                                          lambda n: f'url({process_data_uri(n, None, options)})', m.group(0)), html_content)
        
        # Add decoder JavaScript before closing body tag
        if '</body>' in html_content:
            html_content = html_content.replace('</body>', f'{DECODER_JS}</body>')
        else:
            html_content += DECODER_JS
        
        # Write the processed HTML to the output file
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(html_content)
        
        # Calculate compression statistics
        compressed_size = os.path.getsize(output_path)
        savings = original_size - compressed_size
        savings_percent = (savings / original_size) * 100 if original_size > 0 else 0
        
        print(f"Original size: {original_size:,} bytes")
        print(f"Optimized size: {compressed_size:,} bytes")
        print(f"Savings: {savings:,} bytes ({savings_percent:.2f}%)")
        
        return True
    
    except Exception as e:
        print(f"Error optimizing HTML file: {e}")
        return False

def process_file_in_chunks(input_path, output_path, chunk_size=10*1024*1024, options=None):
    """Process a large HTML file in chunks to avoid memory issues"""
    if options is None:
        options = {}
    
    try:
        # Create a temporary output file
        temp_output = output_path + '.temp'
        
        with open(input_path, 'r', encoding='utf-8') as infile, open(temp_output, 'w', encoding='utf-8') as outfile:
            # Add decoder JavaScript at the beginning
            outfile.write('<!DOCTYPE html>\n<html>\n<head>\n')
            outfile.write(DECODER_JS)
            outfile.write('\n</head>\n<body>\n')
            
            # Process the file in chunks
            chunk = infile.read(chunk_size)
            while chunk:
                # Process data URIs in this chunk
                processed_chunk = process_chunk(chunk, options)
                outfile.write(processed_chunk)
                chunk = infile.read(chunk_size)
            
            # Close the HTML
            outfile.write('\n</body>\n</html>')
        
        # Rename temp file to output file
        os.replace(temp_output, output_path)
        
        # Calculate compression statistics
        original_size = os.path.getsize(input_path)
        compressed_size = os.path.getsize(output_path)
        savings = original_size - compressed_size
        savings_percent = (savings / original_size) * 100 if original_size > 0 else 0
        
        print(f"Original size: {original_size:,} bytes")
        print(f"Optimized size: {compressed_size:,} bytes")
        print(f"Savings: {savings:,} bytes ({savings_percent:.2f}%)")
        
        return True
    
    except Exception as e:
        print(f"Error processing file in chunks: {e}")
        if os.path.exists(temp_output):
            os.remove(temp_output)
        return False

def process_chunk(chunk, options=None):
    """Process a chunk of HTML content"""
    if options is None:
        options = {}
    
    # Process img tags with src attributes
    img_pattern = r'<img[^>]+src=["\'](data:[^;]+;base64,[^"\']+)["\'][^>]*>'
    chunk = re.sub(img_pattern, lambda m: re.sub(r'src=["\'](data:[^;]+;base64,[^"\']+)["\']', 
                                                lambda n: process_data_uri(n, 'img', options), m.group(0)), chunk)
    
    # Process source tags with srcset attributes
    source_pattern = r'<source[^>]+srcset=["\'](data:[^;]+;base64,[^"\']+)["\'][^>]*>'
    chunk = re.sub(source_pattern, lambda m: re.sub(r'srcset=["\'](data:[^;]+;base64,[^"\']+)["\']', 
                                                   lambda n: process_data_uri(n, 'source', options), m.group(0)), chunk)
    
    # Process CSS background images
    css_pattern = r'background-image:\s*url\(["\']?(data:[^;]+;base64,[^"\')\s]+)["\']?\)'
    chunk = re.sub(css_pattern, lambda m: re.sub(r'url\(["\']?(data:[^;]+;base64,[^"\')\s]+)["\']?\)', 
                                                lambda n: f'url({process_data_uri(n, None, options)})', m.group(0)), chunk)
    
    return chunk

def main():
    parser = argparse.ArgumentParser(description='Optimize base64 encoded content in HTML files with PNG to JPEG conversion')
    parser.add_argument('input', help='Input HTML file path')
    parser.add_argument('-o', '--output', help='Output HTML file path (default: input-jpeg-optimized.html)')
    parser.add_argument('-j', '--jpeg-quality', type=int, default=75, choices=range(1, 101),
                        help='JPEG quality for PNG conversion (1-100, default: 75)')
    parser.add_argument('-m', '--min-size', type=int, default=1024,
                        help='Minimum size in bytes to consider for optimization (default: 1024)')
    parser.add_argument('-r', '--min-ratio', type=float, default=0.05,
                        help='Minimum compression ratio to apply changes (default: 0.05)')
    parser.add_argument('-c', '--chunks', action='store_true',
                        help='Process file in chunks (for very large files)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print verbose output for debugging')
    parser.add_argument('-e', '--exclude', nargs='+', default=[],
                        help='List of base64 prefixes (first 26 chars) to exclude from PNG to JPEG conversion')
    
    args = parser.parse_args()
    
    input_path = args.input
    
    # Default output path if not specified
    if not args.output:
        input_file = Path(input_path)
        output_path = str(input_file.with_stem(input_file.stem + '-jpeg_converted'))
    else:
        output_path = args.output
    
    # Set optimization options
    options = {
        'png_to_jpeg': True,  # Always enable PNG to JPEG conversion
        'jpeg_quality': args.jpeg_quality,
        'min_size': args.min_size,
        'min_compression_ratio': args.min_ratio,
        'verbose': args.verbose,
        'excluded_prefixes': args.exclude
    }
    
    print(f"Processing {input_path}")
    print(f"Output will be saved to {output_path}")
    print(f"PNG to JPEG conversion enabled with quality: {args.jpeg_quality}")
    
    if args.exclude:
        print(f"Excluding PNGs with these prefixes (26 chars): {', '.join(args.exclude)}")
    
    if args.chunks:
        success = process_file_in_chunks(input_path, output_path, options=options)
    else:
        success = optimize_html_file(input_path, output_path, options=options)
    
    if success:
        print("Optimization completed successfully!")
    else:
        print("Optimization failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
