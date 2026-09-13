from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, session
from flask_socketio import SocketIO, emit
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
import cv2
import dlib
import numpy as np
from scipy.spatial import distance as dist
import threading
import time
import os
import sqlite3
from datetime import datetime, timedelta
import queue
import secrets
import yaml
import logging
from logging.handlers import RotatingFileHandler
import json
import random
import math
from collections import deque

# ===== ADD THIS IMPORT =====
from utils.helpers import enhance_low_light, apply_clahe_to_frame, adjust_gamma

# Load configuration
with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

# ===== LOAD PERSONALIZED CALIBRATION =====
CALIBRATION_FILE = 'calibration.json'
CALIBRATED_EAR_MEAN = 0.35
CALIBRATED_EAR_STD = 0.021
CALIBRATED_THRESHOLD = 0.25

if os.path.exists(CALIBRATION_FILE):
    try:
        with open(CALIBRATION_FILE, 'r') as f:
            calibration = json.load(f)
            CALIBRATED_EAR_MEAN = calibration.get('avg_ear', 0.35)
            CALIBRATED_EAR_STD = calibration.get('std_ear', 0.021)
            CALIBRATED_THRESHOLD = calibration.get('threshold', 0.25)
            print(f"✅ Loaded personalized calibration: Mean EAR={CALIBRATED_EAR_MEAN:.3f}, Std={CALIBRATED_EAR_STD:.3f}")
            print(f"📊 Personalized threshold: {CALIBRATED_THRESHOLD:.3f}")
    except Exception as e:
        print(f"⚠️ Could not load calibration: {e}")
else:
    print("⚠️ No calibration file found, using defaults")

# ===== NIGHT MODE CONFIGURATION =====
NIGHT_MODE_ENABLED = config.get('night_mode', {}).get('enabled', True)
NIGHT_MODE_GAMMA = config.get('night_mode', {}).get('gamma', 0.7)
NIGHT_MODE_CLIP_LIMIT = config.get('night_mode', {}).get('clahe_clip', 3.0)
NIGHT_MODE_BRIGHTNESS_THRESHOLD = config.get('night_mode', {}).get('brightness_threshold', 80)

# ===== GLASSES MODE CONFIGURATION =====
GLASSES_MODE_ENABLED = config.get('glasses', {}).get('mode_enabled', True)
GLASSES_CALIBRATION_EAR = config.get('glasses', {}).get('calibrated_ear', 0.354)
GLASSES_THRESHOLD_ADJUSTMENT = config.get('glasses', {}).get('threshold_adjustment', 0.85)

# ===== ADAPTIVE THRESHOLD CLASS =====
class AdaptiveThreshold:
    def __init__(self, base_threshold=0.25, window_size=300, adaptation_rate=0.05):
        self.base_threshold = base_threshold
        self.current_threshold = base_threshold
        self.window_size = window_size
        self.adaptation_rate = adaptation_rate
        self.ear_history = deque(maxlen=window_size)
        self.timestamp_history = deque(maxlen=window_size)
        self.confidence_history = deque(maxlen=window_size)
        self.last_update_time = time.time()
        self.update_interval = 30  # Update every 30 frames
        
    def update(self, ear_value, confidence=100, is_drowsy=False):
        """Update adaptive threshold based on recent EAR values"""
        # Only use non-drowsy, high-confidence values for calibration
        if not is_drowsy and confidence > 60 and ear_value > 0.15:
            self.ear_history.append(ear_value)
            self.confidence_history.append(confidence)
            
        # Update threshold periodically
        current_time = time.time()
        if len(self.ear_history) > 50 and (current_time - self.last_update_time) > 2:
            # Calculate rolling statistics
            recent_ears = list(self.ear_history)[-100:]
            mean_ear = np.mean(recent_ears)
            std_ear = np.std(recent_ears)
            
            # Dynamic threshold: mean - 2.5 * std (catches real drowsiness)
            # This is the optimal statistical threshold
            calculated_threshold = mean_ear - (2.5 * std_ear)
            
            # Clamp threshold between reasonable values
            clamped_threshold = max(0.18, min(0.32, calculated_threshold))
            
            # Smooth the threshold change to avoid oscillations
            self.current_threshold = (self.current_threshold * (1 - self.adaptation_rate) + 
                                     clamped_threshold * self.adaptation_rate)
            
            self.last_update_time = current_time
            
            # Debug output
            if random.random() < 0.05:  # Print occasionally
                print(f"📊 Adaptive Threshold: {self.current_threshold:.3f} | Mean EAR: {mean_ear:.3f} | Std: {std_ear:.3f}")
            
            return self.current_threshold
        
        return self.base_threshold
    
    def get_threshold(self):
        return self.current_threshold
    
    def reset(self):
        """Reset to base threshold"""
        self.current_threshold = self.base_threshold
        self.ear_history.clear()
        self.confidence_history.clear()

# Load fast alert config if exists
fast_alert_config = {}
if os.path.exists('fast_alert_config.json'):
    try:
        with open('fast_alert_config.json', 'r') as f:
            fast_alert_config = json.load(f)
            print(f"✅ Loaded fast alert configuration")
    except Exception as e:
        print(f"⚠️ Could not load fast_alert_config.json: {e}")
        fast_alert_config = {
            'ear_threshold': 0.25,
            'consecutive_frames': 6,
            'response_time_seconds': 0.2
        }
else:
    print("⚠️ fast_alert_config.json not found, using defaults")
    fast_alert_config = {
        'ear_threshold': 0.25,
        'consecutive_frames': 6,
        'response_time_seconds': 0.2
    }
    
print("\n" + "="*70)
print("🚀 DROWSINESS DETECTION SYSTEM - ADAPTIVE THRESHOLD VERSION")
print("="*70)
print(f"⚡ Response Time: {fast_alert_config.get('response_time_seconds', 0.2)} seconds")
print(f"🎯 Base EAR Threshold: {CALIBRATED_THRESHOLD:.3f}")
print(f"🔄 Adaptive Threshold: ENABLED")
print(f"📊 Consecutive Frames: {config['detection'].get('consecutive_frames', 6)}")
print(f"👓 Glasses Mode: {'ENABLED' if GLASSES_MODE_ENABLED else 'DISABLED'}")
print(f"🌙 Night Mode: {'ENABLED' if NIGHT_MODE_ENABLED else 'DISABLED'}")
print("="*70)

app = Flask(__name__)
app.config['SECRET_KEY'] = config.get('server', {}).get('secret_key', secrets.token_hex(32))
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Setup logging
if not os.path.exists('logs'):
    os.makedirs('logs')
handler = RotatingFileHandler('logs/app.log', maxBytes=10000000, backupCount=5)
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
handler.setLevel(logging.INFO)
app.logger.addHandler(handler)
app.logger.setLevel(logging.INFO)
app.logger.info('Drowsiness Detection startup - ADAPTIVE THRESHOLD VERSION')

print("✅ Flask app initialized")

# ============================================
# GLOBAL VARIABLES
# ============================================
camera = None
detector = None
predictor = None
detection_active = False
detection_thread = None
frame_queue = queue.Queue(maxsize=2)
current_ear = 0.0
current_mar = 0.0
faces_detected = 0
drowsy_counter = 0
yawn_counter = 0
alert_active = False
total_alerts = 0
alert_cooldown = 0
fps = 0
frame_count = 0
fps_timer = time.time()
stats_history = deque(maxlen=3600)
perclos_values = deque(maxlen=300)
start_time = None
current_head_tilt = 0.0
current_head_yaw = 0.0
current_head_pitch = 0.0
eye_status = "AWAKE"
glasses_detected = False
detection_mode = "STANDARD"
glasses_confidence = 0.0

# ===== BLINK DETECTION VARIABLES =====
blink_start_time = 0
blink_timer = 0
BLINK_IGNORE_FRAMES = 4 
last_closure_time = 0

# ===== GLASSES SMOOTHING HISTORY =====
glasses_history = deque(maxlen=10)

# ===== NIGHT MODE VARIABLES =====
night_mode_active = False
current_brightness = 0.0
enhancement_gain = 0.0

# PRIMARY FACE TRACKING
primary_face_id = None
face_tracking = {}

# Track last prediction state to avoid double recording
last_prediction_state = 0
last_recorded_ear = 0.0

# ===== ADAPTIVE THRESHOLD INSTANCE =====
adaptive_threshold = AdaptiveThreshold(
    base_threshold=CALIBRATED_THRESHOLD,
    window_size=300,
    adaptation_rate=0.03
)

