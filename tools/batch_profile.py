"""Batch run detector on a folder of images and summarize results.
Writes a CSV with filename, boxes_count, total_ms and saves visualization into output/batch_samples/.
"""
from pathlib import Path
import csv
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.ui import Detector
import cv2

INPUT_DIR = Path('inference_results/raw')
OUT_DIR = Path('output/batch_samples')
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV = Path('output/inference_summary.csv')

# Try to load model automatically from environment or known path
model_dir = os.getenv('BUCKWHEAT_MODEL_DIR') or 'inference_model/ppyoloe_plus_crn_m_300e_speed_optimized'
print('Using model_dir:', model_dir)

det = Detector(model_dir=model_dir)
print('Detector ready:', det.is_ready, 'last_error=', det.last_error)

rows = []
count = 0
for p in sorted(INPUT_DIR.glob('*.jpg')):
    img = cv2.imread(str(p))
    if img is None:
        continue
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    res = det.detect_image(img_rgb)
    boxes_cnt = len(getattr(det, 'last_boxes', []))
    total_ms = det.last_timing.get('total_ms', None) if getattr(det, 'last_timing', None) else None
    rows.append((p.name, boxes_cnt, total_ms))
    # Save visualization for first 10 images
    if count < 10:
        outp = OUT_DIR / p.name
        cv2.imwrite(str(outp), cv2.cvtColor(res, cv2.COLOR_RGB2BGR))
    count += 1

with open(CSV, 'w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['filename', 'boxes_count', 'total_ms'])
    w.writerows(rows)

print('Processed', len(rows), 'images. Summary saved to', CSV)
