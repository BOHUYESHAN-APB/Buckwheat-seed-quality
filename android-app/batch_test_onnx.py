#!/usr/bin/env python3
"""Batch test different paddle2onnx export parameters and generate annotated images for comparison."""
import os
import subprocess
import sys

paddle_model_dir = 'inference_model/server_export/output_inference/ppyoloe_plus_crn_m_300e_speed_optimized/ppyoloe_plus_crn_m_300e_speed_optimized'
test_image = 'data/raw/train-use/test/test-001.jpg'
output_base = 'android-app/output'

# Test configurations: (name, opset, enable_paddle_fallback, enable_auto_update_opset)
configs = [
    ('opset11_no_fallback', 11, 'False', 'True'),
    ('opset13_no_fallback', 13, 'False', 'True'),
    ('opset14_no_fallback', 14, 'False', 'True'),
    ('opset14_no_fallback_no_auto', 14, 'False', 'False'),
]

results = []

for name, opset, fallback, auto_update in configs:
    print(f'\n{"="*60}')
    print(f'Testing: {name}')
    print(f'  opset={opset}, fallback={fallback}, auto_update={auto_update}')
    print(f'{"="*60}')
    
    onnx_path = os.path.join(output_base, f'{name}.onnx')
    annotated_path = os.path.join(output_base, f'annotated_{name}.png')
    
    # Convert to ONNX
    cmd = [
        'paddle2onnx',
        '-m', paddle_model_dir,
        '-mf', 'model.pdmodel',
        '-pf', 'model.pdiparams',
        '-s', onnx_path,
        '-ov', str(opset),
        '--enable_paddle_fallback', fallback,
        '--enable_auto_update_opset', auto_update,
    ]
    
    print(f'Running: {" ".join(cmd)}')
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            print(f'FAILED to convert: {result.stderr}')
            results.append((name, 'CONVERT_FAILED', 0, result.stderr[:100]))
            continue
        print('Conversion succeeded')
    except Exception as e:
        print(f'EXCEPTION during conversion: {e}')
        results.append((name, 'CONVERT_EXCEPTION', 0, str(e)[:100]))
        continue
    
    # Test ONNX inference
    cmd_infer = [
        sys.executable,
        'android-app/onnx_annotate_image.py',
        onnx_path,
        test_image,
        annotated_path,
    ]
    
    print(f'Running inference: {" ".join(cmd_infer)}')
    try:
        result = subprocess.run(cmd_infer, capture_output=True, text=True, timeout=60)
        output_text = result.stdout + result.stderr
        
        # Parse detection count from output
        det_count = 0
        if 'out[0] shape=' in output_text:
            # Extract shape
            for line in output_text.split('\n'):
                if 'out[0] shape=' in line:
                    # e.g., "out[0] shape=(300, 6)" or "out[0] shape=(0, 6)"
                    if 'shape=(' in line:
                        shape_str = line.split('shape=(')[1].split(')')[0]
                        det_count = int(shape_str.split(',')[0].strip())
                    break
        
        if result.returncode != 0:
            print(f'Inference FAILED: {output_text[:200]}')
            results.append((name, 'INFER_FAILED', det_count, output_text[:100]))
        else:
            print(f'Inference succeeded, detections={det_count}')
            results.append((name, 'SUCCESS', det_count, ''))
            
    except Exception as e:
        print(f'EXCEPTION during inference: {e}')
        results.append((name, 'INFER_EXCEPTION', 0, str(e)[:100]))

# Print summary
print(f'\n\n{"="*60}')
print('SUMMARY')
print(f'{"="*60}')
print(f'{"Config":<30} {"Status":<20} {"Detections":<10} {"Notes"}')
print('-'*60)
for name, status, det_count, notes in results:
    print(f'{name:<30} {status:<20} {det_count:<10} {notes[:20]}')

print(f'\n{"="*60}')
print('Reference: Paddle inference produced 24 detections')
print(f'{"="*60}')
