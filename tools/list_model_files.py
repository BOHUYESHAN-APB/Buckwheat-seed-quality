from pathlib import Path
p = Path(r'e:/CODE/Buckwheat-seed-quality/android-app/app/src/main/assets/models')
for f in sorted(p.iterdir(), key=lambda x: x.stat().st_size, reverse=True):
    if f.is_file():
        mb = f.stat().st_size/1024/1024
        print(f.name, f'{mb:.2f}MB')
