# -*- coding: utf-8 -*-
"""
Status Check - 系统状态检查脚本
检查微信API连接、配置文件、目录结构等是否正常

用法:
    python status_check.py
"""

import sys
import os
import json
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wechat_api import WeChatAPI, load_config


def check_config():
    """检查配置文件"""
    print("[1/5] 检查配置文件...")
    try:
        config = load_config()
        appid = config["wechat"]["appid"]
        appsecret = config["wechat"]["appsecret"]
        print(f"  AppID: {appid[:8]}...{appid[-4:]}")
        print(f"  AppSecret: {'*' * 20}")
        print(f"  作者: {config['publish']['author']}")
        print(f"  每日文章数: {config['publish']['daily_article_count']}")
        print("  [OK] 配置文件正常\n")
        return config
    except Exception as e:
        print(f"  [FAIL] 配置文件错误: {e}\n")
        return None


def check_directories(config):
    """检查目录结构"""
    print("[2/5] 检查目录结构...")
    dirs_to_check = [
        ("基础目录", config["paths"]["base_dir"]),
        ("输出目录", config["paths"]["output_dir"]),
        ("文章目录", config["paths"]["articles_dir"]),
        ("图片目录", config["paths"]["images_dir"]),
        ("日志目录", config["paths"]["logs_dir"]),
    ]
    all_ok = True
    for name, path in dirs_to_check:
        exists = os.path.exists(path)
        status = "[OK]" if exists else "[MISSING]"
        if not exists:
            all_ok = False
        print(f"  {status} {name}: {path}")

    if all_ok:
        print("  [OK] 目录结构完整\n")
    else:
        print("  [WARN] 部分目录缺失\n")
    return all_ok


def check_wechat_api(config):
    """检查微信API连接"""
    print("[3/5] 检查微信API连接...")
    try:
        api = WeChatAPI(config["wechat"]["appid"], config["wechat"]["appsecret"])
        token = api.get_access_token()
        print(f"  [OK] access_token获取成功 (前20字符: {token[:20]}...)\n")
        return api
    except Exception as e:
        print(f"  [FAIL] API连接失败: {e}")
        print(f"  常见原因: 1)IP未加入白名单 2)AppID/AppSecret错误\n")
        return None


def check_drafts(api):
    """检查草稿箱"""
    print("[4/5] 检查草稿箱...")
    try:
        result = api.batch_get_drafts(offset=0, count=5)
        total = result.get("total_count", 0)
        item_count = result.get("item_count", 0)
        print(f"  [OK] 草稿总数: {total}")
        if item_count > 0:
            for item in result.get("item", []):
                for article in item.get("content", {}).get("news_item", []):
                    title = article.get("title", "无标题")
                    update_time = datetime.datetime.fromtimestamp(
                        item.get("update_time", 0)
                    ).strftime("%Y-%m-%d %H:%M")
                    try:
                        print(f"    - [{update_time}] {title}")
                    except UnicodeEncodeError:
                        print(f"    - [{update_time}] {title.encode('utf-8', errors='replace').decode('utf-8', errors='replace')}")
        print()
        return total
    except Exception as e:
        print(f"  [FAIL] 获取草稿列表失败: {e}\n")
        return 0


def check_local_files(config):
    """检查本地文件"""
    print("[5/5] 检查本地文件...")
    articles_dir = config["paths"]["articles_dir"]
    images_dir = config["paths"]["images_dir"]

    article_files = [f for f in os.listdir(articles_dir) if f.endswith(".json")] if os.path.exists(articles_dir) else []
    image_files = [f for f in os.listdir(images_dir) if f.endswith((".png", ".jpg", ".jpeg"))] if os.path.exists(images_dir) else []
    published_markers = [f for f in os.listdir(articles_dir) if f.endswith(".published")] if os.path.exists(articles_dir) else []

    print(f"  文章JSON文件: {len(article_files)} 个")
    print(f"  图片文件: {len(image_files)} 个")
    print(f"  已发布标记: {len(published_markers)} 个")

    # 检查日志
    logs_dir = config["paths"]["logs_dir"]
    if os.path.exists(logs_dir):
        log_files = sorted([f for f in os.listdir(logs_dir) if f.endswith(".log")], reverse=True)
        if log_files:
            print(f"  最新日志: {log_files[0]}")

    print("\n" + "=" * 50)
    print("系统状态检查完成!")
    print("=" * 50)


def main():
    print("=" * 50)
    print("  微信公众号自动发布系统 - 状态检查")
    print(f"  检查时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50 + "\n")

    config = check_config()
    if not config:
        sys.exit(1)

    check_directories(config)

    api = check_wechat_api(config)
    if api:
        check_drafts(api)

    check_local_files(config)


if __name__ == "__main__":
    main()
