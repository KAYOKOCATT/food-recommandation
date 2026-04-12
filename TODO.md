## 当前实施进度

### 已完成

- Django 5.2 项目结构。
- 用户注册、登录、会话、退出。
- 菜品列表、详情、收藏、评论的基础页面和接口。
- 中文菜品爬虫与 CSV 导入脚本。
- Yelp 数据集探索 notebook，内容推荐实验已具备参考基础。
- mypy、pylint、djlint 项目级配置。
- 离线相似度文件的进程内缓存与最近行为重排服务骨架。
- 中文菜品收藏 0/1 矩阵的 ItemCF/UserCF 算法模块。
- 演示收藏数据生成命令和中文菜品协同过滤离线 JSON 生成命令。
- 菜品表统计字段：`collect_count`、`comment_count`，用于热门排序和展示。
- Yelp TF-IDF 内容推荐离线脚本，输出相似餐厅 JSON 和餐厅元数据 JSON。
- Yelp 数据模型：`YelpBusiness`、`YelpReview` 已加入 ORM。
- `users.User` 已扩展 `source`、`external_user_id`，用于兼容 Yelp 导入用户。
- Yelp 独立导入命令 `import_yelp_data` 已支持商家、用户、评论分阶段入库。
- Yelp Web 页面已接入列表页、详情页和基于 `yelp_content_itemcf.json` 的相似餐厅推荐。

### 当前约束

- 中文菜品没有真实用户行为数据；收藏协同过滤只使用模拟隐式反馈做功能演示。
- `collect_count/comment_count` 是爬取初始数 + 系统内新增行为的混合统计数，不作为真实推荐评估指标。
- Yelp 餐厅数据可做内容推荐和基于 review 的 UserCF/ItemCF。
- 不引入 Redis；先用离线文件/数据库 + Python 内存缓存。
- 不继续扩大 Alpine/HTMX 前端架构，后续重点是核心数据处理和推荐算法。

### 下一步

1. Phase 2 收尾：将 Yelp 图表数据源逐步从 JSON 文件读取迁移到 ORM 查询，减少双数据源维护成本。
2. Phase 2 收尾：补充 Yelp 页面筛选、分页边界和导入命令的更多自动化测试。
3. Phase 3：基于 Yelp review 评分构造 user-business 矩阵，实现 ItemCF 和 UserCF 的 Top-K 召回。
4. Phase 3：决定 Yelp 用户行为是否接入收藏、浏览历史或评分重排，再开放“为你推荐”入口。
5. 中文菜品侧：继续补列表页/详情页统计展示与登录、注册、收藏、评论、推荐重排的回归测试。
