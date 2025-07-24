#!/usr/bin/env python

"""optimise_base64_image_audio.py: Script to optimize base64 encoded content in HTML files. Specialized for JPG/PNG images, SVG, and audio files."""

__author__      = "Ed Watson"
__copyright__   = "Unlicense license"

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

def read_inflate_js():
    """Read the contents of the unzipo.js file"""
    try:
        # Try to find the file in the same directory as this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        js_path = os.path.join(script_dir, 'unzipo.min.js')
        
        # If not found in script directory, try current working directory
        if not os.path.exists(js_path):
            js_path = 'unzipo.min.js'
            
        with open(js_path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        print(f"Warning: Could not read inflate file: {e}")
        print("Decompression functionality may be limited.")
        return "/* inflate could not be loaded */"

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
        // Use unzipo library for decompression if available
        if (typeof unzipo !== 'undefined') {
            // Convert base64 to array buffer
            const binaryString = atob(compressedData);
            const bytes = new Uint8Array(binaryString.length);
            for (let i = 0; i < binaryString.length; i++) {
                bytes[i] = binaryString.charCodeAt(i);
            }
            
            // Decompress
            const decompressed = unzipo.inflate(bytes);
            return arrayBufferToBase64(decompressed);
        } else {
            console.error('unzipo library not available for decompression');
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
<!-- Include unzipo library for gzip decompression -->
<script>
{inflate_js_content}
</script>
"""

# Global counters for audio files
audio_stats = {
    'detected': 0,
    'processed': 0,
    'skipped_small': 0,
    'skipped_no_reduction': 0,
    'skipped_error': 0,
    'details': []
}

# Global counters for image files
image_stats = {
    'detected': 0,
    'processed': 0,
    'skipped_small': 0,
    'skipped_no_reduction': 0,
    'skipped_error': 0,
    'details': []
}

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

def optimize_image(image_data, mime_type, quality=80, convert_to_webp=True, max_dimension=None, verbose=False):
    """
    Optimize an image by reducing quality and optionally converting to WebP
    
    Args:
        image_data: Binary image data
        mime_type: Original MIME type
        quality: JPEG/WebP quality (0-100)
        convert_to_webp: Whether to convert to WebP if beneficial
        max_dimension: Maximum width/height to resize to (preserving aspect ratio)
        verbose: Whether to print verbose output
        
    Returns:
        tuple: (optimized_data, new_mime_type)
    """
    # Add to image stats
    image_stats['detected'] += 1
    image_detail = {
        'mime_type': mime_type,
        'size': len(image_data),
        'status': 'detected'
    }
    
    if not PILLOW_AVAILABLE:
        image_detail['status'] = 'skipped_no_pillow'
        image_detail['reason'] = "Pillow library not available"
        image_stats['details'].append(image_detail)
        image_stats['skipped_error'] += 1
        return image_data, mime_type
    
    # Skip SVG files - handle them separately
    if mime_type == 'image/svg+xml':
        image_detail['status'] = 'skipped_svg'
        image_detail['reason'] = "SVG files are handled separately"
        image_stats['details'].append(image_detail)
        return image_data, mime_type
    
    # Skip if data is too small to benefit from optimization
    if len(image_data) < 1024:  # 1KB
        if verbose:
            print(f"Image file too small to optimize: {len(image_data)} bytes")
        image_detail['status'] = 'skipped_small'
        image_detail['reason'] = f"Too small: {len(image_data)} bytes"
        image_stats['details'].append(image_detail)
        image_stats['skipped_small'] += 1
        return image_data, mime_type
    
    # Check if this is a valid image before processing
    if not is_valid_image(image_data, mime_type):
        if verbose:
            print(f"Warning: Invalid or unsupported image format for {mime_type}")
        image_detail['status'] = 'skipped_invalid'
        image_detail['reason'] = "Invalid or unsupported image format"
        image_stats['details'].append(image_detail)
        image_stats['skipped_error'] += 1
        return image_data, mime_type
    
    try:
        if verbose:
            print(f"Processing image file: {mime_type}, size: {len(image_data)} bytes, quality: {quality}")
        
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
            if verbose:
                print(f"Resized image from {img.width}x{img.height} to {new_width}x{new_height}")
        
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
                original_size = len(image_data)
                new_size = len(webp_data)
                savings = original_size - new_size
                savings_percent = (savings / original_size) * 100 if original_size > 0 else 0
                
                if verbose:
                    print(f"WebP conversion results:")
                    print(f"  Original size: {original_size:,} bytes")
                    print(f"  Optimized size: {new_size:,} bytes")
                    print(f"  Savings: {savings:,} bytes ({savings_percent:.2f}%)")
                
                image_detail['status'] = 'processed_webp'
                image_detail['original_size'] = original_size
                image_detail['optimized_size'] = new_size
                image_detail['savings_percent'] = savings_percent
                image_stats['details'].append(image_detail)
                image_stats['processed'] += 1
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
            original_size = len(image_data)
            new_size = len(optimized_data)
            savings = original_size - new_size
            savings_percent = (savings / original_size) * 100 if original_size > 0 else 0
            
            if verbose:
                print(f"Image optimization results:")
                print(f"  Original size: {original_size:,} bytes")
                print(f"  Optimized size: {new_size:,} bytes")
                print(f"  Savings: {savings:,} bytes ({savings_percent:.2f}%)")
            
            image_detail['status'] = 'processed'
            image_detail['original_size'] = original_size
            image_detail['optimized_size'] = new_size
            image_detail['savings_percent'] = savings_percent
            image_stats['details'].append(image_detail)
            image_stats['processed'] += 1
            return optimized_data, mime_type
        else:
            if verbose:
                print("Optimized image not smaller than original, keeping original")
            image_detail['status'] = 'skipped_no_reduction'
            image_detail['reason'] = "No size reduction achieved"
            image_stats['details'].append(image_detail)
            image_stats['skipped_no_reduction'] += 1
    
    except Exception as e:
        print(f"Image optimization error: {e}")
        image_detail['status'] = 'skipped_error'
        image_detail['reason'] = f"Exception: {str(e)}"
        image_stats['details'].append(image_detail)
        image_stats['skipped_error'] += 1
    
    # Return original if optimization failed or didn't reduce size
    return image_data, mime_type

def optimize_svg(svg_data, verbose=False):
    """
    Optimize SVG content by removing whitespace and unnecessary attributes
    
    Args:
        svg_data: Binary SVG data
        verbose: Whether to print verbose output
        
    Returns:
        tuple: (optimized_data, compression_type)
    """
    # Add to image stats
    image_stats['detected'] += 1
    image_detail = {
        'mime_type': 'image/svg+xml',
        'size': len(svg_data),
        'status': 'detected'
    }
    
    try:
        if verbose:
            print(f"Processing SVG file, size: {len(svg_data)} bytes")
        
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
            original_size = len(svg_data)
            new_size = len(compressed_data)
            savings = original_size - new_size
            savings_percent = (savings / original_size) * 100 if original_size > 0 else 0
            
            if verbose:
                print(f"SVG gzip compression results:")
                print(f"  Original size: {original_size:,} bytes")
                print(f"  Optimized size: {new_size:,} bytes")
                print(f"  Savings: {savings:,} bytes ({savings_percent:.2f}%)")
            
            image_detail['status'] = 'processed_gzip'
            image_detail['original_size'] = original_size
            image_detail['optimized_size'] = new_size
            image_detail['savings_percent'] = savings_percent
            image_stats['details'].append(image_detail)
            image_stats['processed'] += 1
            return compressed_data, 'gzip'
        
        # If gzip compression didn't help, check if minification helped
        minified_data = svg_text.encode('utf-8')
        if len(minified_data) < len(svg_data):
            original_size = len(svg_data)
            new_size = len(minified_data)
            savings = original_size - new_size
            savings_percent = (savings / original_size) * 100 if original_size > 0 else 0
            
            if verbose:
                print(f"SVG minification results:")
                print(f"  Original size: {original_size:,} bytes")
                print(f"  Optimized size: {new_size:,} bytes")
                print(f"  Savings: {savings:,} bytes ({savings_percent:.2f}%)")
            
            image_detail['status'] = 'processed_minified'
            image_detail['original_size'] = original_size
            image_detail['optimized_size'] = new_size
            image_detail['savings_percent'] = savings_percent
            image_stats['details'].append(image_detail)
            image_stats['processed'] += 1
            return minified_data, 'none'
        
        # If neither helped, return original
        if verbose:
            print("SVG optimization did not reduce size, keeping original")
        image_detail['status'] = 'skipped_no_reduction'
        image_detail['reason'] = "No size reduction achieved"
        image_stats['details'].append(image_detail)
        image_stats['skipped_no_reduction'] += 1
        return svg_data, 'none'
    
    except Exception as e:
        print(f"SVG optimization error: {e}")
        image_detail['status'] = 'skipped_error'
        image_detail['reason'] = f"Exception: {str(e)}"
        image_stats['details'].append(image_detail)
        image_stats['skipped_error'] += 1
        return svg_data, 'none'

def optimize_audio(audio_data, mime_type, bitrate=128, verbose=False):
    """
    Optimize audio data by reducing bitrate
    
    Args:
        audio_data: Binary audio data
        mime_type: MIME type
        bitrate: Target bitrate in kbps
        verbose: Whether to print verbose output
        
    Returns:
        tuple: (optimized_data, mime_type)
    """
    # Add to audio stats
    audio_stats['detected'] += 1
    audio_detail = {
        'mime_type': mime_type,
        'size': len(audio_data),
        'status': 'detected'
    }
    
    # Check if ffmpeg is available
    try:
        result = subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        if verbose:
            print(f"FFmpeg version check result: {result.returncode}")
            print(f"FFmpeg stdout: {result.stdout.decode('utf-8', errors='ignore')[:100]}...")
            print(f"FFmpeg stderr: {result.stderr.decode('utf-8', errors='ignore')[:100]}...")
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        print(f"FFmpeg not found or error checking version: {e}")
        audio_detail['status'] = 'skipped_no_ffmpeg'
        audio_detail['reason'] = f"FFmpeg not found or error: {e}"
        audio_stats['details'].append(audio_detail)
        audio_stats['skipped_error'] += 1
        return audio_data, mime_type
    
    # Skip if data is too small to benefit from optimization
    if len(audio_data) < 10240:  # 10KB
        if verbose:
            print(f"Audio file too small to optimize: {len(audio_data)} bytes")
        audio_detail['status'] = 'skipped_small'
        audio_detail['reason'] = f"Too small: {len(audio_data)} bytes"
        audio_stats['details'].append(audio_detail)
        audio_stats['skipped_small'] += 1
        return audio_data, mime_type
    
    try:
        if verbose:
            print(f"Processing audio file: {mime_type}, size: {len(audio_data)} bytes, target bitrate: {bitrate}kbps")
        
        # Create temporary files
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{mime_type.split('/')[-1]}") as input_file, \
             tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as output_file:
            
            # Write audio data to input file
            input_file.write(audio_data)
            input_file.flush()
            
            # Close files to avoid issues on Windows
            input_path = input_file.name
            output_path = output_file.name
        
        if verbose:
            print(f"Created temp files: input={input_path}, output={output_path}")
        
        # Run ffmpeg to optimize
        cmd = [
            "ffmpeg", "-y", "-i", input_path, 
            "-b:a", f"{bitrate}k", 
            "-map", "0:a", 
            output_path
        ]
        
        if verbose:
            print(f"Running FFmpeg command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
        
        if verbose:
            print(f"FFmpeg result: {result.returncode}")
            print(f"FFmpeg stderr: {result.stderr.decode('utf-8', errors='ignore')}")
        
        if result.returncode == 0:
            # Read optimized data
            with open(output_path, "rb") as f:
                optimized_data = f.read()
            
            original_size = len(audio_data)
            new_size = len(optimized_data)
            savings = original_size - new_size
            savings_percent = (savings / original_size) * 100 if original_size > 0 else 0
            
            if verbose:
                print(f"Audio optimization results:")
                print(f"  Original size: {original_size:,} bytes")
                print(f"  Optimized size: {new_size:,} bytes")
                print(f"  Savings: {savings:,} bytes ({savings_percent:.2f}%)")
            
            # Only use optimized data if it's smaller
            if len(optimized_data) < len(audio_data):
                audio_detail['status'] = 'processed'
                audio_detail['original_size'] = original_size
                audio_detail['optimized_size'] = new_size
                audio_detail['savings_percent'] = savings_percent
                audio_stats['details'].append(audio_detail)
                audio_stats['processed'] += 1
                return optimized_data, "audio/mpeg"
            else:
                if verbose:
                    print("Optimized audio not smaller than original, keeping original")
                audio_detail['status'] = 'skipped_no_reduction'
                audio_detail['reason'] = f"No size reduction: {original_size} -> {new_size} bytes"
                audio_stats['details'].append(audio_detail)
                audio_stats['skipped_no_reduction'] += 1
        else:
            if verbose:
                print(f"FFmpeg error: {result.stderr.decode('utf-8', errors='ignore')}")
            audio_detail['status'] = 'skipped_error'
            audio_detail['reason'] = f"FFmpeg error: {result.returncode}"
            audio_stats['details'].append(audio_detail)
            audio_stats['skipped_error'] += 1
    
    except Exception as e:
        print(f"Audio optimization error: {e}")
        audio_detail['status'] = 'skipped_error'
        audio_detail['reason'] = f"Exception: {str(e)}"
        audio_stats['details'].append(audio_detail)
        audio_stats['skipped_error'] += 1
    
    finally:
        # Clean up temporary files
        try:
            os.unlink(input_path)
            os.unlink(output_path)
            if verbose:
                print("Temporary files cleaned up")
        except Exception as e:
            if verbose:
                print(f"Error cleaning up temp files: {e}")
    
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
        verbose = options.get('verbose', False)
        
        if mime_type == 'image/svg+xml':
            # Special handling for SVG
            optimized_data, compression_used = optimize_svg(binary_data, verbose=verbose)
            new_mime_type = mime_type
            compression = compression_used
        elif mime_type.startswith('image/'):
            # Optimize bitmap image
            optimized_data, new_mime_type = optimize_image(
                binary_data, 
                mime_type,
                quality=options.get('image_quality', 80),
                convert_to_webp=options.get('use_webp', True),
                max_dimension=options.get('max_dimension', None),
                verbose=verbose
            )
        elif mime_type.startswith('audio/'):
            # Optimize audio
            if verbose:
                print(f"\nDetected audio file: {mime_type}, size: {len(binary_data)} bytes")
                if tag_name:
                    print(f"In tag: {tag_name}")
            
            optimized_data, new_mime_type = optimize_audio(
                binary_data,
                mime_type,
                bitrate=options.get('audio_bitrate', 128),
                verbose=verbose
            )
            
            # For audio files, always use base64 encoding (not base85)
            # This ensures better compatibility with audio players
            encoded_data = base64.b64encode(optimized_data).decode('ascii')
            
            # For audio files, directly return the data URI format
            # This ensures compatibility with audio players
            return f'data:{new_mime_type};base64,{encoded_data}'
        else:
            # For other types, just keep original
            optimized_data = binary_data
            new_mime_type = mime_type
        
        # Determine if we should use base85 encoding (not for audio)
        use_base85 = options.get('use_base85', True) and not mime_type.startswith('audio/')
        
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

def optimize_html_file(input_path, output_path, options=None, inflate_js_content=None):
    """Optimize base64 content in an HTML file"""
    if options is None:
        options = {}
    
    # If inflate_js_content is not provided, read it
    if inflate_js_content is None:
        inflate_js_content = read_inflate_js()
    
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
        
        # Process source tags with srcset attributes (for images)
        source_srcset_pattern = r'<source[^>]+srcset=["\'](data:[^;]+;base64,[^"\']+)["\'][^>]*>'
        html_content = re.sub(source_srcset_pattern, lambda m: re.sub(r'srcset=["\'](data:[^;]+;base64,[^"\']+)["\']',
                                                                 lambda n: process_data_uri(n, 'source', options), m.group(0)), html_content)
        
        # Process source tags with src attributes (for audio files)
        source_src_pattern = r'<source[^>]+src=["\'](data:audio/[^;]+;base64,[^"\']+)["\'][^>]*>'
        html_content = re.sub(source_src_pattern, lambda m: re.sub(r'src=["\'](data:audio/[^;]+;base64,[^"\']+)["\']',
                                                               lambda n: f'src="{process_data_uri(n, "source", options)}"', m.group(0)), html_content)
        
        # Process audio tags with src attributes
        audio_pattern = r'<audio[^>]+src=["\'](data:audio/[^;]+;base64,[^"\']+)["\'][^>]*>'
        html_content = re.sub(audio_pattern, lambda m: re.sub(r'src=["\'](data:audio/[^;]+;base64,[^"\']+)["\']',
                                                           lambda n: f'src="{process_data_uri(n, "audio", options)}"', m.group(0)), html_content)
        
        # Process CSS background images
        css_pattern = r'background-image:\s*url\(["\']?(data:[^;]+;base64,[^"\')\s]+)["\']?\)'
        html_content = re.sub(css_pattern, lambda m: re.sub(r'url\(["\']?(data:[^;]+;base64,[^"\')\s]+)["\']?\)',
                                                          lambda n: f'url({process_data_uri(n, None, options)})', m.group(0)), html_content)
        
        # Create the complete decoder JS by replacing the placeholder
        decoder_js_start = DECODER_JS.split("{inflate_js_content}")[0]
        decoder_js_end = DECODER_JS.split("{inflate_js_content}")[1]
        complete_decoder_js = decoder_js_start + inflate_js_content + decoder_js_end
        
        # Add decoder JavaScript before closing body tag
        if '</body>' in html_content:
            html_content = html_content.replace('</body>', complete_decoder_js + '</body>')
        else:
            html_content += complete_decoder_js
        
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
        
        # Print image statistics
        print("\n=== IMAGE OPTIMIZATION SUMMARY ===")
        print(f"Total image files detected: {image_stats['detected']}")
        print(f"Image files processed: {image_stats['processed']}")
        print(f"Image files skipped (too small): {image_stats['skipped_small']}")
        print(f"Image files skipped (no size reduction): {image_stats['skipped_no_reduction']}")
        print(f"Image files skipped (errors): {image_stats['skipped_error']}")
        
        # Print audio statistics
        print("\n=== AUDIO OPTIMIZATION SUMMARY ===")
        print(f"Total audio files detected: {audio_stats['detected']}")
        print(f"Audio files processed: {audio_stats['processed']}")
        print(f"Audio files skipped (too small): {audio_stats['skipped_small']}")
        print(f"Audio files skipped (no size reduction): {audio_stats['skipped_no_reduction']}")
        print(f"Audio files skipped (errors): {audio_stats['skipped_error']}")
        
        if options.get('verbose', False):
            if image_stats['details']:
                print("\nDetailed Image File Information:")
                for i, detail in enumerate(image_stats['details'], 1):
                    print(f"\n{i}. Image file: {detail['mime_type']}")
                    print(f"   Size: {detail['size']:,} bytes")
                    print(f"   Status: {detail['status']}")
                    if 'reason' in detail:
                        print(f"   Reason: {detail['reason']}")
                    if 'original_size' in detail and 'optimized_size' in detail:
                        print(f"   Original size: {detail['original_size']:,} bytes")
                        print(f"   Optimized size: {detail['optimized_size']:,} bytes")
                        print(f"   Savings: {detail['savings_percent']:.2f}%")
            
            if audio_stats['details']:
                print("\nDetailed Audio File Information:")
                for i, detail in enumerate(audio_stats['details'], 1):
                    print(f"\n{i}. Audio file: {detail['mime_type']}")
                    print(f"   Size: {detail['size']:,} bytes")
                    print(f"   Status: {detail['status']}")
                    if 'reason' in detail:
                        print(f"   Reason: {detail['reason']}")
                    if 'original_size' in detail and 'optimized_size' in detail:
                        print(f"   Original size: {detail['original_size']:,} bytes")
                        print(f"   Optimized size: {detail['optimized_size']:,} bytes")
                        print(f"   Savings: {detail['savings_percent']:.2f}%")
        
        return True
    
    except Exception as e:
        print(f"Error optimizing HTML file: {e}")
        return False

def process_chunk(chunk, options=None):
    """Process a chunk of HTML content"""
    if options is None:
        options = {}
    
    # Process img tags with src attributes
    img_pattern = r'<img[^>]+src=["\'](data:[^;]+;base64,[^"\']+)["\'][^>]*>'
    chunk = re.sub(img_pattern, lambda m: re.sub(r'src=["\'](data:[^;]+;base64,[^"\']+)["\']',
                                                lambda n: process_data_uri(n, 'img', options), m.group(0)), chunk)
    
    # Process source tags with srcset attributes (for images)
    source_srcset_pattern = r'<source[^>]+srcset=["\'](data:[^;]+;base64,[^"\']+)["\'][^>]*>'
    chunk = re.sub(source_srcset_pattern, lambda m: re.sub(r'srcset=["\'](data:[^;]+;base64,[^"\']+)["\']',
                                                       lambda n: process_data_uri(n, 'source', options), m.group(0)), chunk)
    
    # Process source tags with src attributes (for audio files)
    source_src_pattern = r'<source[^>]+src=["\'](data:audio/[^;]+;base64,[^"\']+)["\'][^>]*>'
    chunk = re.sub(source_src_pattern, lambda m: re.sub(r'src=["\'](data:audio/[^;]+;base64,[^"\']+)["\']',
                                                     lambda n: f'src="{process_data_uri(n, "source", options)}"', m.group(0)), chunk)
    
    # Process audio tags with src attributes
    audio_pattern = r'<audio[^>]+src=["\'](data:audio/[^;]+;base64,[^"\']+)["\'][^>]*>'
    chunk = re.sub(audio_pattern, lambda m: re.sub(r'src=["\'](data:audio/[^;]+;base64,[^"\']+)["\']',
                                                  lambda n: f'src="{process_data_uri(n, "audio", options)}"', m.group(0)), chunk)
    
    # Process CSS background images
    css_pattern = r'background-image:\s*url\(["\']?(data:[^;]+;base64,[^"\')\s]+)["\']?\)'
    chunk = re.sub(css_pattern, lambda m: re.sub(r'url\(["\']?(data:[^;]+;base64,[^"\')\s]+)["\']?\)',
                                                lambda n: f'url({process_data_uri(n, None, options)})', m.group(0)), chunk)
    
    return chunk

def process_file_in_chunks(input_path, output_path, chunk_size=10*1024*1024, options=None, inflate_js_content=None):
    """Process a large HTML file in chunks to avoid memory issues"""
    if options is None:
        options = {}
    
    # If inflate_js_content is not provided, read it
    if inflate_js_content is None:
        inflate_js_content = read_inflate_js()
    
    try:
        # Create a temporary output file
        temp_output = output_path + '.temp'
        
        with open(input_path, 'r', encoding='utf-8') as infile, open(temp_output, 'w', encoding='utf-8') as outfile:
            # Create the complete decoder JS by replacing the placeholder
            decoder_js_start = DECODER_JS.split("{inflate_js_content}")[0]
            decoder_js_end = DECODER_JS.split("{inflate_js_content}")[1]
            complete_decoder_js = decoder_js_start + inflate_js_content + decoder_js_end
            
            # Add decoder JavaScript at the beginning
            outfile.write('<!DOCTYPE html>\n<html>\n<head>\n')
            outfile.write(complete_decoder_js)
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
        
        # Print image statistics
        print("\n=== IMAGE OPTIMIZATION SUMMARY ===")
        print(f"Total image files detected: {image_stats['detected']}")
        print(f"Image files processed: {image_stats['processed']}")
        print(f"Image files skipped (too small): {image_stats['skipped_small']}")
        print(f"Image files skipped (no size reduction): {image_stats['skipped_no_reduction']}")
        print(f"Image files skipped (errors): {image_stats['skipped_error']}")
        
        # Print audio statistics
        print("\n=== AUDIO OPTIMIZATION SUMMARY ===")
        print(f"Total audio files detected: {audio_stats['detected']}")
        print(f"Audio files processed: {audio_stats['processed']}")
        print(f"Audio files skipped (too small): {audio_stats['skipped_small']}")
        print(f"Audio files skipped (no size reduction): {audio_stats['skipped_no_reduction']}")
        print(f"Audio files skipped (errors): {audio_stats['skipped_error']}")
        
        if options.get('verbose', False):
            if image_stats['details']:
                print("\nDetailed Image File Information:")
                for i, detail in enumerate(image_stats['details'], 1):
                    print(f"\n{i}. Image file: {detail['mime_type']}")
                    print(f"   Size: {detail['size']:,} bytes")
                    print(f"   Status: {detail['status']}")
                    if 'reason' in detail:
                        print(f"   Reason: {detail['reason']}")
                    if 'original_size' in detail and 'optimized_size' in detail:
                        print(f"   Original size: {detail['original_size']:,} bytes")
                        print(f"   Optimized size: {detail['optimized_size']:,} bytes")
                        print(f"   Savings: {detail['savings_percent']:.2f}%")
            
            if audio_stats['details']:
                print("\nDetailed Audio File Information:")
                for i, detail in enumerate(audio_stats['details'], 1):
                    print(f"\n{i}. Audio file: {detail['mime_type']}")
                    print(f"   Size: {detail['size']:,} bytes")
                    print(f"   Status: {detail['status']}")
                    if 'reason' in detail:
                        print(f"   Reason: {detail['reason']}")
                    if 'original_size' in detail and 'optimized_size' in detail:
                        print(f"   Original size: {detail['original_size']:,} bytes")
                        print(f"   Optimized size: {detail['optimized_size']:,} bytes")
                        print(f"   Savings: {detail['savings_percent']:.2f}%")
        
        return True
    
    except Exception as e:
        print(f"Error processing file in chunks: {e}")
        if os.path.exists(temp_output):
            os.remove(temp_output)
        return False

def main():
    parser = argparse.ArgumentParser(description='Optimize base64 encoded content (images and audio) in HTML files')
    parser.add_argument('input', help='Input HTML file path')
    parser.add_argument('-o', '--output', help='Output HTML file path (default: input-optimized.html)')
    
    # Image optimization options
    parser.add_argument('-i', '--image-quality', type=int, default=80, choices=range(1, 101),
                        help='Image quality (1-100, default: 80)')
    parser.add_argument('-w', '--webp', action='store_true',
                        help='Convert images to WebP format when beneficial')
    parser.add_argument('-d', '--max-dimension', type=int,
                        help='Maximum image dimension (will resize larger images)')
    
    # Audio optimization options
    parser.add_argument('-a', '--audio-bitrate', type=int, default=128,
                        help='Audio bitrate in kbps (default: 128)')
    
    # General options
    parser.add_argument('-m', '--min-size', type=int, default=1024,
                        help='Minimum size in bytes to consider for optimization (default: 1024)')
    parser.add_argument('-r', '--min-ratio', type=float, default=0.05,
                        help='Minimum compression ratio to apply changes (default: 0.05)')
    parser.add_argument('-85', '--base85', action='store_true',
                        help='Use Base85 encoding instead of Base64 for images (more efficient)')
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
        'image_quality': args.image_quality,
        'audio_bitrate': args.audio_bitrate,
        'use_webp': args.webp,
        'max_dimension': args.max_dimension,
        'min_size': args.min_size,
        'min_compression_ratio': args.min_ratio,
        'use_base85': args.base85,
        'verbose': args.verbose
    }
    
    print(f"Processing {input_path}")
    print(f"Output will be saved to {output_path}")
    print(f"Optimization options:")
    print(f"  - Image quality: {args.image_quality}")
    print(f"  - Audio bitrate: {args.audio_bitrate}kbps")
    print(f"  - Convert to WebP: {args.webp}")
    if args.max_dimension:
        print(f"  - Max dimension: {args.max_dimension}px")
    print(f"  - Use Base85 encoding: {args.base85}")
    print(f"  - Minimum size to optimize: {args.min_size} bytes")
    print(f"  - Minimum compression ratio: {args.min_ratio:.2f}")
    print(f"  - Process in chunks: {args.chunks}")
    print(f"  - Verbose output: {args.verbose}")
    
    # Read the inflate.js content
    inflate_js_content = read_inflate_js()
    
    if args.chunks:
        success = process_file_in_chunks(input_path, output_path, options=options, inflate_js_content=inflate_js_content)
    else:
        success = optimize_html_file(input_path, output_path, options=options, inflate_js_content=inflate_js_content)
    
    if success:
        print("Optimization completed successfully!")
    else:
        print("Optimization failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()
