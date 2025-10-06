#!/usr/bin/env pwsh
# 荞麦种子检测APP - 一键部署脚本
# 使用方法: ./deploy.ps1

Write-Host "🌾 荞麦种子检测APP - 自动部署工具" -ForegroundColor Green
Write-Host "=" * 50

# 1. 检查环境
Write-Host "`n[1/5] 检查Android开发环境..." -ForegroundColor Cyan
$adbPath = Get-Command adb -ErrorAction SilentlyContinue
if (-not $adbPath) {
    Write-Host "❌ 错误: 未找到adb命令，请安装Android SDK Platform Tools" -ForegroundColor Red
    exit 1
}
Write-Host "✅ ADB已安装: $($adbPath.Source)" -ForegroundColor Green

# 2. 构建APK
Write-Host "`n[2/5] 开始构建APK..." -ForegroundColor Cyan
Set-Location android-app
$buildResult = ./gradlew assembleDebug 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ 构建失败，详细信息:" -ForegroundColor Red
    Write-Host $buildResult
    exit 1
}
Write-Host "✅ APK构建成功" -ForegroundColor Green

# 3. 检查APK
Write-Host "`n[3/5] 验证APK文件..." -ForegroundColor Cyan
$apkPath = "app/build/outputs/apk/debug/app-debug.apk"
if (-not (Test-Path $apkPath)) {
    Write-Host "❌ 错误: APK文件不存在" -ForegroundColor Red
    exit 1
}
$apkInfo = Get-Item $apkPath
$apkSizeMB = [math]::Round($apkInfo.Length / 1MB, 2)
Write-Host "✅ APK文件: $apkPath" -ForegroundColor Green
Write-Host "   大小: ${apkSizeMB}MB" -ForegroundColor Gray
Write-Host "   时间: $($apkInfo.LastWriteTime)" -ForegroundColor Gray

# 4. 检查设备连接
Write-Host "`n[4/5] 检查Android设备连接..." -ForegroundColor Cyan
$devices = adb devices | Select-String "device$"
if ($devices.Count -eq 0) {
    Write-Host "⚠️  未检测到连接的设备" -ForegroundColor Yellow
    Write-Host "   请确保:" -ForegroundColor Yellow
    Write-Host "   - 设备已通过USB连接" -ForegroundColor Yellow
    Write-Host "   - 已开启USB调试模式" -ForegroundColor Yellow
    Write-Host "   - 已授权此计算机调试" -ForegroundColor Yellow
    Write-Host "`n跳过安装步骤，APK已准备好手动安装" -ForegroundColor Yellow
    Write-Host "APK位置: $(Resolve-Path $apkPath)" -ForegroundColor Cyan
    exit 0
}
Write-Host "✅ 检测到设备: $($devices.Count)台" -ForegroundColor Green
adb devices -l | Select-String "device" | ForEach-Object { Write-Host "   $_" -ForegroundColor Gray }

# 5. 安装APK
Write-Host "`n[5/5] 安装APK到设备..." -ForegroundColor Cyan
$installResult = adb install -r $apkPath 2>&1
if ($installResult -match "Success") {
    Write-Host "✅ 安装成功！" -ForegroundColor Green
    
    # 启动APP
    Write-Host "`n🚀 正在启动APP..." -ForegroundColor Cyan
    adb shell am start -n com.bohuyeshan.buckwheat/.MainActivity
    Start-Sleep 2
    
    Write-Host "`n✅ 部署完成！APP已在设备上运行" -ForegroundColor Green
    Write-Host "`n📱 使用提示:" -ForegroundColor Yellow
    Write-Host "   1. 授予相机权限以启用实时检测" -ForegroundColor Gray
    Write-Host "   2. 对准荞麦种子查看检测结果" -ForegroundColor Gray
    Write-Host "   3. 点击拍照按钮保存检测图像" -ForegroundColor Gray
    Write-Host "   4. 查看右上角性能监控面板" -ForegroundColor Gray
    
    # 显示实时日志选项
    Write-Host "`n📋 查看实时日志（可选）:" -ForegroundColor Yellow
    Write-Host "   adb logcat | Select-String 'InferenceEngine|PerformanceMonitor'" -ForegroundColor Cyan
} else {
    Write-Host "❌ 安装失败:" -ForegroundColor Red
    Write-Host $installResult
    exit 1
}

Write-Host "`n" + ("=" * 50)
Write-Host "🎉 部署流程已完成！" -ForegroundColor Green
