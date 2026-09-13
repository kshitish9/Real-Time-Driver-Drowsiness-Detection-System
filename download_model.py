"""
Download facial landmark predictor model
"""

import urllib.request
import bz2
import os
import sys
import time

def download_with_progress(url, filename):
    """Download with progress bar"""
    
    def progress_hook(count, block_size, total_size):
        if total_size > 0:
            percent = min(int(count * block_size * 100 / total_size), 100)
            bar_length = 50
            filled_length = int(bar_length * percent / 100)
            bar = '█' * filled_length + '░' * (bar_length - filled_length)
            
            sys.stdout.write(f'\r📥 Downloading: |{bar}| {percent}%')
            sys.stdout.flush()
    
    print(f"📥 Downloading facial landmark predictor...")
    print(f"   URL: {url}")
    print(f"   File: {filename}")
    print()
    
    urllib.request.urlretrieve(url, filename, progress_hook)
    print("\n✅ Download complete!")

def extract_bz2(bz2_file, output_file):
    """Extract bz2 file"""
    print(f"📦 Extracting {bz2_file}...")
    
    file_size = os.path.getsize(bz2_file)
    chunk_size = 1024 * 1024  # 1MB chunks
    
    with bz2.BZ2File(bz2_file, 'rb') as f_in:
        with open(output_file, 'wb') as f_out:
            total_read = 0
            while True:
                chunk = f_in.read(chunk_size)
                if not chunk:
                    break
                f_out.write(chunk)
                total_read += len(chunk)
                percent = min(int(total_read * 100 / file_size), 100)
                sys.stdout.write(f'\r   Progress: {percent}%')
                sys.stdout.flush()
    
    print("\n✅ Extraction complete!")

def verify_model(model_path):
    """Verify the model file is valid"""
    try:
        import dlib
        print("🔍 Verifying model...")
        
        # Try to load the model
        predictor = dlib.shape_predictor(model_path)
        print("✅ Model verification successful!")
        return True
    except Exception as e:
        print(f"❌ Model verification failed: {e}")
        return False

def main():
    print("\n" + "="*60)
    print("🚀 FACIAL LANDMARK PREDICTOR DOWNLOADER")
    print("="*60 + "\n")
    
    # Create models directory
    os.makedirs("models", exist_ok=True)
    
    # Download URLs
    urls = [
        "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2",
        "https://github.com/davisking/dlib-models/raw/master/shape_predictor_68_face_landmarks.dat.bz2"
    ]
    
    filename = "shape_predictor_68_face_landmarks.dat.bz2"
    output_file = "models/shape_predictor_68_face_landmarks.dat"
    
    # Try each URL until successful
    for i, url in enumerate(urls, 1):
        print(f"Trying mirror {i}/{len(urls)}...")
        try:
            # Download
            download_with_progress(url, filename)
            
            # Extract
            extract_bz2(filename, output_file)
            
            # Verify
            if verify_model(output_file):
                break
            else:
                print(f"⚠️ Mirror {i} failed, trying next...")
                continue
                
        except Exception as e:
            print(f"❌ Error with mirror {i}: {e}")
            continue
    
    # Clean up
    if os.path.exists(filename):
        os.remove(filename)
        print(f"🧹 Cleaned up: {filename}")
    
    # Final check
    if os.path.exists(output_file):
        file_size = os.path.getsize(output_file) / (1024 * 1024)
        print(f"\n✅ Model ready: {output_file}")
        print(f"   Size: {file_size:.1f} MB")
        print(f"   Path: {os.path.abspath(output_file)}")
    else:
        print("\n❌ Failed to download model")
        print("\n📝 Manual download instructions:")
        print("   1. Download from: http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2")
        print("   2. Extract to: models/shape_predictor_68_face_landmarks.dat")
        return 1
    
    print("\n" + "="*60)
    print("✅ READY TO RUN!")
    print("   Run: python app.py")
    print("="*60 + "\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())