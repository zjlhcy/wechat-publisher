# -*- coding: utf-8 -*-
"""
Publisher - 文章发布脚本
读取JSON格式的文章数据，上传图片到微信，创建草稿

用法:
    python publisher.py                          # 发布今天最新的文章JSON
    python publisher.py articles/xxx.json        # 发布指定JSON文件
    python publisher.py --all                    # 发布articles目录下所有未发布的JSON

文章JSON格式:
{
  "articles": [
    {
      "title": "文章标题(最多64字)",
      "author": "作者名",
      "digest": "文章摘要(最多120字)",
      "content_html": "<p>正文HTML</p>\n[IMG_1]\n<p>更多内容</p>\n[IMG_2]\n...",
      "cover_image": "/absolute/path/to/cover.jpg",
      "content_images": ["/path/to/img1.jpg", "/path/to/img2.jpg", "/path/to/img3.jpg"],
      "topics": ["#话题1", "#话题2", "#话题3", "#话题4", "#话题5"]
    }
  ]
}
"""

import sys
import os
import json
import re
import logging
import datetime
import time

# 添加当前目录到path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wechat_api import WeChatAPI, load_config

# 日志配置
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

log_file = os.path.join(
    LOG_DIR, f"publish_{datetime.date.today().isoformat()}.log"
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


def format_topics_html(topics):
    """将话题列表格式化为HTML"""
    if not topics:
        return ""

    topics_html = """
<div style="margin-top: 30px; padding: 15px; background: #f7f7f7; border-radius: 8px;">
<p style="font-weight: bold; color: #333; margin-bottom: 10px; font-size: 15px;">热门话题</p>
<p style="color: #576b95; font-size: 14px; line-height: 2;">
"""
    for topic in topics:
        topics_html += f'<span style="margin-right: 8px;">{topic}</span>'
    topics_html += """
</p>
</div>
"""
    return topics_html


def format_content_html(raw_html, image_urls, topics):
    """
    将带图片占位符的HTML替换为实际图片URL，并追加话题区
    [IMG_1] -> <img src="url1" />
    [IMG_2] -> <img src="url2" />
    ...
    """
    content = raw_html

    # 替换图片占位符
    for i, url in enumerate(image_urls):
        placeholder = f"[IMG_{i + 1}]"
        img_tag = (
            f'<img src="{url}" '
            f'style="max-width: 100%; border-radius: 6px; '
            f'margin: 12px 0; display: block;" '
            f'alt="配图{i + 1}" />'
        )
        content = content.replace(placeholder, img_tag)

    # 清理未替换的占位符
    content = re.sub(r"\[IMG_\d+\]", "", content)

    # 追加话题
    content += format_topics_html(topics)

    # 添加基础样式
    styled_content = f"""
<div style="font-size: 16px; line-height: 1.8; color: #333; word-wrap: break-word;">
{content}
</div>
"""
    return styled_content


def publish_article(api, article_data):
    """
    发布单篇文章到微信草稿箱
    返回: (success: bool, media_id: str, error: str)
    """
    title = article_data.get("title", "").strip()
    author = article_data.get("author", "前沿项目观察")
    digest = article_data.get("digest", "").strip()
    content_html = article_data.get("content_html", "")
    cover_image = article_data.get("cover_image", "")
    content_images = article_data.get("content_images", [])
    topics = article_data.get("topics", [])

    # 基本校验
    if not title:
        return False, None, "标题为空"
    if len(title) > 64:
        title = title[:64]
        logger.warning(f"标题超过64字，已截断: {title}")
    if not digest:
        # 自动生成摘要
        plain = re.sub(r"<[^>]+>", "", content_html)
        digest = plain[:110] + "..."
    if len(digest) > 120:
        digest = digest[:120]
    if not content_html:
        return False, None, "正文为空"
    if not cover_image or not os.path.exists(cover_image):
        return False, None, f"封面图不存在: {cover_image}"

    # 上传封面图（永久素材）
    logger.info(f"正在上传封面图: {cover_image}")
    try:
        cover_result = api.upload_permanent_material(cover_image)
        thumb_media_id = cover_result["media_id"]
    except Exception as e:
        return False, None, f"封面图上传失败: {e}"

    # 上传内容图片
    image_urls = []
    for i, img_path in enumerate(content_images):
        if not os.path.exists(img_path):
            logger.warning(f"内容图片不存在，跳过: {img_path}")
            image_urls.append("")
            continue
        logger.info(f"正在上传内容图片 {i + 1}/{len(content_images)}: {img_path}")
        try:
            url = api.upload_image_for_content(img_path)
            image_urls.append(url)
        except Exception as e:
            logger.error(f"内容图片上传失败: {img_path} -> {e}")
            image_urls.append("")

    # 格式化正文
    final_content = format_content_html(content_html, image_urls, topics)

    # 创建草稿
    draft_article = {
        "title": title,
        "author": author,
        "digest": digest,
        "content": final_content,
        "thumb_media_id": thumb_media_id,
        "content_source_url": "",
        "need_open_comment": 0,
        "only_fans_can_comment": 0,
    }

    logger.info(f"正在创建草稿: {title}")
    try:
        result = api.add_draft(draft_article)
        media_id = result["media_id"]
        logger.info(f"草稿创建成功! media_id={media_id}")
        return True, media_id, None
    except Exception as e:
        return False, None, f"草稿创建失败: {e}"


def find_latest_article_json(articles_dir):
    """找到articles目录下最新的未发布JSON文件"""
    json_files = []
    for f in os.listdir(articles_dir):
        if f.endswith(".json"):
            fpath = os.path.join(articles_dir, f)
            # 检查是否有对应的 .published 标记文件
            marker = fpath + ".published"
            if not os.path.exists(marker):
                json_files.append((os.path.getmtime(fpath), fpath))

    if not json_files:
        return None

    json_files.sort(reverse=True)
    return json_files[0][1]


def find_all_unpublished(articles_dir):
    """找到所有未发布的JSON文件"""
    json_files = []
    for f in sorted(os.listdir(articles_dir)):
        if f.endswith(".json"):
            fpath = os.path.join(articles_dir, f)
            marker = fpath + ".published"
            if not os.path.exists(marker):
                json_files.append(fpath)
    return json_files


def mark_as_published(json_path, results):
    """标记JSON文件为已发布，并写入发布结果"""
    marker = json_path + ".published"
    with open(marker, "w", encoding="utf-8") as f:
        json.dump(
            {
                "published_at": datetime.datetime.now().isoformat(),
                "results": results,
            },
            f,
            ensure_ascii=False,
            indent=2,
        )


def main():
    config = load_config()
    # 本地配置文件覆盖（包含敏感信息，已 gitignore）
    local_config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.local.json")
    if os.path.exists(local_config_path):
        with open(local_config_path, "r", encoding="utf-8") as f:
            local_config = json.load(f)
        config["wechat"].update(local_config.get("wechat", {}))
    # 支持环境变量覆盖（用于GitHub Actions等CI环境）
    if os.environ.get("WECHAT_APPID"):
        config["wechat"]["appid"] = os.environ["WECHAT_APPID"]
    if os.environ.get("WECHAT_APPSECRET"):
        config["wechat"]["appsecret"] = os.environ["WECHAT_APPSECRET"]
    api = WeChatAPI(
        config["wechat"]["appid"], config["wechat"]["appsecret"]
    )

    articles_dir = config["paths"]["articles_dir"]

    # 确定要发布的文件
    target_files = []
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--all":
            target_files = find_all_unpublished(articles_dir)
        elif os.path.isabs(arg) or os.path.exists(arg):
            target_files = [arg]
        else:
            # 尝试在articles_dir下找
            candidate = os.path.join(articles_dir, arg)
            if os.path.exists(candidate):
                target_files = [candidate]
            else:
                logger.error(f"文件不存在: {arg}")
                sys.exit(1)
    else:
        latest = find_latest_article_json(articles_dir)
        if latest:
            target_files = [latest]
        else:
            logger.error("没有找到未发布的文章JSON文件")
            sys.exit(1)

    if not target_files:
        logger.error("没有找到待发布的文件")
        sys.exit(1)

    logger.info(f"待发布文件: {target_files}")

    total_success = 0
    total_fail = 0

    for json_path in target_files:
        logger.info(f"\n{'='*60}")
        logger.info(f"处理文件: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        articles = data.get("articles", [])
        if not articles:
            logger.warning(f"文件中没有文章: {json_path}")
            continue

        results = []
        for i, article in enumerate(articles):
            logger.info(f"\n--- 文章 {i + 1}/{len(articles)}: {article.get('title', '无标题')} ---")

            success, media_id, error = publish_article(api, article)
            results.append(
                {
                    "title": article.get("title", ""),
                    "success": success,
                    "media_id": media_id,
                    "error": error,
                }
            )

            if success:
                total_success += 1
                logger.info(f"发布成功: {article.get('title')}")
            else:
                total_fail += 1
                logger.error(f"发布失败: {article.get('title')} -> {error}")

            # 间隔1秒，避免API频率限制
            if i < len(articles) - 1:
                time.sleep(1)

        # 标记为已发布
        mark_as_published(json_path, results)

    # 汇总
    logger.info(f"\n{'='*60}")
    logger.info(f"发布完成! 成功: {total_success}, 失败: {total_fail}")
    print(f"\n发布完成! 成功: {total_success} 篇, 失败: {total_fail} 篇")


if __name__ == "__main__":
    main()
