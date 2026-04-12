# 餐饮个性化推荐系统

## 当前状态

这是一个早期 Django 毕设项目，当前已具备：

- Django 5.2 项目结构，包含用户、菜品、推荐三个业务 app。
- MySQL 业务库配置，支持用户注册/登录、菜品列表、菜品详情、收藏、评论。
- 中文菜品爬取与 CSV 导入脚本。
- Yelp 数据集探索 notebook，已验证内容推荐实验方向，并已完成基础 ORM 落库与 Web 接入。
- mypy、pylint、djlint 的项目级配置。

当前路线是：中文菜品做统计推荐和演示型收藏协同过滤，Yelp 餐厅做内容推荐和邻域协同过滤，实时推荐只做基于最近行为的离线候选重排。Yelp v1 已支持独立数据入库、餐厅列表/详情页，以及基于离线内容相似度的相似餐厅展示。

## 技术栈

| 层级 | 技术选型 | 说明 |
| --- | --- | --- |
| 后端框架 | Django 5.2 | 模板渲染 + 后端业务逻辑 |
| 数据库 | MySQL 8.0 | 用户、菜品、收藏、评论等业务数据 |
| 数据处理 | Pandas + NumPy | 离线数据处理与特征工程 |
| 算法库 | scikit-learn | TF-IDF、相似度计算、邻域推荐 |
| 前端 | HTML/CSS/JavaScript + jQuery | 主要沿用管理后台静态模板 |
| 可选前端增强 | Alpine.js + HTMX | 目前主要用于登录/注册页，不作为后续核心投入 |

不引入 Redis。离线推荐结果或相似度表优先保存为文件或落库，运行时用 Python 进程内缓存读取。

## 当前数据模型

- `apps.users.models.User`：系统统一用户表。本地注册用户继续使用原流程，Yelp 导入用户通过 `source`、`external_user_id` 兼容，不单独维护第二套用户主表。
- `apps.foods.models.Foods` / `Collect` / `Comment`：中文菜品与行为数据。
- `apps.recommendations.models.YelpBusiness`：Yelp 餐厅主表，保存 `business_id`、名称、分类、评分、评论数、城市、州、经纬度、营业状态等。
- `apps.recommendations.models.YelpReview`：Yelp 评论表，关联 `YelpBusiness` 和扩展后的 `User`。

## 架构图

### 总体架构

```text
                    +----------------------+
                    |      Django Web      |
                    | templates + views    |
                    +----------+-----------+
                               |
             +-----------------+-----------------+
             |                                   |
             v                                   v
  +--------------------------+       +--------------------------+
  | 中文菜品业务链路         |       | Yelp 餐厅业务链路        |
  | apps.foods               |       | apps.recommendations     |
  +------------+-------------+       +------------+-------------+
               |                                      |
               v                                      v
  +--------------------------+       +--------------------------+
  | MySQL: Foods/Collect/... |       | MySQL: YelpBusiness/     |
  | + users.User(local)      |       | YelpReview + users.User  |
  +------------+-------------+       +------------+-------------+
               |                                      |
               v                                      v
  +--------------------------+       +--------------------------+
  | food_itemcf.json         |       | yelp_content_itemcf.json |
  | food_usercf.json         |       | (offline candidates)     |
  +--------------------------+       +--------------------------+
```

### 中文菜品推荐链路

```text
food.csv / 爬虫数据
        |
        v
get_data/csvtosql.py
        |
        v
MySQL: Foods
        |
        +------------------------------+
        |                              |
        v                              v
用户收藏/评论                    build_food_collect_cf
Collect / Comment                     |
        |                              v
        +--------------------> food_itemcf.json / food_usercf.json
                                       |
                                       v
apps.foods.services + similarity_cache
                                       |
                                       v
菜品列表页 / 详情页 / UserCF 推荐页
```

### Yelp 餐厅推荐链路

