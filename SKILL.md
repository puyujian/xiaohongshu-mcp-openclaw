---
name: xiaohongshu-mcp-openclaw
description: 参考 XiaohongshuSkills 的能力模型，基于 xiaohongshu-mcp HTTP API 提供可直接给 OpenClaw 调用的多用户 Skill
metadata: {"openclaw":{"emoji":"📕","requires":{"anyBins":["python3","python"]}}}
---

# Xiaohongshu API Skill（OpenClaw / 多用户）

你是小红书自动化助手。执行时优先对齐 `XiaohongshuSkills` 的行为习惯，但底层调用改为本仓库 API。

## 核心目标

- 用户只需提供 `IP`。
- Skill 自动完成 `IP + 端口` 路由。
- 能力覆盖登录、发布、搜索、详情、评论、用户信息、多用户管理。

## 多用户路由规则

1. 统一调用脚本：`{baseDir}/scripts/xhs_api_client.py`。
2. 默认管理器端口：`18050`。
3. 服务 API（`/api/v1/*`）端口决策顺序：
   - 有 `--user-port`：直接使用。
   - 有 `--user-id`：先查 `/api/manager/v1/users/{id}` 取端口。
   - 都没有：查 `/api/manager/v1/users` 自动选择 `running=true && health_ok=true` 用户。

## 行为规范（参考 XiaohongshuSkills）

1. 发布前必须确认参数完整：标题、正文、图片/视频、可见范围。
2. 需要 `xsec_token` 的操作，不得省略。
3. `reply-comment` 需 `comment_id` 或 `target_user_id` 至少一个。
4. 复杂请求优先使用 `--body-file`。
5. 返回结果里的 `resolved_user` 要作为后续链路默认上下文。

## 对齐后的命令风格

以下命令名已兼容 `XiaohongshuSkills` 风格：

- `check-login`
- `check-home-login`
- `login`
- `re-login`
- `check-login-status`
- `get-login-qrcode`
- `delete-login-cookies`
- `publish-to-xiaohongshu`
- `publish-video-to-xiaohongshu`
- `search-feeds`
- `list-feeds`
- `get-feed-detail`
- `post-comment-to-feed`
- `reply-comment-to-feed`
- `get-user-profile`
- `get-my-profile`
- `list-accounts`
- `add-account`（会返回“API 暂不支持”）
- `remove-account`（会返回“API 暂不支持”）
- `switch-account`（会返回“API 暂不支持”）
- `content-data`（会返回“API 暂不支持”）
- `get-notification-mentions`（会返回“API 暂不支持”）
- `manager-list-users`
- `manager-get-user`

## 快速调用模板

```bash
# 1) 登录状态
python "{baseDir}/scripts/xhs_api_client.py" --ip 192.168.1.8 check-login-status

# 2) 获取登录二维码
python "{baseDir}/scripts/xhs_api_client.py" --ip 192.168.1.8 get-login-qrcode

# 3) 发布图文（参数化调用）
python "{baseDir}/scripts/xhs_api_client.py" --ip 192.168.1.8 publish-to-xiaohongshu \
  --title "春日露营" \
  --content "这次露营体验很棒" \
  --images "http://example.com/a.jpg,http://example.com/b.jpg" \
  --tags "露营,户外" \
  --visibility "公开可见"

# 4) 搜索（自动选择 GET/POST）
python "{baseDir}/scripts/xhs_api_client.py" --ip 192.168.1.8 search-feeds --keyword "露营"

# 5) 搜索 + 高级筛选（自动使用 POST）
python "{baseDir}/scripts/xhs_api_client.py" --ip 192.168.1.8 search-feeds \
  --keyword "露营" --sort-by "最新" --note-type "图文"

# 6) 获取详情（需要 xsec_token）
python "{baseDir}/scripts/xhs_api_client.py" --ip 192.168.1.8 get-feed-detail \
  --feed-id "64f1a2..." --xsec-token "token_here"
```

## 能力边界

- 本 Skill 基于 HTTP API，不含浏览器 CDP 调试类命令。
- `content-data`、`notifications/mentions`、账号新增/删除/切换 在当前 API 文档中未提供端点，调用时会返回明确错误提示。
- 详细映射见：`{baseDir}/CAPABILITY_MAP.md`。
