#!/usr/bin/env python3
"""
Script to optimize base64 encoded content in HTML files.
Specialized for JPG/PNG images, SVG, and audio files.

This enhanced version:
1. Optimizes JPG/PNG images by reducing quality and converting to WebP when beneficial
2. Handles SVG files appropriately with text-based optimization
3. Uses a more efficient Base85 encoding instead of Base64 when possible
4. Provides more aggressive optimization options
"""

import os
import re
import sys
import base64
import io
import gzip
from pathlib import Path
import argparse
import tempfile
import subprocess
import binascii
from concurrent.futures import ThreadPoolExecutor
import mimetypes

# Try to import optional dependencies
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False
    print("Warning: Pillow library not found. Image optimization will be limited.")
    print("Install with: pip install Pillow")

# JavaScript for client-side decoding and handling
DECODER_JS = """
<script>
// Base85 decoder
const base85Chars = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz!#$%&()*+-;<=>?@^_`{|}~";
function decodeBase85(encoded) {
    let result = new Uint8Array(Math.floor(encoded.length * 4 / 5));
    let resultIndex = 0;
    
    for (let i = 0; i < encoded.length; i += 5) {
        let chunk = encoded.slice(i, Math.min(i + 5, encoded.length));
        if (chunk.length < 5) {
            chunk = chunk.padEnd(5, 'u'); // 'u' is the padding character (value 84)
        }
        
        let value = 0;
        for (let j = 0; j < chunk.length; j++) {
            let charIndex = base85Chars.indexOf(chunk[j]);
            if (charIndex === -1) continue; // Skip invalid characters
            value = value * 85 + charIndex;
        }
        
        // Extract bytes from the value
        for (let j = 3; j >= 0; j--) {
            if (resultIndex < result.length) {
                result[resultIndex++] = (value >> (j * 8)) & 0xFF;
            }
        }
    }
    
    return result.slice(0, resultIndex);
}

// Convert array buffer to base64
function arrayBufferToBase64(buffer) {
    let binary = '';
    const bytes = new Uint8Array(buffer);
    const len = bytes.byteLength;
    for (let i = 0; i < len; i++) {
        binary += String.fromCharCode(bytes[i]);
    }
    return btoa(binary);
}

// Decompress gzipped data
function decompressGzip(compressedData) {
    try {
        // Use pako library for decompression if available
        if (typeof pako !== 'undefined') {
            // Convert base64 to array buffer
            const binaryString = atob(compressedData);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            
            // Decompress
            const decompressed = pako.inflate(bytes);
            return arrayBufferToBase64(decompressed);
        } else {
            console.error('Pako library not available for decompression');
            return compressedData;
        }
    } catch (err) {
        console.error('Decompression error:', err);
        return compressedData;
    }
}

// Process all optimized content when the page loads
document.addEventListener('DOMContentLoaded', function() {
    // Process all elements with data-optimized attributes
    const elements = document.querySelectorAll('[data-optimized-src]');
    
    elements.forEach(function(element) {
        const encodedData = element.getAttribute('data-optimized-src');
        const encoding = element.getAttribute('data-encoding') || 'base64';
        const compression = element.getAttribute('data-compression') || 'none';
        const mimeType = element.getAttribute('data-mime-type');
        
        if (encodedData && mimeType) {
            try {
                // Decode the data based on encoding type
                let decodedData;
                if (encoding === 'base85') {
                    decodedData = decodeBase85(encodedData);
                    decodedData = arrayBufferToBase64(decodedData);
                } else {
                    // Already base64
                    decodedData = encodedData;
                }
                
                // Decompress if needed
                if (compression === 'gzip') {
                    decodedData = decompressGzip(decodedData);
                }
                
                // Create data URI
                const dataUri = 'data:' + mimeType + ';base64,' + decodedData;
                
                // Set the appropriate attribute based on element type
                if (element.tagName === 'IMG') {
                    element.src = dataUri;
                } else if (element.tagName === 'SOURCE') {
                    element.srcset = dataUri;
                } else if (element.tagName === 'AUDIO') {
                    element.src = dataUri;
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
<!-- Include pako library for gzip decompression -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/pako/2.1.0/pako.min.js"></script>
"""

