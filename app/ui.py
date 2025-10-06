# app/ui.py
# Detector skeleton for PP-YOLO-L inference (Paddle Inference) with fallback mode.
# 说明：
# - 推荐将训练模型导出为 Paddle Inference 格式（model.pdmodel + model.pdiparams）
# - 若需要从 .pdparams 恢复训练模型，请在本文件中实现模型结构并加载参数
# - 当前实现：若未检测到 paddle 或推理模型则使用简单的图像阈值回退展示效果

import os
import time
from typing import Optional, Tuple, List, Dict, Any

import numpy as np
import cv2

try:
    import paddle
    from paddle.inference import Config, create_predictor
    _HAS_PADDLE = True
except Exception:
    _HAS_PADDLE = False


DEFAULT_COLOR_PALETTE: List[Tuple[int, int, int]] = [
    (0, 0, 255),      # Red
    (0, 255, 0),      # Green
    (255, 0, 0),      # Blue
    (0, 255, 255),    # Yellow
    (255, 0, 255),    # Magenta
    (255, 255, 0),    # Cyan
    (0, 128, 255),    # Orange-ish
    (128, 0, 255),    # Purple
]


class Detector:
    """
    Detector 提供最小接口：
      - __init__(model_dir=None, use_gpu=False)
      - load_inference_model(model_dir)
      - detect_image(img_rgb) -> img_rgb_with_visuals

    注意：PP-YOLO-L 需要模型定义或导出的 inference 模型。本文件提供推理加载的占位实现，
    若要接入真实导出模型，请把 model_dir 指向包含 model.pdmodel + model.pdiparams 的目录。
    """

    def __init__(self, model_dir: Optional[str] = None, use_gpu: Optional[bool] = None, gpu_id: int = 0):
        self.model_dir = self._resolve_model_dir(model_dir)
        self.gpu_id = gpu_id
        self._gpu_available = self._probe_gpu_support() if _HAS_PADDLE else False
        if use_gpu is None:
            self.use_gpu = self._gpu_available
            self._gpu_requested = self.use_gpu
        else:
            self.use_gpu = bool(use_gpu)
            self._gpu_requested = self.use_gpu
            if self.use_gpu and not self._gpu_available:
                print("[WARN] 用户请求使用 GPU，但当前 Paddle 安装不支持 CUDA，已回退至 CPU。")
                self.use_gpu = False
        self._using_gpu_runtime = False
        self.predictor = None
        self.input_names = []
        self.output_names = []
        self.is_ready = False
        self.last_error: Optional[str] = None
        # 默认预处理尺寸，可由 infer_cfg.yml 覆盖
        self.target_size = (640, 640)
        # 默认后处理阈值（将置信度阈值提高到 0.5）
        self.score_threshold = 0.5
        # 默认 NMS IoU 阈值（保持原值，可按需调整）
        self.nms_iou_threshold = 0.45
        # 可选的可视化过滤阈值（脚本与 GUI 均可按需覆盖）
        self.min_box_side: float = 6.0
        self.min_box_area: float = 36.0
        self.max_box_aspect_ratio: float = 12.0  # max(longer/shorter)
        self.max_box_count: Optional[int] = 200
        self.class_names: List[str] = []
        self.class_colors: Dict[int, Tuple[int, int, int]] = {}
        self.profile_enabled: bool = True
        self.last_timing: Dict[str, float] = {}
        self.last_boxes: List[Tuple[float, float, float, float, float, int]] = []
        self.keep_ratio: bool = False
        self._outputs_in_original_space: bool = False
        if self.model_dir:
            self.load_inference_model(self.model_dir)

    def _resolve_model_dir(self, model_dir: Optional[str]) -> Optional[str]:
        """根据入参与环境变量决定最终模型目录。"""
        if model_dir and isinstance(model_dir, str):
            model_dir = model_dir.strip()
            if model_dir.lower() in {"", "auto", "none"}:
                model_dir = None
        if not model_dir:
            env_dir = os.getenv("BUCKWHEAT_MODEL_DIR", "").strip()
            if env_dir:
                model_dir = env_dir
        if model_dir and not os.path.isdir(model_dir):
            print(f"[WARN] 指定的模型目录不存在: {model_dir}")
            return None
        return model_dir

    def _probe_gpu_support(self) -> bool:
        if not _HAS_PADDLE:
            return False
        try:
            return bool(paddle.device.is_compiled_with_cuda() and paddle.device.cuda.device_count() > 0)
        except Exception:
            return False

    def load_inference_model(self, model_dir: str):
        """尝试加载 Paddle Inference 导出模型（model.pdmodel + model.pdiparams）。"""
        if not _HAS_PADDLE:
            msg = "Paddle 未安装，进入回退模式（不会执行真实模型推理）。"
            print(msg)
            self.last_error = msg
            self.is_ready = False
            return

        model_file = os.path.join(model_dir, "model.pdmodel")
        params_file = os.path.join(model_dir, "model.pdiparams")
        if not (os.path.exists(model_file) and os.path.exists(params_file)):
            msg = f"未在 {model_dir} 找到 inference 模型 (model.pdmodel / model.pdiparams)。"
            print(msg)
            self.last_error = msg
            self.is_ready = False
            return

        self.class_names = []
        self.class_colors = {}

        # 尝试读取 infer_cfg.yml 中的配置信息
        cfg_path = os.path.join(model_dir, "infer_cfg.yml")
        if os.path.exists(cfg_path):
            try:
                target_hw = None
                parsed_labels: List[str] = []
                try:
                    import yaml  # type: ignore

                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = yaml.safe_load(f)
                    preprocess_conf = []
                    if isinstance(cfg, dict):
                        preprocess_conf = cfg.get("Preprocess") or cfg.get("preprocess") or []
                    for step in preprocess_conf if isinstance(preprocess_conf, list) else []:
                        if isinstance(step, dict):
                            step_type = str(step.get("type") or step.get("Type") or "").lower()
                            if step_type == "resize" and step.get("target_size"):
                                t = step.get("target_size")
                                if isinstance(t, (list, tuple)) and len(t) >= 2:
                                    target_hw = (int(t[0]), int(t[1]))
                                    break
                    label_list = []
                    if isinstance(cfg, dict):
                        label_list = cfg.get("label_list") or cfg.get("LabelList") or []
                    if isinstance(label_list, (list, tuple)):
                        parsed_labels = [str(item) for item in label_list]
                except Exception:
                    target_hw = None

                if target_hw is None:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        txt = f.read()
                    import re

                    m = re.search(r"target_size:\s*\n\s*-\s*(\d+)\s*\n\s*-\s*(\d+)", txt)
                    if m:
                        target_hw = (int(m.group(1)), int(m.group(2)))
                    if not parsed_labels:
                        label_match = re.search(r"label_list:\s*\n((?:\s*-\s*[^\n]+\n)+)", txt)
                        if label_match:
                            lines = [line.strip() for line in label_match.group(1).strip().splitlines()]
                            parsed_labels = [line.split("-", 1)[1].strip() for line in lines if "-" in line]

                if target_hw is not None:
                    h, w = target_hw
                    # cv2.resize 需要 (width, height)
                    self.target_size = (w, h)
                    print(f"从 infer_cfg.yml 读取 target_size -> {self.target_size}")
                # 解析 keep_ratio 设置（若存在）
                try:
                    resize_steps = []
                    if isinstance(cfg, dict):
                        resize_steps = cfg.get("Preprocess") or cfg.get("preprocess") or []
                    for step in resize_steps if isinstance(resize_steps, list) else []:
                        if isinstance(step, dict) and str(step.get("type") or step.get("Type") or "").lower() == "resize":
                            if "keep_ratio" in step:
                                val = step.get("keep_ratio")
                                if isinstance(val, str):
                                    self.keep_ratio = val.strip().lower() in {"true", "1", "yes", "y"}
                                else:
                                    self.keep_ratio = bool(val)
                            break
                except Exception:
                    pass
                if parsed_labels:
                    self.class_names = parsed_labels
                    self._refresh_class_colors()
            except Exception as e:
                msg = f"读取 infer_cfg.yml 失败: {e}"
                print(msg)
                self.last_error = msg

        config = Config(model_file, params_file)
        want_gpu = bool(self.use_gpu)
        if want_gpu:
            gpu_ok = self._probe_gpu_support()
            if not gpu_ok:
                print("[WARN] 当前环境未检测到可用的 CUDA GPU，使用 CPU 推理。")
                want_gpu = False
            else:
                try:
                    config.enable_use_gpu(100, self.gpu_id)
                    self._using_gpu_runtime = True
                except Exception as exc:
                    print(f"[WARN] 启用 GPU 失败 ({exc})，改用 CPU 推理。")
                    want_gpu = False
        if not want_gpu:
            config.disable_gpu()
            config.set_cpu_math_library_num_threads(4)
            self._using_gpu_runtime = False
        self.use_gpu = want_gpu
        config.switch_ir_optim(True)
        config.enable_memory_optim()
        self.predictor = create_predictor(config)
        self.input_names = self.predictor.get_input_names()
        self.output_names = self.predictor.get_output_names()
        self._outputs_in_original_space = len(self.input_names) > 1
        self.is_ready = True
        self.last_error = None
        print("已加载 Paddle Inference 模型：", model_dir)

    def _refresh_class_colors(self):
        if not self.class_names:
            self.class_colors = {}
            return
        palette = DEFAULT_COLOR_PALETTE if DEFAULT_COLOR_PALETTE else [(0, 255, 0)]
        self.class_colors = {
            idx: palette[idx % len(palette)]
            for idx in range(len(self.class_names))
        }

    def preprocess(self, img_rgb: np.ndarray) -> Tuple[np.ndarray, Dict[str, Any]]:
        """根据导出配置决定是否保持纵横比，返回输入张量及缩放/填充元信息。"""
        orig_h, orig_w = img_rgb.shape[:2]
        target = getattr(self, "target_size", (640, 640))
        if isinstance(target, (list, tuple)):
            if len(target) >= 2:
                target_w, target_h = int(target[0]), int(target[1])
            else:
                target_w = target_h = int(target[0])
        else:
            target_w = target_h = int(target)
        target_w = max(1, target_w)
        target_h = max(1, target_h)

        if getattr(self, "keep_ratio", False):
            ratio = min(target_w / float(orig_w), target_h / float(orig_h))
            ratio = max(ratio, 1e-6)
            resized_w = int(round(orig_w * ratio))
            resized_h = int(round(orig_h * ratio))

            resized = cv2.resize(img_rgb, (resized_w, resized_h)) if (resized_w, resized_h) != (orig_w, orig_h) else img_rgb.copy()
            scale_w = resized_w / float(orig_w)
            scale_h = resized_h / float(orig_h)

            pad_w = max(0, target_w - resized_w)
            pad_h = max(0, target_h - resized_h)
            pad_left = pad_w // 2
            pad_right = pad_w - pad_left
            pad_top = pad_h // 2
            pad_bottom = pad_h - pad_top

            padded = np.zeros((target_h, target_w, 3), dtype=img_rgb.dtype)
            padded[pad_top:pad_top + resized_h, pad_left:pad_left + resized_w] = resized

            inp = padded.astype("float32") / 255.0
            inp = inp.transpose(2, 0, 1)  # C,H,W
            inp = np.expand_dims(inp, axis=0)  # 1,C,H,W

            meta: Dict[str, Any] = {
                "orig_size": (orig_w, orig_h),
                "resize_shape": (resized_w, resized_h),
                "resize_ratio": ratio,
                "pad": (pad_left, pad_top),
                "target_size": (target_w, target_h),
                "scale_factor": np.array([[scale_h, scale_w]], dtype=np.float32),
                "scale_wh": (scale_w, scale_h),
                "keep_ratio": True,
            }
        else:
            resized = cv2.resize(img_rgb, (target_w, target_h)) if (target_w, target_h) != (orig_w, orig_h) else img_rgb.copy()
            scale_w = target_w / float(orig_w)
            scale_h = target_h / float(orig_h)

            inp = resized.astype("float32") / 255.0
            inp = inp.transpose(2, 0, 1)
            inp = np.expand_dims(inp, axis=0)

            meta = {
                "orig_size": (orig_w, orig_h),
                "resize_shape": (target_w, target_h),
                "resize_ratio": (scale_w, scale_h),
                "pad": (0.0, 0.0),
                "target_size": (target_w, target_h),
                "scale_factor": np.array([[scale_h, scale_w]], dtype=np.float32),
                "scale_wh": (scale_w, scale_h),
                "keep_ratio": False,
            }
        return inp, meta

    def postprocess(self, raw_outputs: List[np.ndarray], meta: Dict[str, Any]) -> List[Tuple[int, int, int, int, float, int]]:
        """按照 PaddleDetection PP-YOLOE 导出格式解析预测结果。

        PaddleDetection 导出的检测模型默认返回两个输出：
          1. bbox，形状为 [N, 6]，列顺序为 [label, score, xmin, ymin, xmax, ymax]
          2. bbox_num，形状为 [batch_size]，表示每张图片的有效框数量

        该函数会：
          - 根据 bbox_num 截取有效框
          - 根据 score 阈值过滤
          - 将坐标从预处理尺度映射回原图尺寸
          - 对每个类别执行简单 NMS
        返回值为 [(x1, y1, x2, y2, score, cls_id), ...]
        """
        if not raw_outputs:
            print("DEBUG postprocess: empty raw_outputs")
            return []

        try:
            bbox_raw = np.array(raw_outputs[0])
        except Exception as e:
            print("DEBUG postprocess: cannot convert first output to array", e)
            return []

        bbox_raw = np.squeeze(bbox_raw)
        if bbox_raw.ndim == 1:
            # 尝试推断列数（默认为 6）
            cols = 6 if bbox_raw.size % 6 == 0 else bbox_raw.size
            bbox_raw = bbox_raw.reshape(-1, cols)
        if bbox_raw.ndim != 2 or bbox_raw.shape[1] < 6:
            print("DEBUG postprocess: unexpected bbox shape", bbox_raw.shape)
            return []

        total_boxes = bbox_raw.shape[0]
        bbox_num = None
        if len(raw_outputs) > 1:
            try:
                bbox_num_arr = np.array(raw_outputs[1]).astype("int32").reshape(-1)
                if bbox_num_arr.size > 0:
                    bbox_num = int(bbox_num_arr[0])
            except Exception:
                bbox_num = None
        if bbox_num is not None:
            total_boxes = min(total_boxes, max(bbox_num, 0))

        bbox_raw = bbox_raw[:total_boxes, :6]
        if total_boxes == 0:
            return []

        # 列顺序：[label, score, xmin, ymin, xmax, ymax]
        cls_ids = bbox_raw[:, 0].astype(np.int32)
        scores = bbox_raw[:, 1].astype(np.float32)
        coords = bbox_raw[:, 2:6].astype(np.float32)

        score_thresh = float(getattr(self, "score_threshold", 0.5))
        keep = scores >= score_thresh
        if not np.any(keep):
            print("DEBUG postprocess: no boxes above score threshold", score_thresh)
            return []

        cls_ids = cls_ids[keep]
        scores = scores[keep]
        coords = coords[keep]

        orig_size = meta.get("orig_size") if isinstance(meta, dict) else None
        if orig_size is None:
            return []
        orig_w, orig_h = float(orig_size[0]), float(orig_size[1])

        need_transform = True
        if getattr(self, "_outputs_in_original_space", False):
            need_transform = False
        else:
            # 兜底：若检测框坐标已大于预处理尺度，也视为原始坐标
            target_size = None
            if isinstance(meta, dict):
                target_size = meta.get("target_size")
            if isinstance(target_size, (tuple, list)) and len(target_size) >= 2:
                max_target = float(max(target_size[0], target_size[1]))
                if max_target > 0:
                    if float(np.max(coords[:, :4])) > max_target * 1.05:
                        need_transform = False
        if need_transform:
            pad_left, pad_top = (meta.get("pad", (0.0, 0.0)) if isinstance(meta, dict) else (0.0, 0.0))
            pad_left = float(pad_left)
            pad_top = float(pad_top)

            scale_w, scale_h = (meta.get("scale_wh") if isinstance(meta, dict) else (1.0, 1.0))
            scale_w = float(scale_w) if scale_w else 1.0
            scale_h = float(scale_h) if scale_h else 1.0

            coords[:, 0] = np.clip((coords[:, 0] - pad_left) / max(scale_w, 1e-6), 0, orig_w)
            coords[:, 1] = np.clip((coords[:, 1] - pad_top) / max(scale_h, 1e-6), 0, orig_h)
            coords[:, 2] = np.clip((coords[:, 2] - pad_left) / max(scale_w, 1e-6), 0, orig_w)
            coords[:, 3] = np.clip((coords[:, 3] - pad_top) / max(scale_h, 1e-6), 0, orig_h)
        else:
            coords[:, 0] = np.clip(coords[:, 0], 0, orig_w)
            coords[:, 1] = np.clip(coords[:, 1], 0, orig_h)
            coords[:, 2] = np.clip(coords[:, 2], 0, orig_w)
            coords[:, 3] = np.clip(coords[:, 3], 0, orig_h)

        # 按类别执行简易 NMS
        iou_thresh = float(getattr(self, "nms_iou_threshold", 0.45))
        final_boxes: List[Tuple[float, float, float, float, float, int]] = []
        unique_cls = np.unique(cls_ids)
        for cls in unique_cls:
            inds = np.where(cls_ids == cls)[0]
            if inds.size == 0:
                continue
            cls_coords = coords[inds]
            cls_scores = scores[inds]
            order = cls_scores.argsort()[::-1]
            while order.size > 0:
                i = order[0]
                x1, y1, x2, y2 = cls_coords[i]
                score = cls_scores[i]
                final_boxes.append((float(x1), float(y1), float(x2), float(y2), float(score), int(cls)))
                if order.size == 1:
                    break
                # 计算 IoU
                xx1 = np.maximum(x1, cls_coords[order[1:], 0])
                yy1 = np.maximum(y1, cls_coords[order[1:], 1])
                xx2 = np.minimum(x2, cls_coords[order[1:], 2])
                yy2 = np.minimum(y2, cls_coords[order[1:], 3])
                w = np.maximum(0.0, xx2 - xx1)
                h = np.maximum(0.0, yy2 - yy1)
                inter = w * h
                area_i = (x2 - x1) * (y2 - y1)
                area_rest = (cls_coords[order[1:], 2] - cls_coords[order[1:], 0]) * (cls_coords[order[1:], 3] - cls_coords[order[1:], 1])
                iou = inter / (area_i + area_rest - inter + 1e-6)
                remain = np.where(iou <= iou_thresh)[0]
                order = order[remain + 1]

        # 额外的几何过滤，避免极细长/极小框造成噪声
        min_side = float(getattr(self, "min_box_side", 0.0) or 0.0)
        min_area = float(getattr(self, "min_box_area", 0.0) or 0.0)
        max_aspect = float(getattr(self, "max_box_aspect_ratio", 0.0) or 0.0)
        filtered_boxes: List[Tuple[float, float, float, float, float, int]] = []
        for (x1, y1, x2, y2, score, cls_id) in final_boxes:
            w = max(0.0, float(x2) - float(x1))
            h = max(0.0, float(y2) - float(y1))
            area = w * h
            if min_side > 0.0 and (w < min_side or h < min_side):
                continue
            if min_area > 0.0 and area < min_area:
                continue
            if max_aspect > 0.0:
                longer = max(w, h)
                shorter = max(1e-6, min(w, h))
                if longer / shorter > max_aspect:
                    continue
            filtered_boxes.append((x1, y1, x2, y2, score, cls_id))

        if getattr(self, "max_box_count", None) is not None:
            try:
                max_count = int(self.max_box_count)  # type: ignore[attr-defined]
            except Exception:
                max_count = None
            if max_count is not None and max_count > 0 and len(filtered_boxes) > max_count:
                filtered_boxes = sorted(filtered_boxes, key=lambda b: b[4], reverse=True)[:max_count]

        print(
            "DEBUG postprocess:",
            f"score>{score_thresh}, iou<{iou_thresh}, initial={len(final_boxes)}, after_geom={len(filtered_boxes)}"
        )
        return filtered_boxes
        

    def _infer(self, img_rgb: np.ndarray) -> np.ndarray:
        """使用 Paddle Predictor 做推理并绘制结果，同时记录耗时信息。"""
        if not self.is_ready or self.predictor is None:
            return img_rgb

        try:
            boxes, orig, timings = self._run_pipeline(img_rgb)
        except Exception as exc:
            msg = f"执行推理失败: {exc}"
            print(msg)
            self.last_error = msg
            self.last_boxes = []
            if self.profile_enabled:
                self.last_timing = {}
            return img_rgb

        self.last_boxes = boxes
        self.last_error = None
        if self.profile_enabled:
            self.last_timing = timings

        out_img_bgr = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2BGR)
        height, width = out_img_bgr.shape[:2]
        default_palette = DEFAULT_COLOR_PALETTE if DEFAULT_COLOR_PALETTE else [(0, 255, 0)]
        for (x1, y1, x2, y2, score, cls) in boxes:
            cls_idx = int(cls)
            color_bgr = self.class_colors.get(cls_idx)
            if color_bgr is None:
                color_bgr = default_palette[cls_idx % len(default_palette)]
            color_bgr = tuple(int(c) for c in color_bgr)
            x1_i, y1_i, x2_i, y2_i = [int(round(v)) for v in (x1, y1, x2, y2)]
            x1_i = max(0, min(width - 1, x1_i))
            y1_i = max(0, min(height - 1, y1_i))
            x2_i = max(0, min(width - 1, x2_i))
            y2_i = max(0, min(height - 1, y2_i))
            cv2.rectangle(out_img_bgr, (x1_i, y1_i), (x2_i, y2_i), color_bgr, thickness=2)

            label = self.class_names[cls_idx] if 0 <= cls_idx < len(self.class_names) else str(cls_idx)
            text = f"{label} {score * 100:.1f}%"
            font = cv2.FONT_HERSHEY_SIMPLEX
            box_w = max(1, x2_i - x1_i)
            box_h = max(1, y2_i - y1_i)
            # 根据框大小自适应字号并限制范围，防止过大遮挡
            adaptive_scale = min(box_w / 320.0, box_h / 180.0)
            font_scale = max(0.35, min(0.55, adaptive_scale))
            font_thickness = 1 if font_scale <= 0.45 else 2
            (text_w, text_h), text_baseline = cv2.getTextSize(text, font, font_scale, font_thickness)
            text_x = int(max(0, min(x1_i, width - text_w - 1)))
            text_y = int(y1_i) - 6
            min_text_y = text_h + text_baseline + 4
            if text_y < min_text_y:
                text_y = min(height - text_baseline - 1, y2_i + text_h + text_baseline + 6)
            text_y = max(text_baseline + 1, min(height - 1, text_y))
            text_bg_top = max(0, text_y - text_h - text_baseline)
            text_bg_bottom = min(height, text_y + text_baseline)
            text_bg_right = min(width, text_x + text_w)
            if text_bg_bottom > text_bg_top and text_bg_right > text_x:
                cv2.rectangle(out_img_bgr, (text_x, text_bg_top), (text_bg_right, text_bg_bottom), color_bgr, thickness=-1)
            b, g, r = color_bgr
            luma = 0.299 * r + 0.587 * g + 0.114 * b
            text_color = (0, 0, 0) if luma > 128 else (255, 255, 255)
            cv2.putText(out_img_bgr, text, (text_x, text_y), font, font_scale, text_color, font_thickness, cv2.LINE_AA)

        return cv2.cvtColor(out_img_bgr, cv2.COLOR_BGR2RGB)

    def _run_pipeline(self, img_rgb: np.ndarray) -> Tuple[List[Tuple[float, float, float, float, float, int]], Tuple[int, int], Dict[str, float]]:
        """执行预处理->推理->后处理，返回检测框、原图尺寸和耗时。"""
        timings: Dict[str, float] = {}
        t_total = time.perf_counter()

        t0 = time.perf_counter()
        inp, meta = self.preprocess(img_rgb)
        timings["preprocess_ms"] = (time.perf_counter() - t0) * 1000.0

        scale_factor = meta.get("scale_factor") if isinstance(meta, dict) else None

        t1 = time.perf_counter()
        outputs = self._execute_predictor(inp, scale_factor)
        timings["predict_ms"] = (time.perf_counter() - t1) * 1000.0

        t2 = time.perf_counter()
        boxes = self.postprocess(outputs, meta)
        timings["postprocess_ms"] = (time.perf_counter() - t2) * 1000.0

        timings["total_ms"] = (time.perf_counter() - t_total) * 1000.0
        if isinstance(meta, dict) and "orig_size" in meta:
            orig_size = meta["orig_size"]
        else:
            orig_size = (img_rgb.shape[1], img_rgb.shape[0])
        return boxes, orig_size, timings

    def _compute_scale_factor(self, orig_size: Tuple[int, int]) -> np.ndarray:
        """根据原始尺寸和目标尺寸计算 scale_factor，符合 PP-YOLOE 约定。"""
        orig_w = max(1.0, float(orig_size[0]))
        orig_h = max(1.0, float(orig_size[1]))
        target_size = getattr(self, "target_size", (640, 640))
        if isinstance(target_size, (list, tuple)) and len(target_size) >= 2:
            target_w, target_h = float(target_size[0]), float(target_size[1])
        else:
            target_w = target_h = float(target_size)
        scale_h = float(target_h) / orig_h
        scale_w = float(target_w) / orig_w
        return np.array([[scale_h, scale_w]], dtype=np.float32)

    def _execute_predictor(self, inp: np.ndarray, scale_factor: Optional[np.ndarray]) -> List[np.ndarray]:
        outputs: List[np.ndarray] = []
        if self.predictor is None:
            return outputs

        input_handle = self.predictor.get_input_handle(self.input_names[0])
        try:
            input_handle.reshape(inp.shape)
        except Exception:
            pass
        input_handle.copy_from_cpu(inp)

        if len(self.input_names) > 1:
            if scale_factor is None:
                scale_factor = np.array([[1.0, 1.0]], dtype=np.float32)
            sf_handle = self.predictor.get_input_handle(self.input_names[1])
            try:
                sf_handle.reshape(scale_factor.shape)
            except Exception:
                try:
                    flat = scale_factor.reshape(-1)
                    sf_handle.reshape(flat.shape)
                    scale_factor = flat
                except Exception:
                    pass
            sf_handle.copy_from_cpu(scale_factor)

        self.predictor.run()
        for name in self.output_names:
            out_handle = self.predictor.get_output_handle(name)
            outputs.append(out_handle.copy_to_cpu())
        return outputs

    def detect_image(self, img_rgb: np.ndarray) -> np.ndarray:
        """
        对单张 RGB 图片执行检测并返回带可视化的 RGB 图像。
        若模型不可用，使用简单阈值法作为回退示例。
        """
        if self.is_ready:
            return self._infer(img_rgb)

        # 回退：基于亮区域做简单连通域检测以示范可视化过程
        fallback_boxes: List[Tuple[float, float, float, float, float, int]] = []
        gray = cv2.cvtColor(img_rgb, cv2.COLOR_RGB2GRAY)
        _, th = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY)
        contours, _ = cv2.findContours(th, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        out = img_rgb.copy()
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if w * h < 100:
                continue
            cv2.rectangle(out, (x, y), (x + w, y + h), (255, 0, 0), 2)
            fallback_boxes.append((float(x), float(y), float(x + w), float(y + h), 1.0, 0))
        self.last_boxes = fallback_boxes
        if self.profile_enabled:
            self.last_timing = {}
        return out


if __name__ == "__main__":
    # 调试用：python -m app.ui path/to/image.jpg
    det = Detector()
    import sys
    if len(sys.argv) > 1:
        p = sys.argv[1]
        img = cv2.imread(p)
        if img is None:
            print("无法读取图片：", p)
        else:
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            res = det.detect_image(img_rgb)
            res_bgr = cv2.cvtColor(res, cv2.COLOR_RGB2BGR)
            cv2.imwrite("debug_result.jpg", res_bgr)
            print("写出 debug_result.jpg")