import os
import sys
import glob
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
    inp = inp.transpose((2,0,1))
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

def visualize_and_save(im_path, detections, target_size, orig_wh, save_path):
    # detections: numpy array (N,6) -> x1,y1,x2,y2,score,class
    im = cv2.imread(im_path)
    if im is None:
        return False
    w_orig = orig_wh[0]
    h_orig = orig_wh[1]
    if target_size:
        tw, th = target_size
        scale_x = w_orig / float(tw)
        scale_y = h_orig / float(th)
    else:
        scale_x = scale_y = 1.0
    for row in detections:
        try:
            x1,y1,x2,y2,score,cls = row[:6]
        except Exception:
            continue
        if score <= 0.05:
            continue
        x1 = int(x1 * scale_x)
        x2 = int(x2 * scale_x)
        y1 = int(y1 * scale_y)
        y2 = int(y2 * scale_y)
        color = (0,255,0)
        cv2.rectangle(im, (x1,y1), (x2,y2), color, 2)
        label = f"{int(cls)}:{score:.2f}"
        cv2.putText(im, label, (x1, max(0,y1-6)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    os.makedirs(os.path.dirname(save_path), exist_ok=True)
    cv2.imwrite(save_path, im)
    return True

def run_batch():
    model_dir = 'inference_model/server_export/output_inference/ppyoloe_plus_crn_m_300e_speed_optimized/ppyoloe_plus_crn_m_300e_speed_optimized'
    model_file, params_file = find_model_files(model_dir)
    if model_file is None or params_file is None:
        print('Model files not found in', model_dir)
        sys.exit(1)
    cfg_path = load_infer_cfg(model_dir)
    target_size = None
    if cfg_path:
        try:
            with open(cfg_path,'r') as f:
                cfg = yaml.safe_load(f)
            preprocess = cfg.get('Preprocess') or cfg.get('preprocess') or []
            for item in preprocess if isinstance(preprocess, list) else []:
                if isinstance(item, dict):
                    t = item.get('type') or item.get('Type')
                    if t and t.lower().startswith('resize'):
                        ts = item.get('target_size') or item.get('target_size_list') or item.get('target_size_tuple')
                        if ts and len(ts)>=2:
                            target_size = (int(ts[0]), int(ts[1]))
                            break
        except Exception as e:
            print('Failed to parse infer_cfg.yml:', e)
    predictor, config = build_predictor(model_file, params_file, use_gpu=False)
    input_names = predictor.get_input_names()
    out_names = predictor.get_output_names()
    im_paths = sorted(glob.glob('data/raw/train-use/test/*.jpg') + glob.glob('data/raw/train-use/test/*.png'))
    vis_dir = 'inference_results/visuals'
    os.makedirs(vis_dir, exist_ok=True)
    report_lines = []
    report_lines.append('| image | preds | visual |')
    report_lines.append('|---|---:|---|')
    for im in im_paths:
        try:
            inp, orig_wh, _ = preprocess_image(im, target_size=target_size)
            input_handle = predictor.get_input_handle(input_names[0])
            try:
                input_handle.reshape(inp.shape)
            except Exception:
                pass
            input_handle.copy_from_cpu(inp)
            if len(input_names) > 1:
                if target_size:
                    sf = np.array([float(orig_wh[0])/float(target_size[0]), float(orig_wh[1])/float(target_size[1])], dtype=np.float32)
                else:
                    sf = np.array([1.0,1.0], dtype=np.float32)
                sf = np.reshape(sf,(1,2))
                sf_handle = predictor.get_input_handle(input_names[1])
                try:
                    sf_handle.reshape(sf.shape)
                except Exception:
                    pass
                sf_handle.copy_from_cpu(sf)
            predictor.run()
            h = predictor.get_output_handle(out_names[0])
            out = h.copy_to_cpu()
            preds_count = 0
            if isinstance(out, np.ndarray) and out.size>0:
                preds_count = int(out.shape[0])
            vis_path = os.path.join(vis_dir, os.path.basename(im))
            saved = False
            try:
                if isinstance(out, np.ndarray) and out.size>0:
                    saved = visualize_and_save(im, out, target_size, orig_wh, vis_path)
            except Exception:
                saved = False
            visual_rel = os.path.relpath(vis_path)
            report_lines.append(f'| {im} | {preds_count} | {visual_rel} |')
        except Exception as e:
            report_lines.append(f'| {im} | error | - |')
    with open('inference_results/report.md','w',encoding='utf-8') as f:
        f.write('# Inference visuals report\n\n')
        f.write('Generated visuals saved under `inference_results/visuals/`\n\n')
        f.write('\\n'.join(report_lines))
    print('Saved visuals and report to inference_results/')

if __name__ == '__main__':
    run_batch()