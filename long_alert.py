"""
Long Alert Sound Generator for Drowsiness Detection
Creates attention-grabbing alert sounds of 5-10 seconds duration
"""

import wave
import struct
import math
import os
import sys
import array

def create_long_alert_sound(filename="static/sounds/long_alert.wav", duration=8):
    """
    Create a long alert sound file
    duration: 5-10 seconds
    """
    print(f"\n🔊 Creating {duration} second alert sound...")
    
    # Create directory if it doesn't exist
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    # Audio parameters
    sample_rate = 44100  # Hz
    amplitude = 32767  # Max for 16-bit audio
    
    try:
        with wave.open(filename, 'w') as f:
            f.setnchannels(1)  # Mono
            f.setsampwidth(2)  # 16-bit
            f.setframerate(sample_rate)
            
            total_frames = int(sample_rate * duration)
            
            # Progress indicator
            print(f"   Generating {total_frames} frames...")
            
            for i in range(total_frames):
                t = float(i) / sample_rate
                
                # Complex alert pattern for attention grabbing
                if t < 1.0:  # First second - fast beeping
                    # Rapid beeps to grab attention
                    beep_freq = 880 if int(t * 10) % 2 == 0 else 440
                    value = int(amplitude * 0.7 * math.sin(2.0 * math.pi * beep_freq * t))
                    
                elif t < 3.0:  # Seconds 1-3 - siren effect
                    # Rising siren
                    siren_freq = 440 + 440 * math.sin(2.0 * math.pi * 2 * t)
                    value = int(amplitude * 0.8 * math.sin(2.0 * math.pi * siren_freq * t))
                    
                elif t < 5.0:  # Seconds 3-5 - alternating high-low
                    # Alternating tones
                    if int(t * 4) % 2 == 0:
                        value = int(amplitude * 0.9 * math.sin(2.0 * math.pi * 880 * t))
                    else:
                        value = int(amplitude * 0.9 * math.sin(2.0 * math.pi * 1320 * t))
                        
                elif t < 7.0:  # Seconds 5-7 - pulsating
                    # Pulsating tone
                    pulse = 0.5 + 0.5 * math.sin(2.0 * math.pi * 8 * t)
                    value = int(amplitude * pulse * math.sin(2.0 * math.pi * 1000 * t))
                    
                else:  # Last second - final warning
                    # Rapid final beeps
                    if int(t * 8) % 2 == 0:
                        value = int(amplitude * math.sin(2.0 * math.pi * 1760 * t))
                    else:
                        value = int(amplitude * 0.5 * math.sin(2.0 * math.pi * 880 * t))
                
                # Pack the value as 16-bit integer
                data = struct.pack('<h', value)
                f.writeframes(data)
                
                # Show progress every second
                if i % sample_rate == 0:
                    print(f"   Progress: {i//sample_rate}/{duration} seconds", end='\r')
            
            print(f"\n   Progress: {duration}/{duration} seconds")
        
        file_size = os.path.getsize(filename) / 1024
        print(f"✅ Long alert sound created: {filename}")
        print(f"   Duration: {duration} seconds")
        print(f"   Size: {file_size:.1f} KB")
        return True
        
    except Exception as e:
        print(f"❌ Error creating sound: {e}")
        return False


def create_ultra_loud_alert(filename="static/sounds/ultra_alert.wav", duration=10):
    """
    Create an ultra-loud, attention-grabbing alert (stereo)
    """
    print(f"\n🔊 Creating ULTRA LOUD {duration} second alert...")
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    sample_rate = 44100
    amplitude = 32767
    
    try:
        with wave.open(filename, 'w') as f:
            f.setnchannels(2)  # Stereo for more impact
            f.setsampwidth(2)
            f.setframerate(sample_rate)
            
            total_frames = int(sample_rate * duration)
            
            print(f"   Generating {total_frames} stereo frames...")
            
            for i in range(total_frames):
                t = float(i) / sample_rate
                
                # Create a complex stereo pattern
                # Left and right channels have slightly different frequencies
                # Creates a "moving" sound effect
                
                # Base frequency that changes over time
                if t < 3:
                    base_freq = 880
                elif t < 6:
                    base_freq = 660
                else:
                    base_freq = 1320
                
                # Add modulation for attention
                modulation = 0.3 * math.sin(2.0 * math.pi * 5 * t)
                
                # Left channel
                left_freq = base_freq + modulation * 100
                left = int(amplitude * 0.8 * math.sin(2.0 * math.pi * left_freq * t))
                
                # Right channel - slightly different
                right_freq = base_freq - modulation * 100
                right = int(amplitude * 0.8 * math.sin(2.0 * math.pi * right_freq * t))
                
                # Add some noise in the middle for intensity
                if 3 < t < 7:
                    noise = int(amplitude * 0.1 * (2 * math.sin(2.0 * math.pi * 2000 * t)))
                    left += noise
                    right += noise
                
                # Pack stereo data
                data = struct.pack('<hh', left, right)
                f.writeframes(data)
                
                # Show progress
                if i % sample_rate == 0:
                    print(f"   Progress: {i//sample_rate}/{duration} seconds", end='\r')
            
            print(f"\n   Progress: {duration}/{duration} seconds")
        
        file_size = os.path.getsize(filename) / 1024
        print(f"✅ Ultra loud alert created: {filename}")
        print(f"   Duration: {duration} seconds")
        print(f"   Size: {file_size:.1f} KB")
        return True
        
    except Exception as e:
        print(f"❌ Error creating ultra loud sound: {e}")
        return False


