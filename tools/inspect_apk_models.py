import zipfile
from pathlib import Path
apk_dir = Path(r'e:/CODE/Buckwheat-seed-quality/android-app/app/build/outputs/apk/debug')
apks = list(apk_dir.glob('*.apk'))
if not apks:
    print('No APK found in', apk_dir)
    raise SystemExit(1)
apk = apks[-1]
print('Using APK:', apk)
with zipfile.ZipFile(str(apk),'r') as z:
    model_files = [info for info in z.infolist() if info.filename.startswith('assets/models/')]
    if not model_files:
        print('No assets/models in APK')
    else:
        print('Files in assets/models:')
        total = 0
        for info in model_files:
            print(info.filename, f'{info.file_size/1024/1024:.2f}MB')
            total += info.file_size
        print('Total size (models):', f'{total/1024/1024:.2f}MB')
    # extract model.onnx if present
    target = 'assets/models/model.onnx'
    if target in z.namelist():
        out = Path('e:/CODE/Buckwheat-seed-quality/inference_model/temp_output_inference/apk_extracted_model.onnx')
        with z.open(target) as r, open(out,'wb') as f:
            f.write(r.read())
        print('Extracted model to', out)
    else:
        print('model.onnx not found in APK assets/models')
print('Done')