# ============================================
# PERFORMANCE METRICS TRACKING
# ============================================
performance_metrics = {
    'tp': 0,
    'tn': 0,
    'fp': 0,
    'fn': 0,
    'predictions': deque(maxlen=1000),
    'ground_truth': deque(maxlen=1000),
    'ear_values': deque(maxlen=1000),
    'timestamps': deque(maxlen=1000),
    'response_times': deque(maxlen=100),
    'total_samples': 0,
    'face_detected_frames': 0,
    'no_face_frames': 0,
    'threshold_history': deque(maxlen=500)  # Track threshold changes
}

# Load previous metrics
METRICS_FILE = 'performance_metrics.json'
if os.path.exists(METRICS_FILE):
    try:
        with open(METRICS_FILE, 'r') as f:
            saved_metrics = json.load(f)
            for key in ['tp', 'tn', 'fp', 'fn', 'total_samples', 'face_detected_frames', 'no_face_frames']:
                if key in saved_metrics:
                    performance_metrics[key] = saved_metrics[key]
        print("✅ Loaded previous performance metrics")
    except Exception as e:
        print(f"⚠️ Could not load metrics: {e}")

# Alert parameters from config
EAR_THRESHOLD = CALIBRATED_THRESHOLD
MAR_THRESHOLD = config['detection'].get('mouth_ar_threshold', 0.6)
HEAD_TILT_THRESHOLD = config['detection']['head_tilt_threshold']
HEAD_PITCH_THRESHOLD = config['detection'].get('head_pitch_threshold', 20)
CONSECUTIVE_FRAMES = config['detection'].get('consecutive_frames', 8)
YAWN_CONSECUTIVE_FRAMES = config['detection'].get('yawn_consecutive_frames', 10)
ALERT_COOLDOWN = config['alerts'].get('cooldown', 5)
MIN_CONFIDENCE = config['detection'].get('min_confidence', 65)

print(f"⚡ PARAMETERS:")
print(f"   • Base EAR Threshold: {EAR_THRESHOLD:.3f}")
print(f"   • Adaptive Threshold: ENABLED")
print(f"   • MAR Threshold: {MAR_THRESHOLD:.2f}")
print(f"   • Head Tilt Threshold: {HEAD_TILT_THRESHOLD}°")
print(f"   • Head Pitch Threshold: {HEAD_PITCH_THRESHOLD}°")
print(f"   • Frames needed: {CONSECUTIVE_FRAMES}")
print(f"   • Min Confidence: {MIN_CONFIDENCE}%")
print(f"   • Blink ignore frames: {BLINK_IGNORE_FRAMES}")
print(f"   • Response time: ~{CONSECUTIVE_FRAMES/30:.2f} seconds")

# ============================================
# FACIAL LANDMARK INDICES
# ============================================
LEFT_EYE_START = 42
LEFT_EYE_END = 47
RIGHT_EYE_START = 36
RIGHT_EYE_END = 41
LEFT_EYE_INNER = 39
RIGHT_EYE_INNER = 42
LEFT_EYE_OUTER = 36
RIGHT_EYE_OUTER = 45
LEFT_EYEBROW = 21
RIGHT_EYEBROW = 22
NOSE_TIP = 30
NOSE_BRIDGE = 27
CHIN = 8
MOUTH_START = 48
MOUTH_END = 59

# ============================================
# ALARM SYSTEM
# ============================================
ALARM_FILES = [
    'alerts/wake_off.wav',
    'alerts/ultra_rapid.wav',
    'alerts/fire_alarm_intense.wav',
    'alerts/siren_alarm.wav',
    'static/sounds/alert_10sec_ultra.wav',
    'alerts/alert_long.wav',
    'static/sounds/long_alert.wav',
    'alerts/alert.wav',
    'static/sounds/alert.wav'
]

AVAILABLE_ALARMS = []
for alarm_file in ALARM_FILES:
    if os.path.exists(alarm_file):
        AVAILABLE_ALARMS.append(alarm_file)
        print(f"✅ Found alarm: {alarm_file}")

if not AVAILABLE_ALARMS:
    print("⚠️ No alarm files found, will use system beeps only")
else:
    print(f"🔊 {len(AVAILABLE_ALARMS)} alarm sounds available")

# ============================================
# CORE FUNCTIONS
# ============================================

def eye_aspect_ratio(eye):
    """Calculate the Eye Aspect Ratio (EAR)"""
    A = dist.euclidean(eye[1], eye[5])
    B = dist.euclidean(eye[2], eye[4])
    C = dist.euclidean(eye[0], eye[3])
    if C == 0:
        return 0.0
    ear = (A + B) / (2.0 * C)
    return max(0.05, min(ear, 0.45))

def extract_eye_region(gray_img, eye_points):
    """Extract just the eye region for pupil detection"""
    x_coords = [p[0] for p in eye_points]
    y_coords = [p[1] for p in eye_points]
    
    min_x = max(0, min(x_coords) - 5)
    max_x = min(gray_img.shape[1], max(x_coords) + 5)
    min_y = max(0, min(y_coords) - 5)
    max_y = min(gray_img.shape[0], max(y_coords) + 5)
    
    if min_x >= max_x or min_y >= max_y:
        return np.array([])
    
    return gray_img[min_y:max_y, min_x:max_x]

def detect_pupil(eye_roi):
    """Detect if pupil is visible (eye is open)"""
    if eye_roi.size == 0:
        return False
    
    try:
        circles = cv2.HoughCircles(
            eye_roi, 
            cv2.HOUGH_GRADIENT, 
            dp=1, 
            minDist=5,
            param1=50, 
            param2=30, 
            minRadius=2, 
            maxRadius=10
        )
        
        if circles is not None:
            return True
    except:
        pass
    
    try:
        blurred = cv2.GaussianBlur(eye_roi, (5, 5), 0)
        _, thresh = cv2.threshold(blurred, 50, 255, cv2.THRESH_BINARY_INV)
        
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        for contour in contours:
            area = cv2.contourArea(contour)
            if 10 < area < 200:
                perimeter = cv2.arcLength(contour, True)
                if perimeter > 0:
                    circularity = 4 * np.pi * area / (perimeter * perimeter)
                    if circularity > 0.6:
                        return True
    except:
        pass
    
    return False

def detect_eyes_with_glasses(landmarks, gray_img, glasses_detected=False):
    """
    Eye detection that accounts for glasses reflections
    """
    left_eye = landmarks[LEFT_EYE_START:LEFT_EYE_END + 1]
    right_eye = landmarks[RIGHT_EYE_START:RIGHT_EYE_END + 1]
    
    left_ear = eye_aspect_ratio(left_eye)
    right_ear = eye_aspect_ratio(right_eye)
    standard_ear = (left_ear + right_ear) / 2.0
    
    if glasses_detected and GLASSES_MODE_ENABLED:
        left_eye_roi = extract_eye_region(gray_img, left_eye)
        right_eye_roi = extract_eye_region(gray_img, right_eye)
        
        left_pupil_visible = detect_pupil(left_eye_roi)
        right_pupil_visible = detect_pupil(right_eye_roi)
        
        pupil_based_open = left_pupil_visible or right_pupil_visible
        
        glasses_ear_threshold = adaptive_threshold.get_threshold() * GLASSES_THRESHOLD_ADJUSTMENT
        
        is_closed = (standard_ear < glasses_ear_threshold) and not pupil_based_open
        
        confidence = 100 - (abs(standard_ear - glasses_ear_threshold) * 500)
        confidence = max(0, min(100, confidence))
        
        return is_closed, confidence, standard_ear
    else:
        current_threshold = adaptive_threshold.get_threshold()
        is_closed = standard_ear < current_threshold
        confidence = 100 - (abs(standard_ear - current_threshold) * 1000)
        confidence = max(0, min(100, confidence))
        return is_closed, confidence, standard_ear

