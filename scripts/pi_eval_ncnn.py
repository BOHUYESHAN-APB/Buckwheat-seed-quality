import csv
import json
import time
from pathlib import Path

import cv2
import numpy as np

try:
    import ncnn
except ImportError as exc:  # pragma: no cover - runtime dependency on Pi
    raise SystemExit("python ncnn is required: pip install ncnn") from exc


CLASS_NAMES = ["T_AB", "T_C", "K_AB", "K_C", "D"]


def xywh_to_xyxy(x):
    y = x.copy()
    y[:, 0] = x[:, 0] - x[:, 2] / 2
    y[:, 1] = x[:, 1] - x[:, 3] / 2
    y[:, 2] = x[:, 0] + x[:, 2] / 2
    y[:, 3] = x[:, 1] + x[:, 3] / 2
    return y


def nms(boxes, scores, iou_thres=0.45):
    if len(boxes) == 0:
        return []
    boxes = boxes.astype(np.float32)
    scores = scores.astype(np.float32)
    x1, y1, x2, y2 = boxes.T
    areas = (x2 - x1) * (y2 - y1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1)
        h = np.maximum(0.0, yy2 - yy1)
        inter = w * h
        union = areas[i] + areas[order[1:]] - inter
        iou = inter / np.maximum(union, 1e-6)
        order = order[np.where(iou <= iou_thres)[0] + 1]
    return keep


def preprocess(image, imgsz=960):
    orig_h, orig_w = image.shape[:2]
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (imgsz, imgsz), interpolation=cv2.INTER_LINEAR)
    tensor = resized.astype(np.float32) / 255.0
    tensor = np.transpose(tensor, (2, 0, 1))
    return tensor, orig_w, orig_h


def postprocess(pred, orig_w, orig_h, imgsz=960, conf_thres=0.25, iou_thres=0.45):
    pred = np.asarray(pred)
    if pred.ndim == 3:
        pred = pred[0]

    if pred.ndim != 2:
        raise ValueError(f"unexpected NCNN output shape: {pred.shape}")

    # Raw YOLO-style output: [C, N] or [N, C]
    if pred.shape[0] == 4 + len(CLASS_NAMES):
        pred = pred.T
    elif pred.shape[1] != 4 + len(CLASS_NAMES):
        raise ValueError(f"unexpected NCNN raw output shape: {pred.shape}")

    boxes = pred[:, :4]
    cls_scores = pred[:, 4:]
    cls_ids = cls_scores.argmax(axis=1)
    scores = cls_scores[np.arange(len(cls_ids)), cls_ids]
    keep = scores >= conf_thres
    boxes = boxes[keep]
    scores = scores[keep]
    cls_ids = cls_ids[keep]
    if len(boxes) == 0:
        return []

    boxes = xywh_to_xyxy(boxes)
    scale_x = orig_w / imgsz
    scale_y = orig_h / imgsz
    boxes[:, [0, 2]] *= scale_x
    boxes[:, [1, 3]] *= scale_y

    final = []
    for cls_id in np.unique(cls_ids):
        idx = np.where(cls_ids == cls_id)[0]
        kept = nms(boxes[idx], scores[idx], iou_thres=iou_thres)
        for k in kept:
            i = idx[k]
            cls_id_i = int(cls_ids[i])
            cls_name = CLASS_NAMES[cls_id_i] if 0 <= cls_id_i < len(CLASS_NAMES) else str(cls_id_i)
            final.append(
                {
                    "cls_id": cls_id_i,
                    "cls_name": cls_name,
                    "score": float(scores[i]),
                    "box": [float(v) for v in boxes[i]],
                }
            )
    return final


def create_net(param_path, bin_path, use_vulkan=False, num_threads=4):
    net = ncnn.Net()
    net.opt.use_vulkan_compute = use_vulkan
    net.opt.num_threads = num_threads
    ret = net.load_param(str(param_path))
    if ret != 0:
        raise RuntimeError(f"load_param failed: {ret}")
    ret = net.load_model(str(bin_path))
    if ret != 0:
        raise RuntimeError(f"load_model failed: {ret}")
    return net


def run_once(net, tensor, output_name="out0"):
    with net.create_extractor() as ex:
        ex.input("in0", ncnn.Mat(tensor).clone())
        ret, out = ex.extract(output_name)
        if ret != 0:
            raise RuntimeError(f"extract failed: {ret}")
        return np.array(out, dtype=np.float32)


