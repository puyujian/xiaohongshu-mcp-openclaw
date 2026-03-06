# 能力映射（XiaohongshuSkills -> xiaohongshu-mcp API）

## 已适配能力

1. 登录状态检查
- 外部能力：`check-login`、`check-home-login`、`check-login-status`
- 适配命令：`check-login` / `check-home-login` / `check-login-status` / `login-status`
- API：`GET /api/v1/login/status`

2. 登录二维码
- 外部能力：`login`、`get-login-qrcode`
- 适配命令：`login` / `get-login-qrcode` / `login-qrcode`
- API：`GET /api/v1/login/qrcode`

3. 重置登录
- 外部能力：`re-login`、`delete-login-cookies`
- 适配命令：`re-login` / `delete-login-cookies` / `login-reset-cookies`
- API：`DELETE /api/v1/login/cookies`

4. 发布图文
- 外部能力：`publish-to-xiaohongshu`
- 适配命令：`publish-to-xiaohongshu` / `publish`
- API：`POST /api/v1/publish`

5. 发布视频
- 外部能力：`publish-video-to-xiaohongshu`
- 适配命令：`publish-video-to-xiaohongshu` / `publish-video`
- API：`POST /api/v1/publish_video`

6. 获取 Feed 列表
- 外部能力：`list-feeds`
- 适配命令：`list-feeds` / `feeds-list`
- API：`GET /api/v1/feeds/list`

7. 搜索 Feed
- 外部能力：`search-feeds`
- 适配命令：`search-feeds`（自动 GET/POST）
- API：`GET/POST /api/v1/feeds/search`

8. Feed 详情
- 外部能力：`get-feed-detail`
- 适配命令：`get-feed-detail` / `feed-detail`
- API：`POST /api/v1/feeds/detail`

9. 评论
- 外部能力：`post-comment-to-feed`
- 适配命令：`post-comment-to-feed` / `comment`
- API：`POST /api/v1/feeds/comment`

10. 回复评论
- 外部能力：`reply-comment-to-feed`
- 适配命令：`reply-comment-to-feed` / `comment-reply`
- API：`POST /api/v1/feeds/comment/reply`

11. 点赞/取消点赞
- 外部能力：`like_feed`
- 适配命令：`like_feed` / `like-feed`
- API：`POST /api/v1/feeds/like`

12. 收藏/取消收藏
- 外部能力：`favorite_feed`
- 适配命令：`favorite_feed` / `favorite-feed`
- API：`POST /api/v1/feeds/favorite`

13. 用户主页
- 外部能力：`get-user-profile`
- 适配命令：`get-user-profile` / `user-profile`
- API：`POST /api/v1/user/profile`

14. 我的主页
- 外部能力：`get-my-profile`
- 适配命令：`get-my-profile` / `user-me`
- API：`GET /api/v1/user/me`

15. 多用户管理（增强）
- 外部能力：`list-accounts`
- 适配命令：`list-accounts` / `manager-list-users` / `manager-get-user`
- API：`GET /api/manager/v1/users`、`GET /api/manager/v1/users/{id}`
- 增强点：用户仅传 IP，自动通过管理器解析实例端口。

16. 账号增删改
- 外部能力：`add-account`、`edit-account`、`remove-account`
- 适配命令：`add-account` / `edit-account` / `remove-account` / `manager-create-user` / `manager-update-user` / `manager-delete-user`
- API：`POST /api/admin/v1/users`、`PUT /api/admin/v1/users/{id}`、`DELETE /api/admin/v1/users/{id}`
- 增强点：复用 `--user-id`、`--user-port`、`--proxy` 直接构造管理器写操作请求。

17. 批量任务执行（本地聚合）
- 外部能力：批量小红书任务拆解执行
- 适配命令：`batch-run` / `batch`
- API：本地聚合能力（内部仍调用上述 API）
- 增强点：单次 CLI 调用执行多任务，复用用户路由并输出汇总，降低 token/请求开销。

## 暂不支持（当前 API 文档未提供）

1. 浏览器级 CDP 调试/发布脚本（如 test-publish、cdp_publish）
- 原因：当前适配层基于 HTTP API，不直接控制浏览器实例。

2. `content-data` 类数据集工具
- 原因：`docs/API.md` 未定义对应端点。
 - 行为：命令可识别，执行时返回明确错误提示。

3. `notifications/mentions` 提及列表
- 原因：`docs/API.md` 未定义对应端点。
 - 行为：命令可识别（`get-notification-mentions`），执行时返回明确错误提示。

4. 账号切换
- 原因：`docs/API.md` 未定义对应端点。
- 行为：命令可识别（`switch-account`），执行时返回明确错误提示。

## 设计原则

1. 优先复用外部项目命令名，降低迁移成本。
2. 通过命令别名兼容旧调用。
3. 在多用户场景默认自动路由，减少使用复杂度。

