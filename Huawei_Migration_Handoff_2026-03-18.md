# Huawei Migration Handoff

Date: 2026-03-18

## Core conclusion
- This handoff is reconstructed from assistant context, not from a fresh disk scan.
- I did create Huawei/OpenI migration code scaffolding in the repo context during the session.
- I did NOT create a git commit for that migration work.
- I did NOT push that migration work to GitHub.
- Therefore, if the disk is gone and you did not manually commit/push elsewhere, GitHub likely does not contain these new migration files.

## Hard constraints learned from the Huawei guide
Source previously read: `C:\Users\BoHuYeShan\Desktop\华为NPU_OpenI训练复用手册_给AI.md`

Rules fixed by that guide:
- Only Huawei Ascend/NPU + MindSpore.
- No CUDA/GPU route for the migration target.
- OpenI entry should be `scripts/openi_cloudbrain_train_mindspore.py`.
- OpenI parameters should be `key=value` without leading `--`.
- Most important dataset switch parameter: `zip-name=<dataset.zip>`.
- Local output path should be `/cache/output/model`.
- Downloadable results should be under `models-0/model/`.
- Common failure points: wrong COCO annotation path, wrong dataset zip auto-selection, OpenI may pull `master.zip`, so `master` must stay synchronized.
- Research goal is not just reproducibility; it should support advanced algorithms, custom learning-rate curves, ablations, and paper-oriented experiments.

## What the original repo was doing before migration
Repo path used during the work: `E:\CODE\Buckwheat-seed-quality`

Findings from repository analysis:
- Mainline was PaddleDetection / Paddle / CUDA based.
- Training used `train_quality_optimized.sh` and PaddleDetection `tools/train.py`.
- Inference/deployment paths included `app/`, `android-app/`, `app/batch_infer.py`, `app/batch_runner.py`, and `tools/run_inference_on_dataset.py`.
- Export and inference tooling was Paddle/ONNX centric.
- The repo had COCO-style data assumptions, logs, metrics parsers, and experiment bookkeeping.
- At analysis time there was no existing `openi_*.py` or `mindspore*.py` integration.

## Migration direction chosen
Because the user required Huawei free server usage, the technical route changed to:
- OpenI / CloudBrain workflow
- MindSpore runtime
- Ascend/NPU device target
- New migration code in new folders
- Algorithm support research first, then implementation

## Research conclusions
- Reusable assets from the old repo: COCO-style outputs, experiment logs, metrics parsers, evaluation reports, bookkeeping scripts, roadmap docs.
- Practical OpenI/MindSpore patterns confirmed: local staging under `/cache/`, use of `data_url` and `train_url`, Ascend jobs use `device_target="Ascend"`, outputs written locally then uploaded.
- Algorithm support conclusion: phase 1 should use a mature MindYOLO detector on COCO-style data; phase 2 can compare against MindCV SSD / DeepLabV3 and perform ablations.

## New files created in the migration work
Main new directory:
- `huawei_npu_migration/`

Top-level wrapper directory added:
- `scripts/`

### `huawei_npu_migration/README.md`
Purpose:
- migration starter doc
- documents Huawei/OpenI parameter template
- records key troubleshooting fields

Important parameter template:
- `boot_file=scripts/openi_cloudbrain_train_mindspore.py`
- `device=npu`
- `dataset-profile=clean`
- `zip-name=<dataset.zip>`
- `extract-dir=/cache/dataset/data_extracted`
- `checkpoint-dir=/cache/output/model`
- `algorithm=colony_seednet_v1`
- `num-epochs=300`
- `batch-size=8`
- `learning-rate=0.0005`
- `num-workers=8`
- `image-size=384`
- `max-steps-per-epoch=0`
- `stop-after-first-epoch=0`

Key log fields documented there:
- `OPENI_DATASET_ZIP`
- `COLONY_DATASET_ROOT`
- `COLONY_CHECKPOINT_DIR`
- `boot_file`