def infer_image(net, image_path, imgsz=960, repeats=1, conf_thres=0.25, iou_thres=0.45, output_name="out0"):
    image = cv2.imread(str(image_path))
    if image is None:
        raise FileNotFoundError(image_path)
    inp, orig_w, orig_h = preprocess(image, imgsz=imgsz)
    times = []
    output = None
    for _ in range(repeats):
        t0 = time.perf_counter()
        output = run_once(net, inp, output_name=output_name)
        times.append((time.perf_counter() - t0) * 1000.0)
    dets = postprocess(output, orig_w, orig_h, imgsz=imgsz, conf_thres=conf_thres, iou_thres=iou_thres)
    return {
        "image": str(image_path),
        "repeats": repeats,
        "latency_ms": times,
        "avg_latency_ms": float(np.mean(times)),
        "raw_output_shape": list(output.shape),
        "detections": dets,
        "count": len(dets),
    }


def make_video_from_images(image_dir, output_path, fps=12, seconds=3):
    images = sorted(Path(image_dir).glob("*.jpg")) + sorted(Path(image_dir).glob("*.png"))
    if not images:
        raise FileNotFoundError(image_dir)
    frames_needed = fps * seconds
    picked = images[: min(len(images), frames_needed)]
    first = cv2.imread(str(picked[0]))
    h, w = first.shape[:2]
    writer = cv2.VideoWriter(str(output_path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (w, h))
    written = 0
    while written < frames_needed:
        for img_path in picked:
            frame = cv2.imread(str(img_path))
            if frame is None:
                continue
            if frame.shape[:2] != (h, w):
                frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_LINEAR)
            writer.write(frame)
            written += 1
            if written >= frames_needed:
                break
    writer.release()
    return output_path


def infer_video(net, video_path, imgsz=960, conf_thres=0.25, iou_thres=0.45, output_name="out0"):
    cap = cv2.VideoCapture(str(video_path))
    frame_times = []
    frame_counts = []
    frame_idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        inp, orig_w, orig_h = preprocess(frame, imgsz=imgsz)
        t0 = time.perf_counter()
        output = run_once(net, inp, output_name=output_name)
        frame_times.append((time.perf_counter() - t0) * 1000.0)
        dets = postprocess(output, orig_w, orig_h, imgsz=imgsz, conf_thres=conf_thres, iou_thres=iou_thres)
        frame_counts.append({"frame": frame_idx, "count": len(dets)})
        frame_idx += 1
    cap.release()
    return {
        "video": str(video_path),
        "frames": frame_idx,
        "avg_latency_ms": float(np.mean(frame_times)) if frame_times else None,
        "fps_estimate": (1000.0 / float(np.mean(frame_times))) if frame_times else None,
        "frame_times_ms": frame_times,
        "frame_counts": frame_counts,
    }


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--param", required=True)
    parser.add_argument("--bin", required=True)
    parser.add_argument("--image_dir", required=True)
    parser.add_argument("--labels_dir", required=False, default="")
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--imgsz", type=int, default=960)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--fps", type=int, default=12)
    parser.add_argument("--seconds", type=int, default=3)
    parser.add_argument("--conf", type=float, default=0.25)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--output-name", default="out0")
    parser.add_argument("--use-vulkan", action="store_true")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    net = create_net(
        param_path=Path(args.param),
        bin_path=Path(args.bin),
        use_vulkan=args.use_vulkan,
        num_threads=args.threads,
    )

    image_paths = sorted(Path(args.image_dir).glob("*.jpg")) + sorted(Path(args.image_dir).glob("*.png"))
    image_reports = []
    for path in image_paths:
        image_reports.append(
            infer_image(
                net,
                path,
                imgsz=args.imgsz,
                repeats=args.repeats,
                conf_thres=args.conf,
                iou_thres=args.iou,
                output_name=args.output_name,
            )
        )

    video_path = make_video_from_images(
        args.image_dir,
        output_dir / f"test_{args.fps}fps_{args.seconds}s.mp4",
        fps=args.fps,
        seconds=args.seconds,
    )
    video_report = infer_video(
        net,
        video_path,
        imgsz=args.imgsz,
        conf_thres=args.conf,
        iou_thres=args.iou,
        output_name=args.output_name,
    )

    report = {
        "backend": "ncnn",
        "param": args.param,
        "bin": args.bin,
        "imgsz": args.imgsz,
        "image_dir": args.image_dir,
        "labels_dir": args.labels_dir,
        "threads": args.threads,
        "use_vulkan": args.use_vulkan,
        "output_name": args.output_name,
        "image_reports": image_reports,
        "video_report": video_report,
    }
    report_path = output_dir / "pi_eval_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = output_dir / "pi_eval_summary.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["image", "avg_latency_ms", "count", "raw_output_shape"])
        for item in image_reports:
            writer.writerow([item["image"], item["avg_latency_ms"], item["count"], "x".join(map(str, item["raw_output_shape"]))])

    print(report_path)


if __name__ == "__main__":
    main()
