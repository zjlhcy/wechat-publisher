# -*- coding: utf-8 -*-
"""
Cleanup - 本地文件清理脚本
删除output目录中超过指定天数的文章JSON和图片文件（默认1天）

用法:
    python cleanup.py                    # 清理超过1天的文件
    python cleanup.py --days 2           # 清理超过2天的文件
    python cleanup.py --dry-run          # 仅预览，不实际删除
"""

import sys
import os
import json
import time
import logging
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wechat_api import load_config

# 日志配置
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_file = os.path.join(
    LOG_DIR, f"cleanup_{datetime.date.today().isoformat()}.log"
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


def cleanup_directory(directory, max_age_days, dry_run=False):
    """
    清理指定目录中超过max_age_days天的文件
    返回: (deleted_count, total_size_mb)
    """
    deleted_count = 0
    total_size = 0
    now = time.time()
    cutoff = now - (max_age_days * 86400)

    if not os.path.exists(directory):
        logger.warning(f"目录不存在: {directory}")
        return 0, 0

    for item in os.listdir(directory):
        item_path = os.path.join(directory, item)

        # 跳过 .published 标记文件 — 它们跟对应的JSON一起删
        if item.endswith(".published"):
            mtime = os.path.getmtime(item_path)
            if mtime < cutoff:
                size = os.path.getsize(item_path)
                if dry_run:
                    logger.info(f"[预览] 将删除: {item_path} ({size} bytes)")
                else:
                    try:
                        os.remove(item_path)
                        logger.info(f"已删除: {item_path}")
                    except Exception as e:
                        logger.error(f"删除失败: {item_path} -> {e}")
                        continue
                deleted_count += 1
                total_size += size
            continue

        if os.path.isfile(item_path):
            mtime = os.path.getmtime(item_path)
            if mtime < cutoff:
                size = os.path.getsize(item_path)
                if dry_run:
                    logger.info(f"[预览] 将删除: {item_path} ({size} bytes, 修改于 {datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')})")
                else:
                    try:
                        os.remove(item_path)
                        logger.info(f"已删除: {item_path} (修改于 {datetime.datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')})")
                    except Exception as e:
                        logger.error(f"删除失败: {item_path} -> {e}")
                        continue
                deleted_count += 1
                total_size += size

    return deleted_count, total_size / (1024 * 1024)


def main():
    config = load_config()

    # 解析参数
    max_age_days = config.get("publish", {}).get("cleanup_after_days", 1)
    dry_run = False

    for arg in sys.argv[1:]:
        if arg == "--dry-run":
            dry_run = True
        elif arg == "--days" and sys.argv.index(arg) + 1 < len(sys.argv):
            idx = sys.argv.index(arg)
            max_age_days = int(sys.argv[idx + 1])

    logger.info(f"清理配置: 保留 {max_age_days} 天内的文件, dry_run={dry_run}")
    logger.info(f"清理时间: {datetime.datetime.now().isoformat()}")

    output_dir = config["paths"]["output_dir"]
    articles_dir = config["paths"]["articles_dir"]
    images_dir = config["paths"]["images_dir"]

    total_deleted = 0
    total_size_mb = 0

    # 清理文章目录
    logger.info(f"\n--- 清理文章目录: {articles_dir} ---")
    count, size = cleanup_directory(articles_dir, max_age_days, dry_run)
    total_deleted += count
    total_size_mb += size

    # 清理图片目录
    logger.info(f"\n--- 清理图片目录: {images_dir} ---")
    count, size = cleanup_directory(images_dir, max_age_days, dry_run)
    total_deleted += count
    total_size_mb += size

    logger.info(f"\n{'='*60}")
    logger.info(f"清理完成! 删除文件: {total_deleted} 个, 释放空间: {total_size_mb:.2f} MB")
    print(f"\n清理完成! 删除 {total_deleted} 个文件, 释放 {total_size_mb:.2f} MB")


if __name__ == "__main__":
    main()
