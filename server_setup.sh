#!/bin/bash
# ============================================================
# 微信公众号自动发布系统 - 云服务器一键部署脚本
# 适用: Ubuntu 20.04+ / CentOS 7+ / Debian 10+
# 用法: chmod +x server_setup.sh && sudo bash server_setup.sh
# ============================================================
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }

echo "============================================"
echo "  微信公众号自动发布系统 - 服务器部署"
echo "============================================"
echo ""

# ==================== Step 1: Check root ====================
if [ "$EUID" -ne 0 ]; then
    err "请用 sudo 运行: sudo bash server_setup.sh"
fi

# ==================== Step 2: Detect OS ====================
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
else
    err "无法识别操作系统"
fi
log "检测到系统: $OS"

# ==================== Step 3: Install dependencies ====================
log "正在安装依赖包..."

case $OS in
    ubuntu|debian)
        apt-get update -qq
        apt-get install -y -qq python3 python3-pip python3-venv git curl cron 2>&1 | tail -1
        ;;
    centos|rhel|fedora|rocky|almalinux)
        yum install -y -q python3 python3-pip git curl cronie 2>&1 | tail -1
        systemctl enable crond
        systemctl start crond
        ;;
    *)
        warn "未识别的系统: $OS，请手动安装 python3, pip, git, cron"
        ;;
esac
log "依赖包安装完成"

# ==================== Step 4: Clone project ====================
PROJECT_DIR="/opt/wechat-publisher"

if [ -d "$PROJECT_DIR" ]; then
    log "项目目录已存在，正在更新..."
    cd "$PROJECT_DIR"
    git pull
else
    log "正在克隆项目..."
    git clone https://github.com/zjlhcy/wechat-publisher.git "$PROJECT_DIR"
    cd "$PROJECT_DIR"
fi

# ==================== Step 5: Setup Python venv ====================
log "正在配置 Python 虚拟环境..."
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
log "Python 环境配置完成"

# ==================== Step 6: Create config with credentials ====================
log "正在创建配置文件..."

# 提示用户输入 AppSecret（如果环境变量里没有）
if [ -z "$WECHAT_APPSECRET" ]; then
    echo ""
    echo "============================================"
    echo "  请输入微信公众号 AppSecret"
    echo "  (从公众号后台 → 设置与开发 → 基本配置 获取)"
    echo "============================================"
    read -p "AppSecret: " INPUT_SECRET
else
    INPUT_SECRET="$WECHAT_APPSECRET"
fi

cat > config.local.json << EOF
{
  "wechat": {
    "appsecret": "${INPUT_SECRET}"
  }
}
EOF
chmod 600 config.local.json
log "配置文件已创建 (config.local.json)"

# ==================== Step 7: Create directories ====================
mkdir -p output/articles output/images logs
log "目录结构已创建"

# ==================== Step 8: Setup cron job ====================
log "正在配置定时任务 (每天北京时间 7:00)..."

CRON_JOB="0 23 * * * cd ${PROJECT_DIR} && ${PROJECT_DIR}/venv/bin/python generate_articles_v2.py && ${PROJECT_DIR}/venv/bin/python gen_placeholder_images.py && ${PROJECT_DIR}/venv/bin/python publisher.py --all >> ${PROJECT_DIR}/logs/cron.log 2>&1"

# Write crontab (avoid duplicates)
(crontab -l 2>/dev/null | grep -v "wechat-publisher" | grep -v "generate_articles_v2"; echo "$CRON_JOB") | crontab -
log "定时任务已配置: 每天 7:00 自动运行"

# ==================== Step 9: Test run ====================
log "正在进行测试运行..."
source venv/bin/activate

echo ""
echo "--- 第1步: 生成文章 ---"
python generate_articles_v2.py
echo ""

echo "--- 第2步: 生成占位图 ---"
python gen_placeholder_images.py
echo ""

echo "--- 第3步: 发布到微信草稿箱 ---"
python publisher.py --all
echo ""

# ==================== Done ====================
SERVER_IP=$(curl -s ifconfig.me 2>/dev/null || echo "未知")
echo ""
echo "============================================"
echo "  ✅ 部署成功！"
echo "============================================"
echo ""
echo "  服务器IP:    ${SERVER_IP}"
echo "  项目目录:    ${PROJECT_DIR}"
echo "  定时任务:    每天 7:00 自动执行"
echo "  日志文件:    ${PROJECT_DIR}/logs/cron.log"
echo ""
echo "  ⚠️  重要：请将以下IP加入公众号白名单"
echo "     ${SERVER_IP}"
echo "     操作路径: 公众号后台 → 设置与开发 → 基本配置 → IP白名单"
echo ""
echo "  手动运行:"
echo "    cd ${PROJECT_DIR} && source venv/bin/activate"
echo "    python generate_articles_v2.py"
echo "    python gen_placeholder_images.py"
echo "    python publisher.py --all"
echo ""
echo "  查看定时任务日志:"
echo "    tail -f ${PROJECT_DIR}/logs/cron.log"
echo "============================================"
