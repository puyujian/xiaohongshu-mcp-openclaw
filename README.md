# xiaohongshu-mcp OpenClaw Skills（对齐 XiaohongshuSkills）

本目录在你原有 API 基础上，适配了 `white0dew/XiaohongshuSkills` 的命名与使用习惯。

## 目标

- 保持 `XiaohongshuSkills` 的能力风格。
- 调用入口统一改为你的 `xiaohongshu-mcp` HTTP API。
- 适配多用户场景，用户只需提供 `IP`。

## 目录结构

```text
xiaohongshu-mcp-openclaw/
├── CAPABILITY_MAP.md
├── SKILL.md
├── README.md
├── examples/
│   ├── comment_body.json
│   ├── favorite_body.json
│   ├── feed_detail_body.json
│   ├── like_body.json
│   ├── publish_body.json
│   ├── publish_video_body.json
│   ├── reply_comment_body.json
│   ├── search_body.json
│   ├── user_profile_body.json
│   └── batch_tasks.json
└── scripts/
    └── xhs_api_client.py
```

## 快速开始

```bash
# 1) 列出多用户状态
python scripts/xhs_api_client.py --ip 127.0.0.1 manager-list-users

# 2) 自动选健康用户并检查登录
python scripts/xhs_api_client.py --ip 127.0.0.1 check-login-status

# 3) 指定 user_id 查询 feeds
python scripts/xhs_api_client.py --ip 127.0.0.1 --user-id user1 list-feeds
```

## 已兼容的命令别名（XiaohongshuSkills 风格）

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
- `like_feed`
- `favorite_feed`
- `like-feed`
- `favorite-feed`
- `get-user-profile`
- `get-my-profile`
- `list-accounts`
- `manager-list-users`
- `manager-get-user`
- `batch-run`（批量执行）

也保留了旧命名（如 `login-status`、`feeds-list`、`comment`）以兼容已有调用。

以下同名命令也已接入，但会返回明确的“不支持”错误（因为 API 无对应端点）：

- `add-account`
- `remove-account`
- `switch-account`
- `content-data`
- `get-notification-mentions`

## 命令示例

```bash
# 发布图文（无需 body 文件）
python scripts/xhs_api_client.py --ip 127.0.0.1 publish-to-xiaohongshu \
  --title "露营日记" \
  --content "周末露营体验分享" \
  --images "http://example.com/1.jpg,http://example.com/2.jpg" \
  --tags "露营,户外" \
  --visibility "公开可见"

# 发布视频
python scripts/xhs_api_client.py --ip 127.0.0.1 publish-video-to-xiaohongshu \
  --title "露营Vlog" \
  --content "搭帐篷到篝火全记录" \
  --video "/absolute/path/demo.mp4"

# 自动搜索（无筛选走 GET，有筛选走 POST）
python scripts/xhs_api_client.py --ip 127.0.0.1 search-feeds --keyword "露营"
python scripts/xhs_api_client.py --ip 127.0.0.1 search-feeds --keyword "露营" --sort-by "最新" --note-type "图文"

# 评论与回复（需要 xsec_token）
python scripts/xhs_api_client.py --ip 127.0.0.1 post-comment-to-feed \
  --feed-id "64f1a2..." --xsec-token "token_here" --comment-content "写得真好"

python scripts/xhs_api_client.py --ip 127.0.0.1 reply-comment-to-feed \
  --feed-id "64f1a2..." --xsec-token "token_here" --comment-id "comment_id" --comment-content "谢谢"

# 点赞与取消点赞
python scripts/xhs_api_client.py --ip 127.0.0.1 like_feed \
  --feed-id "64f1a2..." --xsec-token "token_here"
python scripts/xhs_api_client.py --ip 127.0.0.1 like_feed \
  --feed-id "64f1a2..." --xsec-token "token_here" --unlike

# 收藏与取消收藏
python scripts/xhs_api_client.py --ip 127.0.0.1 favorite_feed \
  --feed-id "64f1a2..." --xsec-token "token_here"
python scripts/xhs_api_client.py --ip 127.0.0.1 favorite_feed \
  --feed-id "64f1a2..." --xsec-token "token_here" --unfavorite
```

## OpenClaw 推荐流程

1. 将用户请求先拆成原子任务。
2. 若同一轮存在 >=2 个无依赖任务，优先合并到一个 `batch-run` 调用。
3. 若有依赖链，按阶段执行；每个阶段内部仍尽量合并为单次 `batch-run`。
4. 把重复参数放到 `defaults`，只在 `tasks[].args` 传差异参数。

这个流程可以显著减少多轮上下文重复与命令重复带来的 token 消耗。

## 批量任务（降低 token 消耗）

当一次有多个独立任务时，建议改用单次 `batch-run`，避免多轮重复请求。

```bash
python scripts/xhs_api_client.py --ip 127.0.0.1 batch-run \
  --batch-file examples/batch_tasks.json
```

批任务文件结构示例：

```json
{
  "defaults": {
    "user_id": "user1"
  },
  "tasks": [
    {"id": "search-1", "operation": "search-feeds", "args": {"keyword": "露营"}},
    {"id": "like-1", "operation": "like_feed", "body_file": "like_body.json"}
  ]
}
```

说明：
- `defaults`：批次共享参数，减少重复传参。
- `tasks[].args`：子任务参数，键名支持 `-` / `_`。
- `tasks[].body` / `tasks[].body_file`：复杂请求体。
- 可选 `--fail-fast`：遇错立即停止，默认继续执行并汇总结果。

## 参数说明（重点）

- `--ip`：必填，用户只需提供此项。
- `--manager-port`：可选，默认 `18050`。
- `--user-id`：可选，指定用户实例。
- `--user-port`：可选，手动指定业务端口，优先级最高。
- `--body` / `--body-file`：用于单任务复杂 JSON 请求。
- `--batch-file`：批量模式任务文件（仅 `batch-run` 使用）。
- `--fail-fast`：批量模式失败即停（默认不中断）。

## 能力映射

请看 `CAPABILITY_MAP.md`，包含：

- 已适配能力（登录/发布/搜索/详情/评论/用户/多用户）。
- API 暂不支持能力（如 CDP 调试类、content-data、mentions、账号增删切换）。

