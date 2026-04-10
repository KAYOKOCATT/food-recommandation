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

### 当前约束

- 中文菜品没有真实用户行为数据；收藏协同过滤只使用模拟隐式反馈做功能演示。
- `collect_count/comment_count` 是爬取初始数 + 系统内新增行为的混合统计数，不作为真实推荐评估指标。
- Yelp 餐厅数据可做内容推荐和基于 review 的 UserCF/ItemCF。
- 不引入 Redis；先用离线文件/数据库 + Python 内存缓存。
- 不继续扩大 Alpine/HTMX 前端架构，后续重点是核心数据处理和推荐算法。

### 下一步

1. 把已完成的 Yelp TF-IDF notebook 逻辑沉淀为可重复运行的离线脚本，输出餐厅相似度 JSON。
2. 基于 Yelp review 评分构造 user-business 矩阵，实现 ItemCF 和 UserCF 的 Top-K 召回。
3. 在 Django 页面中增加中文菜品推荐展示入口，接入 `food_itemcf.json` 或 `food_usercf.json`。
4. 在列表页/详情页展示 `collect_count/comment_count`，让热门排序依据可见。
5. 补登录、注册、收藏、评论、ItemCF/UserCF 和推荐重排的自动化测试。
