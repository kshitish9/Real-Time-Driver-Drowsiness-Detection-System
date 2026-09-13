import requests
import json
import sqlite3
import os

BASE_URL = "http://127.0.0.1:5000"

print("\n" + "="*70)
print("🔍 DEBUGGING DROWSINESS DETECTION METRICS")
print("="*70)

# Check if Flask app is running
try:
    response = requests.get(f"{BASE_URL}", timeout=2)
    print("✅ Flask app is running")
except:
    print("❌ Flask app is NOT running. Start it with: python app.py")
    exit(1)

# Login
print("\n🔑 Logging in...")
session = requests.Session()
login = session.post(f"{BASE_URL}/login", data={
    'username': 'admin',
    'password': 'admin123'
})

if login.status_code != 200:
    print("❌ Login failed")
    exit(1)

print("✅ Logged in successfully\n")

# Check multiple endpoints
endpoints = [
    "/api/metrics",
    "/api/stats/summary",
    "/api/alerts",
    "/api/sessions"
]

for endpoint in endpoints:
    print(f"\n📡 Fetching {endpoint}...")
    print("-" * 50)
    try:
        response = session.get(f"{BASE_URL}{endpoint}")
        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2))
        else:
            print(f"❌ Status: {response.status_code}")
    except Exception as e:
        print(f"❌ Error: {e}")

# Check database directly
print("\n" + "="*70)
print("📊 CHECKING DATABASE DIRECTLY")
print("="*70)

db_path = 'drowsiness.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check alerts table
    cursor.execute("SELECT COUNT(*) FROM alerts")
    alert_count = cursor.fetchone()[0]
    print(f"\n📊 Alerts in database: {alert_count}")
    
    if alert_count > 0:
        cursor.execute("SELECT timestamp, ear_value, mar_value FROM alerts ORDER BY timestamp DESC LIMIT 5")
        alerts = cursor.fetchall()
        print("\n📋 Recent alerts:")
        for a in alerts:
            print(f"   • {a[0]} - EAR: {a[1]:.3f}, MAR: {a[2]:.3f}")
    
    # Check sessions table
    cursor.execute("SELECT COUNT(*) FROM sessions")
    session_count = cursor.fetchone()[0]
    print(f"\n📊 Sessions in database: {session_count}")
    
    conn.close()
else:
    print("❌ Database file not found")

print("\n" + "="*70)
print("🔧 NEXT STEPS:")
print("="*70)
print("1. Make sure detection is running (START button on dashboard)")
print("2. Let it run for a few minutes to collect data")
print("3. Run this script again to see updated metrics")
print("4. Check http://127.0.0.1:5000/metrics for visual dashboard")
print("="*70)