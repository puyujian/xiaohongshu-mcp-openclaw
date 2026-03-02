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


@dataclass(frozen=True)
class Operation:
    method: str
    path: str
    scope: str  # manager | service
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
    "user-profile": Operation("POST", "/api/v1/user/profile", "service"),
    "user-me": Operation("GET", "/api/v1/user/me", "service"),
    "comment": Operation("POST", "/api/v1/feeds/comment", "service"),
    "comment-reply": Operation("POST", "/api/v1/feeds/comment/reply", "service"),
    "manager-users": Operation("GET", "/api/manager/v1/users", "manager"),
    "manager-user": Operation(
        "GET", "/api/manager/v1/users/{user_id}", "manager", needs_user_id=True
    ),
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
    "user-profile": "user-profile",
    "user-me": "user-me",
    "comment": "comment",
    "comment-reply": "comment-reply",
    "manager-users": "manager-users",
    "manager-user": "manager-user",
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
    "get-user-profile": "user-profile",
    "get-my-profile": "user-me",
    "list-accounts": "manager-users",
    "add-account": "not-supported",
    "remove-account": "not-supported",
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


def load_body(body: str | None, body_file: str | None) -> Any | None:
    if body and body_file:
        raise ValueError("--body 和 --body-file 不能同时使用。")
    if body:
        try:
            return json.loads(body)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--body 不是合法 JSON: {exc}") from exc
    if body_file:
        content = Path(body_file).read_text(encoding="utf-8")
        try:
            return json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"--body-file 内容不是合法 JSON: {exc}") from exc
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

    if operation == "manager-user":
        if not args.user_id:
            raise ValueError("manager-user 需要 --user-id。")
        path = path.replace("{user_id}", parse.quote(args.user_id))

    elif operation == "feeds-search-get":
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

    return method, path, query, payload


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "xiaohongshu-mcp API CLI（支持多用户自动端口解析，兼容 XiaohongshuSkills 命名）"
        )
    )
    parser.add_argument(
        "operation",
        choices=sorted(OPERATION_ALIASES.keys()),
        help="要执行的操作名（支持别名）",
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
        operation_def = CANONICAL_OPERATIONS[canonical_operation]
        body = load_body(args.body, args.body_file)

        if operation_def.unsupported_reason:
            raise ValueError(
                f"操作 {args.operation} 暂不支持：{operation_def.unsupported_reason}"
            )

        host = normalize_host(args.ip)

        method, path, query, payload = build_request(
            operation=canonical_operation,
            args=args,
            body=body,
        )

        resolved_user: dict[str, Any] | None = None
        if operation_def.scope == "manager":
            base_url = f"http://{host}:{args.manager_port}"
        else:
            service_port, resolved_user = resolve_service_user(
                host=host,
                manager_port=args.manager_port,
                timeout=args.timeout,
                user_id=args.user_id,
                user_port=args.user_port,
            )
            base_url = f"http://{host}:{service_port}"

        url = build_url(base_url, path, query)
        response = http_json(url=url, method=method, timeout=args.timeout, payload=payload)

        output: dict[str, Any] = {
            "target": {
                "operation_alias": args.operation,
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