```text
Yelp 原始数据
(business / user / review json)
        |
        v
import_yelp_data
        |
        v
MySQL: YelpBusiness / YelpReview / users.User(source=yelp)
        |
        +------------------------------+
        |                              |
        v                              v
餐厅列表 / 详情 ORM 查询         build_yelp_content_recs
        |                              |
        |                              v
        |                      yelp_content_itemcf.json
        |                              |
        +------------------------------+
                       |
                       v
apps.recommendations.services.YelpService
                       |
                       v
Yelp 餐厅列表页 / 餐厅详情页 / 相似餐厅推荐
```

### 图表与推荐支撑链路

```text
MySQL 业务表 + Yelp 离线相似度文件
          |
          v
apps.recommendations.services
  - ChartService
  - similarity_cache
  - YelpService
          |
          v
apps.recommendations.views
  - /api/v1/charts/*
  - /api/v1/yelp/restaurants/*
          |
          v
Dashboard / Yelp 页面 / 推荐页面
```

## 推荐分层

1. 中文菜品统计推荐：基于已有菜品表、收藏数、评论数、菜系、价格等粗粒度信息生成榜单。
2. 中文菜品收藏协同过滤：基于 `Collect(user_id, food_id)` 生成 0/1 隐式反馈矩阵，实现演示型 ItemCF/UserCF。收藏数据可以用命令生成，但必须标注为模拟数据，不作为真实效果评估依据。
3. Yelp 餐厅内容推荐：基于 business/categories/review/tip 等文本和属性做 TF-IDF 特征，离线生成相似餐厅。
4. Yelp 餐厅协同过滤：基于 review 评分构造 user-business 矩阵，实现 UserCF/ItemCF 这类邻域算法，不把矩阵分解作为 v1 主线。
5. 实时重排：根据用户最近浏览、收藏或评分，读取离线相似度候选，用简单权重合并和过滤，不在线训练模型。

运行时数据边界：

- `YelpBusiness` / `YelpReview` 负责 Yelp 页面展示、图表统计、地理分布等 ORM 查询。
- `data/recommendations/yelp_content_itemcf.json` 只负责离线相似餐厅候选。
- `data/recommendations/yelp_business_profiles.json` 仅保留为离线构建的调试/检查产物，不作为页面或图表运行时依赖。

当前已提供 `apps.recommendations.services.rerank_from_recent_items`，可读取 JSON 格式的离线相似度文件并做最近行为重排。

支持的 JSON 示例：

```json
{
  "business_1": [
    {"business_id": "business_2", "score": 0.91},
    {"business_id": "business_3", "score": 0.72}
  ],
  "business_2": ["business_4", "business_5"]
}
```

中文菜品收藏协同过滤命令：

```bash
# 只预览会生成多少条模拟收藏，不写库
python manage.py generate_demo_collects --dry-run

# 写入演示收藏数据。该数据是 synthetic implicit feedback，不是真实行为。
python manage.py generate_demo_collects --per-user 8 --seed 20260410

# 从 Collect 表生成 ItemCF/UserCF 离线 JSON
python manage.py build_food_collect_cf --algorithm both --top-k 20
```

默认输出：

- `data/recommendations/food_itemcf.json`：菜品到相似菜品。
- `data/recommendations/food_usercf.json`：用户到候选菜品。

Yelp 餐厅内容推荐命令：

```bash
# 开发验证：限制商家和 review 扫描量，先确认产物结构
python manage.py build_yelp_content_recs --business-limit 1000 --review-line-limit 50000 --top-k 10

# 完整离线构建：默认扫描完整 business/review 文件，每家餐厅最多聚合 50 条 review
python manage.py build_yelp_content_recs --top-k 20

# 如需不限制每家餐厅聚合 review 数量，传 0；运行会更慢且更吃内存
python manage.py build_yelp_content_recs --max-reviews-per-business 0
```

默认输出：

