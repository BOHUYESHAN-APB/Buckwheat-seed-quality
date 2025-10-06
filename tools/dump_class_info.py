from pathlib import Path
import sys
sys.path.insert(0, str(Path('.').resolve()))
from app.ui import Detector

model_dir = 'inference_model/ppyoloe_plus_crn_m_300e_speed_optimized'
print('Loading detector from', model_dir)

Det = Detector(model_dir=model_dir)
print('is_ready:', Det.is_ready)
print('last_error:', Det.last_error)
print('class_names:', Det.class_names)
print('num classes:', len(Det.class_names))