def create_police_siren_alert(filename="static/sounds/siren_alert.wav", duration=8):
    """
    Create a police-style siren alert
    """
    print(f"\n🚨 Creating POLICE SIREN alert ({duration} seconds)...")
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    sample_rate = 44100
    amplitude = 32767
    
    try:
        with wave.open(filename, 'w') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(sample_rate)
            
            for i in range(int(sample_rate * duration)):
                t = float(i) / sample_rate
                
                # Police siren effect (alternating between two frequencies)
                if int(t * 2) % 2 == 0:
                    freq = 660  # Lower tone
                else:
                    freq = 1320  # Higher tone
                
                # Add fast warble for intensity
                warble = 0.1 * math.sin(2.0 * math.pi * 10 * t)
                
                value = int(amplitude * 0.9 * math.sin(2.0 * math.pi * (freq + warble * 100) * t))
                
                data = struct.pack('<h', value)
                f.writeframes(data)
        
        print(f"✅ Police siren alert created: {filename}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def create_beep_pattern_alert(filename="static/sounds/beep_alert.wav", duration=6):
    """
    Create a rapid beeping alert
    """
    print(f"\n🔔 Creating RAPID BEEP alert ({duration} seconds)...")
    
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    
    sample_rate = 44100
    amplitude = 32767
    
    try:
        with wave.open(filename, 'w') as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(sample_rate)
            
            beeps_per_second = 8  # Fast beeping
            
            for i in range(int(sample_rate * duration)):
                t = float(i) / sample_rate
                
                # Rapid on-off pattern
                if int(t * beeps_per_second) % 2 == 0:
                    value = int(amplitude * 0.8 * math.sin(2.0 * math.pi * 880 * t))
                else:
                    value = 0  # Silence between beeps
                
                data = struct.pack('<h', value)
                f.writeframes(data)
        
        print(f"✅ Rapid beep alert created: {filename}")
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Main function to create all alert sounds"""
    print("\n" + "="*60)
    print("🔊 LONG ALERT SOUND GENERATOR")
    print("="*60)
    print("\nThis script creates attention-grabbing alert sounds")
    print("of 5-10 seconds duration for drowsiness detection.\n")
    
    # Create sounds directory
    os.makedirs("static/sounds", exist_ok=True)
    os.makedirs("alerts", exist_ok=True)
    
    print("Available alert types:")
    print("1. Long gradual alert (8 seconds) - Recommended")
    print("2. Ultra loud stereo alert (10 seconds)")
    print("3. Police siren alert (8 seconds)")
    print("4. Rapid beep pattern (6 seconds)")
    print("5. Create ALL alerts")
    
    choice = input("\nChoose option (1-5): ").strip()
    
    success_count = 0
    
    if choice == "1" or choice == "5":
        if create_long_alert_sound("static/sounds/long_alert.wav", 8):
            success_count += 1
        if create_long_alert_sound("alerts/alert_long.wav", 8):
            success_count += 1
    
    if choice == "2" or choice == "5":
        if create_ultra_loud_alert("static/sounds/ultra_alert.wav", 10):
            success_count += 1
        if create_ultra_loud_alert("alerts/alert_ultra.wav", 10):
            success_count += 1
    
    if choice == "3" or choice == "5":
        if create_police_siren_alert("static/sounds/siren_alert.wav", 8):
            success_count += 1
        if create_police_siren_alert("alerts/alert_siren.wav", 8):
            success_count += 1
    
    if choice == "4" or choice == "5":
        if create_beep_pattern_alert("static/sounds/beep_alert.wav", 6):
            success_count += 1
        if create_beep_pattern_alert("alerts/alert_beep.wav", 6):
            success_count += 1
    
    if success_count > 0:
        print(f"\n✅ Successfully created {success_count} alert sound(s)!")
        print("\n📁 Sound files saved in:")
        print("   - static/sounds/")
        print("   - alerts/")
        
        print("\n🔊 To use these alerts:")
        print("   1. Update config.yaml:")
        print("      alerts:")
        print("        sound: true")
        print("        sound_file: static/sounds/long_alert.wav")
        print("        cooldown: 8")
        print("        volume: 0.9")
        print("\n   2. Or update app.py to use the new sound")
    else:
        print("\n❌ No sounds were created")

if __name__ == "__main__":
    main()