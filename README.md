# 餐饮个性化推荐系统

## 当前状态

这是一个早期 Django 毕设项目，当前已具备：

- Django 5.2 项目结构，包含用户、菜品两个业务 app。
- MySQL 业务库配置，支持用户注册/登录、菜品列表、菜品详情、收藏、评论。
- 中文菜品爬取与 CSV 导入脚本。
- Yelp 数据集探索 notebook，已验证内容推荐实验方向。
- mypy、pylint、djlint 的项目级配置。

推荐系统尚未完整接入 Web 页面。当前路线是：中文菜品做统计推荐和演示型收藏协同过滤，Yelp 餐厅做内容推荐和邻域协同过滤，实时推荐只做基于最近行为的离线候选重排。

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

## 推荐分层

1. 中文菜品统计推荐：基于已有菜品表、收藏数、评论数、菜系、价格等粗粒度信息生成榜单。
2. 中文菜品收藏协同过滤：基于 `Collect(user_id, food_id)` 生成 0/1 隐式反馈矩阵，实现演示型 ItemCF/UserCF。收藏数据可以用命令生成，但必须标注为模拟数据，不作为真实效果评估依据。
3. Yelp 餐厅内容推荐：基于 business/categories/review/tip 等文本和属性做 TF-IDF 特征，离线生成相似餐厅。
4. Yelp 餐厅协同过滤：基于 review 评分构造 user-business 矩阵，实现 UserCF/ItemCF 这类邻域算法，不把矩阵分解作为 v1 主线。
5. 实时重排：根据用户最近浏览、收藏或评分，读取离线相似度候选，用简单权重合并和过滤，不在线训练模型。

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

## 质量检查

```bash
python manage.py check
python -m mypy apps config
python -m pylint apps config
python -m djlint templates --check --profile django
```

## 数据导入

中文菜品数据由 `get_data/spider.py` 生成 `food.csv`，再用 `get_data/csvtosql.py` 导入 MySQL。导入脚本读取上面的 MySQL 环境变量，并使用参数化 SQL。

```bash
python get_data/csvtosql.py
```

## 文档现状

- `notebooks/`：数据集探索和算法实验记录。
- `docs/`：前端组件化尝试的文档，后续不作为主要开发方向。
- `TODO.md`：按当前路线维护的任务清单。
