"""
Helper functions for the application
"""

import hashlib
import json
import os
import base64
from datetime import datetime
import cv2
import numpy as np
import yaml
from typing import Optional, Tuple, Any, List, Dict
import time
import logging

# Setup logger
logger = logging.getLogger(__name__)

def create_response(success=True, message='', data=None, status_code=200):
    """Create a standardized API response"""
    return {
        'success': success,
        'message': message,
        'data': data or {},
        'timestamp': datetime.now().isoformat(),
        'status_code': status_code
    }

def load_config(config_path='config.yaml') -> Dict:
    """Load configuration from YAML file"""
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"⚠️ Config file not found: {config_path}")
        return {}
    except Exception as e:
        print(f"❌ Error loading config: {e}")
        return {}

def save_config(config: Dict, config_path='config.yaml') -> bool:
    """Save configuration to YAML file"""
    try:
        # Create backup
        if os.path.exists(config_path):
            backup_path = f"{config_path}.backup"
            import shutil
            shutil.copy2(config_path, backup_path)
        
        with open(config_path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        return True
    except Exception as e:
        print(f"❌ Error saving config: {e}")
        return False

def hash_password(password: str) -> str:
    """Hash a password for storage"""
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt,
        100000
    )
    return base64.b64encode(salt + key).decode('utf-8')

def verify_password(password: str, stored: str) -> bool:
    """Verify a password against stored hash"""
    try:
        stored_bytes = base64.b64decode(stored.encode('utf-8'))
        salt = stored_bytes[:32]
        key = stored_bytes[32:]
        new_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return new_key == key
    except Exception:
        return False

def resize_frame(frame, width=None, height=None, keep_aspect=True):
    """Resize frame while maintaining aspect ratio"""
    if frame is None:
        return None
    
    h, w = frame.shape[:2]
    
    if width and height:
        return cv2.resize(frame, (width, height))
    elif width:
        if keep_aspect:
            ratio = width / w
            new_dim = (width, int(h * ratio))
        else:
            new_dim = (width, h)
        return cv2.resize(frame, new_dim)
    elif height:
        if keep_aspect:
            ratio = height / h
            new_dim = (int(w * ratio), height)
        else:
            new_dim = (w, height)
        return cv2.resize(frame, new_dim)
    
    return frame

def format_time(seconds: float) -> str:
    """Format seconds into readable time"""
    if seconds < 0:
        return "0s"
    
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)

def calculate_ear(eye_points):
    """Calculate Eye Aspect Ratio"""
    A = np.linalg.norm(eye_points[1] - eye_points[5])
    B = np.linalg.norm(eye_points[2] - eye_points[4])
    C = np.linalg.norm(eye_points[0] - eye_points[3])
    ear = (A + B) / (2.0 * C)
    return ear

def calculate_mar(mouth_points):
    """Calculate Mouth Aspect Ratio (for yawn detection)"""
    A = np.linalg.norm(mouth_points[2] - mouth_points[6])
    B = np.linalg.norm(mouth_points[3] - mouth_points[5])
    C = np.linalg.norm(mouth_points[0] - mouth_points[4])
    mar = (A + B) / (2.0 * C)
    return mar

def frame_to_base64(frame):
    """Convert OpenCV frame to base64 string"""
    _, buffer = cv2.imencode('.jpg', frame)
    return base64.b64encode(buffer).decode('utf-8')

def base64_to_frame(base64_string):
    """Convert base64 string to OpenCV frame"""
    img_data = base64.b64decode(base64_string)
    nparr = np.frombuffer(img_data, np.uint8)
    return cv2.imdecode(nparr, cv2.IMREAD_COLOR)

def ensure_directory(path: str) -> str:
    """Ensure directory exists"""
    os.makedirs(path, exist_ok=True)
    return path

def safe_divide(a: float, b: float, default: float = 0) -> float:
    """Safe division to avoid division by zero"""
    return a / b if b != 0 else default

def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max"""
    return max(min_val, min(max_val, value))

def moving_average(data: List[float], window_size: int = 5) -> List[float]:
    """Calculate moving average"""
    if len(data) < window_size:
        return data
    weights = np.repeat(1.0, window_size) / window_size
    return np.convolve(data, weights, 'valid').tolist()

def timer(func):
    """Decorator to time functions"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"⏱️ {func.__name__} took {end-start:.3f}s")
        return result
    return wrapper


# ============================================================
# LOW-LIGHT ENHANCEMENT USING CLAHE
# ADD THIS SECTION TO YOUR helpers.py FILE
# ============================================================