### `huawei_npu_migration/algorithm_support_matrix.md`
Included rows for:
- MindCV classification
- MindYOLO detection
- MindCV SSD
- MindCV DeepLabV3
- MindSpore `CocoDataset`
- custom `ColonySeedNet-v1`

Priority recorded there:
- phase 1: MindYOLO + COCO
- phase 2: SSD / DeepLabV3 comparisons and ablations

### `huawei_npu_migration/scripts/openi_prepare_dataset.py`
Implemented:
- `parse_kv_arguments(raw_items)`
- `pick_value(values, keys, default)`
- `list_zip_files(root_dir)`
- `select_dataset_zip(candidates, explicit_zip_name)`
- `unzip_if_needed(zip_path, extract_root)`
- `detect_coco_layout(dataset_root)`
- manifest writing

Important behavior:
- accepts `key=value` and `--key=value`
- supports dashed and underscored key forms
- zip selection prefers explicit `zip-name`, then names containing `clean`, then non-merged zips
- detects train/val annotation and image layout for COCO-style datasets

### `huawei_npu_migration/scripts/openi_cloudbrain_train_mindspore.py`
Purpose:
- main OpenI/CloudBrain training entry for Ascend only

Important behavior:
- only accepts `npu` or `ascend`, normalized to `Ascend`
- rejects GPU/CUDA style device selection
- selects dataset zip, extracts data, detects COCO layout, writes manifest
- builds downstream training command for `mindspore_colony_train.py`
- exports env vars: `DEVICE_TARGET`, `OPENI_DATASET_ZIP`, `COLONY_DATASET_ROOT`, `COLONY_CHECKPOINT_DIR`, `COLONY_EXTRACT_DIR`
- always writes `mindspore_run_summary.json`
- prints exactly: `OPENI_DATASET_ZIP`, `COLONY_DATASET_ROOT`, `COLONY_CHECKPOINT_DIR`, `boot_file`

### `huawei_npu_migration/scripts/mindspore_colony_train.py`
Purpose:
- dry-run planner / dispatcher for Ascend MindSpore training

Registry included:
- `mindyolo_yolov5`
- `mindyolo_yolov8`
- `mindcv_ssd`
- `mindcv_deeplabv3`
- `colony_seednet_v1`

Important helper logic:
- recommended downstream command generation
- warmup + cosine schedule generation
- `colony_seednet_v1` recipe generation
- writes `mindspore_training_plan.json`
- can write execution summary if later run in execute mode

### `huawei_npu_migration/algorithms/colony_seednet_v1.md`
Design note for custom algorithm:
- base detector: MindYOLO YOLOv8
- Ascend/MindSpore-compatible small-object strategy
- staged curriculum augmentation
- warmup + cosine schedule as migration baseline
- tile inference for small objects
- focal-like classification + CIoU + DFL + inverse-frequency class weighting

### `huawei_npu_migration/configs/colony_seednet_v1.yaml`
Stub config with:
- framework: MindSpore
- device_target: Ascend
- COCO data section
- four classes: `seeda`, `seedb`, `seedc`, `seedd`
- training hyperparameters
- curriculum augmentation settings
- small-object inference settings

### top-level wrappers in `scripts/`
Added wrappers:
- `scripts/openi_prepare_dataset.py`
- `scripts/openi_cloudbrain_train_mindspore.py`
- `scripts/mindspore_colony_train.py`

Reason:
- OpenI needed `boot_file=scripts/openi_cloudbrain_train_mindspore.py`
- actual implementation stayed organized under `huawei_npu_migration/scripts/`
- wrappers dynamically import the real module in `main()` to avoid import-order warnings

### `huawei_npu_migration/.gitignore`
Ignored temp validation paths:
- `tmp_extract/`
- `tmp_model/`
- `tmp_run/`
- `tmp_plan_check/`

