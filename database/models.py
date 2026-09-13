"""
Database models for the drowsiness detection system
"""

import sqlite3
from datetime import datetime
import hashlib
import os
from flask_login import UserMixin

class User(UserMixin):
    """User model for authentication - Fixed for Flask-Login"""
    
    def __init__(self, id=None, username=None, password_hash=None, 
                 email=None, is_admin=False, created_at=None, last_login=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.email = email
        self.is_admin = is_admin
        self.created_at = created_at or datetime.now()
        self.last_login = last_login
    
    # Flask-Login required methods
    def is_active(self):
        """Return True if user is active"""
        return True
    
    def is_authenticated(self):
        """Return True if user is authenticated"""
        return True
    
    def is_anonymous(self):
        """Return False as this is not an anonymous user"""
        return False
    
    def get_id(self):
        """Return the user ID as string"""
        return str(self.id)
    
    @classmethod
    def from_db_row(cls, row):
        """Create User object from database row"""
        if not row:
            return None
        return cls(
            id=row[0],
            username=row[1],
            password_hash=row[2],
            email=row[3],
            is_admin=bool(row[4]),
            created_at=datetime.fromisoformat(row[5]) if row[5] else None,
            last_login=datetime.fromisoformat(row[6]) if row[6] else None
        )
    
    @staticmethod
    def hash_password(password):
        """Hash password for storage"""
        salt = os.urandom(32)
        key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return salt + key
    
    @staticmethod
    def verify_password(password, stored_hash):
        """Verify password against stored hash"""
        salt = stored_hash[:32]
        key = stored_hash[32:]
        new_key = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt,
            100000
        )
        return new_key == key
    
    @classmethod
    def get_by_username(cls, username, db_path='database/drowsiness.db'):
        """Get user by username"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, password_hash, email, is_admin, created_at, last_login
            FROM users WHERE username = ?
        ''', (username,))
        
        row = cursor.fetchone()
        conn.close()
        
        return cls.from_db_row(row) if row else None
    
    @classmethod
    def get_by_id(cls, user_id, db_path='database/drowsiness.db'):
        """Get user by ID"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, username, password_hash, email, is_admin, created_at, last_login
            FROM users WHERE id = ?
        ''', (user_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        return cls.from_db_row(row) if row else None
    
    @classmethod
    def authenticate(cls, username, password, db_path='database/drowsiness.db'):
        """Authenticate user"""
        user = cls.get_by_username(username, db_path)
        if user and user.password_hash and cls.verify_password(password, user.password_hash):
            return user
        return None
    
    @classmethod
    def create(cls, username, password, email=None, is_admin=False, db_path='database/drowsiness.db'):
        """Create new user"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        password_hash = cls.hash_password(password)
        
        try:
            cursor.execute('''
                INSERT INTO users (username, password_hash, email, is_admin, created_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (username, password_hash, email, is_admin, datetime.now().isoformat()))
            
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            
            return cls.get_by_id(user_id, db_path)
        except sqlite3.IntegrityError:
            conn.close()
            return None
    
    def update_last_login(self, db_path='database/drowsiness.db'):
        """Update user's last login time"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users SET last_login = ? WHERE id = ?
        ''', (datetime.now().isoformat(), self.id))
        
        conn.commit()
        conn.close()
    
    def to_dict(self):
        """Convert to dictionary (safe for JSON)"""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'is_admin': self.is_admin,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }


class Event:
    """Drowsy event model"""
    
    def __init__(self, id=None, timestamp=None, ear=None, head_tilt=None, 
                 user_id=None, screenshot_path=None):
        self.id = id
        self.timestamp = timestamp or datetime.now()
        self.ear = ear
        self.head_tilt = head_tilt
        self.user_id = user_id
        self.screenshot_path = screenshot_path
    
    @classmethod
    def from_db_row(cls, row):
        """Create Event object from database row"""
        if not row:
            return None
        return cls(
            id=row[0],
            timestamp=datetime.fromisoformat(row[1]) if row[1] else None,
            ear=row[2],
            head_tilt=row[3],
            user_id=row[4],
            screenshot_path=row[5]
        )
    
    @classmethod
    def get_recent(cls, limit=100, db_path='database/drowsiness.db'):
        """Get recent events"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, timestamp, ear, head_tilt, user_id, screenshot_path
            FROM drowsy_events
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [cls.from_db_row(row) for row in rows]
    
    @classmethod
    def get_by_date_range(cls, start_date, end_date, db_path='database/drowsiness.db'):
        """Get events within date range"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, timestamp, ear, head_tilt, user_id, screenshot_path
            FROM drowsy_events
            WHERE date(timestamp) BETWEEN ? AND ?
            ORDER BY timestamp
        ''', (start_date, end_date))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [cls.from_db_row(row) for row in rows]
    
    def save(self, db_path='database/drowsiness.db'):
        """Save event to database"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO drowsy_events (timestamp, ear, head_tilt, user_id, screenshot_path)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            self.timestamp.isoformat(),
            self.ear,
            self.head_tilt,
            self.user_id,
            self.screenshot_path
        ))
        
        self.id = cursor.lastrowid
        conn.commit()
        conn.close()
        return self.id
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'ear': self.ear,
            'head_tilt': self.head_tilt,
            'user_id': self.user_id,
            'screenshot_path': self.screenshot_path
        }


