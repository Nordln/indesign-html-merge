#!/usr/bin/env python3
"""
Script to optimise base64 encoded content in HTML files.
Specialized for JPG/PNG images, SVG, and audio files.
This version ensures audio compatibility while still optimising.
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
    print("Warning: Pillow library not found. Image optimisation will be limited.")
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

// Process all optimised content when the page loads
document.addEventListener('DOMContentLoaded', function() {
    // Process all elements with data-optimised attributes
    const elements = document.querySelectorAll('[data-optimised-src]');
    
    elements.forEach(function(element) {
        const encodedData = element.getAttribute('data-optimised-src');
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
                console.error('Error processing optimised content:', err);
            }
        }
    });
});
</script>
<!-- Include pako library for gzip decompression -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/pako/2.1.0/pako.min.js"></script>
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

def is_valid_base64(s):
    """Check if a string is valid base64"""
    try:
        # Try to decode the base64 string
        decoded = base64.b64decode(s)
        return True
    except Exception:
        return False

def optimise_audio(audio_data, mime_type, bitrate=128, verbose=False):
    """
    optimise audio data by reducing bitrate
    
    Args:
        audio_data: Binary audio data
        mime_type: MIME type
        bitrate: Target bitrate in kbps
        verbose: Whether to print verbose output
        
    Returns:
        tuple: (optimised_data, mime_type)
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
    
    # Skip if data is too small to benefit from optimisation
    if len(audio_data) < 10240:  # 10KB
        if verbose:
            print(f"Audio file too small to optimise: {len(audio_data)} bytes")
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
        
        # Run ffmpeg to optimise
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
            # Read optimised data
            with open(output_path, "rb") as f:
                optimised_data = f.read()
            
            original_size = len(audio_data)
            new_size = len(optimised_data)
            savings = original_size - new_size
            savings_percent = (savings / original_size) * 100 if original_size > 0 else 0
            
            if verbose:
                print(f"Audio optimisation results:")
                print(f"  Original size: {original_size:,} bytes")
                print(f"  optimised size: {new_size:,} bytes")
                print(f"  Savings: {savings:,} bytes ({savings_percent:.2f}%)")
            
            # Only use optimised data if it's smaller
            if len(optimised_data) < len(audio_data):
                audio_detail['status'] = 'processed'
                audio_detail['original_size'] = original_size
                audio_detail['optimised_size'] = new_size
                audio_detail['savings_percent'] = savings_percent
                audio_stats['details'].append(audio_detail)
                audio_stats['processed'] += 1
                return optimised_data, "audio/mpeg"
            else:
                if verbose:
                    print("optimised audio not smaller than original, keeping original")
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
        print(f"Audio optimisation error: {e}")
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
    
    # Return original if optimisation failed or didn't reduce size
    return audio_data, mime_type

def process_data_uri(match, tag_name=None, options=None):
    """Process a data URI match and return optimised version"""
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
        
        # Skip if data is too small to benefit from optimisation
        if len(binary_data) < options.get('min_size', 1024):
            return data_uri
        
        # optimise based on content type
        compression = 'none'
        
        if mime_type.startswith('audio/'):
            # optimise audio
            verbose = options.get('verbose', False)
            if verbose:
                print(f"\nDetected audio file: {mime_type}, size: {len(binary_data)} bytes")
                if tag_name:
                    print(f"In tag: {tag_name}")
            
            optimised_data, new_mime_type = optimise_audio(
                binary_data,
                mime_type,
                bitrate=options.get('audio_bitrate', 128),
                verbose=verbose
            )
            
            # For audio files, always use base64 encoding (not base85)
            # This ensures better compatibility with audio players
            encoded_data = base64.b64encode(optimised_data).decode('ascii')
            encoding = 'base64'
            
            # For audio files, directly return the data URI format
            # This ensures compatibility with audio players
            return f'data:{new_mime_type};base64,{encoded_data}'
        else:
            # For non-audio files, just return the original data URI
            return data_uri
        
    except Exception as e:
        print(f"Error processing data URI: {e}")
        return data_uri  # Return original on error

