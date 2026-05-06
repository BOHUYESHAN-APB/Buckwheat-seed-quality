import argparse
import csv
import json
from pathlib import Path
from statistics import mean, median


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def percentile(sorted_values, q):
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return float(sorted_values[0])
    rank = (len(sorted_values) - 1) * q
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    frac = rank - low
    return float(sorted_values[low] * (1.0 - frac) + sorted_values[high] * frac)


def summarize_pi_eval(report, label):
    image_latencies = [float(item["avg_latency_ms"]) for item in report.get("image_reports", [])]
    image_counts = [int(item.get("count", 0)) for item in report.get("image_reports", [])]
    sorted_latencies = sorted(image_latencies)
    video = report.get("video_report", {})
    result = {
        "label": label,
        "backend": report.get("backend", label),
        "imgsz": report.get("imgsz"),
        "image_count": len(image_latencies),
        "image_latency_mean_ms": float(mean(image_latencies)) if image_latencies else None,
        "image_latency_median_ms": float(median(image_latencies)) if image_latencies else None,
        "image_latency_p90_ms": percentile(sorted_latencies, 0.9),
        "image_latency_min_ms": float(min(image_latencies)) if image_latencies else None,
        "image_latency_max_ms": float(max(image_latencies)) if image_latencies else None,
        "image_detection_count_mean": float(mean(image_counts)) if image_counts else None,
        "video_frames": int(video.get("frames", 0) or 0),
        "video_latency_mean_ms": float(video.get("avg_latency_ms")) if video.get("avg_latency_ms") is not None else None,
        "video_fps_estimate": float(video.get("fps_estimate")) if video.get("fps_estimate") is not None else None,
    }
    if "use_vulkan" in report:
        result["use_vulkan"] = bool(report["use_vulkan"])
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--onnx-report", required=True)
    parser.add_argument("--ncnn-report", required=True)
    parser.add_argument("--yolo11-bench", required=True)
    parser.add_argument("--remote-meta", required=True)
    parser.add_argument("--pt-probe", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    onnx_report = load_json(args.onnx_report)
    ncnn_report = load_json(args.ncnn_report)
    yolo11_bench = load_json(args.yolo11_bench)
    remote_meta = load_json(args.remote_meta)
    pt_probe = load_json(args.pt_probe)

    onnx_summary = summarize_pi_eval(onnx_report, "buckwheat_v2_onnx_cpu")
    ncnn_summary = summarize_pi_eval(ncnn_report, "buckwheat_v2_ncnn_cpu")

    onnx_image = onnx_summary["image_latency_mean_ms"]
    ncnn_image = ncnn_summary["image_latency_mean_ms"]
    onnx_video = onnx_summary["video_latency_mean_ms"]
    ncnn_video = ncnn_summary["video_latency_mean_ms"]

    summary = {
        "hardware": {
            "uname": remote_meta.get("uname", {}).get("stdout", "").strip(),
            "os_release": remote_meta.get("os_release", {}).get("stdout", "").strip(),
            "vulkan_device_summary": remote_meta.get("vulkan_summary", {}).get("stdout", "").strip(),
        },
        "pt_status": {
            "available_on_pi": "torch OK" in pt_probe.get("venv_probe", {}).get("stdout", ""),
            "probe_stdout": pt_probe.get("venv_probe", {}).get("stdout", "").strip(),
        },
        "references": {
            "yolo11_v1_pi_model_only_onnx": {
                "model_path": yolo11_bench.get("model_path"),
                "input_shape": yolo11_bench.get("input_shape"),
                "latency_ms_mean": yolo11_bench.get("latency_ms_mean"),
                "throughput_ips": yolo11_bench.get("throughput_ips"),
            }
        },
        "benchmarks": {
            "buckwheat_v2_onnx_cpu": onnx_summary,
            "buckwheat_v2_ncnn_cpu": ncnn_summary,
        },
        "comparisons": {
            "ncnn_vs_onnx_image_speedup_x": (onnx_image / ncnn_image) if onnx_image and ncnn_image else None,
            "ncnn_vs_onnx_video_speedup_x": (onnx_video / ncnn_video) if onnx_video and ncnn_video else None,
            "onnx_vs_yolo11_image_latency_ratio_x": (
                onnx_image / yolo11_bench.get("latency_ms_mean")
                if onnx_image and yolo11_bench.get("latency_ms_mean")
                else None
            ),
            "ncnn_vs_yolo11_image_latency_ratio_x": (
                ncnn_image / yolo11_bench.get("latency_ms_mean")
                if ncnn_image and yolo11_bench.get("latency_ms_mean")
                else None
            ),
            "detection_count_alignment": {
                "onnx_image_detection_count_mean": onnx_summary["image_detection_count_mean"],
                "ncnn_image_detection_count_mean": ncnn_summary["image_detection_count_mean"],
                "status": "mismatch" if onnx_summary["image_detection_count_mean"] != ncnn_summary["image_detection_count_mean"] else "match",
            },
        },
    }

    summary_path = output_dir / "benchmark_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    csv_path = output_dir / "benchmark_summary.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["model_label", "metric", "value"])
        for label, item in summary["benchmarks"].items():
            for key, value in item.items():
                writer.writerow([label, key, value])
        for key, value in summary["references"]["yolo11_v1_pi_model_only_onnx"].items():
            writer.writerow(["yolo11_v1_pi_model_only_onnx", key, value])
        for key, value in summary["comparisons"].items():
            writer.writerow(["comparisons", key, json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value])

    print(summary_path)


if __name__ == "__main__":
    main()