def encode_base85(data):
    """Encode binary data using Base85 encoding"""
    try:
        # Use Python's base64 module for a85 encoding
        encoded = base64.a85encode(data)
        # Convert to string and remove padding
        result = encoded.decode('ascii').replace('<~', '').replace('~>', '')
        return result
    except Exception as e:
        print(f"Base85 encoding error: {e}")
        # Fall back to base64 if there's an error
        return base64.b64encode(data).decode('ascii')

def is_valid_image(data, mime_type):
    """Check if data is a valid image that Pillow can process"""
    if not PILLOW_AVAILABLE:
        return False
    
    # Skip SVG files - Pillow doesn't support them
    if mime_type == 'image/svg+xml':
        return False
    
    try:
        # Try to open the image to verify it's valid
        img = Image.open(io.BytesIO(data))
        img.verify()  # Verify it's a valid image
        return True
    except Exception:
        return False

def optimize_image(image_data, mime_type, quality=80, convert_to_webp=True, max_dimension=None):
    """
    Optimize an image by reducing quality and optionally converting to WebP
    
    Args:
        image_data: Binary image data
        mime_type: Original MIME type
        quality: JPEG/WebP quality (0-100)
        convert_to_webp: Whether to convert to WebP if beneficial
        max_dimension: Maximum width/height to resize to (preserving aspect ratio)
        
    Returns:
        tuple: (optimized_data, new_mime_type)
    """
    if not PILLOW_AVAILABLE:
        return image_data, mime_type
    
    # Skip SVG files - handle them separately
    if mime_type == 'image/svg+xml':
        return image_data, mime_type
    
    # Check if this is a valid image before processing
    if not is_valid_image(image_data, mime_type):
        print(f"Warning: Invalid or unsupported image format for {mime_type}")
        return image_data, mime_type
    
    try:
        # Open the image
        img = Image.open(io.BytesIO(image_data))
        
        # Resize if needed
        if max_dimension and (img.width > max_dimension or img.height > max_dimension):
            if img.width > img.height:
                new_width = max_dimension
                new_height = int(img.height * (max_dimension / img.width))
            else:
                new_height = max_dimension
                new_width = int(img.width * (max_dimension / img.height))
            img = img.resize((new_width, new_height), Image.LANCZOS)
        
        # Try WebP conversion if requested
        if convert_to_webp:
            webp_output = io.BytesIO()
            if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
                img.save(webp_output, format="WEBP", quality=quality, lossless=False)
            else:
                img.save(webp_output, format="WEBP", quality=quality)
            webp_data = webp_output.getvalue()
            
            # Only use WebP if it's smaller
            if len(webp_data) < len(image_data):
                return webp_data, "image/webp"
        
        # If not converting to WebP or WebP wasn't smaller, optimize the original format
        output = io.BytesIO()
        
        if mime_type == "image/jpeg":
            img.save(output, format="JPEG", quality=quality, optimize=True)
        elif mime_type == "image/png":
            img.save(output, format="PNG", optimize=True)
        else:
            # For other formats, just save in original format
            img.save(output, format=img.format if img.format else "PNG")
        
        optimized_data = output.getvalue()
        
        # Only return optimized data if it's actually smaller
        if len(optimized_data) < len(image_data):
            return optimized_data, mime_type
    
    except Exception as e:
        print(f"Image optimization error: {e}")
    
    # Return original if optimization failed or didn't reduce size
    return image_data, mime_type

