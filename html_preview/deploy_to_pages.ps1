<#
PowerShell 脚本: deploy_to_pages.ps1
用途: 将 `html_preview/deployment_assets` 目录中的图片复制到本地 GitHub Pages 仓库的 `img/` 目录，提交并推送。

用法示例:
.
# 1) 在 PowerShell 中运行: .\deploy_to_pages.ps1 -PagesRepoPath "C:\path\to\pages-repo" -Branch "gh-pages"
# 2) 脚本将:
#    - 验证输入目录存在
#    - 在 pages 仓库中创建 img 目录（如果不存在）
#    - 复制所有文件
#    - 执行 git add/commit/push
#    - 打印出要检查的最终 URL 示例

注意:
- 该脚本假定本机已经设置好 git 凭据（或使用 SSH key）。
- 若仓库有未提交的更改，脚本会停止并提示用户处理。
- 不会自动创建远程仓库或远程分支。

参数:
- PagesRepoPath (string) - 本地 Pages 仓库路径（必需）
- Branch (string) - 要推送的分支，默认 gh-pages
- AssetSource (string) - 源图片目录，默认是脚本同目录下的 "deployment_assets"
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [string]$PagesRepoPath,

    [Parameter(Mandatory=$false)]
    [string]$Branch = "gh-pages",

    [Parameter(Mandatory=$false)]
    [string]$AssetSource = "$(Split-Path -Parent $MyInvocation.MyCommand.Definition)\deployment_assets",
    [Parameter(Mandatory=$false)]
    [string]$TargetSubpath = "img" # relative path inside pages repo where assets will be copied. e.g., 'model/img'
)

function Write-Info($msg){ Write-Host $msg -ForegroundColor Cyan }
function Write-Warn($msg){ Write-Host $msg -ForegroundColor Yellow }
function Write-Err($msg){ Write-Host $msg -ForegroundColor Red }

# 1) 验证路径
if (-not (Test-Path $PagesRepoPath)){
    Write-Err "Pages 仓库路径不存在: $PagesRepoPath"
    exit 2
}

if (-not (Test-Path $AssetSource)){
    Write-Err "Asset 源目录不存在: $AssetSource"
    exit 2
}

# 2) 简单的 git 检查
Push-Location $PagesRepoPath
try{
    $gitStatus = git status --porcelain
} catch {
    Write-Err "无法在 $PagesRepoPath 执行 git. 请确保 git 已安装并且该目录是一个 git 仓库。"
    Pop-Location
    exit 3
}
if ($gitStatus -ne ""){
    Write-Warn "Pages 仓库有未提交的更改。请先提交或 stash。"
    Pop-Location
    exit 4
}

# 3) 切换到目标分支
$currBranch = git rev-parse --abbrev-ref HEAD
if ($currBranch -ne $Branch){
    Write-Info "切换到分支 $Branch"
    git fetch origin $Branch
    git checkout $Branch
}

# 4) 创建目标子路径目录（例如 model/img 或 img）
$imgDir = Join-Path $PagesRepoPath $TargetSubpath
if (-not (Test-Path $imgDir)){
    New-Item -ItemType Directory -Path $imgDir | Out-Null
    Write-Info "创建目录: $imgDir"
}

# 5) 复制文件
git add img
Get-ChildItem -Path $AssetSource -File | ForEach-Object {
    $dest = Join-Path $imgDir $_.Name
    Copy-Item -Path $_.FullName -Destination $dest -Force
    Write-Info "复制: $($_.Name) -> $TargetSubpath/"
}

# 6) Git add/commit/push
git add $TargetSubpath
$commitMessage = "Add preview images for Buckwheat project preview page"
$commitRes = git commit -m $commitMessage
if ($LASTEXITCODE -ne 0){
    Write-Warn "git commit 未创建新的提交。可能是内容未变化。"
} else {
    Write-Info "推送到 origin/$Branch"
    git push origin $Branch
}

# 7) 恢复分支（可选，保持在 gh-pages）
# 可移除或自定义

# 8) 显示结果提示
Write-Host "\n部署完成。检查以下 URL 是否可访问（替换为你的 GitHub Pages 域和仓库子路径）：" -ForegroundColor Green
Write-Host "https://<your-username>.github.io/buckwheat-project/img/test-001.jpg" -ForegroundColor Green
Write-Host "https://<your-username>.github.io/buckwheat-project/img/test-015.jpg" -ForegroundColor Green
Write-Host "如果你使用自定义域或不同子路径，请根据实际情况修改 window.__ASSET_BASE__。"

Pop-Location
