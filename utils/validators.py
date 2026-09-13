"""
Validation utilities for the drowsiness detection system
"""

import re
import os
from datetime import datetime, timedelta
from typing import Tuple, List, Any

class Validators:
    """Collection of validation methods"""
    
    EMAIL_PATTERN = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    USERNAME_PATTERN = r'^[a-zA-Z0-9_]{3,50}$'
    IP_PATTERN = r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
    
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 128
    
    @staticmethod
    def validate_email(email: str) -> bool:
        if not email or not isinstance(email, str):
            return False
        return re.match(Validators.EMAIL_PATTERN, email) is not None
    
    @staticmethod
    def validate_username(username: str) -> Tuple[bool, str]:
        if not username:
            return False, "Username cannot be empty"
        if len(username) < 3:
            return False, "Username must be at least 3 characters"
        if len(username) > 50:
            return False, "Username cannot exceed 50 characters"
        if not re.match(Validators.USERNAME_PATTERN, username):
            return False, "Username can only contain letters, numbers, and underscores"
        return True, "Username is valid"
    
    @staticmethod
    def validate_password(password: str) -> Tuple[bool, str]:
        if not password:
            return False, "Password cannot be empty"
        
        if len(password) < Validators.MIN_PASSWORD_LENGTH:
            return False, f"Password must be at least {Validators.MIN_PASSWORD_LENGTH} characters"
        
        if len(password) > Validators.MAX_PASSWORD_LENGTH:
            return False, f"Password cannot exceed {Validators.MAX_PASSWORD_LENGTH} characters"
        
        if not any(c.isupper() for c in password):
            return False, "Password must contain at least one uppercase letter"
        
        if not any(c.islower() for c in password):
            return False, "Password must contain at least one lowercase letter"
        
        if not any(c.isdigit() for c in password):
            return False, "Password must contain at least one number"
        
        if not any(c in '!@#$%^&*()_+-=[]{}|;:,.<>?' for c in password):
            return False, "Password must contain at least one special character"
        
        return True, "Password is valid"
    
    @staticmethod
    def validate_ear_threshold(value: Any) -> bool:
        try:
            val = float(value)
            return 0.1 <= val <= 0.4
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def validate_mar_threshold(value: Any) -> bool:
        try:
            val = float(value)
            return 0.2 <= val <= 1.0
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def validate_head_tilt_threshold(value: Any) -> bool:
        try:
            val = float(value)
            return 5 <= val <= 30
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def validate_consecutive_frames(value: Any) -> bool:
        try:
            val = int(value)
            return 1 <= val <= 50
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def validate_camera_id(value: Any) -> bool:
        try:
            val = int(value)
            return 0 <= val <= 10
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def validate_fps(value: Any) -> bool:
        try:
            val = int(value)
            return 5 <= val <= 60
        except (TypeError, ValueError):
            return False
    
    @staticmethod
    def validate_cooldown(value: Any) -> bool:
        try:
            val = int(value)
            return 1 <= val <= 60
        except (TypeError, ValueError):
            return False

class ConfigValidator:
    """Validate configuration dictionary"""
    
    REQUIRED_SECTIONS = ['server', 'database', 'detection', 'camera', 'alerts', 'storage']
    
    @staticmethod
    def validate(config: dict) -> Tuple[bool, List[str]]:
        errors = []
        
        for section in ConfigValidator.REQUIRED_SECTIONS:
            if section not in config:
                errors.append(f"Missing required section: {section}")
        
        if errors:
            return False, errors
        
        detection = config.get('detection', {})
        if not Validators.validate_ear_threshold(detection.get('ear_threshold', 0.22)):
            errors.append("Invalid EAR threshold (must be 0.1-0.4)")
        
        if not Validators.validate_head_tilt_threshold(detection.get('head_tilt_threshold', 15)):
            errors.append("Invalid head tilt threshold (must be 5-30)")
        
        if not Validators.validate_consecutive_frames(detection.get('consecutive_frames', 20)):
            errors.append("Invalid consecutive frames (must be 1-50)")
        
        camera = config.get('camera', {})
        if not Validators.validate_camera_id(camera.get('device_id', 0)):
            errors.append("Invalid camera ID (must be 0-10)")
        
        if not Validators.validate_fps(camera.get('fps', 30)):
            errors.append("Invalid FPS (must be 5-60)")
        
        alerts = config.get('alerts', {})
        if not Validators.validate_cooldown(alerts.get('cooldown', 10)):
            errors.append("Invalid alert cooldown (must be 1-60 seconds)")
        
        return len(errors) == 0, errors

class RequestValidator:
    """Validate API requests"""
    
    VALID_FORMATS = ['csv', 'json', 'excel']
    VALID_PERIODS = ['hour', 'day', 'week', 'month', 'year', 'all']
    
    @staticmethod
    def validate_start_request(data: dict) -> Tuple[bool, str]:
        return True, "Request is valid"
    
    @staticmethod
    def validate_settings_update(data: dict) -> Tuple[bool, str]:
        if not data:
            return False, "Settings cannot be empty"
        
        validators = {
            'ear_threshold': Validators.validate_ear_threshold,
            'mar_threshold': Validators.validate_mar_threshold,
            'head_tilt_threshold': Validators.validate_head_tilt_threshold,
            'consecutive_frames': Validators.validate_consecutive_frames,
            'fps': Validators.validate_fps,
            'alert_cooldown': Validators.validate_cooldown
        }
        
        for key, value in data.items():
            if key in validators and not validators[key](value):
                return False, f"Invalid value for {key}"
        
        return True, "Settings are valid"
    
    @staticmethod
    def validate_export_request(params: dict) -> Tuple[bool, str]:
        format_type = params.get('format', 'csv')
        period = params.get('period', 'day')
        
        if format_type not in RequestValidator.VALID_FORMATS:
            return False, f"Invalid format. Must be one of: {', '.join(RequestValidator.VALID_FORMATS)}"
        
        if period not in RequestValidator.VALID_PERIODS:
            return False, f"Invalid period. Must be one of: {', '.join(RequestValidator.VALID_PERIODS)}"
        
        return True, "Request is valid"