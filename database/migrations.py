"""
Database migration utilities
"""

import sqlite3
import json
from datetime import datetime
import os
import shutil

class Migration:
    """Handle database migrations"""
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.migrations_table = 'migrations'
    
    def get_current_version(self):
        """Get current database version"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create migrations table if not exists
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.migrations_table} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version INTEGER,
                name TEXT,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute(f'SELECT MAX(version) FROM {self.migrations_table}')
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result[0] else 0
    
    def apply_migrations(self):
        """Apply all pending migrations"""
        current_version = self.get_current_version()
        migrations = self.get_migration_list()
        
        for version, name, migration_func in migrations:
            if version > current_version:
                print(f"Applying migration {version}: {name}")
                self.apply_migration(version, name, migration_func)
    
    def apply_migration(self, version, name, migration_func):
        """Apply a single migration"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Begin transaction
            cursor.execute('BEGIN TRANSACTION')
            
            # Apply migration
            migration_func(cursor)
            
            # Record migration
            cursor.execute(f'''
                INSERT INTO {self.migrations_table} (version, name)
                VALUES (?, ?)
            ''', (version, name))
            
            # Commit
            conn.commit()
            print(f"✅ Migration {version} applied successfully")
            
        except Exception as e:
            conn.rollback()
            print(f"❌ Migration {version} failed: {e}")
            raise
        finally:
            conn.close()
    
    def get_migration_list(self):
        """Get list of all migrations"""
        return [
            (1, "Initial schema", self.migration_001_initial),
            (2, "Add user sessions", self.migration_002_user_sessions),
            (3, "Add settings table", self.migration_003_settings),
            (4, "Add indexes", self.migration_004_indexes),
            (5, "Add screenshot path", self.migration_005_screenshot_path),
        ]
    
    def migration_001_initial(self, cursor):
        """Migration 1: Initial database schema"""
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash BLOB NOT NULL,
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
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
        
        # Create default admin user
        from models import User
        admin_password = User.hash_password('admin123')
        cursor.execute('''
            INSERT OR IGNORE INTO users (username, password_hash, is_admin)
            VALUES (?, ?, 1)
        ''', ('admin', admin_password))
    
    def migration_002_user_sessions(self, cursor):
        """Migration 2: Add detection sessions table"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS detection_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                user_id INTEGER,
                total_frames INTEGER DEFAULT 0,
                drowsy_events INTEGER DEFAULT 0,
                avg_ear REAL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
    
    def migration_003_settings(self, cursor):
        """Migration 3: Add settings table"""
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Insert default settings
        default_settings = [
            ('version', '1.0.0'),
            ('ear_threshold', '0.22'),
            ('head_tilt_threshold', '15'),
            ('consecutive_frames', '20'),
            ('alert_cooldown', '10'),
        ]
        
        for key, value in default_settings:
            cursor.execute('''
                INSERT OR IGNORE INTO settings (key, value)
                VALUES (?, ?)
            ''', (key, value))
    
    def migration_004_indexes(self, cursor):
        """Migration 4: Add indexes for performance"""
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_events_timestamp 
            ON drowsy_events (timestamp)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_events_user 
            ON drowsy_events (user_id)
        ''')
        
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_sessions_user 
            ON detection_sessions (user_id)
        ''')
    
    def migration_005_screenshot_path(self, cursor):
        """Migration 5: Add screenshot path to events"""
        cursor.execute('''
            ALTER TABLE drowsy_events 
            ADD COLUMN screenshot_path TEXT
        ''')


def backup_database(db_path, backup_dir='backups'):
    """Create a backup of the database"""
    if not os.path.exists(db_path):
        return None
    
    # Create backup directory
    os.makedirs(backup_dir, exist_ok=True)
    
    # Generate backup filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backup_dir, f'drowsiness_backup_{timestamp}.db')
    
    # Copy database
    shutil.copy2(db_path, backup_path)
    
    # Compress backup
    import gzip
    with open(backup_path, 'rb') as f_in:
        with gzip.open(f'{backup_path}.gz', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
    
    os.remove(backup_path)
    
    return f'{backup_path}.gz'


def restore_database(backup_path, db_path):
    """Restore database from backup"""
    if not os.path.exists(backup_path):
        return False
    
    # Decompress if gzipped
    if backup_path.endswith('.gz'):
        import gzip
        with gzip.open(backup_path, 'rb') as f_in:
            with open(db_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
    else:
        shutil.copy2(backup_path, db_path)
    
    return True


def export_schema(db_path, output_path='schema.sql'):
    """Export database schema to SQL file"""
    conn = sqlite3.connect(db_path)
    
    with open(output_path, 'w') as f:
        for line in conn.iterdump():
            if line.startswith('CREATE TABLE'):
                f.write(line + '\n\n')
    
    conn.close()
    return output_path


def vacuum_database(db_path):
    """Vacuum database to optimize size"""
    conn = sqlite3.connect(db_path)
    conn.execute('VACUUM')
    conn.close()
    return True


def check_integrity(db_path):
    """Check database integrity"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute('PRAGMA integrity_check')
    result = cursor.fetchone()
    
    conn.close()
    
    return result[0] == 'ok'