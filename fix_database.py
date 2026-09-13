import sqlite3
import os

DB_PATH = 'drowsiness.db'

print("\n" + "="*70)
print("🔧 FIXING DATABASE SCHEMA")
print("="*70)

if not os.path.exists(DB_PATH):
    print(f"❌ Database file not found: {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check current schema
cursor.execute("PRAGMA table_info(alerts)")
columns = cursor.fetchall()
print("\n📊 Current alerts table columns:")
for col in columns:
    print(f"   • {col[1]} ({col[2]})")

# Add missing columns if they don't exist
column_names = [col[1] for col in columns]

if 'glasses_confidence' not in column_names:
    print("\n➕ Adding missing column: glasses_confidence")
    cursor.execute("ALTER TABLE alerts ADD COLUMN glasses_confidence REAL")
else:
    print("\n✅ glasses_confidence column already exists")

if 'detection_mode' not in column_names:
    print("➕ Adding missing column: detection_mode")
    cursor.execute("ALTER TABLE alerts ADD COLUMN detection_mode TEXT")
else:
    print("✅ detection_mode column already exists")

if 'response_time' not in column_names:
    print("➕ Adding missing column: response_time")
    cursor.execute("ALTER TABLE alerts ADD COLUMN response_time REAL")
else:
    print("✅ response_time column already exists")

if 'alarm_used' not in column_names:
    print("➕ Adding missing column: alarm_used")
    cursor.execute("ALTER TABLE alerts ADD COLUMN alarm_used TEXT")
else:
    print("✅ alarm_used column already exists")

if 'screenshot_path' not in column_names:
    print("➕ Adding missing column: screenshot_path")
    cursor.execute("ALTER TABLE alerts ADD COLUMN screenshot_path TEXT")
else:
    print("✅ screenshot_path column already exists")

conn.commit()

# Verify the fix
cursor.execute("PRAGMA table_info(alerts)")
updated_columns = cursor.fetchall()
print("\n📊 Updated alerts table columns:")
for col in updated_columns:
    print(f"   • {col[1]} ({col[2]})")

conn.close()
print("\n" + "="*70)
print("✅ DATABASE FIX COMPLETE")
print("="*70)