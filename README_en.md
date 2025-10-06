# Buckwheat Seed Quality Detection

> This repository follows the [Apache-2.0](LICENSE) license. We enhance PaddleDetection's **PP-YOLOE+ (L)** baseline to inspect buckwheat seeds at scale, adding small-object refinements, adaptive training regimes, and a desktop inference workflow.

## 📌 Project Overview

- **Inspection scope**: classify plump kernels versus defects (impurities, hollow grains) on high-resolution trays.
- **Model base**: PP-YOLOE+ (L) with the CRN backbone at 800×800 input, combined with our batch annotation and augmentation pipeline.
- **Optimisation highlights**:
  - Cosine restart learning-rate scheduling with staged resume training. Experiment traces live in `quality_optimized_training_*.log`, `accelerated_training_*.log`, and `balanced_restart_*.log`.
  - Dual preprocessing pipelines (letterbox & stretch) plus post-processing alignment in `app/ui.py`, keeping camera overlays pixel-aligned with the original imagery.
  - `logs_analysis/` converts raw training logs into `training_metrics.csv` and companion plots for fast regression checks.
  - Ongoing plans are tracked in [Buckwheat Improvement Roadmap](Buckwheat_Improvement_Roadmap.md).
- **Visualization tooling**: `python app/main.py` starts the desktop UI (CUDA auto-detect, webcam/batch modes, confidence tuning, zoom controls).

## 🖼️ Batch Annotation Examples

Samples come from `inference_results/archive/ppyoloe_plus_postprocess_fix/`, the curated set also referenced by the Readme documentation:

| ![Batch annotation 001](inference_results/archive/ppyoloe_plus_postprocess_fix/test-001.jpg) | ![Batch annotation 015](inference_results/archive/ppyoloe_plus_postprocess_fix/test-015.jpg) | ![Batch annotation 030](inference_results/archive/ppyoloe_plus_postprocess_fix/test-030.jpg) |
| --- | --- | --- |
| test-001 | test-015 | test-030 |

| ![Batch annotation 033](inference_results/archive/ppyoloe_plus_postprocess_fix/test-033.jpg) | ![Batch annotation 040](inference_results/archive/ppyoloe_plus_postprocess_fix/test-040.jpg) | ![Batch annotation 044](inference_results/archive/ppyoloe_plus_postprocess_fix/test-044.jpg) |
| --- | --- | --- |
| test-033 | test-040 | test-044 |

> **Readme documentation assets**: We preserve 45 PaddleDetection official renders in `inference_results/archive/ppdet_official/` for consistent manuals. Example: ![PPDet Official preview](inference_results/archive/ppdet_official/test-001.jpg)

## 🚀 Quick Start

```powershell
# 1) Install PaddlePaddle (GPU build recommended if CUDA is available)
python -m pip install paddlepaddle-gpu==3.1.0 -i https://mirror.baidu.com/pypi/simple

# 2) Install PaddleDetection dependencies
pip install -r PaddleDetection/requirements.txt

# 3) Launch the desktop inference client
python app/main.py
```

- Batch inference: `python -m app.batch_infer --input-dir inference_results/raw --output-dir inference_results/showcase`
- Resume training: `bash train_quality_optimized.sh` (continues the 300-epoch plan from the latest checkpoint).
- Log parsing: `python logs_analysis/parse_training_logs.py` outputs `training_metrics.csv`, `training_loss.png`, and `training_ap.png`.

## 📊 Metric Snapshot

| Strategy | Log source | Best epoch | AP@[0.5:0.95] | AP@0.5 | Notes |
| --- | --- | --- | --- | --- | --- |
| Quality Optimized | `quality_optimized_training_20250919_18xxxx.log` | 159 | 0.167 | 0.204 | Metrics from `logs_analysis/training_metrics.csv`; `max_mem_reserved` ≈ 22.6 GB |
| Accelerated Restart | `accelerated_training_20250919_175406.log` | TBC | — | — | Run `python tools/eval.py` to collect validation results |
| Balanced Restart | `balanced_restart_training_20250919_174427.log` | Pending | — | — | Logs archived; slated for integration into `logs_analysis` |

> The roadmap entry "Small-sample staged learning rate (2025-10-03)" details transfer-learning tweaks, staged LR decay, and jitter-response experiments.
> **Heads-up (2025-10-03)**: The rented training server expired. Verify checkpoints and evaluation artifacts before starting new runs.

## 📜 License & Acknowledgements

- All additions stay under Apache-2.0.
- Thanks to PaddleDetection for PP-YOLOE+ baselines and export tooling; our work centres on small-object optimisation, real-time inference UI, and log analytics.
- Please keep the attribution above if you build downstream projects on top of this repository.

---
简体中文 | English
