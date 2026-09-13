"""
Setup script for Drowsiness Detection System
"""

import subprocess
import sys
import os
import platform

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"🚀 {text}")
    print("="*60)

def print_step(step, text):
    """Print step with emoji"""
    emojis = ['📦', '🔧', '📥', '⚙️', '🧪', '✅']
    print(f"{emojis[step % len(emojis)]} {text}")

def check_python_version():
    """Check Python version"""
    print_step(0, "Checking Python version...")
    
    version = sys.version_info
    print(f"   Python {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher required")
        return False
    
    print("✅ Python version OK")
    return True

def install_requirements():
    """Install all requirements"""
    print_step(1, "Installing requirements...")
    
    # Upgrade pip
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--upgrade", "pip"])
    
    # Install requirements
    requirements = [
        "flask==2.3.3",
        "flask-socketio==5.3.4",
        "flask-login==0.6.2",
        "flask-cors==4.0.0",
        "werkzeug==2.3.7",
        "opencv-python==4.8.1.78",
        "numpy==1.24.3",
        "scipy==1.11.3",
        "pygame==2.5.2",
        "pyyaml==6.0.1"
    ]
    
    for req in requirements:
        print(f"   Installing {req}...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", req])
        except:
            print(f"   ⚠️ Failed to install {req}, continuing...")
    
    print("✅ Requirements installed")

def check_dlib():
    """Check if dlib installed correctly"""
    print_step(2, "Checking dlib installation...")
    
    try:
        import dlib
        print(f"✅ dlib version: {dlib.__version__}")
        return True
    except ImportError:
        print("❌ dlib not installed")
        
        # Platform specific installation
        system = platform.system()
        python_version = f"{sys.version_info.major}{sys.version_info.minor}"
        
        if system == "Windows":
            print("📥 Installing dlib for Windows...")
            try:
                # Try pre-built wheel for Windows
                if python_version == "310":
                    url = "https://github.com/z-mahmud22/Dlib_Windows_Python3.x/raw/main/dlib-19.24.2-cp310-cp310-win_amd64.whl"
                elif python_version == "39":
                    url = "https://github.com/z-mahmud22/Dlib_Windows_Python3.x/raw/main/dlib-19.24.2-cp39-cp39-win_amd64.whl"
                else:
                    url = "https://github.com/z-mahmud22/Dlib_Windows_Python3.x/raw/main/dlib-19.24.2-cp310-cp310-win_amd64.whl"
                
                subprocess.check_call([sys.executable, "-m", "pip", "install", url])
                print("✅ dlib installed successfully")
                return True
            except:
                print("❌ Failed to install dlib")
                print("\n📝 Manual installation instructions:")
                print("   1. Download from: https://github.com/z-mahmud22/Dlib_Windows_Python3.x")
                print("   2. Install with: pip install <downloaded_file>.whl")
        else:
            print("📥 Installing dlib from source (may take a while)...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "dlib"])
                print("✅ dlib installed successfully")
                return True
            except:
                print("❌ Failed to install dlib")
        
        return False

def create_directories():
    """Create necessary directories"""
    print_step(3, "Creating directories...")
    
    directories = [
        'models',
        'templates',
        'static/css',
        'static/js',
        'static/img',
        'static/sounds',
        'logs',
        'alerts',
        'database',
        'captures'
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"   ✅ Created: {directory}")

def create_alert_sound():
    """Create a simple alert sound"""
    print_step(4, "Creating alert sound...")
    
    try:
        import wave
        import struct
        import math
        
        sound_path = "static/sounds/alert.wav"
        
        if not os.path.exists(sound_path):
            print("   Generating alert.wav...")
            
            with wave.open(sound_path, 'w') as f:
                f.setnchannels(1)  # Mono
                f.setsampwidth(2)   # 16-bit
                f.setframerate(44100)  # 44.1kHz
                
                duration = 1.0  # seconds
                frequency = 880  # Hz
                sample_rate = 44100
                
                for i in range(int(sample_rate * duration)):
                    t = float(i) / sample_rate
                    # Create a beep with fade in/out
                    envelope = 0.5 * (1 - math.cos(2 * math.pi * t))  # Fade envelope
                    value = int(32767.0 * math.sin(2.0 * math.pi * frequency * t) * envelope)
                    data = struct.pack('<h', value)
                    f.writeframes(data)
            
            print(f"   ✅ Created: {sound_path}")
        else:
            print("   ✅ Alert sound already exists")
            
    except Exception as e:
        print(f"   ⚠️ Could not create alert sound: {e}")
        
        # Create a simple text file as fallback
        with open("static/sounds/README.txt", "w") as f:
            f.write("Place alert.wav here for sound alerts")

def create_env_file():
    """Create .env file"""
    print_step(5, "Creating environment file...")
    
    env_content = """# Drowsiness Detection Environment Variables
FLASK_APP=app.py
FLASK_ENV=development
FLASK_DEBUG=1
SECRET_KEY=your-secret-key-here-change-in-production
DATABASE_PATH=drowsiness.db
"""
    
    if not os.path.exists(".env"):
        with open(".env", "w") as f:
            f.write(env_content)
        print("   ✅ Created: .env")
    else:
        print("   ✅ .env already exists")

def create_gitignore():
    """Create .gitignore file"""
    print_step(6, "Creating .gitignore...")
    
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
env/
venv/
ENV/
env.bak/
venv.bak/

# Flask
instance/
.webassets-cache

# Database
*.db
*.sqlite
*.sqlite3

# Models
*.dat
*.bz2

# Captures
captures/
screenshots/

# Logs
logs/
*.log

# Environment
.env
.venv
*.whl

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db
"""
    
    if not os.path.exists(".gitignore"):
        with open(".gitignore", "w") as f:
            f.write(gitignore_content)
        print("   ✅ Created: .gitignore")
    else:
        print("   ✅ .gitignore already exists")

def main():
    """Main setup function"""
    print_header("DROWSINESS DETECTION SYSTEM SETUP")
    
    # Check Python version
    if not check_python_version():
        return 1
    
    # Install requirements
    install_requirements()
    
    # Check dlib
    check_dlib()
    
    # Create directories
    create_directories()
    
    # Create alert sound
    create_alert_sound()
    
    # Create env file
    create_env_file()
    
    # Create gitignore
    create_gitignore()
    
    print_header("SETUP COMPLETE!")
    print("\n📝 Next steps:")
    print("   1. Download facial landmark model:")
    print("      python download_model.py")
    print("   2. Run the application:")
    print("      python app.py")
    print("   3. Open browser to:")
    print("      http://127.0.0.1:5000")
    print("\n🔑 Default login:")
    print("   Username: admin")
    print("   Password: admin123")
    print("\n" + "="*60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())