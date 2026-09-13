"""
Database operations for drowsiness detection system
"""

import sqlite3
import csv
import json
from datetime import datetime, timedelta
from contextlib import contextmanager

class Database:
    def __init__(self, db_path):
        self.db_path = db_path
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def init_db(self):
        """Initialize database tables"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    email TEXT,
                    is_admin BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login TIMESTAMP
                )
            ''')
            
            # Events table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS drowsy_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TIMESTAMP NOT NULL,
                    ear REAL NOT NULL,
                    head_tilt REAL NOT NULL,
                    user_id INTEGER,
                    screenshot_path TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Sessions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS detection_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    user_id INTEGER,
                    total_frames INTEGER,
                    drowsy_events INTEGER,
                    avg_ear REAL,
                    FOREIGN KEY (user_id) REFERENCES users (id)
                )
            ''')
            
            # Settings table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
    
    def save_event(self, event_data):
        """Save drowsy event to database"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO drowsy_events (timestamp, ear, head_tilt, user_id)
                VALUES (?, ?, ?, ?)
            ''', (
                event_data['timestamp'],
                event_data['ear'],
                event_data['head_tilt'],
                event_data.get('user_id')
            ))
            conn.commit()
    
    def get_recent_events(self, limit=100):
        """Get recent drowsy events"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, ear, head_tilt 
                FROM drowsy_events 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_daily_stats(self):
        """Get statistics for today"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            today = datetime.now().strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_events,
                    AVG(ear) as avg_ear,
                    MIN(ear) as min_ear,
                    MAX(ear) as max_ear,
                    AVG(head_tilt) as avg_tilt
                FROM drowsy_events 
                WHERE date(timestamp) = ?
            ''', (today,))
            
            return dict(cursor.fetchone())
    
    def get_weekly_stats(self):
        """Get weekly statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT 
                    date(timestamp) as date,
                    COUNT(*) as events,
                    AVG(ear) as avg_ear
                FROM drowsy_events 
                WHERE date(timestamp) >= ?
                GROUP BY date(timestamp)
                ORDER BY date
            ''', (week_ago,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_monthly_stats(self):
        """Get monthly statistics"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            month_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            
            cursor.execute('''
                SELECT 
                    strftime('%Y-%m-%d', timestamp) as date,
                    COUNT(*) as events,
                    AVG(ear) as avg_ear
                FROM drowsy_events 
                WHERE date(timestamp) >= ?
                GROUP BY date(timestamp)
                ORDER BY date
            ''', (month_ago,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def export_data(self, format='csv', start_date=None, end_date=None):
        """Export data to specified format"""
        with self.get_connection() as conn:
            query = "SELECT timestamp, ear, head_tilt FROM drowsy_events"
            params = []
            
            if start_date and end_date:
                query += " WHERE date(timestamp) BETWEEN ? AND ?"
                params = [start_date, end_date]
            elif start_date:
                query += " WHERE date(timestamp) >= ?"
                params = [start_date]
            elif end_date:
                query += " WHERE date(timestamp) <= ?"
                params = [end_date]
            
            query += " ORDER BY timestamp"
            
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            if format == 'csv':
                output = StringIO()
                writer = csv.writer(output)
                writer.writerow(['Timestamp', 'EAR', 'Head Tilt'])
                writer.writerows(rows)
                return output.getvalue()
            
            elif format == 'json':
                data = [{'timestamp': r[0], 'ear': r[1], 'head_tilt': r[2]} 
                       for r in rows]
                return json.dumps(data, indent=2)
    
    def save_session(self, session_data):
        """Save detection session"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO detection_sessions 
                (start_time, end_time, user_id, total_frames, drowsy_events, avg_ear)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                session_data['start_time'],
                session_data.get('end_time'),
                session_data.get('user_id'),
                session_data.get('total_frames', 0),
                session_data.get('drowsy_events', 0),
                session_data.get('avg_ear', 0)
            ))
            conn.commit()
    
    def get_setting(self, key, default=None):
        """Get a setting value"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT value FROM settings WHERE key = ?', (key,))
            row = cursor.fetchone()
            return row[0] if row else default
    
    def set_setting(self, key, value):
        """Set a setting value"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO settings (key, value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))
            conn.commit()