def detect_eyes_closed_robust(landmarks, gray_img):
    """Robust eye closure detection using multiple methods"""
    left_eye = landmarks[LEFT_EYE_START:LEFT_EYE_END + 1]
    right_eye = landmarks[RIGHT_EYE_START:RIGHT_EYE_END + 1]
    
    left_ear = eye_aspect_ratio(left_eye)
    right_ear = eye_aspect_ratio(right_eye)
    standard_ear = (left_ear + right_ear) / 2.0
    
    left_center = np.mean(left_eye, axis=0).astype(int)
    right_center = np.mean(right_eye, axis=0).astype(int)
    
    h, w = gray_img.shape
    eye_h, eye_w = 15, 25
    
    left_roi = gray_img[
        max(0, left_center[1]-eye_h):min(h, left_center[1]+eye_h),
        max(0, left_center[0]-eye_w):min(w, left_center[0]+eye_w)
    ]
    right_roi = gray_img[
        max(0, right_center[1]-eye_h):min(h, right_center[1]+eye_h),
        max(0, right_center[0]-eye_w):min(w, right_center[0]+eye_w)
    ]
    
    left_intensity = np.mean(left_roi) if left_roi.size > 0 else 128
    right_intensity = np.mean(right_roi) if right_roi.size > 0 else 128
    avg_intensity = (left_intensity + right_intensity) / 2.0
    
    intensity_score = 1.0 - (avg_intensity / 255.0)
    
    def get_eye_opening(eye_points):
        top_y = min(eye_points[:, 1])
        bottom_y = max(eye_points[:, 1])
        return bottom_y - top_y
    
    left_opening = get_eye_opening(left_eye)
    right_opening = get_eye_opening(right_eye)
    avg_opening = (left_opening + right_opening) / 2.0
    
    opening_score = min(1.0, avg_opening / 12.0)
    
    def get_eye_contour_ratio(eye_points):
        width = dist.euclidean(eye_points[0], eye_points[3])
        height = (dist.euclidean(eye_points[1], eye_points[5]) + dist.euclidean(eye_points[2], eye_points[4])) / 2
        if width == 0:
            return 0
        return height / width
    
    left_ratio = get_eye_contour_ratio(left_eye)
    right_ratio = get_eye_contour_ratio(right_eye)
    contour_ratio = (left_ratio + right_ratio) / 2
    contour_score = 1.0 - min(1.0, contour_ratio / 0.3)
    
    ear_closure = 1.0 - min(1.0, standard_ear / 0.25)
    
    closure_score = (ear_closure * 0.35) + (intensity_score * 0.25) + ((1.0 - opening_score) * 0.25) + (contour_score * 0.15)
    
    is_closed = closure_score > 0.55
    
    if is_closed:
        estimated_ear = 0.12 + (closure_score - 0.55) * 0.1
        estimated_ear = min(0.18, max(0.08, estimated_ear))
    else:
        estimated_ear = standard_ear
    
    confidence = closure_score * 100
    
    return is_closed, confidence, estimated_ear

def mouth_aspect_ratio(mouth):
    """Calculate Mouth Aspect Ratio for yawn detection"""
    A = dist.euclidean(mouth[2], mouth[6])
    B = dist.euclidean(mouth[3], mouth[5])
    C = dist.euclidean(mouth[0], mouth[4])
    
    if C == 0:
        return 0.0
        
    mar = (A + B) / (2.0 * C)
    return mar

