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

## 批量执行（降 token）

1. 当用户一次提出 >=2 个彼此独立的小红书任务时，优先使用 `batch-run`，避免逐条重复调用。
2. 将共同参数放入 `defaults`：`ip`、`manager_port`、`user_id`、`user_port`、`timeout`。
3. 每个子任务写入 `tasks[]`：
   - `operation`：命令别名（如 `search-feeds`、`like_feed`）。
   - `args`：该子任务特有参数（支持 `-` 或 `_` 命名）。
   - `body` 或 `body_file`：复杂请求体。
4. 默认批任务会继续执行并汇总失败项；需要失败即停时加 `--fail-fast`。
5. 若多个子任务共用同一用户路由，脚本会自动复用解析结果，减少重复请求。

### 批量调用模板

```bash
python "{baseDir}/scripts/xhs_api_client.py" --ip 192.168.1.8 batch-run \
  --batch-file "{baseDir}/examples/batch_tasks.json"
```

## OpenClaw 执行决策（强约束）

1. 先做任务拆解：把用户请求拆成最小原子任务（一个任务对应一个 operation）。
2. 决策规则：
   - 仅 1 个任务：允许单命令调用。
   - >=2 个且互不依赖：必须使用 `batch-run`，禁止逐条单独调用。
   - 存在依赖链（A→B→C）：按阶段执行；每个阶段内部能并行的任务仍必须用 `batch-run`。
3. 组包规则：
   - 把重复参数放进 `defaults`（如 `ip/user_id/timeout`）。
   - 每个 `tasks[i].args` 仅保留差异参数。
   - 复杂请求优先使用 `body_file`，避免长 JSON 内联导致 token 增长。
4. 执行与回传：
   - 默认不使用 `--fail-fast`，先拿完整汇总；除非用户明确要求失败即停。
   - 优先读取 `summary.failed_total` 与 `results[].task_id` 输出失败清单。
   - 成功任务若包含 `resolved_user`，后续阶段沿用该上下文。
5. 禁止事项：
   - 在可批量场景下，禁止“同一轮多次调用 `xhs_api_client.py` 单任务命令”。
   - 禁止在 `batch-run` 外层使用 `--body` / `--body-file`。

### 批量文件最小模板

```json
{
  "defaults": {
    "user_id": "user1",
    "timeout": 60
  },
  "tasks": [
    {
      "id": "t1",
      "operation": "search-feeds",
      "args": {
        "keyword": "露营"
      }
    },
    {
      "id": "t2",
      "operation": "like_feed",
      "body_file": "like_body.json"
    }
  ]
}
```

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
- `like_feed`
- `favorite_feed`
- `like-feed`
- `favorite-feed`
- `get-user-profile`
- `get-my-profile`
- `get-notification-mentions`
- `list-accounts`
- `add-account`
- `edit-account`
- `remove-account`
- `switch-account`（会返回“API 暂不支持”）
- `content-data`（会返回“API 暂不支持”）
- `manager-list-users`
- `manager-get-user`
- `manager-create-user`
- `manager-update-user`
- `manager-delete-user`
- `batch-run`（批量执行）

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

# 7) 点赞/取消点赞
python "{baseDir}/scripts/xhs_api_client.py" --ip 192.168.1.8 like_feed \
  --feed-id "64f1a2..." --xsec-token "token_here"
python "{baseDir}/scripts/xhs_api_client.py" --ip 192.168.1.8 like_feed \
  --feed-id "64f1a2..." --xsec-token "token_here" --unlike

# 8) 收藏/取消收藏
python "{baseDir}/scripts/xhs_api_client.py" --ip 192.168.1.8 favorite_feed \
  --feed-id "64f1a2..." --xsec-token "token_here"
python "{baseDir}/scripts/xhs_api_client.py" --ip 192.168.1.8 favorite_feed \
  --feed-id "64f1a2..." --xsec-token "token_here" --unfavorite
```

## 能力边界

- 本 Skill 基于 HTTP API，不含浏览器 CDP 调试类命令。
- `content-data`、`notifications/mentions`、账号新增/删除/切换 在当前 API 文档中未提供端点，调用时会返回明确错误提示。
- 详细映射见：`{baseDir}/CAPABILITY_MAP.md`。