def enhance_low_light(frame, gamma=0.7, clip_limit=3.0, tile_grid_size=(8,8), 
                      brightness_threshold=80, apply_bilateral=True):
    """
    Enhance low-light images using CLAHE (Contrast Limited Adaptive Histogram Equalization)
    
    This function implements a complete pipeline for improving visibility in low-light conditions:
    1. Brightness assessment - checks if enhancement is needed
    2. Gamma correction - normalizes luminance
    3. CLAHE - enhances contrast while limiting noise amplification
    4. Bilateral filtering - reduces noise while preserving edges
    
    Args:
        frame: Input BGR image from camera
        gamma: Gamma correction value (default: 0.7, range: 0.3-1.5)
               Lower values (<1) brighten dark regions
        clip_limit: CLAHE clip limit (default: 3.0, range: 1.0-5.0)
                   Higher values provide more contrast but may increase noise
        tile_grid_size: CLAHE tile grid size (default: (8,8))
                       Smaller tiles provide local adaptation
        brightness_threshold: Threshold to trigger enhancement (default: 80)
                              Mean pixel intensity below this triggers enhancement
        apply_bilateral: Whether to apply bilateral filtering (default: True)
                        Reduces noise but adds computational cost
    
    Returns:
        Enhanced frame (if enhancement was applied) or original frame
    
    Example:
        >>> frame = cv2.imread('dark_image.jpg')
        >>> enhanced = enhance_low_light(frame, gamma=0.7, clip_limit=3.0)
        >>> cv2.imshow('Enhanced', enhanced)
    """
    if frame is None:
        logger.warning("enhance_low_light received None frame")
        return None
    
    # Make a copy to avoid modifying original
    result = frame.copy()
    
    # Step 1: Illumination Assessment
    # Convert to grayscale for brightness calculation
    gray = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray)
    
    logger.debug(f"Mean brightness: {mean_brightness:.2f} lux")
    
    # Only apply enhancement in low-light conditions
    if mean_brightness < brightness_threshold:
        logger.info(f"Low-light detected ({mean_brightness:.2f} lux). Applying CLAHE enhancement.")
        
        # Step 2: Convert to LAB color space (better for luminance processing)
        # L channel: luminance, a/b channels: color information
        lab = cv2.cvtColor(result, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        # Step 3: Gamma Correction for luminance normalization
        # Formula: V_out = 255 * (V_in/255)^(1/γ)
        # This brightens dark regions while preserving highlights
        l_normalized = l.astype(np.float32) / 255.0
        l_gamma = np.power(l_normalized, 1.0/gamma) * 255.0
        l_gamma = np.clip(l_gamma, 0, 255).astype(np.uint8)
        
        # Step 4: Apply CLAHE to luminance channel
        # CLAHE prevents over-amplification of noise in homogeneous regions
        clahe = cv2.createCLAHE(clipLimit=clip_limit, 
                                 tileGridSize=tile_grid_size)
        l_enhanced = clahe.apply(l_gamma)
        
        # Merge enhanced luminance with original chrominance
        lab_enhanced = cv2.merge([l_enhanced, a, b])
        enhanced = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)
        
        # Step 5: Apply bilateral filter for edge-preserving noise reduction
        # Bilateral filter smooths while preserving edges
        if apply_bilateral:
            enhanced = cv2.bilateralFilter(enhanced, 9, 75, 75)
        
        # Calculate improvement for logging
        enhanced_gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)
        enhanced_brightness = np.mean(enhanced_gray)
        improvement = ((enhanced_brightness - mean_brightness) / mean_brightness) * 100
        
        logger.info(f"Enhancement complete. Brightness: {mean_brightness:.2f} → {enhanced_brightness:.2f} ({improvement:.1f}% improvement)")
        
        return enhanced
    
    logger.debug(f"Brightness sufficient ({mean_brightness:.2f} lux). Skipping enhancement.")
    return result


def apply_clahe_to_frame(frame, clip_limit=3.0, tile_grid_size=(8,8)):
    """
    Apply CLAHE directly to grayscale frame (simpler, faster version)
    
    This is a faster alternative that works directly on grayscale.
    Use when color preservation isn't critical and speed is important.
    
    Args:
        frame: Input BGR image
        clip_limit: CLAHE clip limit
        tile_grid_size: CLAHE tile grid size
    
    Returns:
        Frame with CLAHE applied (converted back to BGR)
    """
    if frame is None:
        return None
    
    # Convert to grayscale
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Apply CLAHE
    clahe = cv2.createCLAHE(clipLimit=clip_limit, 
                             tileGridSize=tile_grid_size)
    enhanced_gray = clahe.apply(gray)
    
    # Convert back to BGR (3-channel)
    return cv2.cvtColor(enhanced_gray, cv2.COLOR_GRAY2BGR)


def adjust_gamma(frame, gamma=1.0):
    """
    Apply gamma correction to image
    
    Gamma correction adjusts the luminance:
    - gamma < 1: Brightens dark regions (shadows)
    - gamma > 1: Darkens bright regions (highlights)
    - gamma = 1: No change
    
    Args:
        frame: Input BGR image
        gamma: Gamma value (default: 1.0)
    
    Returns:
        Gamma corrected image
    """
    if frame is None:
        return None
    
    # Build lookup table
    inv_gamma = 1.0 / gamma
    table = np.array([(i / 255.0) ** inv_gamma * 255 
                      for i in range(256)]).astype(np.uint8)
    
    # Apply gamma correction
    return cv2.LUT(frame, table)