def get_head_tilt(landmarks):
    """Estimate head tilt angle from eye positions"""
    left_eye_outer = landmarks[LEFT_EYE_OUTER]
    left_eye_inner = landmarks[LEFT_EYE_INNER]
    right_eye_outer = landmarks[RIGHT_EYE_OUTER]
    right_eye_inner = landmarks[RIGHT_EYE_INNER]
    
    left_eye_center = ((left_eye_outer[0] + left_eye_inner[0]) // 2,
                       (left_eye_outer[1] + left_eye_inner[1]) // 2)
    right_eye_center = ((right_eye_outer[0] + right_eye_inner[0]) // 2,
                        (right_eye_outer[1] + right_eye_inner[1]) // 2)
    
    delta_x = right_eye_center[0] - left_eye_center[0]
    delta_y = right_eye_center[1] - left_eye_center[1]
    
    if delta_x == 0:
        return 0.0
    
    angle = np.degrees(np.arctan(delta_y / delta_x))
    return angle

def get_head_pitch(landmarks):
    """Estimate head pitch (nodding)"""
    nose = landmarks[NOSE_TIP]
    left_eye = landmarks[LEFT_EYE_OUTER]
    right_eye = landmarks[RIGHT_EYE_OUTER]
    
    eye_y = (left_eye[1] + right_eye[1]) // 2
    pitch = (nose[1] - eye_y) / 5
    return pitch

def get_head_yaw(landmarks):
    """Estimate head yaw (turning left/right)"""
    nose = landmarks[NOSE_TIP]
    left_eye = landmarks[LEFT_EYE_OUTER]
    right_eye = landmarks[RIGHT_EYE_OUTER]
    
    eye_x = (left_eye[0] + right_eye[0]) // 2
    yaw = (nose[0] - eye_x) / 5
    return yaw

def is_head_nodding(pitch_history):
    """Detect if head is nodding (falling asleep)"""
    if len(pitch_history) < 5:
        return False
    
    recent_pitch = list(pitch_history)[-5:]
    pitch_change = max(recent_pitch) - min(recent_pitch)
    return abs(pitch_change) > 10

# ============================================
# FACE TRACKING
# ============================================

def generate_face_id(face, frame_shape):
    """Generate unique ID for a face"""
    cx = face.left() + face.width() // 2
    cy = face.top() + face.height() // 2
    
    quant_cx = round(cx / 15)
    quant_cy = round(cy / 15)
    quant_size = round(face.width() / 15)
    
    return f"{quant_cx}_{quant_cy}_{quant_size}"

def calculate_face_score(face, frame_shape, tracking_data):
    """Calculate score for face priority"""
    h, w = frame_shape[:2]
    
    size_score = (face.width() * face.height()) / (w * h) * 100
    
    cx = face.left() + face.width() // 2
    cy = face.top() + face.height() // 2
    
    center_dist = np.sqrt(((cx - w//2) / (w/2))**2 + ((cy - h//2) / (h/2))**2)
    position_score = max(0, 100 - center_dist * 50)
    
    aspect_ratio = face.width() / face.height() if face.height() > 0 else 1
    shape_score = 100 if 0.8 < aspect_ratio < 1.2 else 50
    
    face_id = generate_face_id(face, frame_shape)
    if face_id in tracking_data:
        consistency_score = min(tracking_data[face_id]['count'] * 2, 100)
    else:
        consistency_score = 0
    
    total_score = (size_score * 0.4) + (position_score * 0.3) + (shape_score * 0.2) + (consistency_score * 0.1)
    
    return total_score

def select_primary_face(faces, frame_shape):
    """Select primary face to track"""
    global primary_face_id, face_tracking
    
    if len(faces) == 0:
        primary_face_id = None
        return None
    
    face_scores = []
    for face in faces:
        face_id = generate_face_id(face, frame_shape)
        score = calculate_face_score(face, frame_shape, face_tracking)
        face_scores.append((score, face, face_id))
    
    face_scores.sort(key=lambda x: x[0], reverse=True)
    best_score, best_face, best_face_id = face_scores[0]
    
    if best_face_id in face_tracking:
        face_tracking[best_face_id]['last_seen'] = time.time()
        face_tracking[best_face_id]['count'] += 1
    else:
        face_tracking[best_face_id] = {
            'last_seen': time.time(),
            'count': 1,
            'score': best_score
        }
    
    primary_face_id = best_face_id
    
    current_time = time.time()
    for fid in list(face_tracking.keys()):
        if current_time - face_tracking[fid]['last_seen'] > 5:
            del face_tracking[fid]
    
    return best_face

# ============================================
# DATABASE FUNCTIONS
# ============================================

def init_database():
    """Initialize SQLite database"""
    conn = sqlite3.connect(config['database']['path'])
    c = conn.cursor()
    
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ear_value REAL,
        mar_value REAL,
        head_tilt REAL,
        head_pitch REAL,
        head_yaw REAL,
        glasses_detected BOOLEAN,
        glasses_confidence REAL,
        detection_mode TEXT,
        duration INTEGER,
        response_time REAL,
        alarm_used TEXT,
        screenshot_path TEXT,
        user_id INTEGER,
        threshold_used REAL,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        end_time TIMESTAMP,
        avg_ear REAL,
        avg_mar REAL,
        avg_tilt REAL,
        avg_pitch REAL,
        alerts_count INTEGER,
        yawn_count INTEGER,
        glasses_percent REAL,
        user_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    admin_exists = c.execute("SELECT * FROM users WHERE username='admin'").fetchone()
    if not admin_exists:
        hashed = generate_password_hash('admin123')
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)",
                 ('admin', hashed))
        print("✅ Admin user created")
    
    if AVAILABLE_ALARMS:
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                 ('preferred_alarm', AVAILABLE_ALARMS[0]))
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                 ('alarm_volume', str(config['alerts']['volume'])))
    
    conn.commit()
    conn.close()
    print("✅ Database ready")

init_database()

# ============================================
# INITIALIZE DLIB
# ============================================

print("\n📷 Initializing dlib face detector...")
try:
    detector = dlib.get_frontal_face_detector()
    
    predictor_path = config['models']['landmark_predictor']
    if os.path.exists(predictor_path):
        predictor = dlib.shape_predictor(predictor_path)
        print("✅ dlib face detector and predictor loaded")
    else:
        print(f"❌ Landmark predictor not found at {predictor_path}")
        print("   Please run: python download_model.py")
        predictor = None
except Exception as e:
    print(f"❌ dlib initialization error: {e}")
    detector = None
    predictor = None

def init_camera():
    """Initialize camera"""
    global camera
    try:
        if camera is not None:
            camera.release()
        
        camera = cv2.VideoCapture(config['camera']['device_id'], cv2.CAP_DSHOW)
        camera.set(cv2.CAP_PROP_FRAME_WIDTH, config['camera']['width'])
        camera.set(cv2.CAP_PROP_FRAME_HEIGHT, config['camera']['height'])
        camera.set(cv2.CAP_PROP_FPS, config['camera']['fps'])
        camera.set(cv2.CAP_PROP_BUFFERSIZE, config['camera']['buffer_size'])
        
        if config['camera']['autofocus']:
            camera.set(cv2.CAP_PROP_AUTOFOCUS, 1)
        
        if config['camera']['auto_exposure']:
            camera.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
        
        if camera.isOpened():
            print("✅ Camera opened successfully")
            ret, frame = camera.read()
            if ret:
                print(f"✅ Test frame captured: {frame.shape}")
            return True
        else:
            print("❌ Cannot open camera")
            return False
    except Exception as e:
        print(f"❌ Camera error: {e}")
        return False

init_camera()

# ============================================
# ALERT SYSTEM
# ============================================

def play_enhanced_alert():
    """Play attention-grabbing fire alarm sound"""
    try:
        import winsound
        
        def play_alarm_thread():
            print("🔊 Attempting to play alarm...")
            
            wake_off_file = config['alerts']['sound_file']
            if os.path.exists(wake_off_file):
                print(f"🔊 Playing wake-off alarm: {wake_off_file}")
                try:
                    winsound.PlaySound(wake_off_file, winsound.SND_FILENAME)
                    return
                except Exception as e:
                    print(f"⚠️ Error playing wake-off alarm: {e}")
            
            if AVAILABLE_ALARMS:
                alarm_file = random.choice(AVAILABLE_ALARMS)
                print(f"🔊 Playing alarm: {alarm_file}")
                try:
                    winsound.PlaySound(alarm_file, winsound.SND_FILENAME)
                    return
                except Exception as e:
                    print(f"⚠️ Error playing alarm file: {e}")
            
            for i in range(10):
                freq = 1046 if i % 2 == 0 else 880
                winsound.Beep(freq, 200)
                time.sleep(0.1)
        
        threading.Thread(target=play_alarm_thread, daemon=True).start()
        
    except ImportError:
        print("⚠️ winsound not available")
        print("\a" * 10)

# ============================================
# PERFORMANCE METRICS FUNCTIONS
# ============================================

def record_prediction(ear_value, is_drowsy_predicted, actual_state=None, face_detected=True, threshold_used=None):
    """Record prediction for metrics"""
    global performance_metrics
    
    if not face_detected:
        return
    
    performance_metrics['face_detected_frames'] += 1
    
    if actual_state is None:
        actual_state = 1 if ear_value < adaptive_threshold.get_threshold() else 0
    
    performance_metrics['ear_values'].append(float(ear_value))
    performance_metrics['predictions'].append(int(is_drowsy_predicted))
    performance_metrics['ground_truth'].append(int(actual_state))
    performance_metrics['timestamps'].append(datetime.now().isoformat())
    performance_metrics['total_samples'] += 1
    
    if threshold_used:
        performance_metrics['threshold_history'].append(threshold_used)
    
    if is_drowsy_predicted == 1 and actual_state == 1:
        performance_metrics['tp'] += 1
        app.logger.debug(f"True Positive - EAR: {ear_value:.3f}")
    elif is_drowsy_predicted == 0 and actual_state == 0:
        performance_metrics['tn'] += 1
        app.logger.debug(f"True Negative - EAR: {ear_value:.3f}")
    elif is_drowsy_predicted == 1 and actual_state == 0:
        performance_metrics['fp'] += 1
        app.logger.warning(f"False Positive (False Alarm) - EAR: {ear_value:.3f}")
    elif is_drowsy_predicted == 0 and actual_state == 1:
        performance_metrics['fn'] += 1
        app.logger.warning(f"False Negative (Missed Drowsy) - EAR: {ear_value:.3f}")

def record_no_face_frame():
    """Record a frame with no face detected"""
    global performance_metrics
    performance_metrics['no_face_frames'] += 1

def record_response_time(response_time):
    """Record alert response time"""
    performance_metrics['response_times'].append(response_time)

def calculate_metrics():
    """Calculate performance metrics"""
    tp = performance_metrics['tp']
    tn = performance_metrics['tn']
    fp = performance_metrics['fp']
    fn = performance_metrics['fn']
    total = performance_metrics['total_samples']
    
    if total == 0:
        return {
            'accuracy': 0, 'precision': 0, 'recall': 0, 'f1_score': 0,
            'specificity': 0, 'false_positive_rate': 0, 'false_negative_rate': 0,
            'missed_drowsy': 0, 'false_alarms': 0,
            'avg_response_time': 0, 'total_samples': 0,
            'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0,
            'face_detected_frames': 0, 'no_face_frames': 0
        }
    
    accuracy = (tp + tn) / total * 100
    precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
    specificity = tn / (tn + fp) * 100 if (tn + fp) > 0 else 0
    
    f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
    
    fpr = fp / (fp + tn) * 100 if (fp + tn) > 0 else 0
    fnr = fn / (fn + tp) * 100 if (fn + tp) > 0 else 0
    
    avg_response = np.mean(list(performance_metrics['response_times'])) if performance_metrics['response_times'] else 0
    
    return {
        'accuracy': round(accuracy, 2),
        'precision': round(precision, 2),
        'recall': round(recall, 2),
        'f1_score': round(f1_score, 2),
        'specificity': round(specificity, 2),
        'false_positive_rate': round(fpr, 2),
        'false_negative_rate': round(fnr, 2),
        'missed_drowsy': fn,
        'false_alarms': fp,
        'avg_response_time': round(avg_response, 3),
        'total_samples': total,
        'tp': tp, 'tn': tn, 'fp': fp, 'fn': fn,
        'face_detected_frames': performance_metrics['face_detected_frames'],
        'no_face_frames': performance_metrics['no_face_frames']
    }

def save_metrics_to_file():
    """Save metrics to JSON file"""
    metrics = calculate_metrics()
    metrics['last_updated'] = datetime.now().isoformat()
    metrics['ear_threshold'] = adaptive_threshold.get_threshold()
    metrics['consecutive_frames'] = CONSECUTIVE_FRAMES
    metrics['adaptive_enabled'] = True
    
    with open(METRICS_FILE, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    return metrics

# ============================================
# USER CLASS
# ============================================

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username
    
    def get_id(self):
        return str(self.id)

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(config['database']['path'])
    c = conn.cursor()
    user = c.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    if user:
        return User(user[0], user[1])
    return None

# ============================================
# DETECTION LOOP - ADAPTIVE THRESHOLD VERSION
# ============================================

def detection_loop():
    """Main detection loop with adaptive thresholding"""
    global detection_active, current_ear, current_mar, faces_detected, drowsy_counter, yawn_counter
    global alert_active, total_alerts, alert_cooldown, fps, frame_count
    global fps_timer, stats_history, perclos_values, start_time
    global current_head_tilt, current_head_yaw, current_head_pitch, eye_status
    global glasses_detected, detection_mode, primary_face_id, glasses_confidence
    global night_mode_active, current_brightness, enhancement_gain
    global last_prediction_state, last_recorded_ear
    global blink_start_time, blink_timer, last_closure_time
    
    print("\n🔵 DETECTION LOOP STARTED - ADAPTIVE THRESHOLD VERSION")
    print(f"⚡ Base Threshold: {EAR_THRESHOLD:.3f}")
    print(f"🔄 Adaptive Threshold: ENABLED")
    print(f"⚡ Consecutive frames needed: {CONSECUTIVE_FRAMES}")
    print(f"👓 Glasses mode: {'ENABLED' if GLASSES_MODE_ENABLED else 'DISABLED'}")
    print(f"🌙 Night mode: {'ENABLED' if NIGHT_MODE_ENABLED else 'DISABLED'}")
    start_time = datetime.now()
    
    fps_counter = 0
    closed_frames = 0
    yawn_frames = 0
    total_frames = 0
    ear_history = deque(maxlen=5)
    mar_history = deque(maxlen=5)
    pitch_history = deque(maxlen=15)
    
    last_prediction_state = 0
    last_recorded_ear = 0.0
    blink_start_time = 0
    
    while detection_active:
        try:
            if camera and camera.isOpened() and predictor is not None:
                ret, frame = camera.read()
                
                if ret:
                    frame_count += 1
                    total_frames += 1
                    
                    if config['performance']['downsample_ratio'] < 1.0:
                        new_width = int(frame.shape[1] * config['performance']['downsample_ratio'])
                        new_height = int(frame.shape[0] * config['performance']['downsample_ratio'])
                        frame = cv2.resize(frame, (new_width, new_height))
                    
                    original_frame = frame.copy()
                    
                    if NIGHT_MODE_ENABLED:
                        enhanced_frame = enhance_low_light(
                            frame, 
                            gamma=NIGHT_MODE_GAMMA,
                            clip_limit=NIGHT_MODE_CLIP_LIMIT,
                            brightness_threshold=NIGHT_MODE_BRIGHTNESS_THRESHOLD
                        )
                        
                        if enhanced_frame is not frame:
                            night_mode_active = True
                            gray_original = cv2.cvtColor(original_frame, cv2.COLOR_BGR2GRAY)
                            gray_enhanced = cv2.cvtColor(enhanced_frame, cv2.COLOR_BGR2GRAY)
                            original_brightness = np.mean(gray_original)
                            enhanced_brightness = np.mean(gray_enhanced)
                            current_brightness = enhanced_brightness
                            
                            if original_brightness > 0:
                                enhancement_gain = ((enhanced_brightness - original_brightness) / original_brightness) * 100
                            else:
                                enhancement_gain = 0
                                
                            frame = enhanced_frame
                        else:
                            night_mode_active = False
                            current_brightness = np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
                            enhancement_gain = 0
                    else:
                        night_mode_active = False
                        current_brightness = np.mean(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY))
                        enhancement_gain = 0
                    
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    gray = cv2.equalizeHist(gray)
                    
                    faces = detector(gray, 0)
                    faces_detected = len(faces)
                    
                    face_detected_this_frame = faces_detected > 0
                    
                    if not face_detected_this_frame:
                        record_no_face_frame()
                        drowsy_counter = max(0, drowsy_counter - 1)
                        eye_status = "NO FACE"
                        last_prediction_state = 0
                        blink_start_time = 0
                    else:
                        primary_face = select_primary_face(faces, frame.shape)
                        
                        if primary_face is not None:
                            landmarks = predictor(gray, primary_face)
                            
                            points = np.zeros((68, 2), dtype=int)
                            for i in range(68):
                                points[i] = (landmarks.part(i).x, landmarks.part(i).y)
                            
                            # Get current adaptive threshold
                            current_threshold = adaptive_threshold.get_threshold()
                            
                            # Eye closure detection
                            if GLASSES_MODE_ENABLED:
                                is_closed, closure_confidence, robust_ear = detect_eyes_with_glasses(
                                    points, gray, glasses_detected
                                )
                            else:
                                is_closed, closure_confidence, robust_ear = detect_eyes_closed_robust(points, gray)
                            
                            left_eye = points[LEFT_EYE_START:LEFT_EYE_END + 1]
                            right_eye = points[RIGHT_EYE_START:RIGHT_EYE_END + 1]
                            left_ear = eye_aspect_ratio(left_eye)
                            right_ear = eye_aspect_ratio(right_eye)
                            standard_ear = (left_ear + right_ear) / 2.0
                            
                            ear_history.append(robust_ear)
                            smoothed_ear = sum(ear_history) / len(ear_history)
                            
                            mouth = points[MOUTH_START:MOUTH_END + 1]
                            mar = mouth_aspect_ratio(mouth)
                            mar_history.append(mar)
                            smoothed_mar = sum(mar_history) / len(mar_history)
                            
                            head_tilt = get_head_tilt(points)
                            head_pitch = get_head_pitch(points)
                            head_yaw = get_head_yaw(points)
                            pitch_history.append(head_pitch)
                            
                            # Update adaptive threshold periodically
                            if frame_count % 30 == 0:
                                adaptive_threshold.update(smoothed_ear, closure_confidence, 
                                                         drowsy_counter >= CONSECUTIVE_FRAMES)
                                current_threshold = adaptive_threshold.get_threshold()
                                
                                # Log threshold changes
                                if random.random() < 0.1:
                                    print(f"📊 Current Adaptive Threshold: {current_threshold:.3f}")
                            
                            if smoothed_mar > MAR_THRESHOLD:
                                yawn_frames += 1
                            else:
                                yawn_frames = max(0, yawn_frames - 1)
                            
                            if yawn_frames >= YAWN_CONSECUTIVE_FRAMES:
                                yawn_counter += 1
                                socketio.emit('yawn_detected', {
                                    'mar': float(smoothed_mar),
                                    'timestamp': datetime.now().isoformat()
                                })
                            
                            x, y, w, h = primary_face.left(), primary_face.top(), primary_face.width(), primary_face.height()
                            
                            eyes_closed = is_closed or (standard_ear < current_threshold)
                            head_down = abs(head_pitch) > HEAD_PITCH_THRESHOLD
                            is_nodding = is_head_nodding(pitch_history)
                            
                            if eyes_closed or head_down or is_nodding:
                                if eyes_closed:
                                    if blink_start_time == 0:
                                        blink_start_time = time.time()
                                    
                                    closure_duration = time.time() - blink_start_time
                                    
                                    if closure_duration > (BLINK_IGNORE_FRAMES / 30):
                                        drowsy_counter += 1
                                        closed_frames += 1
                                else:
                                    blink_start_time = 0
                                    drowsy_counter = max(0, drowsy_counter - 1)
                                
                                if eyes_closed:
                                    eye_status = "EYES CLOSED"
                                elif head_down:
                                    eye_status = "HEAD DOWN"
                                else:
                                    eye_status = "NODDING"
                                
                                status_color = (0, 0, 255)
                                
                                current_prediction = 1 if drowsy_counter >= CONSECUTIVE_FRAMES else 0
                                
                                if current_prediction != last_prediction_state:
                                    record_prediction(smoothed_ear, current_prediction, 
                                                    face_detected=True, threshold_used=current_threshold)
                                    last_prediction_state = current_prediction
                                    last_recorded_ear = smoothed_ear
                                
                                if (drowsy_counter >= CONSECUTIVE_FRAMES and 
                                    not alert_active and 
                                    alert_cooldown <= 0 and
                                    closure_confidence >= MIN_CONFIDENCE):
                                    
                                    alert_active = True
                                    total_alerts += 1
                                    alert_cooldown = ALERT_COOLDOWN * 30
                                    
                                    response_time = CONSECUTIVE_FRAMES/30
                                    
                                    print(f"\n🚨 ALERT #{total_alerts} - {eye_status} detected!")
                                    print(f"   EAR: {smoothed_ear:.3f} | Threshold: {current_threshold:.3f}")
                                    print(f"   Counter: {drowsy_counter}/{CONSECUTIVE_FRAMES}")
                                    print(f"   Confidence: {closure_confidence:.0f}%")
                                    
                                    record_response_time(response_time)
                                    
                                    if config['alerts']['sound']:
                                        print("🔊 Triggering alarm...")
                                        threading.Thread(target=play_enhanced_alert, daemon=True).start()
                                    
                                    if config['storage']['save_screenshots']:
                                        save_screenshot(frame, total_alerts)
                                    
                                    alarm_used = config['alerts']['sound_file'] if os.path.exists(config['alerts']['sound_file']) else "system_beep"
                                    save_alert_to_db(smoothed_ear, smoothed_mar, drowsy_counter, head_tilt, head_pitch, head_yaw,
                                                   glasses_detected, glasses_confidence, detection_mode, response_time, alarm_used,
                                                   current_threshold)
                                    
                                    socketio.emit('drowsy_alert', {
                                        'ear': float(smoothed_ear),
                                        'mar': float(smoothed_mar),
                                        'head_tilt': float(head_tilt),
                                        'head_pitch': float(head_pitch),
                                        'head_yaw': float(head_yaw),
                                        'glasses': glasses_detected,
                                        'glasses_confidence': glasses_confidence,
                                        'mode': detection_mode,
                                        'status': eye_status,
                                        'alert_id': total_alerts,
                                        'response_time': response_time,
                                        'night_mode': night_mode_active,
                                        'enhancement_gain': float(enhancement_gain),
                                        'threshold_used': round(current_threshold, 3)
                                    })
                            else:
                                eye_status = "AWAKE"
                                drowsy_counter = max(0, drowsy_counter - 1)
                                status_color = (0, 255, 0)
                                blink_start_time = 0
                                
                                current_prediction = 0
                                if current_prediction != last_prediction_state:
                                    record_prediction(current_ear, current_prediction, face_detected=True)
                                    last_prediction_state = current_prediction
                            
                            # Draw UI elements
                            if drowsy_counter >= CONSECUTIVE_FRAMES:
                                rect_color = (0, 0, 255)
                            elif drowsy_counter > 0:
                                rect_color = (0, 165, 255)
                            else:
                                rect_color = (0, 255, 0)
                            
                            cv2.rectangle(frame, (x, y), (x+w, y+h), rect_color, 3)
                            cv2.putText(frame, eye_status, (x, y-10), 
                                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
                            
                            for i in range(LEFT_EYE_START, LEFT_EYE_END + 1):
                                cv2.circle(frame, (points[i][0], points[i][1]), 2, (0, 255, 0), -1)
                            for i in range(RIGHT_EYE_START, RIGHT_EYE_END + 1):
                                cv2.circle(frame, (points[i][0], points[i][1]), 2, (0, 255, 0), -1)
                            
                            current_ear = smoothed_ear
                            current_mar = smoothed_mar
                            current_head_tilt = head_tilt
                            current_head_pitch = head_pitch
                            current_head_yaw = head_yaw
                        else:
                            drowsy_counter = max(0, drowsy_counter - 1)
                            eye_status = "NO FACE"
                    
                    if alert_cooldown > 0:
                        alert_cooldown -= 1
                    else:
                        alert_active = False
                    
                    if total_frames > 0:
                        perclos = (closed_frames / total_frames) * 100
                        perclos_values.append(perclos)
                    
                    # HUD
                    cv2.putText(frame, f"EAR: {current_ear:.3f}", (10, 30),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.putText(frame, f"Threshold: {adaptive_threshold.get_threshold():.3f}", (10, 60),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                    cv2.putText(frame, f"MAR: {current_mar:.3f}", (10, 90),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                    cv2.putText(frame, f"Tilt: {current_head_tilt:.1f}°", (10, 120),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 165, 0), 2)
                    cv2.putText(frame, f"Faces: {faces_detected}", (10, 150),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                    
                    if drowsy_counter >= CONSECUTIVE_FRAMES:
                        counter_color = (0, 0, 255)
                    elif drowsy_counter > 0:
                        counter_color = (0, 165, 255)
                    else:
                        counter_color = (0, 255, 0)
                    
                    cv2.putText(frame, f"Counter: {drowsy_counter}/{CONSECUTIVE_FRAMES}", (10, 180),
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, counter_color, 2)
                    
                    if night_mode_active:
                        cv2.putText(frame, f"NIGHT MODE: +{enhancement_gain:.0f}%", (10, 240),
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
                    
                    if drowsy_counter >= CONSECUTIVE_FRAMES:
                        cv2.putText(frame, "!!! DROWSY ALERT !!!", (150, 150),
                                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
                    
                    fps_counter += 1
                    if time.time() - fps_timer >= 1:
                        fps = fps_counter
                        fps_counter = 0
                        fps_timer = time.time()
                        
                        stats = {
                            'timestamp': datetime.now().isoformat(),
                            'ear': float(current_ear),
                            'threshold': adaptive_threshold.get_threshold(),
                            'mar': float(current_mar),
                            'head_tilt': float(current_head_tilt),
                            'head_pitch': float(current_head_pitch),
                            'head_yaw': float(current_head_yaw),
                            'glasses': glasses_detected,
                            'faces': int(faces_detected),
                            'fps': fps,
                            'perclos': perclos if total_frames > 0 else 0,
                            'counter': drowsy_counter,
                            'status': eye_status,
                            'night_mode': night_mode_active
                        }
                        stats_history.append(stats)
                        
                        if frame_count % 100 == 0:
                            save_metrics_to_file()
                        
                        socketio.emit('detection_update', {
                            'current_ear': float(current_ear),
                            'current_threshold': adaptive_threshold.get_threshold(),
                            'current_mar': float(current_mar),
                            'current_tilt': float(current_head_tilt),
                            'current_pitch': float(current_head_pitch),
                            'current_yaw': float(current_head_yaw),
                            'glasses_detected': glasses_detected,
                            'faces_detected': int(faces_detected),
                            'is_drowsy': bool(drowsy_counter >= CONSECUTIVE_FRAMES),
                            'eye_status': eye_status,
                            'fps': fps,
                            'perclos': perclos if total_frames > 0 else 0,
                            'total_alerts': total_alerts,
                            'drowsy_counter': drowsy_counter,
                            'threshold_frames': CONSECUTIVE_FRAMES,
                            'night_mode': night_mode_active,
                            'current_brightness': float(current_brightness),
                            'enhancement_gain': float(enhancement_gain)
                        })
                    
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if ret:
                        if frame_queue.full():
                            frame_queue.get()
                        frame_queue.put(buffer.tobytes())
                    
                    if config['performance']['skip_frames'] > 0:
                        for _ in range(config['performance']['skip_frames']):
                            camera.read()
                    
                    time.sleep(0.01)
                else:
                    time.sleep(0.1)
            else:
                init_camera()
                time.sleep(2)
        except Exception as e:
            print(f"❌ Loop error: {e}")
            app.logger.error(f"Detection loop error: {e}")
            time.sleep(0.1)
    
    print("🔴 DETECTION LOOP STOPPED")

def save_screenshot(frame, alert_id):
    """Save alert screenshot"""
    try:
        screenshot_dir = config['storage']['screenshot_dir']
        os.makedirs(screenshot_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{screenshot_dir}/alert_{alert_id}_{timestamp}.jpg"
        cv2.imwrite(filename, frame)
        app.logger.info(f"Screenshot saved: {filename}")
        return filename
    except Exception as e:
        app.logger.error(f"Failed to save screenshot: {e}")
        return None

def save_alert_to_db(ear_value, mar_value, duration, head_tilt, head_pitch, head_yaw, 
                     glasses, glasses_conf, mode, response_time, alarm_used="default", threshold_used=None):
    """Save alert to database"""
    try:
        conn = sqlite3.connect(config['database']['path'])
        c = conn.cursor()
        
        c.execute("PRAGMA table_info(alerts)")
        columns = [col[1] for col in c.fetchall()]
        
        base_cols = ['ear_value', 'mar_value', 'duration', 'head_tilt', 'head_pitch', 'head_yaw', 
                    'glasses_detected', 'user_id']
        base_vals = [ear_value, mar_value, duration, head_tilt, head_pitch, head_yaw, glasses, 1]
        
        extra_cols = []
        extra_vals = []
        
        if 'glasses_confidence' in columns:
            extra_cols.append('glasses_confidence')
            extra_vals.append(glasses_conf)
        
        if 'detection_mode' in columns:
            extra_cols.append('detection_mode')
            extra_vals.append(mode)
        
        if 'response_time' in columns:
            extra_cols.append('response_time')
            extra_vals.append(response_time)
        
        if 'alarm_used' in columns:
            extra_cols.append('alarm_used')
            extra_vals.append(alarm_used)
        
        if 'threshold_used' in columns and threshold_used:
            extra_cols.append('threshold_used')
            extra_vals.append(threshold_used)
        
        all_cols = base_cols + extra_cols
        placeholders = ','.join(['?' for _ in all_cols])
        all_vals = base_vals + extra_vals
        
        query = f"INSERT INTO alerts ({','.join(all_cols)}) VALUES ({placeholders})"
        
        c.execute(query, all_vals)
        conn.commit()
        conn.close()
        print(f"✅ Alert saved to DB")
        return True
        
    except Exception as e:
        print(f"❌ Failed to save alert to DB: {e}")
        try:
            conn = sqlite3.connect(config['database']['path'])
            c = conn.cursor()
            c.execute("""INSERT INTO alerts (ear_value, mar_value, duration, head_tilt, head_pitch, head_yaw, glasses_detected, user_id) 
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                     (ear_value, mar_value, duration, head_tilt, head_pitch, head_yaw, glasses, 1))
            conn.commit()
            conn.close()
            print("✅ Alert saved with minimal fields")
            return True
        except Exception as e2:
            print(f"❌ Even minimal insert failed: {e2}")
            return False

# ============================================
# ROUTES
# ============================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/analytics')
@login_required
def analytics():
    return render_template('analytics.html', user=current_user)

@app.route('/settings')
@login_required
def settings():
    return render_template('settings.html', user=current_user)

@app.route('/calibrate', methods=['GET', 'POST'])
@login_required
def calibrate():
    return render_template('calibrate.html', user=current_user)

@app.route('/metrics')
@login_required
def metrics_dashboard():
    return render_template('metrics_dashboard.html', user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember', False)
        
        conn = sqlite3.connect(config['database']['path'])
        c = conn.cursor()
        user = c.execute("SELECT id, username, password_hash FROM users WHERE username = ?", 
                        (username,)).fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], password):
            login_user(User(user[0], user[1]), remember=remember)
            app.logger.info(f"User {username} logged in")
            return redirect(url_for('dashboard'))
        
        return render_template('login.html', error='Invalid credentials')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/video_feed')
@login_required
def video_feed():
    def generate():
        while True:
            try:
                if not frame_queue.empty():
                    frame_data = frame_queue.get()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_data + b'\r\n')
                else:
                    time.sleep(0.03)
            except:
                break
    
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

# ============================================
# API ENDPOINTS
# ============================================

@app.route('/api/start', methods=['POST'])
@login_required
def start_detection():
    global detection_active, detection_thread, drowsy_counter, alert_active, alert_cooldown, start_time
    global last_prediction_state, blink_start_time, adaptive_threshold
    
    if detector is None or predictor is None:
        return jsonify({'status': 'error', 'message': 'Face detector not loaded'})
    
    if not camera or not camera.isOpened():
        if not init_camera():
            return jsonify({'status': 'error', 'message': 'Camera not available'})
    
    if not detection_active:
        detection_active = True
        drowsy_counter = 0
        alert_active = False
        alert_cooldown = 0
        last_prediction_state = 0
        blink_start_time = 0
        adaptive_threshold.reset()  # Reset adaptive threshold on start
        start_time = datetime.now()
        detection_thread = threading.Thread(target=detection_loop, daemon=True)
        detection_thread.start()
        app.logger.info("Detection started - ADAPTIVE THRESHOLD VERSION")
        return jsonify({'status': 'success', 'mode': 'adaptive', 'response_time': f"{CONSECUTIVE_FRAMES/30:.2f}s"})
    
    return jsonify({'status': 'error', 'message': 'Already running'})

@app.route('/api/stop', methods=['POST'])
@login_required
def stop_detection():
    global detection_active
    detection_active = False
    return jsonify({'status': 'success'})

@app.route('/api/status')
@login_required
def get_status():
    global start_time
    
    uptime = 0
    if start_time and detection_active:
        uptime = (datetime.now() - start_time).total_seconds() / 60
    
    face_confidence_val = face_tracking.get(primary_face_id, {}).get('score', 0) if primary_face_id else 0
    
    return jsonify({
        'active': detection_active,
        'stats': {
            'current_ear': float(current_ear),
            'current_threshold': adaptive_threshold.get_threshold(),
            'current_mar': float(current_mar),
            'current_tilt': float(current_head_tilt),
            'current_pitch': float(current_head_pitch),
            'current_yaw': float(current_head_yaw),
            'glasses_detected': glasses_detected,
            'glasses_confidence': round(glasses_confidence, 1),
            'detection_mode': detection_mode,
            'eye_status': eye_status,
            'faces_detected': int(faces_detected),
            'is_drowsy': bool(drowsy_counter >= CONSECUTIVE_FRAMES),
            'is_yawning': bool(current_mar > MAR_THRESHOLD),
            'fps': fps,
            'total_alerts': total_alerts,
            'uptime': round(uptime, 1),
            'drowsy_counter': drowsy_counter,
            'threshold_frames': CONSECUTIVE_FRAMES,
            'face_confidence': round(face_confidence_val, 1),
            'night_mode': night_mode_active,
            'current_brightness': round(current_brightness, 1),
            'enhancement_gain': round(enhancement_gain, 1),
            'adaptive_enabled': True,
            'calibrated_mean': CALIBRATED_EAR_MEAN
        },
        'detector_ready': detector is not None and predictor is not None,
        'camera_ready': camera is not None and camera.isOpened(),
        'alarms_available': len(AVAILABLE_ALARMS),
        'adaptive_config': {
            'enabled': True,
            'base_threshold': EAR_THRESHOLD,
            'current_threshold': adaptive_threshold.get_threshold(),
            'window_size': 300,
            'adaptation_rate': 0.03
        }
    })

@app.route('/api/reset_threshold', methods=['POST'])
@login_required
def reset_threshold():
    """Reset adaptive threshold to base value"""
    global adaptive_threshold
    adaptive_threshold.reset()
    return jsonify({
        'status': 'success',
        'threshold': adaptive_threshold.get_threshold(),
        'message': 'Threshold reset to base value'
    })

@app.route('/api/calibrate_threshold', methods=['POST'])
@login_required
def calibrate_threshold():
    """Manually calibrate threshold based on recent data"""
    data = request.json
    ear_values = data.get('ear_values', [])
    
    if len(ear_values) > 10:
        mean_ear = np.mean(ear_values)
        std_ear = np.std(ear_values)
        
        optimal_threshold = mean_ear - (2.5 * std_ear)
        optimal_threshold = max(0.18, min(0.32, optimal_threshold))
        
        # Update adaptive threshold
        adaptive_threshold.base_threshold = optimal_threshold
        adaptive_threshold.current_threshold = optimal_threshold
        
        return jsonify({
            'status': 'success',
            'mean_ear': round(mean_ear, 3),
            'std_ear': round(std_ear, 3),
            'new_threshold': round(optimal_threshold, 3),
            'message': f'Threshold calibrated to {optimal_threshold:.3f}'
        })
    
    return jsonify({'status': 'error', 'message': f'Need more data. Got {len(ear_values)} samples'})

@app.route('/api/night_mode', methods=['POST'])
@login_required
def toggle_night_mode():
    global NIGHT_MODE_ENABLED
    
    data = request.json
    if 'enabled' in data:
        NIGHT_MODE_ENABLED = data['enabled']
        app.logger.info(f"Night mode {'enabled' if NIGHT_MODE_ENABLED else 'disabled'}")
        
        config['night_mode']['enabled'] = NIGHT_MODE_ENABLED
        with open('config.yaml', 'w') as f:
            yaml.dump(config, f)
        
        return jsonify({'status': 'success', 'night_mode': NIGHT_MODE_ENABLED})
    
    return jsonify({'status': 'error', 'message': 'Missing enabled parameter'})

@app.route('/api/glasses_mode', methods=['POST'])
@login_required
def toggle_glasses_mode():
    global GLASSES_MODE_ENABLED
    
    data = request.json
    GLASSES_MODE_ENABLED = data.get('enabled', False)
    
    config['glasses'] = config.get('glasses', {})
    config['glasses']['mode_enabled'] = GLASSES_MODE_ENABLED
    
    with open('config.yaml', 'w') as f:
        yaml.dump(config, f)
    
    return jsonify({'status': 'success', 'glasses_mode': GLASSES_MODE_ENABLED})

@app.route('/api/alarms')
@login_required
def get_alarms():
    return jsonify({
        'available_alarms': AVAILABLE_ALARMS,
        'count': len(AVAILABLE_ALARMS),
        'current_alarm': config['alerts']['sound_file']
    })

@app.route('/api/test_alarm', methods=['POST'])
@login_required
def test_alarm():
    threading.Thread(target=play_enhanced_alert, daemon=True).start()
    return jsonify({'status': 'success', 'message': 'Alarm test triggered'})

@app.route('/api/history')
@login_required
def get_history():
    return jsonify({'history': list(stats_history)[-300:]})

@app.route('/api/alerts')
@login_required
def get_alerts():
    conn = sqlite3.connect(config['database']['path'])
    c = conn.cursor()
    
    try:
        alerts = c.execute("""SELECT timestamp, ear_value, mar_value, head_tilt, head_pitch, head_yaw, 
                                    glasses_detected, glasses_confidence, detection_mode, duration, 
                                    response_time, alarm_used, threshold_used 
                             FROM alerts 
                             WHERE user_id = ? 
                             ORDER BY timestamp DESC 
                             LIMIT 50""", (1,)).fetchall()
    except sqlite3.OperationalError:
        alerts = c.execute("""SELECT timestamp, ear_value, mar_value, head_tilt, head_pitch, head_yaw, 
                                    glasses_detected, duration 
                             FROM alerts 
                             WHERE user_id = ? 
                             ORDER BY timestamp DESC 
                             LIMIT 50""", (1,)).fetchall()
        alerts = [list(a) + [None, None, None, None, None] for a in alerts]
    
    conn.close()
    
    return jsonify({
        'alerts': [{
            'timestamp': a[0],
            'ear': a[1],
            'mar': a[2] if len(a) > 2 else 0,
            'head_tilt': a[3] if len(a) > 3 else 0,
            'head_pitch': a[4] if len(a) > 4 else 0,
            'head_yaw': a[5] if len(a) > 5 else 0,
            'glasses_detected': bool(a[6]) if len(a) > 6 else False,
            'glasses_confidence': a[7] if len(a) > 7 else 0,
            'detection_mode': a[8] if len(a) > 8 else 'ADAPTIVE',
            'duration': a[9] if len(a) > 9 else 0,
            'response_time': a[10] if len(a) > 10 else 0.1,
            'alarm_used': a[11] if len(a) > 11 else 'default',
            'threshold_used': a[12] if len(a) > 12 else None
        } for a in alerts]
    })

@app.route('/api/sessions')
@login_required
def get_sessions():
    conn = sqlite3.connect(config['database']['path'])
    c = conn.cursor()
    sessions = c.execute("""SELECT start_time, end_time, avg_ear, avg_mar, avg_tilt, avg_pitch, 
                                  alerts_count, yawn_count, glasses_percent 
                           FROM sessions 
                           WHERE user_id = ? 
                           ORDER BY start_time DESC 
                           LIMIT 10""", (1,)).fetchall()
    conn.close()
    
    return jsonify({
        'sessions': [{
            'start': s[0],
            'end': s[1],
            'avg_ear': s[2],
            'avg_mar': s[3],
            'avg_tilt': s[4],
            'avg_pitch': s[5],
            'alerts': s[6],
            'yawns': s[7],
            'glasses_percent': s[8]
        } for s in sessions]
    })

@app.route('/api/stats/summary')
@login_required
def get_stats_summary():
    conn = sqlite3.connect(config['database']['path'])
    c = conn.cursor()
    
    total = c.execute("SELECT COUNT(*) FROM alerts WHERE user_id = ?", (1,)).fetchone()[0] or 0
    avg_ear = c.execute("SELECT AVG(ear_value) FROM alerts WHERE user_id = ?", (1,)).fetchone()[0] or 0
    avg_mar = c.execute("SELECT AVG(mar_value) FROM alerts WHERE user_id = ?", (1,)).fetchone()[0] or 0
    avg_tilt = c.execute("SELECT AVG(head_tilt) FROM alerts WHERE user_id = ?", (1,)).fetchone()[0] or 0
    avg_pitch = c.execute("SELECT AVG(head_pitch) FROM alerts WHERE user_id = ?", (1,)).fetchone()[0] or 0
    
    today = datetime.now().strftime('%Y-%m-%d')
    today_count = c.execute("""SELECT COUNT(*) FROM alerts 
                              WHERE user_id = ? AND DATE(timestamp) = ?""", (1, today)).fetchone()[0] or 0
    
    glasses_count = c.execute("""SELECT COUNT(*) FROM alerts 
                                WHERE user_id = ? AND glasses_detected = 1""", (1,)).fetchone()[0] or 0
    
    yawn_count = c.execute("SELECT COUNT(*) FROM alerts WHERE user_id = ? AND mar_value > ?", 
                          (1, MAR_THRESHOLD)).fetchone()[0] or 0
    
    avg_response = c.execute("SELECT AVG(response_time) FROM alerts WHERE user_id = ?", (1,)).fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        'total_alerts': total,
        'avg_ear': round(avg_ear, 3),
        'avg_mar': round(avg_mar, 3),
        'avg_tilt': round(avg_tilt, 1),
        'avg_pitch': round(avg_pitch, 1),
        'today_alerts': today_count,
        'glasses_alerts': glasses_count,
        'yawn_alerts': yawn_count,
        'avg_response_time': round(avg_response, 3),
        'glasses_percent': round((glasses_count / total * 100) if total > 0 else 0, 1),
        'current_threshold': adaptive_threshold.get_threshold(),
        'base_threshold': EAR_THRESHOLD,
        'frames_needed': CONSECUTIVE_FRAMES,
        'adaptive_enabled': True
    })

@app.route('/api/metrics')
@login_required
def get_metrics():
    metrics = calculate_metrics()
    
    tp = metrics['tp']
    tn = metrics['tn']
    fp = metrics['fp']
    fn = metrics['fn']
    
    tpr = tp / (tp + fn) if (tp + fn) > 0 else 0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0
    
    roc_points = [
        {'fpr': 0.0, 'tpr': 0.0},
        {'fpr': round(fpr * 0.5, 3), 'tpr': round(tpr * 0.6, 3)},
        {'fpr': round(fpr, 3), 'tpr': round(tpr, 3)},
        {'fpr': round(min(1.0, fpr * 1.5), 3), 'tpr': round(min(1.0, tpr * 1.2), 3)},
        {'fpr': 1.0, 'tpr': 1.0}
    ]
    
    auc_score = 0
    for i in range(1, len(roc_points)):
        auc_score += (roc_points[i]['fpr'] - roc_points[i-1]['fpr']) * (roc_points[i]['tpr'] + roc_points[i-1]['tpr']) / 2
    
    return jsonify({
        'metrics': metrics,
        'roc': {
            'points': roc_points,
            'auc': round(auc_score, 3),
            'tpr': round(tpr * 100, 2),
            'fpr': round(fpr * 100, 2)
        },
        'confusion_matrix': {
            'true_positive': tp,
            'true_negative': tn,
            'false_positive': fp,
            'false_negative': fn,
            'missed_drowsy': fn,
            'false_alarms': fp
        },
        'adaptive_info': {
            'enabled': True,
            'current_threshold': adaptive_threshold.get_threshold(),
            'base_threshold': EAR_THRESHOLD
        }
    })

@app.route('/api/metrics/reset', methods=['POST'])
@login_required
def reset_metrics():
    global performance_metrics, last_prediction_state
    performance_metrics = {
        'tp': 0, 'tn': 0, 'fp': 0, 'fn': 0,
        'predictions': deque(maxlen=1000),
        'ground_truth': deque(maxlen=1000),
        'ear_values': deque(maxlen=1000),
        'timestamps': deque(maxlen=1000),
        'response_times': deque(maxlen=100),
        'total_samples': 0,
        'face_detected_frames': 0,
        'no_face_frames': 0,
        'threshold_history': deque(maxlen=500)
    }
    last_prediction_state = 0
    app.logger.info("Performance metrics reset")
    save_metrics_to_file()
    return jsonify({'status': 'success'})

@app.route('/api/config', methods=['GET', 'POST'])
@login_required
def handle_config():
    global CONSECUTIVE_FRAMES, MAR_THRESHOLD, HEAD_TILT_THRESHOLD, HEAD_PITCH_THRESHOLD, MIN_CONFIDENCE
    
    if request.method == 'POST':
        data = request.json
        if 'ear_threshold' in data:
            adaptive_threshold.base_threshold = data['ear_threshold']
            adaptive_threshold.current_threshold = data['ear_threshold']
        if 'mar_threshold' in data:
            MAR_THRESHOLD = data['mar_threshold']
        if 'consecutive_frames' in data:
            CONSECUTIVE_FRAMES = data['consecutive_frames']
        if 'min_confidence' in data:
            MIN_CONFIDENCE = data['min_confidence']
        return jsonify({'status': 'success'})
    
    return jsonify({
        'ear_threshold': adaptive_threshold.get_threshold(),
        'base_threshold': adaptive_threshold.base_threshold,
        'mar_threshold': MAR_THRESHOLD,
        'consecutive_frames': CONSECUTIVE_FRAMES,
        'min_confidence': MIN_CONFIDENCE,
        'adaptive_enabled': True,
        'response_time': f"{CONSECUTIVE_FRAMES/30:.2f}s"
    })

@socketio.on('connect')
def handle_connect():
    app.logger.info(f"Client connected: {request.sid}")
    emit('connected', {
        'data': 'Connected to server',
        'alarms': len(AVAILABLE_ALARMS),
        'adaptive_mode': True,
        'glasses_optimized': GLASSES_MODE_ENABLED,
        'response_time': f"{CONSECUTIVE_FRAMES/30:.2f}s",
        'current_threshold': adaptive_threshold.get_threshold(),
        'night_mode_available': True
    })

@socketio.on('disconnect')
def handle_disconnect():
    app.logger.info(f"Client disconnected: {request.sid}")

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    app.logger.error(f'Server Error: {error}')
    return render_template('500.html'), 500

if __name__ == '__main__':
    dirs = [
        'models', 'templates', 'static', 'static/css', 'static/js', 'static/sounds',
        config['storage']['screenshot_dir'], 'logs', 'alerts', 'database'
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    
    print("\n" + "="*70)
    print("📡 DROWSINESS DETECTION SERVER READY - ADAPTIVE THRESHOLD VERSION")
    print("="*70)
    print(f"   URL: http://{config['server']['host']}:{config['server']['port']}")
    print(f"   Login: admin / admin123")
    print(f"   Adaptive Threshold: ENABLED")
    print(f"   Current Threshold: {adaptive_threshold.get_threshold():.3f}")
    print(f"   Base Threshold: {EAR_THRESHOLD:.3f}")
    print(f"   Consecutive frames: {CONSECUTIVE_FRAMES}")
    print(f"   Glasses mode: {'ON' if GLASSES_MODE_ENABLED else 'OFF'}")
    print("="*70)
    print("\n📊 FEATURES:")
    print("   ✓ Adaptive thresholding (self-calibrating)")
    print("   ✓ Personalized calibration from calibration.json")
    print("   ✓ Glasses-aware detection")
    print("   ✓ Night mode with CLAHE enhancement")
    print("   ✓ Real-time performance metrics")
    print("="*70 + "\n")
    
    socketio.run(
        app, 
        host=config['server']['host'], 
        port=config['server']['port'], 
        debug=config['server']['debug'],
        use_reloader=False,
        allow_unsafe_werkzeug=True
    )