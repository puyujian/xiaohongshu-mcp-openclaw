#!/usr/bin/env python3
"""xiaohongshu-mcp HTTP API 客户端（OpenClaw Skill 专用）"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request

DEFAULT_MANAGER_PORT = 18050
DEFAULT_TIMEOUT = 60

TASK_BOOL_FIELDS = {
    "is_original",
    "load_all_comments",
    "click_more_replies",
    "unlike",
    "unfavorite",
}
TASK_INT_FIELDS = {
    "manager_port",
    "user_port",
    "timeout",
    "max_replies_threshold",
    "max_comment_items",
}
TASK_OPTION_DEFAULTS: dict[str, Any] = {
    "proxy": None,
    "keyword": None,
    "sort_by": None,
    "note_type": None,
    "publish_time": None,
    "search_scope": None,
    "location": None,
    "title": None,
    "content": None,
    "images": None,
    "video": None,
    "tags": None,
    "products": None,
    "visibility": None,
    "is_original": False,
    "feed_id": None,
    "xsec_token": None,
    "comment_id": None,
    "target_user_id": None,
    "comment_content": None,
    "unlike": False,
    "unfavorite": False,
    "profile_user_id": None,
    "load_all_comments": False,
    "click_more_replies": False,
    "max_replies_threshold": None,
    "max_comment_items": None,
    "scroll_speed": None,
}
TASK_CONFIG_KEYS = set(TASK_OPTION_DEFAULTS.keys()) | {
    "ip",
    "manager_port",
    "user_id",
    "user_port",
    "timeout",
}


@dataclass(frozen=True)
class Operation:
    method: str
    path: str
    scope: str  # manager | service | local
    needs_user_id: bool = False
    unsupported_reason: str | None = None


CANONICAL_OPERATIONS: dict[str, Operation] = {
    "health": Operation("GET", "/health", "service"),
    "login-status": Operation("GET", "/api/v1/login/status", "service"),
    "login-qrcode": Operation("GET", "/api/v1/login/qrcode", "service"),
    "login-reset-cookies": Operation("DELETE", "/api/v1/login/cookies", "service"),
    "publish": Operation("POST", "/api/v1/publish", "service"),
    "publish-video": Operation("POST", "/api/v1/publish_video", "service"),
    "feeds-list": Operation("GET", "/api/v1/feeds/list", "service"),
    "feeds-search-get": Operation("GET", "/api/v1/feeds/search", "service"),
    "feeds-search-post": Operation("POST", "/api/v1/feeds/search", "service"),
    "search-feeds": Operation("AUTO", "/api/v1/feeds/search", "service"),
    "feed-detail": Operation("POST", "/api/v1/feeds/detail", "service"),
    "like-feed": Operation("POST", "/api/v1/feeds/like", "service"),
    "favorite-feed": Operation("POST", "/api/v1/feeds/favorite", "service"),
    "user-profile": Operation("POST", "/api/v1/user/profile", "service"),
    "user-me": Operation("GET", "/api/v1/user/me", "service"),
    "comment": Operation("POST", "/api/v1/feeds/comment", "service"),
    "comment-reply": Operation("POST", "/api/v1/feeds/comment/reply", "service"),
    "manager-users": Operation("GET", "/api/manager/v1/users", "manager"),
    "manager-user": Operation(
        "GET", "/api/manager/v1/users/{user_id}", "manager", needs_user_id=True
    ),
    "manager-create-user": Operation("POST", "/api/admin/v1/users", "manager"),
    "manager-update-user": Operation(
        "PUT", "/api/admin/v1/users/{user_id}", "manager", needs_user_id=True
    ),
    "manager-delete-user": Operation(
        "DELETE", "/api/admin/v1/users/{user_id}", "manager", needs_user_id=True
    ),
    "batch-run": Operation("BATCH", "", "local"),
    "not-supported": Operation(
        "UNSUPPORTED",
        "",
        "service",
        unsupported_reason=(
            "当前 xiaohongshu-mcp HTTP API 未提供该能力对应端点，无法直接适配。"
        ),
    ),
}

OPERATION_ALIASES: dict[str, str] = {
    # 兼容原有命名
    "health": "health",
    "login-status": "login-status",
    "login-qrcode": "login-qrcode",
    "login-reset-cookies": "login-reset-cookies",
    "publish": "publish",
    "publish-video": "publish-video",
    "feeds-list": "feeds-list",
    "feeds-search-get": "feeds-search-get",
    "feeds-search-post": "feeds-search-post",
    "search-feeds": "search-feeds",
    "feed-detail": "feed-detail",
    "like-feed": "like-feed",
    "favorite-feed": "favorite-feed",
    "user-profile": "user-profile",
    "user-me": "user-me",
    "comment": "comment",
    "comment-reply": "comment-reply",
    "manager-users": "manager-users",
    "manager-user": "manager-user",
    "manager-create-user": "manager-create-user",
    "manager-update-user": "manager-update-user",
    "manager-delete-user": "manager-delete-user",
    "batch-run": "batch-run",
    "batch": "batch-run",
    # 兼容 XiaohongshuSkills 命名风格
    "check-login": "login-status",
    "check-home-login": "login-status",
    "login": "login-qrcode",
    "check-login-status": "login-status",
    "get-login-qrcode": "login-qrcode",
    "delete-login-cookies": "login-reset-cookies",
    "re-login": "login-reset-cookies",
    "publish-to-xiaohongshu": "publish",
    "publish-video-to-xiaohongshu": "publish-video",
    "list-feeds": "feeds-list",
    "get-feed-detail": "feed-detail",
    "post-comment-to-feed": "comment",
    "reply-comment-to-feed": "comment-reply",
    "like_feed": "like-feed",
    "favorite_feed": "favorite-feed",
    "get-user-profile": "user-profile",
    "get-my-profile": "user-me",
    "list-accounts": "manager-users",
    "add-account": "manager-create-user",
    "create-account": "manager-create-user",
    "edit-account": "manager-update-user",
    "update-account": "manager-update-user",
    "remove-account": "manager-delete-user",
    "delete-account": "manager-delete-user",
    "switch-account": "not-supported",
    "get-notification-mentions": "not-supported",
    "get_notification_mentions": "not-supported",
    "content-data": "not-supported",
    "content_data": "not-supported",
    "manager-list-users": "manager-users",
    "manager-get-user": "manager-user",
}


def normalize_host(ip_value: str) -> str:
    raw = ip_value.strip()
    if not raw:
        raise ValueError("参数 --ip 不能为空。")
    if "://" not in raw:
        raw = f"http://{raw}"
    parsed = parse.urlparse(raw)
    if not parsed.hostname:
        raise ValueError(f"无法解析主机/IP: {ip_value}")
    return parsed.hostname


def parse_json_text(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        return {}
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return {"raw": text}


def http_json(url: str, method: str, timeout: int, payload: Any | None = None) -> Any:
    headers = {"Accept": "application/json"}
    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return parse_json_text(body)
    except error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            json.dumps(
                {
                    "http_status": exc.code,
                    "url": url,
                    "error": parse_json_text(error_body),
                },
                ensure_ascii=False,
            )
        ) from exc
    except error.URLError as exc:
        raise RuntimeError(f"请求失败: {exc.reason}") from exc


def select_best_user(users: list[dict[str, Any]]) -> dict[str, Any]:
    if not users:
        raise RuntimeError("管理器返回 users 为空，无法解析业务端口。")

    healthy_running = [
        user for user in users if user.get("running") is True and user.get("health_ok") is True
    ]
    if healthy_running:
        return healthy_running[0]

    running = [user for user in users if user.get("running") is True]
    if running:
        return running[0]

    return users[0]


def ensure_port(value: Any, from_field: str) -> int:
    if value is None:
        raise RuntimeError(f"未找到端口字段: {from_field}")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"端口字段无效: {from_field}={value}") from exc


def resolve_service_user(
    host: str,
    manager_port: int,
    timeout: int,
    user_id: str | None,
    user_port: int | None,
) -> tuple[int, dict[str, Any]]:
    if user_port is not None:
        return user_port, {
            "id": user_id or "manual-port",
            "port": user_port,
            "source": "user_port",
        }

    manager_base = f"http://{host}:{manager_port}"
    if user_id:
        single = http_json(
            f"{manager_base}/api/manager/v1/users/{parse.quote(user_id)}",
            method="GET",
            timeout=timeout,
        )
        user = single.get("user") if isinstance(single, dict) else None
        if not isinstance(user, dict):
            raise RuntimeError("管理器返回单用户信息异常，无法解析端口。")
        user_port_value = ensure_port(user.get("port"), "user.port")
        user_with_source = dict(user)
        user_with_source["source"] = "manager-user"
        return user_port_value, user_with_source

    all_users = http_json(
        f"{manager_base}/api/manager/v1/users",
        method="GET",
        timeout=timeout,
    )
    users = all_users.get("users") if isinstance(all_users, dict) else None
    if not isinstance(users, list):
        raise RuntimeError("管理器返回 users 字段异常，无法自动选择端口。")
    selected = select_best_user([user for user in users if isinstance(user, dict)])
    selected_port = ensure_port(selected.get("port"), "users[].port")
    selected_with_source = dict(selected)
    selected_with_source["source"] = "manager-users-auto-select"
    return selected_port, selected_with_source


def build_url(base_url: str, path: str, query: dict[str, str] | None = None) -> str:
    url = f"{base_url}{path}"
    if query:
        url = f"{url}?{parse.urlencode(query)}"
    return url


def load_json_file(file_path: Path, source: str) -> Any:
    try:
        content = file_path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise ValueError(f"读取 {source} 失败: {exc}") from exc
    try:
        return json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{source} 不是合法 JSON: {exc}") from exc


def load_body(body: str | None, body_file: str | None) -> Any | None:
    if body and body_file:
        raise ValueError("--body 和 --body-file 不能同时使用。")
    if body:
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--body 不是合法 JSON: {exc}") from exc
    if body_file:
        return load_json_file(Path(body_file), "--body-file")
    return None


def split_csv(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [item.strip() for item in raw.split(",") if item.strip()]


def pick_filters(args: argparse.Namespace) -> dict[str, str]:
    filters: dict[str, str] = {}
    if args.sort_by:
        filters["sort_by"] = args.sort_by
    if args.note_type:
        filters["note_type"] = args.note_type
    if args.publish_time:
        filters["publish_time"] = args.publish_time
    if args.search_scope:
        filters["search_scope"] = args.search_scope
    if args.location:
        filters["location"] = args.location
    return filters


def ensure_dict_body(operation: str, body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        raise ValueError(f"操作 {operation} 的请求体必须是 JSON 对象。")
    return body


def validate_body(operation: str, body: Any) -> dict[str, Any]:
    payload = ensure_dict_body(operation, body)

    if operation == "publish":
        if not payload.get("title"):
            raise ValueError("publish 缺少 title。")
        if not payload.get("content"):
            raise ValueError("publish 缺少 content。")
        images = payload.get("images")
        if not isinstance(images, list) or len(images) == 0:
            raise ValueError("publish 缺少 images，且 images 必须是非空数组。")

    if operation == "publish-video":
        if not payload.get("title"):
            raise ValueError("publish-video 缺少 title。")
        if not payload.get("content"):
            raise ValueError("publish-video 缺少 content。")
        if not payload.get("video"):
            raise ValueError("publish-video 缺少 video。")

    if operation == "feed-detail":
        if not payload.get("feed_id"):
            raise ValueError("feed-detail 缺少 feed_id。")
        if not payload.get("xsec_token"):
            raise ValueError("feed-detail 缺少 xsec_token。")

    if operation == "user-profile":
        if not payload.get("user_id"):
            raise ValueError("user-profile 缺少 user_id。")
        if not payload.get("xsec_token"):
            raise ValueError("user-profile 缺少 xsec_token。")

    if operation == "comment":
        if not payload.get("feed_id"):
            raise ValueError("comment 缺少 feed_id。")
        if not payload.get("xsec_token"):
            raise ValueError("comment 缺少 xsec_token。")
        if not payload.get("content"):
            raise ValueError("comment 缺少 content。")

    if operation == "comment-reply":
        if not payload.get("feed_id"):
            raise ValueError("comment-reply 缺少 feed_id。")
        if not payload.get("xsec_token"):
            raise ValueError("comment-reply 缺少 xsec_token。")
        if not payload.get("content"):
            raise ValueError("comment-reply 缺少 content。")
        if not payload.get("comment_id") and not payload.get("user_id"):
            raise ValueError("comment-reply 需要 comment_id 或 user_id 至少一个。")

    if operation == "like-feed":
        if not payload.get("feed_id"):
            raise ValueError("like-feed 缺少 feed_id。")
        if not payload.get("xsec_token"):
            raise ValueError("like-feed 缺少 xsec_token。")

    if operation == "favorite-feed":
        if not payload.get("feed_id"):
            raise ValueError("favorite-feed 缺少 feed_id。")
        if not payload.get("xsec_token"):
            raise ValueError("favorite-feed 缺少 xsec_token。")

    if operation == "manager-create-user":
        if not str(payload.get("id") or "").strip():
            raise ValueError("manager-create-user 缺少 id。")
        port = payload.get("port")
        if not isinstance(port, int) or port <= 0:
            raise ValueError("manager-create-user 缺少合法 port。")
        proxy = payload.get("proxy", "")
        if proxy is None:
            payload["proxy"] = ""
        elif not isinstance(proxy, str):
            raise ValueError("manager-create-user 的 proxy 必须是字符串。")
        else:
            payload["proxy"] = proxy.strip()

    if operation == "manager-update-user":
        port = payload.get("port")
        if not isinstance(port, int) or port <= 0:
            raise ValueError("manager-update-user 缺少合法 port。")
        proxy = payload.get("proxy", "")
        if proxy is None:
            payload["proxy"] = ""
        elif not isinstance(proxy, str):
            raise ValueError("manager-update-user 的 proxy 必须是字符串。")
        else:
            payload["proxy"] = proxy.strip()

    if operation in {"feeds-search-post", "search-feeds"} and not payload.get("keyword"):
        raise ValueError(f"{operation} 缺少 keyword。")

    return payload


def build_publish_body(args: argparse.Namespace) -> dict[str, Any]:
    title = (args.title or "").strip()
    content = (args.content or "").strip()
    images = split_csv(args.images)

    if not title:
        raise ValueError("publish 需要 --title。")
    if not content:
        raise ValueError("publish 需要 --content。")
    if not images:
        raise ValueError("publish 需要 --images，使用英文逗号分隔图片 URL。")

    body: dict[str, Any] = {"title": title, "content": content, "images": images}
    tags = split_csv(args.tags)
    products = split_csv(args.products)
    if tags:
        body["tags"] = tags
    if products:
        body["products"] = products
    if args.is_original:
        body["is_original"] = True
    if args.visibility:
        body["visibility"] = args.visibility
    return body


def build_publish_video_body(args: argparse.Namespace) -> dict[str, Any]:
    title = (args.title or "").strip()
    content = (args.content or "").strip()
    video = (args.video or "").strip()

    if not title:
        raise ValueError("publish-video 需要 --title。")
    if not content:
        raise ValueError("publish-video 需要 --content。")
    if not video:
        raise ValueError("publish-video 需要 --video（本地绝对路径）。")

    body: dict[str, Any] = {"title": title, "content": content, "video": video}
    tags = split_csv(args.tags)
    products = split_csv(args.products)
    if tags:
        body["tags"] = tags
    if products:
        body["products"] = products
    if args.visibility:
        body["visibility"] = args.visibility
    return body


def build_feed_detail_body(args: argparse.Namespace) -> dict[str, Any]:
    feed_id = (args.feed_id or "").strip()
    xsec_token = (args.xsec_token or "").strip()
    if not feed_id:
        raise ValueError("feed-detail 需要 --feed-id。")
    if not xsec_token:
        raise ValueError("feed-detail 需要 --xsec-token。")

    body: dict[str, Any] = {"feed_id": feed_id, "xsec_token": xsec_token}
    if args.load_all_comments:
        body["load_all_comments"] = True

    comment_config: dict[str, Any] = {}
    if args.click_more_replies:
        comment_config["click_more_replies"] = True
    if args.max_replies_threshold is not None:
        comment_config["max_replies_threshold"] = args.max_replies_threshold
    if args.max_comment_items is not None:
        comment_config["max_comment_items"] = args.max_comment_items
    if args.scroll_speed:
        comment_config["scroll_speed"] = args.scroll_speed

    if comment_config:
        body["comment_config"] = comment_config
    return body


def build_user_profile_body(args: argparse.Namespace) -> dict[str, Any]:
    user_id = (args.profile_user_id or "").strip()
    xsec_token = (args.xsec_token or "").strip()
    if not user_id:
        raise ValueError("user-profile 需要 --profile-user-id。")
    if not xsec_token:
        raise ValueError("user-profile 需要 --xsec-token。")
    return {"user_id": user_id, "xsec_token": xsec_token}


def build_comment_body(args: argparse.Namespace) -> dict[str, Any]:
    feed_id = (args.feed_id or "").strip()
    xsec_token = (args.xsec_token or "").strip()
    content = (args.comment_content or args.content or "").strip()

    if not feed_id:
        raise ValueError("comment 需要 --feed-id。")
    if not xsec_token:
        raise ValueError("comment 需要 --xsec-token。")
    if not content:
        raise ValueError("comment 需要 --comment-content 或 --content。")

    return {"feed_id": feed_id, "xsec_token": xsec_token, "content": content}


def build_reply_comment_body(args: argparse.Namespace) -> dict[str, Any]:
    feed_id = (args.feed_id or "").strip()
    xsec_token = (args.xsec_token or "").strip()
    content = (args.comment_content or args.content or "").strip()
    comment_id = (args.comment_id or "").strip()
    target_user_id = (args.target_user_id or "").strip()

    if not feed_id:
        raise ValueError("comment-reply 需要 --feed-id。")
    if not xsec_token:
        raise ValueError("comment-reply 需要 --xsec-token。")
    if not content:
        raise ValueError("comment-reply 需要 --comment-content 或 --content。")
    if not comment_id and not target_user_id:
        raise ValueError("comment-reply 需要 --comment-id 或 --target-user-id 至少一个。")

    body: dict[str, Any] = {
        "feed_id": feed_id,
        "xsec_token": xsec_token,
        "content": content,
    }
    if comment_id:
        body["comment_id"] = comment_id
    if target_user_id:
        body["user_id"] = target_user_id
    return body


def build_like_feed_body(args: argparse.Namespace) -> dict[str, Any]:
    feed_id = (args.feed_id or "").strip()
    xsec_token = (args.xsec_token or "").strip()
    if not feed_id:
        raise ValueError("like-feed 需要 --feed-id。")
    if not xsec_token:
        raise ValueError("like-feed 需要 --xsec-token。")
    body: dict[str, Any] = {"feed_id": feed_id, "xsec_token": xsec_token}
    if args.unlike:
        body["unlike"] = True
    return body


def build_favorite_feed_body(args: argparse.Namespace) -> dict[str, Any]:
    feed_id = (args.feed_id or "").strip()
    xsec_token = (args.xsec_token or "").strip()
    if not feed_id:
        raise ValueError("favorite-feed 需要 --feed-id。")
    if not xsec_token:
        raise ValueError("favorite-feed 需要 --xsec-token。")
    body: dict[str, Any] = {"feed_id": feed_id, "xsec_token": xsec_token}
    if args.unfavorite:
        body["unfavorite"] = True
    return body


def build_manager_create_user_body(args: argparse.Namespace) -> dict[str, Any]:
    user_id = (args.user_id or "").strip()
    proxy = (args.proxy or "").strip()
    if not user_id:
        raise ValueError("manager-create-user 需要 --user-id。")
    if args.user_port is None:
        raise ValueError("manager-create-user 需要 --user-port。")
    return {"id": user_id, "port": args.user_port, "proxy": proxy}


def build_manager_update_user_body(args: argparse.Namespace) -> dict[str, Any]:
    if not (args.user_id or "").strip():
        raise ValueError("manager-update-user 需要 --user-id。")
    if args.user_port is None:
        raise ValueError(
            "manager-update-user 需要 --user-port；如需自定义请求体可使用 --body/--body-file。"
        )
    return {"port": args.user_port, "proxy": (args.proxy or "").strip()}


def build_search_request(
    args: argparse.Namespace,
    body: Any | None,
) -> tuple[str, dict[str, str], dict[str, Any] | None]:
    filters_from_args = pick_filters(args)

    if body is not None:
        payload = ensure_dict_body("search-feeds", body)
        keyword = (args.keyword or payload.get("keyword") or "").strip()
        if not keyword:
            raise ValueError("search-feeds 需要 keyword（可通过 --keyword 或 body.keyword 提供）。")

        filters: dict[str, Any] = {}
        raw_filters = payload.get("filters")
        if isinstance(raw_filters, dict):
            filters.update(raw_filters)
        filters.update(filters_from_args)

        post_body: dict[str, Any] = {"keyword": keyword}
        if filters:
            post_body["filters"] = filters
        return "POST", {}, validate_body("search-feeds", post_body)

    keyword = (args.keyword or "").strip()
    if not keyword:
        raise ValueError("search-feeds 需要 --keyword。")

    if filters_from_args:
        post_body = {"keyword": keyword, "filters": filters_from_args}
        return "POST", {}, validate_body("search-feeds", post_body)

    return "GET", {"keyword": keyword}, None


def build_request(
    operation: str,
    args: argparse.Namespace,
    body: Any | None,
) -> tuple[str, str, dict[str, str], dict[str, Any] | None]:
    op = CANONICAL_OPERATIONS[operation]
    method = op.method
    path = op.path
    query: dict[str, str] = {}
    payload: dict[str, Any] | None = None

    if op.needs_user_id:
        user_id = (args.user_id or "").strip()
        if not user_id:
            raise ValueError(f"{operation} 需要 --user-id。")
        path = path.replace("{user_id}", parse.quote(user_id))

    if operation == "feeds-search-get":
        keyword = (args.keyword or "").strip()
        if not keyword:
            raise ValueError("feeds-search-get 需要 --keyword。")
        query["keyword"] = keyword

    elif operation == "feeds-search-post":
        if body is None:
            keyword = (args.keyword or "").strip()
            if not keyword:
                raise ValueError("feeds-search-post 需要 --body/--body-file 或 --keyword。")
            payload = {"keyword": keyword}
            filters = pick_filters(args)
            if filters:
                payload["filters"] = filters
        else:
            payload = validate_body(operation, body)

    elif operation == "search-feeds":
        method, query, payload = build_search_request(args, body)

    elif operation == "publish":
        payload = validate_body(operation, body if body is not None else build_publish_body(args))

    elif operation == "publish-video":
        payload = validate_body(
            operation,
            body if body is not None else build_publish_video_body(args),
        )

    elif operation == "feed-detail":
        payload = validate_body(operation, body if body is not None else build_feed_detail_body(args))

    elif operation == "user-profile":
        payload = validate_body(operation, body if body is not None else build_user_profile_body(args))

    elif operation == "comment":
        payload = validate_body(operation, body if body is not None else build_comment_body(args))

    elif operation == "comment-reply":
        payload = validate_body(operation, body if body is not None else build_reply_comment_body(args))

    elif operation == "like-feed":
        payload = validate_body(operation, body if body is not None else build_like_feed_body(args))

    elif operation == "favorite-feed":
        payload = validate_body(
            operation,
            body if body is not None else build_favorite_feed_body(args),
        )

    elif operation == "manager-create-user":
        payload = validate_body(
            operation,
            body if body is not None else build_manager_create_user_body(args),
        )

    elif operation == "manager-update-user":
        payload = validate_body(
            operation,
            body if body is not None else build_manager_update_user_body(args),
        )

    return method, path, query, payload


def normalize_task_value(key: str, value: Any, source: str) -> Any:
    if key in TASK_BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "y"}:
                return True
            if normalized in {"false", "0", "no", "n"}:
                return False
        raise ValueError(f"{source} 必须是布尔值。")

    if key in TASK_INT_FIELDS:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError(f"{source} 必须是整数。")
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{source} 必须是整数。") from exc

    if key == "ip":
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{source} 必须是非空字符串。")
        return value.strip()

    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{source} 必须是字符串。")
    return value


def normalize_task_config(raw: Any, source: str) -> dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{source} 必须是 JSON 对象。")

    normalized: dict[str, Any] = {}
    for raw_key, raw_value in raw.items():
        if not isinstance(raw_key, str) or not raw_key.strip():
            raise ValueError(f"{source} 存在非法字段名。")
        key = raw_key.replace("-", "_").strip()
        if key not in TASK_CONFIG_KEYS:
            raise ValueError(f"{source} 包含不支持字段: {raw_key}")
        normalized[key] = normalize_task_value(key, raw_value, f"{source}.{raw_key}")
    return normalized


def base_task_args(cli_args: argparse.Namespace) -> dict[str, Any]:
    values = dict(TASK_OPTION_DEFAULTS)
    values.update(
        {
            "ip": cli_args.ip,
            "manager_port": cli_args.manager_port,
            "user_id": cli_args.user_id,
            "user_port": cli_args.user_port,
            "timeout": cli_args.timeout,
        }
    )
    return values


def load_task_body(task: dict[str, Any], batch_base_dir: Path, index: int) -> Any | None:
    has_body = "body" in task
    has_body_file = "body_file" in task
    if has_body and has_body_file:
        raise ValueError(f"tasks[{index}] 不能同时设置 body 和 body_file。")
    if has_body:
        return task.get("body")
    if has_body_file:
        raw_body_file = task.get("body_file")
        if not isinstance(raw_body_file, str) or not raw_body_file.strip():
            raise ValueError(f"tasks[{index}].body_file 必须是非空字符串。")
        body_path = Path(raw_body_file.strip())
        if not body_path.is_absolute():
            body_path = (batch_base_dir / body_path).resolve()
        return load_json_file(body_path, f"tasks[{index}].body_file")
    return None


def resolve_operation(operation_alias: str) -> tuple[str, Operation]:
    canonical_operation = OPERATION_ALIASES.get(operation_alias)
    if canonical_operation is None:
        raise ValueError(f"未知操作: {operation_alias}")
    operation_def = CANONICAL_OPERATIONS[canonical_operation]
    if operation_def.unsupported_reason:
        raise ValueError(
            f"操作 {operation_alias} 暂不支持：{operation_def.unsupported_reason}"
        )
    return canonical_operation, operation_def


def execute_operation(
    operation_alias: str,
    args: argparse.Namespace,
    body: Any | None,
    route_cache: dict[tuple[str, int, str | None, int | None], tuple[int, dict[str, Any]]]
    | None = None,
) -> dict[str, Any]:
    canonical_operation, operation_def = resolve_operation(operation_alias)
    if canonical_operation == "batch-run":
        raise ValueError("batch-run 不能作为子任务 operation。")

    host = normalize_host(args.ip)
    method, path, query, payload = build_request(
        operation=canonical_operation,
        args=args,
        body=body,
    )

    resolved_user: dict[str, Any] | None = None
    route_cache_hit = False

    if operation_def.scope == "manager":
        base_url = f"http://{host}:{args.manager_port}"
    elif operation_def.scope == "service":
        cache_key = (host, args.manager_port, args.user_id, args.user_port)
        if route_cache is not None and cache_key in route_cache:
            service_port, cached_user = route_cache[cache_key]
            resolved_user = dict(cached_user)
            route_cache_hit = True
        else:
            service_port, resolved = resolve_service_user(
                host=host,
                manager_port=args.manager_port,
                timeout=args.timeout,
                user_id=args.user_id,
                user_port=args.user_port,
            )
            resolved_user = dict(resolved)
            if route_cache is not None:
                route_cache[cache_key] = (service_port, dict(resolved_user))
        base_url = f"http://{host}:{service_port}"
    else:
        raise RuntimeError(f"操作 {operation_alias} 不是可执行 HTTP 操作。")

    url = build_url(base_url, path, query)
    response = http_json(url=url, method=method, timeout=args.timeout, payload=payload)

    output: dict[str, Any] = {
        "target": {
            "operation_alias": operation_alias,
            "canonical_operation": canonical_operation,
            "host": host,
            "base_url": base_url,
            "method": method,
            "path": path,
            "url": url,
        },
        "response": response,
    }
    if payload is not None:
        output["request_body"] = payload
    if resolved_user is not None:
        output["resolved_user"] = resolved_user
    if operation_def.scope == "service" and route_cache is not None:
        output["target"]["route_cache_hit"] = route_cache_hit
    return output


def execute_batch(args: argparse.Namespace) -> int:
    if not args.batch_file:
        raise ValueError("batch-run 需要 --batch-file。")
    if args.body or args.body_file:
        raise ValueError(
            "batch-run 不支持 --body/--body-file，请在批任务 JSON 中为每个任务设置 body 或 body_file。"
        )

    batch_path = Path(args.batch_file)
    if not batch_path.is_absolute():
        batch_path = (Path.cwd() / batch_path).resolve()

    batch_spec = load_json_file(batch_path, "--batch-file")
    if not isinstance(batch_spec, dict):
        raise ValueError("--batch-file 顶层必须是 JSON 对象。")

    raw_tasks = batch_spec.get("tasks")
    if not isinstance(raw_tasks, list) or len(raw_tasks) == 0:
        raise ValueError("--batch-file 必须包含非空 tasks 数组。")

    default_overrides = normalize_task_config(batch_spec.get("defaults"), "batch.defaults")
    shared_task_args = base_task_args(args)
    shared_task_args.update(default_overrides)

    route_cache: dict[tuple[str, int, str | None, int | None], tuple[int, dict[str, Any]]] = {}
    results: list[dict[str, Any]] = []

    for index, raw_task in enumerate(raw_tasks, start=1):
        task_id = f"task-{index}"
        operation_alias: str | None = None
        try:
            if not isinstance(raw_task, dict):
                raise ValueError(f"tasks[{index}] 必须是 JSON 对象。")

            raw_task_id = raw_task.get("id")
            if raw_task_id is not None:
                if not isinstance(raw_task_id, str) or not raw_task_id.strip():
                    raise ValueError(f"tasks[{index}].id 必须是非空字符串。")
                task_id = raw_task_id.strip()

            raw_operation = raw_task.get("operation")
            if not isinstance(raw_operation, str) or not raw_operation.strip():
                raise ValueError(f"tasks[{index}].operation 必须是非空字符串。")
            operation_alias = raw_operation.strip()

            task_overrides = normalize_task_config(raw_task.get("args"), f"tasks[{index}].args")
            task_args_values = dict(shared_task_args)
            task_args_values.update(task_overrides)
            task_args = argparse.Namespace(**task_args_values)

            task_body = load_task_body(raw_task, batch_path.parent, index)
            task_output = execute_operation(
                operation_alias=operation_alias,
                args=task_args,
                body=task_body,
                route_cache=route_cache,
            )
            task_output["task_id"] = task_id
            task_output["success"] = True
            results.append(task_output)
        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "task_id": task_id,
                    "operation_alias": operation_alias,
                    "success": False,
                    "error": str(exc),
                }
            )
            if args.fail_fast:
                break

    requested_total = len(raw_tasks)
    executed_total = len(results)
    success_total = sum(1 for item in results if item.get("success") is True)
    failed_total = executed_total - success_total
    skipped_total = requested_total - executed_total

    route_cache_hits = 0
    for item in results:
        if item.get("success") is True:
            target = item.get("target")
            if isinstance(target, dict) and target.get("route_cache_hit") is True:
                route_cache_hits += 1

    output: dict[str, Any] = {
        "target": {
            "operation_alias": args.operation,
            "canonical_operation": "batch-run",
            "batch_file": str(batch_path),
            "fail_fast": args.fail_fast,
        },
        "summary": {
            "requested_total": requested_total,
            "executed_total": executed_total,
            "success_total": success_total,
            "failed_total": failed_total,
            "skipped_total": skipped_total,
            "route_cache_entries": len(route_cache),
            "route_cache_hits": route_cache_hits,
        },
        "results": results,
    }

    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if failed_total == 0 else 1


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "xiaohongshu-mcp API CLI（支持多用户自动端口解析，兼容 XiaohongshuSkills 命名）"
        )
    )
    parser.add_argument(
        "operation",
        choices=sorted(OPERATION_ALIASES.keys()),
        help="要执行的操作名（支持别名，含 batch-run）",
    )

    parser.add_argument("--ip", required=True, help="服务 IP 或域名（用户仅需提供此项）")
    parser.add_argument(
        "--manager-port",
        type=int,
        default=DEFAULT_MANAGER_PORT,
        help="管理器端口，默认 18050",
    )
    parser.add_argument("--user-id", help="目标用户 ID（用于 manager-user 或路由到指定用户）")
    parser.add_argument("--user-port", type=int, help="直接指定业务端口（可选）")
    parser.add_argument("--proxy", help="账号代理地址（用于 add-account / edit-account）")

    parser.add_argument("--keyword", help="搜索关键词")
    parser.add_argument("--sort-by", help="搜索排序，如 综合/最新/最多点赞")
    parser.add_argument("--note-type", help="笔记类型，如 不限/视频/图文")
    parser.add_argument("--publish-time", help="发布时间筛选，如 不限/一天内/一周内")
    parser.add_argument("--search-scope", help="搜索范围，如 不限/已看过/未看过")
    parser.add_argument("--location", help="位置筛选，如 不限/同城/附近")

    parser.add_argument("--title", help="标题")
    parser.add_argument("--content", help="正文内容")
    parser.add_argument("--images", help="图片 URL 列表，英文逗号分隔")
    parser.add_argument("--video", help="本地视频绝对路径")
    parser.add_argument("--tags", help="标签列表，英文逗号分隔")
    parser.add_argument("--products", help="商品 ID 列表，英文逗号分隔")
    parser.add_argument("--visibility", help="可见范围")
    parser.add_argument("--is-original", action="store_true", help="发布图文时声明原创")

    parser.add_argument("--feed-id", help="帖子 ID")
    parser.add_argument("--xsec-token", help="xsec_token")
    parser.add_argument("--comment-id", help="评论 ID")
    parser.add_argument("--target-user-id", help="回复目标用户 ID（对应 user_id）")
    parser.add_argument("--comment-content", help="评论/回复内容")
    parser.add_argument("--unlike", action="store_true", help="点赞接口中执行取消点赞")
    parser.add_argument("--unfavorite", action="store_true", help="收藏接口中执行取消收藏")
    parser.add_argument("--profile-user-id", help="用户主页查询用 user_id")

    parser.add_argument("--load-all-comments", action="store_true", help="加载全部评论")
    parser.add_argument("--click-more-replies", action="store_true", help="展开更多回复")
    parser.add_argument("--max-replies-threshold", type=int, help="更多回复最大阈值")
    parser.add_argument("--max-comment-items", type=int, help="最大加载评论数")
    parser.add_argument(
        "--scroll-speed",
        choices=["slow", "normal", "fast"],
        help="评论加载滚动速度",
    )

    parser.add_argument("--body", help="JSON 字符串请求体")
    parser.add_argument("--body-file", help="JSON 文件请求体")
    parser.add_argument("--batch-file", help="batch-run 模式下的任务 JSON 文件")
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="batch-run 模式下遇到失败即停止后续任务",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="HTTP 超时秒数，默认 60",
    )
    return parser


def main() -> int:
    parser = create_parser()
    args = parser.parse_args()

    try:
        canonical_operation = OPERATION_ALIASES[args.operation]
        if canonical_operation == "batch-run":
            return execute_batch(args)

        body = load_body(args.body, args.body_file)
        output = execute_operation(
            operation_alias=args.operation,
            args=args,
            body=body,
            route_cache=None,
        )
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001
        print(
            json.dumps({"success": False, "error": str(exc)}, ensure_ascii=False, indent=2),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())