def optimise_html_file(input_path, output_path, options=None):
    """optimise base64 content in an HTML file"""
    if options is None:
        options = {}
    
    try:
        # Read the HTML file
        with open(input_path, 'r', encoding='utf-8') as file:
            html_content = file.read()
        
        # Track original size
        original_size = len(html_content.encode('utf-8'))
        
        # Process audio in source tags with src attributes (for audio files)
        source_src_pattern = r'<source[^>]+src=["\'](data:audio/[^;]+;base64,[^"\']+)["\'][^>]*>'
        html_content = re.sub(source_src_pattern, lambda m: re.sub(r'src=["\'](data:audio/[^;]+;base64,[^"\']+)["\']',
                                                               lambda n: f'src="{process_data_uri(n, "source", options)}"', m.group(0)), html_content)
        
        # Process audio tags with src attributes
        audio_pattern = r'<audio[^>]+src=["\'](data:audio/[^;]+;base64,[^"\']+)["\'][^>]*>'
        html_content = re.sub(audio_pattern, lambda m: re.sub(r'src=["\'](data:audio/[^;]+;base64,[^"\']+)["\']', 
                                                            lambda n: f'src="{process_data_uri(n, "audio", options)}"', m.group(0)), html_content)
        
        # Write the processed HTML to the output file
        with open(output_path, 'w', encoding='utf-8') as file:
            file.write(html_content)
        
        # Calculate compression statistics
        compressed_size = os.path.getsize(output_path)
        savings = original_size - compressed_size
        savings_percent = (savings / original_size) * 100 if original_size > 0 else 0
        
        print(f"Original size: {original_size:,} bytes")
        print(f"optimised size: {compressed_size:,} bytes")
        print(f"Savings: {savings:,} bytes ({savings_percent:.2f}%)")
        
        # Print audio statistics
        print("\n=== AUDIO optimisation SUMMARY ===")
        print(f"Total audio files detected: {audio_stats['detected']}")
        print(f"Audio files processed: {audio_stats['processed']}")
        print(f"Audio files skipped (too small): {audio_stats['skipped_small']}")
        print(f"Audio files skipped (no size reduction): {audio_stats['skipped_no_reduction']}")
        print(f"Audio files skipped (errors): {audio_stats['skipped_error']}")
        
        if options.get('verbose', False) and audio_stats['details']:
            print("\nDetailed Audio File Information:")
            for i, detail in enumerate(audio_stats['details'], 1):
                print(f"\n{i}. Audio file: {detail['mime_type']}")
                print(f"   Size: {detail['size']:,} bytes")
                print(f"   Status: {detail['status']}")
                if 'reason' in detail:
                    print(f"   Reason: {detail['reason']}")
                if 'original_size' in detail and 'optimised_size' in detail:
                    print(f"   Original size: {detail['original_size']:,} bytes")
                    print(f"   optimised size: {detail['optimised_size']:,} bytes")
                    print(f"   Savings: {detail['savings_percent']:.2f}%")
        
        return True
    
    except Exception as e:
        print(f"Error optimising HTML file: {e}")
        return False

def process_chunk(chunk, options=None):
    """Process a chunk of HTML content"""
    if options is None:
        options = {}
    
    # Process audio in source tags with src attributes (for audio files)
    source_src_pattern = r'<source[^>]+src=["\'](data:audio/[^;]+;base64,[^"\']+)["\'][^>]*>'
    chunk = re.sub(source_src_pattern, lambda m: re.sub(r'src=["\'](data:audio/[^;]+;base64,[^"\']+)["\']',
                                                     lambda n: f'src="{process_data_uri(n, "source", options)}"', m.group(0)), chunk)
    
    # Process audio tags with src attributes
    audio_pattern = r'<audio[^>]+src=["\'](data:audio/[^;]+;base64,[^"\']+)["\'][^>]*>'
    chunk = re.sub(audio_pattern, lambda m: re.sub(r'src=["\'](data:audio/[^;]+;base64,[^"\']+)["\']',
                                                   lambda n: f'src="{process_data_uri(n, "audio", options)}"', m.group(0)), chunk)
    
    return chunk

