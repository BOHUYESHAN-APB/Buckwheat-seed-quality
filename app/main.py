import threading
import time
import os
import sys
from collections import OrderedDict, deque
from typing import Optional
from tkinter import filedialog, messagebox

import customtkinter as ctk
from PIL import Image, ImageTk
import cv2

# 尝试导入 UI/检测实现（稍后由 app/ui.py 提供 Detector 接口）
try:
    from app.ui import Detector
except Exception:
    try:
        from ui import Detector
    except Exception:
        Detector = None


class App(ctk.CTk):
    def __init__(self, width=1000, height=700):
        super().__init__()
        self.title("Buckwheat Detection - new-model")
        self.geometry(f"{width}x{height}")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        # UI 布局
        self.grid_columnconfigure(1, weight=1)
        self.grid_columnconfigure(2, weight=0)
        self.grid_rowconfigure(0, weight=1)

    # 控制面板
        self.control_frame = ctk.CTkFrame(self, width=260)
        self.control_frame.grid(row=0, column=0, sticky="nswe", padx=8, pady=8)

        self.btn_load = ctk.CTkButton(self.control_frame, text="加载图片", command=self.load_image)
        self.btn_load.pack(pady=6, fill="x")

        # 摄像头设备选择（可以输入数字索引或 URL，例如手机 IP 摄像头）
        self.cam_select_label = ctk.CTkLabel(self.control_frame, text="摄像头设备（索引或 URL）")
        self.cam_select_label.pack(pady=(8, 2), fill="x")
        self.cam_entry = ctk.CTkEntry(self.control_frame)
        self.cam_entry.insert(0, "0")
        self.cam_entry.pack(pady=2, fill="x")
        self.btn_scan_cam = ctk.CTkButton(self.control_frame, text="扫描摄像头", command=self._start_scan_cameras)
        self.btn_scan_cam.pack(pady=6, fill="x")

        self.btn_start_cam = ctk.CTkButton(self.control_frame, text="启动摄像头", command=self.start_camera)
        self.btn_start_cam.pack(pady=6, fill="x")

        self.btn_stop_cam = ctk.CTkButton(self.control_frame, text="停止摄像头", command=self.stop_camera, state="disabled")
        self.btn_stop_cam.pack(pady=6, fill="x")

        self.status_label = ctk.CTkLabel(self.control_frame, text="状态: 就绪")
        self.status_label.pack(pady=12, fill="x")

        # 缩放控件
        self.zoom_in_btn = ctk.CTkButton(self.control_frame, text="放大", command=lambda: self._zoom(1.25))
        self.zoom_in_btn.pack(pady=4, fill="x")
        self.zoom_out_btn = ctk.CTkButton(self.control_frame, text="缩小", command=lambda: self._zoom(0.8))
        self.zoom_out_btn.pack(pady=4, fill="x")
        self.zoom_reset_btn = ctk.CTkButton(self.control_frame, text="重置缩放", command=lambda: self._set_zoom(1.0))
        self.zoom_reset_btn.pack(pady=4, fill="x")

        # 置信度阈值与模型控制
        self.score_label = ctk.CTkLabel(self.control_frame, text="置信度阈值")
        self.score_label.pack(pady=(8, 2), fill="x")
        self.score_entry = ctk.CTkEntry(self.control_frame)
        self.score_entry.insert(0, "0.5")
        self.score_entry.pack(pady=2, fill="x")
        self.score_apply_btn = ctk.CTkButton(self.control_frame, text="应用阈值", command=self._apply_score_threshold)
        self.score_apply_btn.pack(pady=4, fill="x")

        # 模型目录与重载/诊断按钮
        # 模型预设
        self._workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        (self.model_presets,
         self.model_preset_validity) = self._discover_model_presets()
        self.auto_reload_on_preset = True
        self._current_preset_name = None
        preset_names = list(self.model_presets.keys())
        valid_defaults = [name for name in preset_names if self.model_preset_validity.get(name)]
        if valid_defaults:
            default_preset = valid_defaults[0]
        elif preset_names:
            default_preset = preset_names[0]
        else:
            default_preset = ""
        if preset_names:
            default_value = default_preset if default_preset else preset_names[0]
            self.model_preset_var = ctk.StringVar(value=default_value)
            self.model_preset_menu = ctk.CTkOptionMenu(
                self.control_frame,
                variable=self.model_preset_var,
                values=preset_names,
                command=self._on_model_preset_changed,
            )
        else:
            self.model_preset_var = ctk.StringVar(value="未发现模型预设")
            self.model_preset_menu = ctk.CTkOptionMenu(
                self.control_frame,
                variable=self.model_preset_var,
                values=["未发现模型预设"],
                state="disabled",
            )
        self.model_preset_menu.pack(pady=(8, 4), fill="x")

        self.model_dir_entry = ctk.CTkEntry(self.control_frame)
        # 预填充环境变量模型目录（若存在），否则使用默认预设
        prefill = None
        try:
            env_md = os.getenv("BUCKWHEAT_MODEL_DIR", "").strip()
            if env_md:
                prefill = self._resolve_model_path(env_md, allow_missing=True)
        except Exception:
            prefill = None
        if not prefill and default_preset:
            prefill = self.model_presets.get(default_preset)
        if prefill:
            self.model_dir_entry.insert(0, prefill)
        self.model_dir_entry.pack(pady=(2, 2), fill="x")
        self.reload_model_btn = ctk.CTkButton(self.control_frame, text="重载模型", command=self._reload_model)
        self.reload_model_btn.pack(pady=4, fill="x")
        self.show_diag_btn = ctk.CTkButton(self.control_frame, text="显示诊断信息", command=self._show_diagnostics)
        self.show_diag_btn.pack(pady=4, fill="x")

        # 画布区域
        self.display_frame = ctk.CTkFrame(self)
        self.display_frame.grid(row=0, column=1, sticky="nswe", padx=8, pady=8)
        self.display_label = ctk.CTkLabel(self.display_frame, text="")
        self.display_label.pack(expand=True)

        # Detector 实例（延迟加载）
        self.detector = None
        if Detector is not None:
            try:
                self.detector = Detector()
            except Exception as e:
                self.set_status(f"Detector 初始化失败: {e}")

        # 性能统计面板
        self._fps_samples = deque(maxlen=30)
        self._max_metric_classes = 4
        self._metrics_class_names = []
        self.class_count_labels = {}
        self._build_metrics_panel()

        # 摄像头线程控制
        self._cam_thread = None
        self._cam_running = threading.Event()
        self._scan_thread = None

        # 窗口关闭处理
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _resolve_model_path(self, path: str, allow_missing: bool = False) -> Optional[str]:
        if not path:
            return None
        path = path.strip()
        if not path:
            return None
        if os.path.isabs(path):
            normalized = os.path.normpath(path)
        else:
            base_dir = getattr(self, "_workspace_root", os.getcwd())
            normalized = os.path.normpath(os.path.join(base_dir, path))
        if allow_missing or os.path.exists(normalized):
            return normalized
        return None

    def _looks_like_inference_dir(self, path: str) -> bool:
        if not path or not os.path.isdir(path):
            return False
        expected_files = (
            "model.pdparams",
            "model.pdiparams",
            "inference.pdmodel",
            "model.pdmodel",
            "infer_cfg.yaml",
            "infer_cfg.yml",
            "deploy.yaml",
        )
        for fname in expected_files:
            if os.path.exists(os.path.join(path, fname)):
                return True
        return False

    def _discover_model_presets(self) -> tuple[OrderedDict[str, str], dict[str, bool]]:
        presets: OrderedDict[str, str] = OrderedDict()
        validity: dict[str, bool] = {}

        def already_registered(target_path: str) -> bool:
            if not target_path:
                return False
            if target_path in presets.values():
                return True
            for existing_path in presets.values():
                if not existing_path:
                    continue
                if os.path.exists(existing_path) and os.path.exists(target_path):
                    try:
                        if os.path.samefile(existing_path, target_path):
                            return True
                    except OSError:
                        continue
            return False

        def register(label: str, candidate_path: Optional[str], already_resolved: bool = False):
            if not candidate_path:
                return
            resolved = candidate_path if already_resolved else self._resolve_model_path(candidate_path, allow_missing=True)
            if not resolved or already_registered(resolved):
                return
            is_valid = self._looks_like_inference_dir(resolved)
            display_label = label if is_valid else f"{label} (缺少导出)"
            final_label = display_label
            counter = 2
            while final_label in presets:
                final_label = f"{display_label} #{counter}"
                counter += 1
            presets[final_label] = resolved
            validity[final_label] = is_valid

        env_path = os.getenv("BUCKWHEAT_MODEL_DIR", "").strip()
        env_resolved = self._resolve_model_path(env_path, allow_missing=True)
        register("环境变量模型", env_resolved, already_resolved=True)

        default_candidates = [
            ("Speed optimized", "inference_model/ppyoloe_plus_crn_m_300e_speed_optimized"),
            ("Best model", "output/best_model"),
            ("Final model", "output/model_final"),
        ]
        for label, rel_path in default_candidates:
            register(label, rel_path)

        auto_search_roots = [
            os.path.join(self._workspace_root, "output"),
            os.path.join(self._workspace_root, "inference_model"),
        ]
        for root_dir in auto_search_roots:
            if not os.path.isdir(root_dir):
                continue
            for entry in sorted(os.listdir(root_dir)):
                candidate_path = os.path.join(root_dir, entry)
                if not os.path.isdir(candidate_path):
                    continue
                if not self._looks_like_inference_dir(candidate_path):
                    continue
                label = entry
                if root_dir.endswith("output"):
                    label = f"output/{entry}"
                elif root_dir.endswith("inference_model"):
                    label = f"inference_model/{entry}"
                register(label, candidate_path, already_resolved=True)

        return presets, validity

    def set_status(self, text: str):
        self.status_label.configure(text=f"状态: {text}")

    def load_image(self):
        path = filedialog.askopenfilename(title="选择图片", filetypes=[("Images", "*.jpg *.png *.jpeg *.bmp"), ("All", "*.*")])
        if not path:
            return
        self.set_status("加载图片中...")
        try:
            img = cv2.imread(path)
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            # 调用检测（若实现）
            if self.detector:
                result_img = self.detector.detect_image(img_rgb)
                boxes = getattr(self.detector, "last_boxes", [])
                counts = self._count_boxes_by_name(boxes, getattr(self.detector, "class_names", []))
                timings = getattr(self.detector, "last_timing", {})
                self._schedule_metrics_update(None, counts, getattr(self.detector, "class_names", []), timings)
            else:
                result_img = img_rgb
                self._reset_metrics_panel()
            self._show_image(result_img)
            self.set_status("图片检测完成")
        except Exception as e:
            messagebox.showerror("错误", f"加载或检测图片失败: {e}")
            self.set_status("错误")

    def _show_image(self, img_rgb):
        # 保存原始结果图用于缩放
        self._current_image_rgb = img_rgb
        # 实际渲染遵循 self.display_scale
        self._render_current_image()

    def _render_current_image(self):
        if getattr(self, "_current_image_rgb", None) is None:
            return
        img_rgb = self._current_image_rgb
        pil = Image.fromarray(img_rgb)
        w, h = pil.size
        # 先按用户缩放因子，再限制最大窗口尺寸以避免超大图片
        scale = getattr(self, "display_scale", 1.0)
        sw, sh = int(w * scale), int(h * scale)
        # 限制最大尺寸
        max_w, max_h = 1200, 900
        if sw > max_w or sh > max_h:
            fit_scale = min(max_w / sw, max_h / sh)
            sw = max(1, int(sw * fit_scale))
            sh = max(1, int(sh * fit_scale))
        if sw <= 0 or sh <= 0:
            return
        if (sw, sh) != (w, h):
            pil = pil.resize((sw, sh))
        ctk_img = ctk.CTkImage(light_image=pil, dark_image=pil, size=(sw, sh))
        self.display_label.configure(image=ctk_img, text="")
        self.display_label.image = ctk_img

    def _build_metrics_panel(self):
        self.metrics_frame = ctk.CTkFrame(self, width=220)
        self.metrics_frame.grid(row=0, column=2, sticky="nswe", padx=(0, 8), pady=8)
        self.metrics_title = ctk.CTkLabel(self.metrics_frame, text="实时性能")
        self.metrics_title.pack(anchor="w", padx=6, pady=(12, 4))

        self.fps_label = ctk.CTkLabel(self.metrics_frame, text="FPS: --")
        self.fps_label.pack(anchor="w", padx=6, pady=2)

        self.latency_label = ctk.CTkLabel(self.metrics_frame, text="推理耗时: -- ms")
        self.latency_label.pack(anchor="w", padx=6, pady=2)

        self.counts_title = ctk.CTkLabel(self.metrics_frame, text="标签计数")
        self.counts_title.pack(anchor="w", padx=6, pady=(12, 4))

        self.count_container = ctk.CTkFrame(self.metrics_frame)
        self.count_container.pack(fill="both", expand=True, padx=6, pady=(0, 8))

        metric_names = self._derive_metric_names([], {})
        self._rebuild_metric_labels(metric_names)
        self._reset_metrics_panel()

    def _derive_metric_names(self, class_names, counts_dict):
        names = []
        for name in class_names:
            if not name:
                continue
            if name not in names:
                names.append(name)
            if len(names) >= self._max_metric_classes:
                break
        if len(names) < self._max_metric_classes:
            for name in counts_dict.keys():
                if not name:
                    continue
                if name not in names:
                    names.append(name)
                if len(names) >= self._max_metric_classes:
                    break
        placeholder_index = 1
        while len(names) < self._max_metric_classes:
            candidate = f"标签{placeholder_index}"
            placeholder_index += 1
            if candidate in names:
                continue
            names.append(candidate)
        return names

    def _rebuild_metric_labels(self, names):
        for widget in self.count_container.winfo_children():
            widget.destroy()
        self.class_count_labels = {}
        for name in names:
            label = ctk.CTkLabel(self.count_container, text=f"{name}: 0")
            label.pack(anchor="w", fill="x", pady=2)
            self.class_count_labels[name] = label
        self._metrics_class_names = names

    def _reset_metrics_panel(self):
        self.fps_label.configure(text="FPS: --")
        self.latency_label.configure(text="推理耗时: -- ms")
        for name, label in self.class_count_labels.items():
            label.configure(text=f"{name}: 0")

    def _schedule_metrics_update(self, fps_value, counts_dict, class_names, timings):
        def _update():
            if not self.winfo_exists():
                return
            try:
                self._update_metrics_ui(fps_value, counts_dict, class_names, timings)
            except Exception:
                pass

        self.after(0, _update)

    def _update_metrics_ui(self, fps_value, counts_dict, class_names, timings):
        metric_names = self._derive_metric_names(class_names, counts_dict)
        if metric_names != self._metrics_class_names:
            self._rebuild_metric_labels(metric_names)

        if fps_value is not None:
            self.fps_label.configure(text=f"FPS: {fps_value:.1f}")
        else:
            self.fps_label.configure(text="FPS: --")

        total_ms = None
        if isinstance(timings, dict):
            total_ms = timings.get("total_ms")
            if total_ms is None:
                total_ms = timings.get("total")
        if total_ms is not None:
            self.latency_label.configure(text=f"推理耗时: {total_ms:.1f} ms")
        else:
            self.latency_label.configure(text="推理耗时: -- ms")

        for name, label in self.class_count_labels.items():
            value = counts_dict.get(name, 0)
            label.configure(text=f"{name}: {value}")

    def _count_boxes_by_name(self, boxes, class_names):
        counts = {}
        for box in boxes:
            if not box:
                continue
            try:
                cls_id = int(box[5]) if len(box) > 5 else -1
            except Exception:
                cls_id = -1
            if cls_id >= 0 and class_names and 0 <= cls_id < len(class_names):
                name = class_names[cls_id]
            elif cls_id >= 0:
                name = f"类别{cls_id + 1}"
            else:
                name = "未分类"
            counts[name] = counts.get(name, 0) + 1
        return counts

    def _calculate_fps(self):
        if len(self._fps_samples) < 2:
            return None
        first = self._fps_samples[0]
        last = self._fps_samples[-1]
        elapsed = last - first
        if elapsed <= 0:
            return None
        frames = len(self._fps_samples) - 1
        return frames / elapsed

    def _zoom(self, factor: float):
        self.display_scale = getattr(self, "display_scale", 1.0) * factor
        # 限制缩放范围
        self.display_scale = max(0.1, min(self.display_scale, 8.0))
        self._render_current_image()

    def _set_zoom(self, value: float):
        self.display_scale = float(value)
        self._render_current_image()

    def _apply_score_threshold(self):
        try:
            v = float(self.score_entry.get().strip())
        except Exception:
            messagebox.showerror("错误", "请输入有效的置信度阈值，例如 0.5")
            return
        if self.detector:
            self.detector.score_threshold = v
            messagebox.showinfo("已应用", f"置信度阈值已设置为 {v}")
        else:
            messagebox.showwarning("警告", "Detector 未初始化，无法应用阈值")

    def _reload_model(self):
        md = self.model_dir_entry.get().strip() or None
        if not md:
            md = os.getenv("BUCKWHEAT_MODEL_DIR", None)
        if not md:
            messagebox.showerror("错误", "未指定模型目录，请在上方输入或设置环境变量 BUCKWHEAT_MODEL_DIR")
            return
        if not self.detector:
            messagebox.showerror("错误", "Detector 未初始化")
            return
        if not os.path.isdir(md):
            messagebox.showerror("错误", f"模型目录不存在: {md}")
            self.set_status("模型目录不存在")
            return
        if not self._looks_like_inference_dir(md):
            messagebox.showwarning(
                "缺少推理文件",
                "该目录缺少 Paddle Inference 导出的 model.pdmodel / model.pdiparams，"
                "请先执行导出或选择其他预设。",
            )
            self.set_status("模型目录缺少导出文件")
            return
        self.set_status("正在重载模型...")
        try:
            self.detector.load_inference_model(md)
            if self.detector.is_ready:
                messagebox.showinfo("成功", f"模型已从 {md} 加载")
                self.set_status("模型已加载")
                current_selection = self.model_preset_var.get() if hasattr(self, "model_preset_var") else None
                if current_selection and self.model_presets.get(current_selection):
                    selected_path = self.model_presets[current_selection]
                    try:
                        if os.path.samefile(selected_path, md):
                            self._current_preset_name = current_selection
                    except OSError:
                        if os.path.abspath(selected_path) == os.path.abspath(md):
                            self._current_preset_name = current_selection
            else:
                messagebox.showwarning("加载失败", f"模型加载未成功，请查看诊断信息")
                self.set_status("模型加载失败")
        except Exception as e:
            messagebox.showerror("错误", f"加载模型失败: {e}")
            self.set_status("模型加载出错")

    def _on_model_preset_changed(self, preset_name: str):
        if not preset_name:
            return
        path = self.model_presets.get(preset_name)
        if not path:
            return
        valid = self.model_preset_validity.get(preset_name, False)
        self.model_dir_entry.delete(0, "end")
        self.model_dir_entry.insert(0, path)
        if not os.path.isdir(path):
            self.set_status(f"预设未找到: {preset_name}")
            messagebox.showwarning("提示", f"预设路径不存在或尚未导出: {path}")
            return
        if not valid or not self._looks_like_inference_dir(path):
            self.set_status(f"预设缺少导出文件: {preset_name}")
            messagebox.showwarning(
                "提示",
                "该预设目录存在但缺少 Paddle Inference 导出的 model.pdmodel / model.pdiparams，"
                "请先执行 PaddleDetection 的导出指令 (paddledet --export_model)。",
            )
            return
        self.set_status(f"已选择预设: {preset_name}")
        if getattr(self, "auto_reload_on_preset", False):
            self._reload_model()

    def _show_diagnostics(self):
        if not self.detector:
            messagebox.showinfo("诊断信息", "Detector 未初始化")
            return
        info_lines = []
        info_lines.append(f"is_ready: {self.detector.is_ready}")
        info_lines.append(f"last_error: {self.detector.last_error}")
        info_lines.append(f"last_timing: {self.detector.last_timing}")
        info_lines.append(f"last_boxes_count: {len(getattr(self.detector, 'last_boxes', []))}")
        info_lines.append(f"class_names: {getattr(self.detector, 'class_names', [])}")
        messagebox.showinfo("诊断信息", "\n".join(info_lines))

    def _on_close(self):
        try:
            self._cam_running.clear()
        except Exception:
            pass
        try:
            if self._cam_thread and self._cam_thread.is_alive():
                self._cam_thread.join(timeout=1.0)
        except Exception:
            pass
        try:
            if self._scan_thread and self._scan_thread.is_alive():
                self._scan_thread.join(timeout=1.0)
        except Exception:
            pass
        try:
            if self.detector and hasattr(self.detector, "predictor"):
                predictor = getattr(self.detector, "predictor", None)
                if predictor:
                    del predictor
        except Exception:
            pass
        try:
            self.quit()
        except Exception:
            pass
        self.destroy()

    def start_camera(self, device=None):
        if self._cam_thread and self._cam_thread.is_alive():
            return
        self._cam_running.set()
        self.btn_start_cam.configure(state="disabled")
        self.btn_stop_cam.configure(state="normal")
        self.set_status("摄像头启动中...")
        self._fps_samples.clear()
        self._reset_metrics_panel()
        # 如果未传入 device，则读取输入框内容
        dev = device
        if dev is None:
            try:
                dev_str = self.cam_entry.get().strip()
                # 若为数字索引则转换为 int，否则保持字符串（支持 RTSP/HTTP/USB 路径）
                if dev_str.isdigit():
                    dev = int(dev_str)
                else:
                    dev = dev_str
            except Exception:
                dev = 0
        self._cam_thread = threading.Thread(target=self._camera_loop, args=(dev,), daemon=True)
        self._cam_thread.start()

    def stop_camera(self):
        self._cam_running.clear()
        self.btn_start_cam.configure(state="normal")
        self.btn_stop_cam.configure(state="disabled")
        self.set_status("摄像头停止")
        self._fps_samples.clear()
        self._reset_metrics_panel()

    def _camera_loop(self, device):
        # VideoCapture 可以接收 int 索引或字符串 URL
        # 若 device 是字符串形式的数字，转换为 int
        try:
            if isinstance(device, str) and device.isdigit():
                device = int(device)
        except Exception:
            pass
        cap = self._open_capture(device)
        if not cap or not cap.isOpened():
            self.set_status("无法打开摄像头")
            return
        self.set_status("摄像头运行中")
        try:
            while self._cam_running.is_set():
                ret, frame = cap.read()
                if not ret:
                    time.sleep(0.01)
                    continue
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                if self.detector:
                    try:
                        start_time = time.perf_counter()
                        result = self.detector.detect_image(frame_rgb)
                        detect_ms = (time.perf_counter() - start_time) * 1000.0
                    except Exception:
                        result = frame_rgb
                        detect_ms = None
                else:
                    result = frame_rgb
                    detect_ms = None
                # 显示
                self._show_image(result)
                if detect_ms is not None:
                    self._fps_samples.append(time.perf_counter())
                    fps_value = self._calculate_fps()
                    boxes = getattr(self.detector, "last_boxes", []) if self.detector else []
                    class_names = getattr(self.detector, "class_names", []) if self.detector else []
                    counts = self._count_boxes_by_name(boxes, class_names)
                    timings = getattr(self.detector, "last_timing", {}) if self.detector else {"total_ms": detect_ms}
                    if not isinstance(timings, dict):
                        timings = {}
                    if detect_ms is not None and "total_ms" not in timings:
                        timings["total_ms"] = detect_ms
                    self._schedule_metrics_update(fps_value, counts, class_names, timings)
                # 控制帧率以降低 CPU 占用
                time.sleep(0.02)
        finally:
            cap.release()
            self.set_status("摄像头已关闭")
            self._cam_thread = None
            self._fps_samples.clear()
            self._schedule_metrics_update(None, {}, getattr(self.detector, "class_names", []), None)

    def _start_scan_cameras(self):
        """在后台线程扫描本机常见摄像头索引（0..5），并把首个可用索引写回输入框。"""
        if getattr(self, "_scan_thread", None) and self._scan_thread.is_alive():
            return
        self._scan_thread = threading.Thread(target=self.scan_cameras, daemon=True)
        self._scan_thread.start()

    def scan_cameras(self, max_index: int = 5):
        found = []
        self.set_status("扫描摄像头中...")
        for i in range(0, max_index + 1):
            try:
                cap = self._open_capture(i)
                # 尝试打开并立即释放
                if cap is not None and cap.isOpened():
                    found.append(i)
                    cap.release()
                else:
                    # 仍释放以防资源泄露
                    try:
                        cap.release()
                    except Exception:
                        pass
            except Exception:
                pass
        if found:
            # 将第一个可用索引写回输入框
            self.cam_entry.delete(0, 'end')
            self.cam_entry.insert(0, str(found[0]))
            self.set_status(f"发现摄像头: {found}; 已选择 {found[0]}")
            messagebox.showinfo("扫描完成", f"发现摄像头索引: {found}\n已选择 {found[0]}")
        else:
            self.set_status("未发现本地摄像头（请输入设备索引或摄像头 URL）")
            messagebox.showinfo("扫描完成", "未发现本地摄像头。若使用手机摄像头，请在输入框填写手机的摄像头 URL（例如 RTSP/HTTP）。")
        self._scan_thread = None

    def _open_capture(self, device):
        """尝试使用多个后端打开摄像头，减少 Windows 上的驱动警告。"""
        backends = []
        if isinstance(device, int):
            backends = [
                getattr(cv2, "CAP_DSHOW", None),
                getattr(cv2, "CAP_MSMF", None),
                getattr(cv2, "CAP_ANY", None),
            ]
        else:
            backends = [getattr(cv2, "CAP_ANY", None)]
        for backend in backends:
            try:
                if backend is None:
                    cap = cv2.VideoCapture(device)
                else:
                    cap = cv2.VideoCapture(device, backend)
            except Exception:
                cap = None
            if cap is not None and cap.isOpened():
                return cap
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass
        return None

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()