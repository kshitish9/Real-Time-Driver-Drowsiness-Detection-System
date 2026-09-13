"""
Continuous Live Metrics Monitor
Run this while your Flask app is running
Press Ctrl+C to stop
"""

import requests
import json
import time
from datetime import datetime
import os

BASE_URL = "http://127.0.0.1:5000"

def clear_screen():
    """Clear terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def fetch_metrics(session):
    """Fetch metrics from API"""
    try:
        response = session.get(f"{BASE_URL}/api/metrics", timeout=5)
        if response.status_code == 200:
            return response.json()
    except:
        pass
    return None

def display_metrics(data):
    """Display metrics in a nice format"""
    if not data or 'metrics' not in data:
        return
    
    m = data['metrics']
    tp = m.get('tp', 0)
    tn = m.get('tn', 0)
    fp = m.get('fp', 0)
    fn = m.get('fn', 0)
    total = m.get('total_samples', tp + tn + fp + fn)
    
    clear_screen()
    
    print("="*80)
    print(f"📊 LIVE METRICS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
    
    # Confusion Matrix
    print("\n📊 CONFUSION MATRIX:")
    print("-" * 60)
    print(f"{'':20} | {'Drowsy':^10} | {'Awake':^10}")
    print("-" * 60)
    print(f"{'Predicted Drowsy':20} | {tp:>4} (TP)  | {fp:>4} (FP)")
    print(f"{'Predicted Awake':20} | {fn:>4} (FN)  | {tn:>4} (TN)")
    print("-" * 60)
    print(f"{'TOTAL':20} | {tp+fn:>4}     | {fp+tn:>4}")
    print("-" * 60)
    
    # Performance Metrics
    if total > 0:
        accuracy = (tp + tn) / total * 100
        precision = tp / (tp + fp) * 100 if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) * 100 if (tp + fn) > 0 else 0
        f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        
        print(f"\n✅ PERFORMANCE METRICS:")
        print("-" * 40)
        print(f"   Accuracy      : {accuracy:>6.2f}%")
        print(f"   Precision     : {precision:>6.2f}%")
        print(f"   Recall        : {recall:>6.2f}%")
        print(f"   F1-Score      : {f1:>6.2f}%")
        print(f"   Total Samples : {total:>6}")
        
        # Interpretation
        print(f"\n📈 INTERPRETATION:")
        print("-" * 40)
        if fp == 0:
            print("   ✓ ZERO FALSE POSITIVES! Perfect precision")
        else:
            print(f"   • False Positives: {fp}")
        if fn == 0:
            print("   ✓ ZERO FALSE NEGATIVES! Perfect recall")
        else:
            print(f"   • False Negatives: {fn}")
    else:
        print("\n⚠️ No data collected yet. Start detection and wait...")
    
    print("\n" + "="*80)
    print("Press Ctrl+C to stop monitoring")

def main():
    print("\n" + "="*80)
    print("📡 CONTINUOUS LIVE METRICS MONITOR")
    print("="*80)
    print("\nMake sure your Flask app is running!")
    print(f"URL: {BASE_URL}")
    print("\nPress Ctrl+C to stop\n")
    
    # Login once
    session = requests.Session()
    login_response = session.post(f"{BASE_URL}/login", data={
        'username': 'admin',
        'password': 'admin123'
    })
    
    if login_response.status_code != 200:
        print("❌ Login failed! Make sure Flask is running")
        return
    
    print("✅ Connected to Flask app")
    print("⏳ Waiting for data collection...\n")
    time.sleep(2)
    
    try:
        while True:
            data = fetch_metrics(session)
            display_metrics(data)
            time.sleep(2)  # Update every 2 seconds
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped")

if __name__ == "__main__":
    main()