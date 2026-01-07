# build_with_spec.py
import PyInstaller.__main__
import os
import shutil

print("🔨 Building with SPEC file...")

# Clean
for folder in ['build', 'dist']:
    if os.path.exists(folder):
        shutil.rmtree(folder)

# Build
PyInstaller.__main__.run([
    'MangaDexDownloaderPro.spec',
    '--clean',
    '--noconfirm',
])

print("\n✅ Build complete!")

exe_path = "dist/MangaDexDownloaderPro.exe"
if os.path.exists(exe_path):
    size_mb = os.path.getsize(exe_path) / (1024 * 1024)
    print(f"📦 Size:   {size_mb:.2f} MB")