# Huawei Ascend / OpenI / MindSpore Migration Scaffold

> 本目录用于将荞麦籽质检项目从 Paddle/CUDA 主线迁移至 **华为昇腾 Ascend NPU + MindSpore** 运行环境，通过 OpenI (CloudBrain) 进行调度。

## 仓库信息

| 平台 | URL |
|------|-----|
| OpenI | https://openi.pcl.ac.cn/bhys/mic.git |
| GitHub | https://github.com/BOHUYESHAN-APB/CNN-MicroAI-Colony |

## 目录结构

```
huawei_npu_migration/
├── README.md                              # 本文件
├── algorithm_support_matrix.md            # 算法支持矩阵
├── algorithms/
│   └── colony_seednet_v1.md               # ColonySeedNet-v1 设计说明
├── configs/
│   └── colony_seednet_v1.yaml             # ColonySeedNet-v1 配置
├── scripts/
│   ├── openi_prepare_dataset.py           # 数据集准备（zip 选择/解压/COCO 检测）
│   ├── openi_cloudbrain_train_mindspore.py # OpenI/CloudBrain 主入口
│   └── mindspore_colony_train.py          # MindSpore 训练调度器
└── .gitignore                             # 临时路径忽略
```

## OpenI 参数模板（key=value 风格）

在 OpenI 创建任务时，`boot_file` 指向顶层 wrapper：

```
boot_file=scripts/openi_cloudbrain_train_mindspore.py
```

其余参数使用 `key=value` 格式（无 `--` 前缀）：

```
device=npu
dataset-profile=clean
zip-name=<dataset.zip>
extract-dir=/cache/dataset/data_extracted
checkpoint-dir=/cache/output/model
algorithm=colony_seednet_v1
num-epochs=300
batch-size=8
learning-rate=0.0005
num-workers=8
image-size=384
max-steps-per-epoch=0
stop-after-first-epoch=0
```

## 关键故障排查字段

程序会在标准输出中打印以下 4 个字段，便于定位 OpenI 任务问题：

| 字段 | 含义 |
|------|------|
| `OPENI_DATASET_ZIP` | 最终选用的数据集 zip 文件名 |
| `COLONY_DATASET_ROOT` | 解压后数据集根目录（含 COCO train/val 子目录） |
| `COLONY_CHECKPOINT_DIR` | 模型输出目录 |
| `boot_file` | OpenI 启动入口脚本路径 |

## 硬约束

1. **仅允许 Huawei Ascend/NPU + MindSpore**，不提供 CUDA/GPU 路由。
2. OpenI 参数必须为 `key=value` 格式（禁止 `--key=value`）。
3. 数据集 zip 选择优先级：显式指定 > 名称含 `clean` > 非 merged zips。
4. COCO 布局必须检测 `train/` 与 `val/` 下的 `annotations/` 及 `images/` 目录。
5. 本地输出路径为 `/cache/output/model`，下载结果位于 `models-0/model/`。

## 本地验证

```bash
# 编译检查
python -m py_compile huawei_npu_migration/scripts/openi_prepare_dataset.py
python -m py_compile huawei_npu_migration/scripts/openi_cloudbrain_train_mindspore.py
python -m py_compile huawei_npu_migration/scripts/mindspore_colony_train.py

# 帮助信息
python huawei_npu_migration/scripts/openi_cloudbrain_train_mindspore.py --help

# 本地 key=value dry-run（需本地存在 zip 或使用模拟 zip）
python scripts/openi_cloudbrain_train_mindspore.py \
    zip-name=data.zip \
    extract-dir=./tmp_extract \
    checkpoint-dir=./tmp_model \
    algorithm=colony_seednet_v1
```