## Validation already performed during the session
- LSP diagnostics were run on new migration scripts and wrappers.
- Unused import warning in `openi_prepare_dataset.py` was fixed.
- Type warning in `mindspore_colony_train.py` was fixed by widening `write_json` payload typing.
- Wrapper E402 issues were fixed by delayed `__import__` inside `main()`.
- `python -m py_compile` was reported successful on new migration scripts and wrappers.
- `python <script> --help` was reported successful for migration scripts and wrappers.
- Dry-run of `mindspore_colony_train.py` with `algorithm=colony_seednet_v1` generated a training plan and algorithm recipe.
- Dry-run of `scripts/openi_cloudbrain_train_mindspore.py` with `key=value` arguments correctly printed:
  - `OPENI_DATASET_ZIP=data.zip`
  - `COLONY_DATASET_ROOT=<...tmp_extract\data>`
  - `COLONY_CHECKPOINT_DIR=<...tmp_model>`
  - `boot_file=scripts/openi_cloudbrain_train_mindspore.py`

## User-provided repo metadata that must be preserved
- OpenI repo: `https://openi.pcl.ac.cn/bhys/mic.git`
- GitHub repo: `https://github.com/BOHUYESHAN-APB/CNN-MicroAI-Colony`

Known branch heads already provided by the user:
- `cloudbrain`: `3b8ab985ba8ffd2250e326908fe83ba5729c8b11`
- `main`: `6707eaae6b05db30ffce40d129b1a904b6be24eb`
- `master`: `b4ccf5b5e35db449da9e5bee022bdfd0354538f9`

## Important learning-rate document recovered earlier
Relevant file previously found:
- `E:\CODE\Buckwheat-seed-quality\Buckwheat_Improvement_Roadmap.md`

Important line references remembered from the session:
- `Buckwheat_Improvement_Roadmap.md:53` section `小样本分层动态学习率方案（2025-10-03）`
- `Buckwheat_Improvement_Roadmap.md:74` layer-wise LR multipliers
- `Buckwheat_Improvement_Roadmap.md:82` staged LR schedule table
- `Buckwheat_Improvement_Roadmap.md:91` jitter-trigger rule

Interpretation:
- this is not plain cosine decay
- it combines transfer learning, layer-wise LR, staged schedule, and jitter-response control
- `README_en.md:55` also referenced it by English name

## Workspace state remembered before this handoff request
- New untracked directories existed in the repo context: `huawei_npu_migration/` and `scripts/`
- There was also an unrelated modified file not touched by the assistant: `android-app/build/reports/problems/problems-report.html`
- No commit was created by the assistant.
- No push was made by the assistant.

## Recommended next actions in a new AI window
1. Recreate the migration files from this handoff if they are missing locally.
2. Preserve Huawei-only constraint: Ascend/NPU + MindSpore only.
3. Restore first: migration docs, dataset prep script, cloudbrain entry, training dispatcher, ColonySeedNet-v1 design/config, and top-level wrappers.
4. Re-run dry validation: `py_compile`, `--help`, and a local key=value dry-run.
5. Then decide whether to commit to GitHub/OpenI and whether to wire in real MindYOLO third-party code.

## Recovery prompt for another window
"Continue Huawei Ascend/OpenI migration for the repository that was originally Paddle/CUDA based. Only Huawei Ascend/NPU + MindSpore is allowed. Recreate and continue the migration scaffold described in the Desktop handoff file. The main entry must be `scripts/openi_cloudbrain_train_mindspore.py` and OpenI parameters must be key=value style. Restore `huawei_npu_migration/`, top-level `scripts/` wrappers, ColonySeedNet-v1 design, dataset zip selection/extraction logic, COCO layout detection, manifest/run-summary JSON generation, and the exact troubleshooting prints `OPENI_DATASET_ZIP` / `COLONY_DATASET_ROOT` / `COLONY_CHECKPOINT_DIR` / `boot_file`. GitHub repo is `https://github.com/BOHUYESHAN-APB/CNN-MicroAI-Colony`; OpenI repo is `https://openi.pcl.ac.cn/bhys/mic.git`; known branch heads are cloudbrain `3b8ab985ba8ffd2250e326908fe83ba5729c8b11`, main `6707eaae6b05db30ffce40d129b1a904b6be24eb`, master `b4ccf5b5e35db449da9e5bee022bdfd0354538f9`."