class DetectionSession:
    """Detection session model"""
    
    def __init__(self, id=None, start_time=None, end_time=None, user_id=None,
                 total_frames=0, drowsy_events=0, avg_ear=0.0):
        self.id = id
        self.start_time = start_time or datetime.now()
        self.end_time = end_time
        self.user_id = user_id
        self.total_frames = total_frames
        self.drowsy_events = drowsy_events
        self.avg_ear = avg_ear
    
    @classmethod
    def from_db_row(cls, row):
        """Create Session object from database row"""
        if not row:
            return None
        return cls(
            id=row[0],
            start_time=datetime.fromisoformat(row[1]) if row[1] else None,
            end_time=datetime.fromisoformat(row[2]) if row[2] else None,
            user_id=row[3],
            total_frames=row[4],
            drowsy_events=row[5],
            avg_ear=row[6]
        )
    
    def save(self, db_path='database/drowsiness.db'):
        """Save session to database"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        if self.id:
            # Update existing session
            cursor.execute('''
                UPDATE detection_sessions
                SET end_time = ?, total_frames = ?, drowsy_events = ?, avg_ear = ?
                WHERE id = ?
            ''', (
                self.end_time.isoformat() if self.end_time else None,
                self.total_frames,
                self.drowsy_events,
                self.avg_ear,
                self.id
            ))
        else:
            # Insert new session
            cursor.execute('''
                INSERT INTO detection_sessions (start_time, end_time, user_id, total_frames, drowsy_events, avg_ear)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                self.start_time.isoformat(),
                self.end_time.isoformat() if self.end_time else None,
                self.user_id,
                self.total_frames,
                self.drowsy_events,
                self.avg_ear
            ))
            self.id = cursor.lastrowid
        
        conn.commit()
        conn.close()
        return self.id
    
    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'user_id': self.user_id,
            'total_frames': self.total_frames,
            'drowsy_events': self.drowsy_events,
            'avg_ear': self.avg_ear,
            'duration': (self.end_time - self.start_time).total_seconds() if self.end_time else 0
        }


class Setting:
    """System settings model"""
    
    def __init__(self, key=None, value=None, updated_at=None):
        self.key = key
        self.value = value
        self.updated_at = updated_at or datetime.now()
    
    @classmethod
    def from_db_row(cls, row):
        """Create Setting object from database row"""
        if not row:
            return None
        return cls(
            key=row[0],
            value=row[1],
            updated_at=datetime.fromisoformat(row[2]) if row[2] else None
        )
    
    @classmethod
    def get(cls, key, default=None, db_path='database/drowsiness.db'):
        """Get setting by key"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT key, value, updated_at FROM settings WHERE key = ?', (key,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return cls.from_db_row(row)
        return default
    
    @classmethod
    def set(cls, key, value, db_path='database/drowsiness.db'):
        """Set setting value"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO settings (key, value, updated_at)
            VALUES (?, ?, ?)
        ''', (key, value, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        return cls.get(key, db_path=db_path)
    
    @classmethod
    def get_all(cls, db_path='database/drowsiness.db'):
        """Get all settings"""
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT key, value, updated_at FROM settings ORDER BY key')
        rows = cursor.fetchall()
        conn.close()
        
        return {row[0]: cls.from_db_row(row) for row in rows}