import os
import sys
import glob
import json
import yaml
import cv2
import numpy as np
try:
    import paddle.inference as paddle_infer
except Exception as e:
    print("Failed to import paddle.inference:", e)
    sys.exit(1)


def find_model_files(model_dir):
    model_file = None
    params_file = None
    if not os.path.isdir(model_dir):
        return None, None
    for name in os.listdir(model_dir):
        if name.endswith('.pdmodel'):
            model_file = os.path.join(model_dir, name)
        if name.endswith('.pdiparams') or name.endswith('.pdparams'):
            params_file = os.path.join(model_dir, name)
    return model_file, params_file


def load_infer_cfg(model_dir):
    for root, dirs, files in os.walk(model_dir):
        if 'infer_cfg.yml' in files:
            return os.path.join(root, 'infer_cfg.yml')
    return None


def preprocess_image(im_path, target_size=None):
    # Normalize path to avoid leading-backslash being treated as drive-root on Windows.
    if os.path.isabs(im_path):
        if im_path.startswith('\\') or im_path.startswith('/'):
            im_path = os.path.join(os.getcwd(), im_path.lstrip('\\/'))
        else:
            im_path = os.path.abspath(im_path)
    else:
        im_path = os.path.abspath(im_path)

    im = cv2.imread(im_path)
    if im is None:
        raise FileNotFoundError(im_path)
    im_rgb = cv2.cvtColor(im, cv2.COLOR_BGR2RGB)
    orig_h, orig_w = im_rgb.shape[:2]
    if target_size:
        w, h = target_size
        im_resized = cv2.resize(im_rgb, (w, h))
    else:
        im_resized = im_rgb
    inp = im_resized.astype('float32')
    inp /= 255.0
    inp = inp.transpose((2, 0, 1))
    inp = np.expand_dims(inp, axis=0)
    return inp, (orig_w, orig_h), im


def build_predictor(model_file, params_file, use_gpu=False):
    config = paddle_infer.Config(model_file, params_file)
    if use_gpu:
        config.enable_use_gpu(100, 0)
    else:
        config.disable_gpu()
        try:
            config.enable_mkldnn()
        except Exception:
            pass
    config.switch_ir_optim(True)
    predictor = paddle_infer.create_predictor(config)
    return predictor, config


def run_single(predictor, input_names, img_path, target_size):
    inp, orig_wh, _ = preprocess_image(img_path, target_size=target_size)
    input_handle = predictor.get_input_handle(input_names[0])
    try:
        input_handle.reshape(inp.shape)
    except Exception:
        pass
    input_handle.copy_from_cpu(inp)

    if len(input_names) > 1:
        try:
            if target_size:
                sf = np.array([float(orig_wh[0]) / float(target_size[0]),
                               float(orig_wh[1]) / float(target_size[1])], dtype=np.float32)
            else:
                sf = np.array([1.0, 1.0], dtype=np.float32)
            sf = np.reshape(sf, (1, 2))
        except Exception:
            sf = np.array([1.0, 1.0], dtype=np.float32)
            sf = np.reshape(sf, (1, 2))
        sf_handle = predictor.get_input_handle(input_names[1])
        try:
            sf_handle.reshape(sf.shape)
        except Exception:
            pass
        sf_handle.copy_from_cpu(sf)

    predictor.run()
    out_names = predictor.get_output_names()
    outputs = {}
    for n in out_names:
        h = predictor.get_output_handle(n)
        out = h.copy_to_cpu()
        outputs[n] = out
    return outputs


def main():
    model_dir = 'inference_model/server_export/output_inference/ppyoloe_plus_crn_m_300e_speed_optimized/ppyoloe_plus_crn_m_300e_speed_optimized'
    model_file, params_file = find_model_files(model_dir)
    if model_file is None or params_file is None:
        print('Model files not found in', model_dir)
        sys.exit(1)

    cfg_path = load_infer_cfg(model_dir)
    target_size = None
    if cfg_path:
        try:
            with open(cfg_path, 'r') as f:
                cfg = yaml.safe_load(f)
            preprocess = cfg.get('Preprocess') or cfg.get('preprocess') or []
            for item in preprocess if isinstance(preprocess, list) else []:
                if isinstance(item, dict):
                    t = item.get('type') or item.get('Type')
                    if t and t.lower().startswith('resize'):
                        ts = item.get('target_size') or item.get('target_size_list') or item.get('target_size_tuple')
                        if ts and len(ts) >= 2:
                            target_size = (int(ts[0]), int(ts[1]))
                            break
        except Exception as e:
            print('Failed to parse infer_cfg.yml:', e)

    predictor, config = build_predictor(model_file, params_file, use_gpu=False)
    input_names = predictor.get_input_names()

    im_paths = sorted(glob.glob('data/raw/train-use/test/*.jpg') + glob.glob('data/raw/train-use/test/*.png'))
    os.makedirs('inference_results', exist_ok=True)

    report_lines = []
    report_lines.append('| image | preds | gt_shapes | note |')
    report_lines.append('|---|---:|---:|---|')

    for im in im_paths:
        try:
            outputs = run_single(predictor, input_names, im, target_size)
            first_out = next(iter(outputs.values()))
            try:
                preds_count = int(first_out.shape[0])
            except Exception:
                preds_count = 0
            note = ''
        except Exception as e:
            preds_count = -1
            note = 'infer_error'
            outputs = {}

        json_path = os.path.splitext(im)[0] + '.json'
        gt_count = 0
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    j = json.load(f)
                shapes = j.get('shapes') or []
                gt_count = len(shapes)
            except Exception:
                note = 'json_parse_error'
        else:
            note = 'no_json'

        report_lines.append(f'| {im} | {preds_count} | {gt_count} | {note} |')

    with open('inference_results/report.md', 'w', encoding='utf-8') as f:
        f.write('# Inference report\n\n')
        f.write('Generated by [`batch_infer_report.py`](inference_model/server_export/batch_infer_report.py:1)\n\n')
        f.write('\\n'.join(report_lines))

    print('Report written to inference_results/report.md')


if __name__ == '__main__':
    main()