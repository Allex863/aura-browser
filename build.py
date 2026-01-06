#!/usr/bin/env python3
"""
Build script for Aura Browser
Creates standalone executable for Windows
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

def check_dependencies():
    """Check if required packages are installed"""
    required = ['PyQt6', 'PyQt6_WebEngine', 'requests', 'Pillow', 'pyinstaller']
    
    print("🔍 Checking dependencies...")
    for package in required:
        try:
            __import__(package.replace('-', '_').lower())
            print(f"  ✅ {package}")
        except ImportError:
            print(f"  ❌ {package} not installed")
            print(f"  Installing {package}...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
    
    print("✅ All dependencies are installed")

def create_icon():
    """Create application icon if not exists"""
    icon_path = Path("src/icon.ico")
    
    if not icon_path.exists():
        print("🎨 Creating application icon...")
        # Простой скрипт создания иконки
        icon_script = """
from PIL import Image, ImageDraw

sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
images = []
primary = (138,43,226)
accent = (255,255,255)

for w,h in sizes:
    img = Image.new('RGBA',(w,h),(0,0,0,0))
    draw = ImageDraw.Draw(img)
    
    # Градиентный круг
    for y in range(h):
        for x in range(w):
            dist = ((x-w/2)**2+(y-h/2)**2)**0.5
            if dist <= min(w,h)/2-2:
                ratio = dist/(min(w,h)/2)
                r = int(primary[0]*(1-ratio)+100*ratio)
                g = int(primary[1]*(1-ratio)+100*ratio)
                b = int(primary[2]*(1-ratio)+200*ratio)
                draw.point((x,y),(r,g,b,255))
    
    # Буква A
    draw.line([(w//3,h*2//3),(w//2,h//3)],accent,max(2,w//16))
    draw.line([(w//2,h//3),(w*2//3,h*2//3)],accent,max(2,w//16))
    draw.line([(w//2-w//8,h//2),(w//2+w//8,h//2)],accent,max(1,w//32))
    
    images.append(img)

images[0].save('src/icon.ico','ICO',sizes=sizes,append_images=images[1:])
        """
        
        # Создаем иконку
        exec(icon_script)
        print("✅ Icon created: src/icon.ico")

def clean_build():
    """Clean previous build artifacts"""
    print("🧹 Cleaning previous builds...")
    
    folders_to_remove = ['build', 'dist', '__pycache__']
    files_to_remove = ['AuraBrowser.spec']
    
    for folder in folders_to_remove:
        if os.path.exists(folder):
            shutil.rmtree(folder)
            print(f"  Removed: {folder}")
    
    for file in files_to_remove:
        if os.path.exists(file):
            os.remove(file)
            print(f"  Removed: {file}")

def build_executable():
    """Build the executable using PyInstaller"""
    print("🔨 Building executable...")
    
    # Команда PyInstaller
    cmd = [
        'pyinstaller',
        '--windowed',
        '--onefile',
        '--noconsole',
        '--icon=src/icon.ico',
        '--name=AuraBrowser',
        '--add-data=src/icon.ico;.',
        '--hidden-import=PyQt6.QtWebEngineWidgets',
        '--hidden-import=PyQt6.QtWebEngineCore',
        '--hidden-import=urllib.parse',
        '--clean',
        'src/working_browser.py'
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print("✅ Build successful!")
        
        # Проверяем размер файла
        exe_path = Path("dist/AuraBrowser.exe")
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print(f"📦 Executable size: {size_mb:.1f} MB")
            print(f"📍 Location: {exe_path.absolute()}")
    except subprocess.CalledProcessError as e:
        print(f"❌ Build failed: {e}")
        sys.exit(1)

def create_archive():
    """Create ZIP archive for distribution"""
    print("📦 Creating distribution archive...")
    
    import zipfile
    import datetime
    
    # Имя архива с датой
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    archive_name = f"AuraBrowser_v1.0_{date_str}.zip"
    
    # Файлы для включения в архив
    files_to_include = [
        ("dist/AuraBrowser.exe", "AuraBrowser.exe"),
        ("README.md", "README.md"),
        ("LICENSE", "LICENSE"),
    ]
    
    # Создаем архив
    with zipfile.ZipFile(archive_name, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for source, target in files_to_include:
            if os.path.exists(source):
                zipf.write(source, target)
                print(f"  Added: {target}")
    
    print(f"✅ Archive created: {archive_name}")

def main():
    """Main build function"""
    print("=" * 50)
    print("       AURA BROWSER BUILD SCRIPT")
    print("=" * 50)
    
    # Проверяем что мы в правильной директории
    if not os.path.exists("src/working_browser.py"):
        print("❌ Error: src/working_browser.py not found")
        print("Please run this script from the project root directory")
        sys.exit(1)
    
    # Шаги сборки
    steps = [
        ("Check dependencies", check_dependencies),
        ("Create icon", create_icon),
        ("Clean previous builds", clean_build),
        ("Build executable", build_executable),
        ("Create archive", create_archive),
    ]
    
    for step_name, step_func in steps:
        print(f"\n🔹 Step: {step_name}")
        try:
            step_func()
        except Exception as e:
            print(f"❌ Error in {step_name}: {e}")
            if step_name != "Clean previous builds":
                sys.exit(1)
    
    print("\n" + "=" * 50)
    print("🎉 BUILD COMPLETED SUCCESSFULLY!")
    print("=" * 50)
    print("\nYour Aura Browser is ready!")
    print(f"📍 Executable: dist/AuraBrowser.exe")
    print(f"📦 Archive: AuraBrowser_v1.0_*.zip")
    print("\nTo upload to GitHub:")
    print("1. Go to https://github.com/yourusername/aura-browser/releases")
    print("2. Click 'Draft a new release'")
    print("3. Upload the ZIP file")
    print("4. Add release notes")
    print("5. Publish!")

if __name__ == "__main__":
    main()