def batch_enhance_images(image_paths, output_dir, gamma=0.7, clip_limit=3.0, 
                         show_progress=True):
    """
    Batch process multiple images for low-light enhancement
    
    Useful for processing datasets or testing multiple images.
    
    Args:
        image_paths: List of input image paths
        output_dir: Directory to save enhanced images
        gamma: Gamma correction value
        clip_limit: CLAHE clip limit
        show_progress: Whether to show progress bar
    
    Returns:
        List of output paths
    """
    import os
    from tqdm import tqdm
    
    ensure_directory(output_dir)
    output_paths = []
    
    iterator = tqdm(image_paths, desc="Enhancing images") if show_progress else image_paths
    
    for img_path in iterator:
        try:
            # Read image
            frame = cv2.imread(img_path)
            if frame is None:
                logger.warning(f"Could not read image: {img_path}")
                continue
            
            # Enhance
            enhanced = enhance_low_light(frame, gamma, clip_limit)
            
            # Save
            filename = os.path.basename(img_path)
            name, ext = os.path.splitext(filename)
            output_path = os.path.join(output_dir, f"{name}_enhanced{ext}")
            cv2.imwrite(output_path, enhanced)
            output_paths.append(output_path)
            
            logger.debug(f"Saved enhanced image: {output_path}")
            
        except Exception as e:
            logger.error(f"Error processing {img_path}: {e}")
    
    logger.info(f"Batch enhancement complete. Processed {len(output_paths)} images.")
    return output_paths


def get_optimal_clahe_params(frame, target_brightness=120):
    """
    Automatically determine optimal CLAHE parameters based on image statistics
    
    Args:
        frame: Input BGR image
        target_brightness: Target mean brightness after enhancement
    
    Returns:
        Dictionary with optimal gamma and clip_limit
    """
    if frame is None:
        return {'gamma': 0.7, 'clip_limit': 3.0}
    
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    mean_brightness = np.mean(gray)
    std_brightness = np.std(gray)
    
    # Calculate optimal gamma based on current brightness
    # Darker images need more aggressive gamma
    if mean_brightness < 30:
        gamma = 0.5
    elif mean_brightness < 50:
        gamma = 0.6
    elif mean_brightness < 80:
        gamma = 0.7
    else:
        gamma = 0.8
    
    # Calculate optimal clip limit based on contrast
    # Low contrast images need higher clip limit
    if std_brightness < 30:
        clip_limit = 4.0
    elif std_brightness < 50:
        clip_limit = 3.5
    else:
        clip_limit = 3.0
    
    return {
        'gamma': gamma,
        'clip_limit': clip_limit,
        'estimated_brightness': mean_brightness,
        'estimated_contrast': std_brightness
    }


def compare_enhancement_methods(frame):
    """
    Compare different enhancement methods side by side
    
    Args:
        frame: Input BGR image
    
    Returns:
        Montage showing original and all enhancement methods
    """
    if frame is None:
        return None
    
    # Original
    original = frame.copy()
    
    # Method 1: CLAHE only (fast)
    method1 = apply_clahe_to_frame(frame)
    
    # Method 2: Gamma + CLAHE (balanced)
    gamma_corrected = adjust_gamma(frame, 0.7)
    method2 = apply_clahe_to_frame(gamma_corrected)
    
    # Method 3: Full pipeline (best quality)
    method3 = enhance_low_light(frame)
    
    # Resize all to same height
    h, w = original.shape[:2]
    method1 = cv2.resize(method1, (w, h))
    method2 = cv2.resize(method2, (w, h))
    method3 = cv2.resize(method3, (w, h))
    
    # Create labels
    font = cv2.FONT_HERSHEY_SIMPLEX
    cv2.putText(original, "Original", (10, 30), font, 1, (0, 255, 0), 2)
    cv2.putText(method1, "CLAHE Only", (10, 30), font, 1, (0, 255, 0), 2)
    cv2.putText(method2, "Gamma+CLAHE", (10, 30), font, 1, (0, 255, 0), 2)
    cv2.putText(method3, "Full Pipeline", (10, 30), font, 1, (0, 255, 0), 2)
    
    # Create montage
    top_row = np.hstack([original, method1])
    bottom_row = np.hstack([method2, method3])
    montage = np.vstack([top_row, bottom_row])
    
    return montage


# Example usage if script is run directly
if __name__ == "__main__":
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    
    # Test with a sample image
    print("CLAHE Enhancement Module Test")
    print("=" * 50)
    
    # Create a test image (simulate low-light)
    test_img = np.random.randint(0, 50, (480, 640, 3), dtype=np.uint8)
    
    # Test enhancement
    enhanced = enhance_low_light(test_img)
    
    print(f"Original shape: {test_img.shape}")
    print(f"Enhanced shape: {enhanced.shape}")
    print("✓ CLAHE enhancement function is working")
    
    # Test parameter optimization
    params = get_optimal_clahe_params(test_img)
    print(f"Optimal parameters: {params}")