def process_file_in_chunks(input_path, output_path, chunk_size=10*1024*1024, options=None):
    """Process a large HTML file in chunks to avoid memory issues"""
    if options is None:
        options = {}
    
    try:
        # Create a temporary output file
        temp_output = output_path + '.temp'
        
        with open(input_path, 'r', encoding='utf-8') as infile, open(temp_output, 'w', encoding='utf-8') as outfile:
            # Process the file in chunks
            chunk = infile.read(chunk_size)
            while chunk:
                # Process data URIs in this chunk
                processed_chunk = process_chunk(chunk, options)
                outfile.write(processed_chunk)
                chunk = infile.read(chunk_size)
        
        # Rename temp file to output file
        os.replace(temp_output, output_path)
        
        # Calculate compression statistics
        original_size = os.path.getsize(input_path)
        compressed_size = os.path.getsize(output_path)
        savings = original_size - compressed_size
        savings_percent = (savings / original_size) * 100 if original_size > 0 else 0
        
        print(f"Original size: {original_size:,} bytes")
        print(f"optimised size: {compressed_size:,} bytes")
        print(f"Savings: {savings:,} bytes ({savings_percent:.2f}%)")
        
        # Print audio statistics
        print("\n=== AUDIO optimisation SUMMARY ===")
        print(f"Total audio files detected: {audio_stats['detected']}")
        print(f"Audio files processed: {audio_stats['processed']}")
        print(f"Audio files skipped (too small): {audio_stats['skipped_small']}")
        print(f"Audio files skipped (no size reduction): {audio_stats['skipped_no_reduction']}")
        print(f"Audio files skipped (errors): {audio_stats['skipped_error']}")
        
        if options.get('verbose', False) and audio_stats['details']:
            print("\nDetailed Audio File Information:")
            for i, detail in enumerate(audio_stats['details'], 1):
                print(f"\n{i}. Audio file: {detail['mime_type']}")
                print(f"   Size: {detail['size']:,} bytes")
                print(f"   Status: {detail['status']}")
                if 'reason' in detail:
                    print(f"   Reason: {detail['reason']}")
                if 'original_size' in detail and 'optimised_size' in detail:
                    print(f"   Original size: {detail['original_size']:,} bytes")
                    print(f"   optimised size: {detail['optimised_size']:,} bytes")
                    print(f"   Savings: {detail['savings_percent']:.2f}%")
        
        return True
    
    except Exception as e:
        print(f"Error processing file in chunks: {e}")
        if os.path.exists(temp_output):
            os.remove(temp_output)
        return False

def main():
    parser = argparse.ArgumentParser(description='optimise base64 encoded audio in HTML files with compatibility')
    parser.add_argument('input', help='Input HTML file path')
    parser.add_argument('-o', '--output', help='Output HTML file path (default: input-audio-optimised.html)')
    parser.add_argument('-b', '--bitrate', type=int, default=128,
                        help='Audio bitrate in kbps (default: 128)')
    parser.add_argument('-m', '--min-size', type=int, default=1024,
                        help='Minimum size in bytes to consider for optimisation (default: 1024)')
    parser.add_argument('-c', '--chunks', action='store_true',
                        help='Process file in chunks (for very large files)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Print verbose output for debugging')
    
    args = parser.parse_args()
    
    input_path = args.input
    
    # Default output path if not specified
    if not args.output:
        input_file = Path(input_path)
        output_path = str(input_file.with_stem(input_file.stem + '-audio_optimised'))
    else:
        output_path = args.output
    
    # Set optimisation options
    options = {
        'audio_bitrate': args.bitrate,
        'min_size': args.min_size,
        'verbose': args.verbose
    }
    
    print(f"Processing {input_path}")
    print(f"Output will be saved to {output_path}")
    print(f"Optimisation options: {options}")
    print(f"Audio bitrate set to: {args.bitrate}kbps")
    
    if args.chunks:
        success = process_file_in_chunks(input_path, output_path, options=options)
    else:
        success = optimise_html_file(input_path, output_path, options=options)
    
    if success:
        print("Optimisation completed successfully!")
    else:
        print("Optimisation failed.")
        sys.exit(1)

if __name__ == "__main__":
    main()