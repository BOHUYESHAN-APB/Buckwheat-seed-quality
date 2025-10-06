#!/bin/bash

# PP-YOLOE+ Quality-Optimized Training
# 质量保证的优化训练配置

export CUDA_VISIBLE_DEVICES=0
export FLAGS_cudnn_exhaustive_search=1
export FLAGS_cudnn_batchnorm_spatial_persistent=1

CONFIG_FILE="configs/ppyoloe_plus/ppyoloe_plus_crn_m_300e_speed_optimized.yml"
LOG_FILE="quality_optimized_training_$(date +%Y%m%d_%H%M%S).log"

echo "=== PP-YOLOE+ 质量优化训练 ==="
echo "开始时间: $(date)"
echo "配置: $CONFIG_FILE"
# 自动检测最新checkpoint
LATEST_CHECKPOINT=$(ls -t output/*.pdparams 2>/dev/null | grep -E '[0-9]+\.pdparams' | head -1 | sed 's/.*\/\([0-9]\+\)\.pdparams/\1/')

if [ -z "$LATEST_CHECKPOINT" ]; then
    echo "❌ 未找到checkpoint文件!"
    exit 1
fi

echo "Resume from: output/$LATEST_CHECKPOINT (Epoch $((LATEST_CHECKPOINT + 1)))"

# 检查checkpoint
if [ -f "output/$LATEST_CHECKPOINT.pdparams" ]; then
    echo "✅ Checkpoint $LATEST_CHECKPOINT 存在，从Epoch $((LATEST_CHECKPOINT + 1))重新开始"
REMAINING_EPOCHS=$((300 - LATEST_CHECKPOINT))
echo "剩余epochs: $REMAINING_EPOCHS"
else
    echo "❌ Checkpoint $LATEST_CHECKPOINT 不存在!"
    exit 1
fi

echo "启动质量优化训练..."
echo "按 Ctrl+C 可安全停止"
echo ""

# 启动训练
# 启动训练
python tools/train.py \
    -c $CONFIG_FILE \
    -r output/$LATEST_CHECKPOINT \
    --eval \
    --use_vdl=True \
    --vdl_log_dir vdl_dir \
    2>&1 | tee $LOG_FILE

echo ""
echo "=== 训练完成 ==="
echo "结束时间: $(date)"
echo "模型已保存到: output/"
echo "可视化日志: vdl_dir/ppyoloe_plus_quality/"
echo "训练日志: $LOG_FILE"