def optimize_svg(svg_data):
    """
    Optimize SVG content by removing whitespace and unnecessary attributes
    
    Args:
        svg_data: Binary SVG data
        
    Returns:
        bytes: Optimized SVG data
    """
    try:
        # Decode SVG data
        svg_text = svg_data.decode('utf-8')
        
        # Basic SVG minification
        # Remove comments
        svg_text = re.sub(r'<!--.*?-->', '', svg_text, flags=re.DOTALL)
        
        # Remove whitespace between tags
        svg_text = re.sub(r'>\s+<', '><', svg_text)
        
        # Remove leading/trailing whitespace in lines
        svg_text = re.sub(r'^\s+|\s+$', '', svg_text, flags=re.MULTILINE)
        
        # Try to compress with gzip
        compressed_data = gzip.compress(svg_text.encode('utf-8'))
        
        # Only use compressed data if it's smaller
        if len(compressed_data) < len(svg_data):
            return compressed_data, 'gzip'
        
        # If gzip compression didn't help, return minified SVG
        return svg_text.encode('utf-8'), 'none'
    
    except Exception as e:
        print(f"SVG optimization error: {e}")
        return svg_data, 'none'

def optimize_audio(audio_data, mime_type, bitrate=128):
    """
    Optimize audio data by reducing bitrate
    
    Args:
        audio_data: Binary audio data
        mime_type: MIME type
        bitrate: Target bitrate in kbps
        
    Returns:
        tuple: (optimized_data, mime_type)
    """
    # Check if ffmpeg is available
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    except (subprocess.SubprocessError, FileNotFoundError):
        print("FFmpeg not found. Audio optimization skipped.")
        return audio_data, mime_type
    
    try:
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{mime_type.split('/')[-1]}") as input_file, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as output_file:
            
            # Write audio data to input file
            input_file.write(audio_data)
            input_file.flush()
            
            # Close files to avoid issues on Windows
            input_path = input_file.name
            output_path = output_file.name
        
        # Run ffmpeg to optimize
        cmd = [
            "ffmpeg", "-y", "-i", input_path, 
            "-b:a", f"{bitrate}k", 
            "-map", "0:a", 
            output_path
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        
        if result.returncode == 0:
            # Read optimized data
            with open(output_path, "rb") as f:
                optimized_data = f.read()
            
            # Only use optimized data if it's smaller
            if len(optimized_data) < len(audio_data):
                return optimized_data, "audio/mpeg"
    
    except Exception as e:
        print(f"Audio optimization error: {e}")
    
    finally:
        # Clean up temporary files
        try:
            os.unlink(input_path)
            os.unlink(output_path)
        except:
            pass
    
    # Return original if optimization failed or didn't reduce size
    return audio_data, mime_type

def is_valid_base64(s):
    """Check if a string is valid base64"""
    try:
        # Try to decode the base64 string
        decoded = base64.b64decode(s)
        return True
    except Exception:
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
        
        # Optimize based on content type
        compression = 'none'
        
        if mime_type == 'image/svg+xml':
            # Special handling for SVG
            optimized_data, compression_used = optimize_svg(binary_data)
            new_mime_type = mime_type
            compression = compression_used
        elif mime_type.startswith('image/'):
            # Optimize bitmap image
            optimized_data, new_mime_type = optimize_image(
                binary_data, 
                mime_type,
                quality=options.get('image_quality', 80),
                convert_to_webp=options.get('use_webp', True),
                max_dimension=options.get('max_dimension', None)
            )
        elif mime_type.startswith('audio/'):
            # Optimize audio
            optimized_data, new_mime_type = optimize_audio(
                binary_data,
                mime_type,
                bitrate=options.get('audio_bitrate', 128)
            )
        else:
            # For other types, just keep original
            optimized_data = binary_data
            new_mime_type = mime_type
        
        # Determine if we should use base85 encoding
        use_base85 = options.get('use_base85', True)
        
        # Encode the optimized data
        if use_base85:
            encoded_data = encode_base85(optimized_data)
            encoding = 'base85'
        else:
            encoded_data = base64.b64encode(optimized_data).decode('ascii')
            encoding = 'base64'
        
        # Calculate compression ratio
        original_size = len(base64_data)
        new_size = len(encoded_data)
        compression_ratio = (original_size - new_size) / original_size
        
        # Only use optimized version if it provides significant benefit
        min_ratio = options.get('min_compression_ratio', 0.05)  # 5% minimum improvement
        
        if compression_ratio < min_ratio:
            return data_uri
        
        # For img, audio, and source tags, replace with data-optimized attributes
        if tag_name in ['img', 'source', 'audio']:
            return f'data-optimized-src="{encoded_data}" data-mime-type="{new_mime_type}" data-encoding="{encoding}" data-compression="{compression}"'
        
        # For CSS background images or other contexts
        return f'data-optimized-src="{encoded_data}" data-mime-type="{new_mime_type}" data-encoding="{encoding}" data-compression="{compression}"'
        
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
        
        # Process audio tags with src attributes
        audio_pattern = r'<audio[^>]+src=["\'](data:[^;]+;base64,[^"\']+)["\'][^>]*>'
        html_content = re.sub(audio_pattern, lambda m: re.sub(r'src=["\'](data:[^;]+;base64,[^"\']+)["\']', 
                                                           lambda n: process_data_uri(n, 'audio', options), m.group(0)), html_content)
        
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
    
    # Process audio tags with src attributes
    audio_pattern = r'<audio[^>]+src=["\'](data:[^;]+;base64,[^"\']+)["\'][^>]*>'
    chunk = re.sub(audio_pattern, lambda m: re.sub(r'src=["\'](data:[^;]+;base64,[^"\']+)["\']', 
                                                 lambda n: process_data_uri(n, 'audio', options), m.group(0)), chunk)
    
    # Process CSS background images
    css_pattern = r'background-image:\s*url\(["\']?(data:[^;]+;base64,[^"\')\s]+)["\']?\)'
    chunk = re.sub(css_pattern, lambda m: re.sub(r'url\(["\']?(data:[^;]+;base64,[^"\')\s]+)["\']?\)', 
                                                lambda n: f'url({process_data_uri(n, None, options)})', m.group(0)), chunk)
    
    return chunk

def main():
    parser = argparse.ArgumentParser(description='Optimize base64 encoded content in HTML files')
    parser.add_argument('input', help='Input HTML file path')
    parser.add_argument('-o', '--output', help='Output HTML file path (default: input-optimized.html)')
    parser.add_argument('-q', '--quality', type=int, default=80, choices=range(1, 101),
                        help='Image quality (1-100, default: 80)')
    parser.add_argument('-b', '--bitrate', type=int, default=128,
                        help='Audio bitrate in kbps (default: 128)')
    parser.add_argument('-w', '--webp', action='store_true',
                        help='Convert images to WebP format when beneficial')
    parser.add_argument('-d', '--max-dimension', type=int,
                        help='Maximum image dimension (will resize larger images)')
    parser.add_argument('-m', '--min-size', type=int, default=1024,
                        help='Minimum size in bytes to consider for optimization (default: 1024)')
    parser.add_argument('-r', '--min-ratio', type=float, default=0.05,
                        help='Minimum compression ratio to apply changes (default: 0.05)')
    parser.add_argument('-85', '--base85', action='store_true',
                        help='Use Base85 encoding instead of Base64 (more efficient)')
    parser.add_argument('-c', '--chunks', action='store_true',
                        help='Process file in chunks (for very large files)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print verbose output for debugging')
    
    args = parser.parse_args()
    
    input_path = args.input
    
    # Default output path if not specified
    if not args.output:
        input_file = Path(input_path)
        output_path = str(input_file.with_stem(input_file.stem + '-optimised'))
    else:
        output_path = args.output
    
    # Set optimization options
    options = {
        'image_quality': args.quality,
        'audio_bitrate': args.bitrate,
        'use_webp': args.webp,
        'max_dimension': args.max_dimension,
        'min_size': args.min_size,
        'min_compression_ratio': args.min_ratio,
        'use_base85': args.base85,
        'verbose': args.verbose
    }
    
    print(f"Processing {input_path}")
    print(f"Output will be saved to {output_path}")
    print(f"Optimization options: {options}")
    
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