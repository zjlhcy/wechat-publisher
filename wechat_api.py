# -*- coding: utf-8 -*-
"""
WeChat Official Account API Client
封装微信公众号API：access_token管理、素材上传、草稿箱操作
"""

import requests
import json
import time
import os
import logging

logger = logging.getLogger(__name__)


class WeChatAPI:
    """微信公众号API客户端"""

    BASE_URL = "https://api.weixin.qq.com/cgi-bin"

    def __init__(self, appid, appsecret):
        self.appid = appid
        self.appsecret = appsecret
        self._access_token = None
        self._token_expires_at = 0

    def get_access_token(self):
        """获取access_token，带缓存（提前5分钟刷新）"""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        url = f"{self.BASE_URL}/token"
        params = {
            "grant_type": "client_credential",
            "appid": self.appid,
            "secret": self.appsecret,
        }
        resp = requests.get(url, params=params, timeout=30)
        data = resp.json()

        if "access_token" not in data:
            errcode = data.get("errcode", "unknown")
            errmsg = data.get("errmsg", "unknown")
            logger.error(f"获取access_token失败: errcode={errcode}, errmsg={errmsg}")
            raise RuntimeError(
                f"获取access_token失败: [{errcode}] {errmsg}\n"
                f"常见原因：1)IP未加入白名单 2)AppID/AppSecret错误 3)网络问题"
            )

        self._access_token = data["access_token"]
        self._token_expires_at = time.time() + data.get("expires_in", 7200) - 300
        logger.info("access_token获取成功")
        return self._access_token

    def upload_permanent_material(self, image_path):
        """
        上传永久图片素材（用于封面图thumb_media_id）
        返回: {"media_id": "...", "url": "...", "item_id": "..."}
        """
        token = self.get_access_token()
        url = f"{self.BASE_URL}/material/add_material"
        params = {"access_token": token, "type": "image"}

        filename = os.path.basename(image_path)
        with open(image_path, "rb") as f:
            files = {"media": (filename, f, "image/jpeg")}
            resp = requests.post(url, params=params, files=files, timeout=60)

        data = resp.json()
        if "media_id" not in data:
            errcode = data.get("errcode", "unknown")
            errmsg = data.get("errmsg", "unknown")
            logger.error(f"上传永久素材失败: {image_path} -> [{errcode}] {errmsg}")
            raise RuntimeError(f"上传永久素材失败: [{errcode}] {errmsg}")

        logger.info(f"永久素材上传成功: {image_path} -> media_id={data['media_id']}")
        return data

    def upload_content_image(self, image_path):
        """
        上传文章内容图片（返回URL用于在正文中引用）
        返回: {"url": "https://mmbiz.qpic.cn/..."}
        """
        token = self.get_access_token()
        url = f"{self.BASE_URL}/media/uploadimg"
        params = {"access_token": token}

        filename = os.path.basename(image_path)
        with open(image_path, "rb") as f:
            files = {"media": (filename, f, "image/jpeg")}
            resp = requests.post(url, params=params, files=files, timeout=60)

        data = resp.json()
        if "url" not in data:
            errcode = data.get("errcode", "unknown")
            errmsg = data.get("errmsg", "unknown")
            logger.error(f"上传内容图片失败: {image_path} -> [{errcode}] {errmsg}")
            raise RuntimeError(f"上传内容图片失败: [{errcode}] {errmsg}")

        logger.info(f"内容图片上传成功: {image_path}")
        return data

    def add_draft(self, article):
        """
        新建草稿
        article: {
            "title": "标题",
            "author": "作者",
            "digest": "摘要",
            "content": "HTML正文",
            "thumb_media_id": "封面图media_id",
            "content_source_url": "",
            "need_open_comment": 0,
            "only_fans_can_comment": 0
        }
        返回: {"media_id": "草稿media_id"}
        """
        token = self.get_access_token()
        url = f"{self.BASE_URL}/draft/add"
        params = {"access_token": token}
        payload = {"articles": [article]}

        # 使用 ensure_ascii=False 发送 UTF-8 编码的 JSON
        # 避免 requests 默认的 ensure_ascii=True 将中文转为 \uXXXX 导致字节膨胀
        json_str = json.dumps(payload, ensure_ascii=False)
        resp = requests.post(
            url,
            params=params,
            data=json_str.encode("utf-8"),
            headers={"Content-Type": "application/json; charset=utf-8"},
            timeout=30,
        )
        data = resp.json()

        if "media_id" not in data:
            errcode = data.get("errcode", "unknown")
            errmsg = data.get("errmsg", "unknown")
            logger.error(f"创建草稿失败: [{errcode}] {errmsg}")
            raise RuntimeError(f"创建草稿失败: [{errcode}] {errmsg}")

        logger.info(f"草稿创建成功: media_id={data['media_id']}")
        return data

    def batch_get_drafts(self, offset=0, count=20):
        """获取草稿列表"""
        token = self.get_access_token()
        url = f"{self.BASE_URL}/draft/batchget"
        params = {"access_token": token}
        payload = {"offset": offset, "count": count, "no_content": 1}

        resp = requests.post(
            url, params=params, json=payload, timeout=30
        )
        return resp.json()

    def delete_draft(self, media_id):
        """删除草稿"""
        token = self.get_access_token()
        url = f"{self.BASE_URL}/draft/delete"
        params = {"access_token": token}
        payload = {"media_id": media_id}

        resp = requests.post(
            url, params=params, json=payload, timeout=30
        )
        return resp.json()

    def upload_image_for_content(self, image_path, max_size_kb=1024):
        """
        上传内容图片并自动压缩（微信限制1MB）
        返回图片URL
        """
        # 检查文件大小，超过限制则压缩
        file_size = os.path.getsize(image_path)
        if file_size > max_size_kb * 1024:
            compressed_path = self._compress_image(image_path, max_size_kb)
            if compressed_path:
                result = self.upload_content_image(compressed_path)
                try:
                    os.remove(compressed_path)
                except:
                    pass
                return result["url"]

        result = self.upload_content_image(image_path)
        return result["url"]

    def _compress_image(self, image_path, max_size_kb):
        """压缩图片到指定大小以内"""
        try:
            from PIL import Image

            img = Image.open(image_path)
            if img.mode != "RGB":
                img = img.convert("RGB")

            compressed_path = image_path.rsplit(".", 1)[0] + "_compressed.jpg"
            quality = 90

            while quality > 20:
                img.save(compressed_path, "JPEG", quality=quality)
                if os.path.getsize(compressed_path) <= max_size_kb * 1024:
                    break
                quality -= 10

            logger.info(f"图片压缩: {image_path} -> quality={quality}")
            return compressed_path
        except Exception as e:
            logger.warning(f"图片压缩失败: {e}")
            return None


def load_config(config_path=None):
    """加载配置文件"""
    if config_path is None:
        config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "config.json"
        )
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)
