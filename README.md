# 餐饮个性化推荐系统

## 项目简介

本项目是一个面向餐饮场景的个性化推荐系统，旨在解决现有推荐系统在准确性、个性化和实时性方面的不足。系统采用**协同过滤算法**作为核心推荐引擎，结合用户行为数据（收藏、浏览、评分）和商家多维属性（菜系类型、用户评分、地理位置），为用户提供精准的餐厅和菜品推荐。

**核心目标**：验证推荐算法思想与系统设计能力，而非复现工业级大数据架构。

## 技术栈

| 层级     | 技术选型                  | 说明                                  |
| -------- | ------------------------- | ------------------------------------- |
| 后端框架 | Django 4.x                | Python Web 开发框架，提供模板引擎渲染 |
| 数据库   | MySQL 8.0                 | 业务数据持久化存储                    |
| 缓存层   | Redis                     | 推荐结果缓存、热点数据加速            |
| 数据处理 | Pandas + NumPy            | 数据预处理与特征工程                  |
| 算法库   | Scikit-learn              | 协同过滤算法实现                      |
| 前端     | HTML5 + CSS3 + JavaScript | 模板引擎之外实现轻量交互              |
| 可视化   | ECharts                   | 推荐效果数据可视化                    |

## 系统架构

1. Python Django 实现后台业务逻辑 + 前端界面的模板渲染
2. 数据加载：需要把训练数据的 csv 加载到业务数据库（MYSQL）作为初始数据（冷启动解决）
3. 统计服务：指标有：平均评分、评分/评论数（热门程度）、TOP类别、最近的热门……**统计完毕后写会业务数据库**
4. 离线推荐服务：得到用户的推荐列表（UserCF or LSM）+ 菜品/餐厅相似度预计算（副产物,ItemCF）
5. 可选的 Redis 缓存
6. 实时推荐服务：方案一->用户点击了喜欢/收藏/评分，触发业务记录，送到实施推荐算法；方案二->用户最近的浏览记录，触发ItemCF

## 核心功能

### 1. 用户画像构建

- 收藏频率分析
- 口味偏好标签提取
- 消费能力评估
- 地理位置偏好

### 2. 商家特征建模

- 菜系类型分类
- 用户评分聚合
- 地理位置信息
- 热门程度计算

### 3. 推荐算法

- **基于用户的协同过滤** (User-Based CF)：找到相似用户群体，推荐他们喜欢的餐厅
- **基于物品的协同过滤** (Item-Based CF)：根据用户历史偏好，推荐相似餐厅/菜品
- **基于内容的推荐** 不依赖大量用户行为数据，通过商家数据包含的 UGC（用户生成内容），构建特征进行推荐
- **隐语义模型协同过滤（选做）**

### 4. 推荐服务设计

#### 4.1 目标

- **首页信息流**：首先是统计推荐，最简单且对冷启动友好（全站热门）；然后是离线推荐，根据用户-物品-评分行为矩阵，计算用户之间的相似度进行推荐
- **详情页推荐**，字面意思，基于 UserCF 即可；

#### 分层

实时个性化推荐，离线个性化推荐（矩阵），统计推荐（非个性化），相似性推荐（基于内容相似度对比 or “购买了本菜的人也买了”）

核心数据字段：菜品/餐厅的评分；用户对餐厅的评价（UGC）；菜品/餐厅的类别/标签/描述（PGC）；用户 id/菜品 id/餐厅 id 关联

实时推荐服务：根据时段、地点等设定规则；离线推荐服务：算好之后存起来；离线统计服务：数据集统计信息落库；

基于模型；协同过滤；基于内容

美食推荐网站

## 数据库设计

1. 用户表-user（如果要做用户画像或者人口统计学，则增加字段）

```sql
CREATE TABLE user (
  id bigint NOT NULL AUTO_INCREMENT,
  username varchar(255) NOT NULL,
  password varchar(255) NOT NULL,
  email varchar(100) UNIQUE NOT NULL,
  phone varchar(11) UNIQUE NOT NULL,
  info longtext DEFAULT NULL,
  face varchar(255) DEFAULT NULL COMMENT '头像',
  regtime datetime(6) NOT NULL,
)
```

2. 菜品表-myapp_foods 
```sql
CREATE TABLE myapp_foods (
  id bigint NOT NULL AUTO_INCREMENT COMMENT ‘核心关联’,
  foodname varchar(70) NOT NULL,
  foodtype varchar(20) NOT NULL COMMENT '菜系种类，核心字段',
  recommend varchar(255) NULL DEFAULT NULL '推荐理由UGC，核心字段',
  imgurl varchar(255) NOT NULL,
  price decimal(5, 2) NOT NULL,    
)
```

3. 餐厅表-restaurant
```sql
CREATE TABLE restaurant (
    business_id varchar(255) not null primary key,
    name varchar(255) not null,
    categories varchar(255) not null comment '类别，逗号分割',
    stars decimal defalut null comment '评分，满分五分',
    review_count int not null default 0 comment '评论数'
)
```

### 核心数据表

| 表名 | 说明 |
| ---- | ---- |

### E-R 关系

## 快速开始

### 环境要求

- Python 3.10+
- MySQL 8.0
- Redis 6.0+

### 安装依赖

```bash
python -m venv .venv
pip install -r requirements.txt
```

建议使用 **vscode** 作为开发环境，注意 mypy & pylint & djlint & pylance 是否启用。

pylint 的 vscode 配置如下，请修改为自己的目录：

```json
"pylint.args": [
    "--load-plugins",
    "pylint_django",
    "--load-plugins",
    "pylint_django.checkers.migrations",
    "--django-settings-module=${YOUR_APP_NAME}.settings",
    "--disable=C0115,C0116,E1136,E0307"
]
```

前端类型提示（实际引用 lib/esm.js）：

```bash
npm install -D @types/alpinejs
npm install -D htmx.org
```

见 `/global.d.ts`

### 数据库配置

```bash

```

### 启动服务

```bash
# 启动 Django 开发服务器
python manage.py runserver
```

访问 http://127.0.0.1:8000 查看系统

## 项目结构

```

```

## 推荐算法说明

### 协同过滤核心逻辑

### 算法评估指标

## 参考资料

- [HTMX](https://htmx.org/docs/#requests)
- [Apline](https://alpinejs.dev/directives/cloak)