- `data/recommendations/yelp_content_itemcf.json`：Yelp 餐厅到相似餐厅的 TF-IDF 内容相似度。
- `data/recommendations/yelp_business_profiles.json`：参与构建的 Yelp 餐厅元数据和聚合 review 数。

Yelp 数据入库命令：

```bash
# 只导入餐厅主数据
python manage.py import_yelp_data --mode businesses --data-dir data/archive_4

# 只导入 Yelp 用户
python manage.py import_yelp_data --mode users --data-dir data/archive_4

# 只导入评论（需要先有 businesses 和 users）
python manage.py import_yelp_data --mode reviews --data-dir data/archive_4

# 全量导入
python manage.py import_yelp_data --mode all --data-dir data/archive_4
```

说明：

- 导入脚本保持独立命令形式，不放进请求链路。
- 导入按 `business_id`、`review_id` 和稳定生成的 Yelp 用户名做幂等更新。
- Yelp Web 页面与图表当前采用“数据库展示 + JSON 相似度候选”的混合模式。
- 运行时降级策略：
  - 相似度文件缺失、损坏或结构异常时，相似推荐和网络图返回空结果，不影响页面主内容。
  - JSON 中候选商家不存在于数据库时，运行时直接跳过该候选。

`Foods.collect_count` 和 `Foods.comment_count` 是展示/排序用统计字段。初始值来自
`food.csv` 的 `收藏数量`、`评论数量`，后续由本系统收藏、取消收藏、发表评论增量维护。
`generate_demo_collects` 生成演示收藏时也会同步增加 `collect_count`，但这些数据仍然属于
synthetic implicit feedback。

## 快速开始

### 环境要求

- Python 3.12（当前开发环境）
- MySQL 8.0
- Node.js 仅用于前端类型提示，可选

### 安装依赖

```bash
python -m venv .venv
pip install -r requirements.txt
npm install
```

### 环境变量

未设置环境变量时会使用本地开发默认值。

```bash
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
MYSQL_DATABASE=food_recommend
MYSQL_USER=root
MYSQL_PASSWORD=5247
MYSQL_HOST=localhost
MYSQL_PORT=3306
```

### 启动

```bash
python manage.py migrate
python manage.py runserver
```

访问 `http://127.0.0.1:8000/`。

## Web 入口

- 中文菜品首页：`/api/v1/user_index/`
- 中文菜品列表：`/api/v1/food_list/`
- 中文菜品 UserCF 推荐：`/api/v1/foods/recommendations/usercf/`
- Yelp 餐厅列表：`/api/v1/yelp/restaurants/`
- Yelp 餐厅详情：`/api/v1/yelp/restaurants/<business_id>/`
- 数据可视化：`/api/v1/charts/dashboard/`

## 质量检查

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python -m mypy apps config
python -m pylint apps config
python -m djlint templates --check --profile django
python manage.py test apps.recommendations.tests
```

## 数据导入

中文菜品数据由 `get_data/spider.py` 生成 `food.csv`，再用 `get_data/csvtosql.py` 导入 MySQL。导入脚本读取上面的 MySQL 环境变量，并使用参数化 SQL。

```bash
python get_data/csvtosql.py
```

Yelp 原始数据默认从 `data/archive_4/` 读取，至少需要以下文件：

- `yelp_academic_dataset_business.json`
- `yelp_academic_dataset_user.json`
- `yelp_academic_dataset_review.json`

推荐接入顺序：

1. 先运行 `python manage.py migrate`
2. 运行 `python manage.py import_yelp_data --mode all --data-dir data/archive_4`
3. 如需重建内容相似度，再运行 `python manage.py build_yelp_content_recs --top-k 20`

## 文档现状

- `notebooks/`：数据集探索和算法实验记录。
- `docs/`：前端组件化尝试的文档，后续不作为主要开发方向。
- `TODO.md`：按当前路线维护的任务清单。
