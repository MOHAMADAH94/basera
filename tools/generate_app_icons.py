from PIL import Image
from pathlib import Path

img = Image.open(Path("assets/basera_app_icon.png")).convert("RGBA")

android_sizes = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}
base = Path("android/app/src/main/res")
for folder, size in android_sizes.items():
    out_dir = base / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    # Prefer PNG over any existing .webp defaults
    resized = img.resize((size, size), Image.Resampling.LANCZOS)
    resized.save(out_dir / "ic_launcher.png")
    webp = out_dir / "ic_launcher.webp"
    if webp.exists():
        webp.unlink()
    print(f"wrote {out_dir / 'ic_launcher.png'} ({size})")

fg_dir = base / "drawable"
fg_dir.mkdir(parents=True, exist_ok=True)
img.resize((432, 432), Image.Resampling.LANCZOS).save(fg_dir / "ic_launcher_foreground.png")
print("wrote drawable/ic_launcher_foreground.png")

ios_dir = Path("ios/Runner/Assets.xcassets/AppIcon.appiconset")
if ios_dir.exists():
    bg = Image.new("RGBA", img.size, (15, 76, 92, 255))
    flat = Image.alpha_composite(bg, img).convert("RGB")
    sizes = {
        "Icon-App-20x20@1x.png": 20,
        "Icon-App-20x20@2x.png": 40,
        "Icon-App-20x20@3x.png": 60,
        "Icon-App-29x29@1x.png": 29,
        "Icon-App-29x29@2x.png": 58,
        "Icon-App-29x29@3x.png": 87,
        "Icon-App-40x40@1x.png": 40,
        "Icon-App-40x40@2x.png": 80,
        "Icon-App-40x40@3x.png": 120,
        "Icon-App-60x60@2x.png": 120,
        "Icon-App-60x60@3x.png": 180,
        "Icon-App-76x76@1x.png": 76,
        "Icon-App-76x76@2x.png": 152,
        "Icon-App-83.5x83.5@2x.png": 167,
        "Icon-App-1024x1024@1x.png": 1024,
    }
    for name, size in sizes.items():
        flat.resize((size, size), Image.Resampling.LANCZOS).save(ios_dir / name)
        print(name, size)
else:
    print("no ios AppIcon set")

print("done")
