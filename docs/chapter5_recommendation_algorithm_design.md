# 第五章 基于 TF-IDF 与协同过滤算法的推荐功能设计

本章介绍系统所采用的三种核心推荐算法——基于 TF-IDF 的内容推荐、邻近协同过滤（ItemCF / UserCF）以及基于 Spark ALS 的矩阵分解——的数学原理、算法选择依据与工程实现细节。系统以"离线构建、在线轻量读取"为设计原则，将重计算前移到离线阶段，在线页面仅执行查询、过滤与轻量重排，从而保证推荐服务的响应速度与演示稳定性。

## 5.1 算法原理介绍

### 5.1.1 TF-IDF 内容推荐原理

TF-IDF（Term Frequency–Inverse Document Frequency）是一种经典的文本特征权重计算方法，通过衡量词语在文档中的局部出现频率与在整个语料库中的稀有程度，为每个词语赋予一个能够反映其区分能力的权重。在本系统中，每家餐厅被视为一个"文档"，其文档内容由餐厅名称、类别标签以及聚合的用户评论文本共同构成，从而将餐厅之间的内容相似度计算转化为向量空间中的余弦相似度计算。

**1. 词频（Term Frequency, TF）**

词频衡量的是某个词语在特定文档中出现的频繁程度。为避免文档长度对词频的绝对影响，通常采用归一化词频：

$$
\text{TF}(t, d) = \frac{f_{t,d}}{\sum_{t' \in d} f_{t',d}}
$$

其中，$f_{t,d}$ 表示词语 $t$ 在文档 $d$ 中出现的原始频次，分母为文档 $d$ 中所有词语的频次之和。

**2. 逆文档频率（Inverse Document Frequency, IDF）**

逆文档频率用于降低在大量文档中普遍出现的常见词（如停用词）的权重，同时提升稀有词的区分能力：

$$
\text{IDF}(t) = \log \frac{N + 1}{n_t + 1}
$$

其中，$N$ 为语料库中的文档总数，$n_t$ 为包含词语 $t$ 的文档数量。本系统在工程实现中采用 scikit-learn 的 `TfidfVectorizer`，其默认使用平滑 IDF 变体 $\log((1+N)/(1+n_t)) + 1$，并在行方向进行 L2 归一化。

**3. TF-IDF 权重**

将词频与逆文档频率相乘，即可得到词语 $t$ 在文档 $d$ 中的 TF-IDF 权重：

$$
\text{TF-IDF}(t, d) = \text{TF}(t, d) \times \text{IDF}(t)
$$

对于整个语料库，可构建一个文档-词语矩阵 $\mathbf{X} \in \mathbb{R}^{M \times V}$，其中 $M$ 为餐厅（文档）数量，$V$ 为特征词表大小，矩阵的每一行即对应一家餐厅的 TF-IDF 特征向量。

**4. 余弦相似度**

得到餐厅的 TF-IDF 向量后，两家餐厅 $i$ 与 $j$ 之间的内容相似度通过余弦相似度计算：

$$
\text{sim}(i, j) = \cos(\theta) = \frac{\mathbf{x}_i \cdot \mathbf{x}_j}{\|\mathbf{x}_i\| \|\mathbf{x}_j\|}
$$

其中，$\mathbf{x}_i$ 与 $\mathbf{x}_j$ 分别为餐厅 $i$ 和餐厅 $j$ 的 TF-IDF 向量。由于 `TfidfVectorizer` 已进行 L2 归一化，上式可简化为两向量的点积。在工程实现中，本系统使用 `NearestNeighbors(metric="cosine")` 为每家餐厅高效检索与其内容最相似的 Top-K 邻居。

### 5.1.2 邻近协同过滤原理

邻近协同过滤（Neighborhood-based Collaborative Filtering）是一种基于用户行为数据（如收藏、评分）的推荐方法，核心思想是：若两个物品被同一批用户喜欢，则它们可能相似（ItemCF）；若两个用户喜欢同一批物品，则他们可能品味相近（UserCF）。本系统的中文菜品推荐与 Yelp 实验推荐均采用了这一思想。

**1. ItemCF 物品相似度**

设用户-物品交互集合为 $\mathcal{R}$，$U(i)$ 表示与物品 $i$ 发生过交互的用户集合。物品 $i$ 与物品 $j$ 之间的相似度可采用基于共现的改进余弦相似度（Adjusted Cosine）进行度量：

$$
\text{sim}(i, j) = \frac{|U(i) \cap U(j)|}{\sqrt{|U(i)| \cdot |U(j)|}}
$$

其中，分子为同时交互过物品 $i$ 和 $j$ 的用户数（共现次数），分母为两个物品各自交互用户数量的几何平均，起到归一化作用，避免热门物品因基数大而过度占优。

在获得物品相似度后，对于目标用户 $u$ 及其历史交互物品集合 $I_u$，系统通过加权求和预测用户对候选物品 $j$ 的偏好得分：

$$
\hat{r}_{u,j} = \sum_{i \in I_u} \text{sim}(i, j) \cdot r_{u,i}
$$

在隐式反馈场景下（如收藏），$r_{u,i}$ 通常取值为 1，此时得分退化为历史物品与候选物品相似度的累加。

**2. UserCF 用户相似度**

设 $I(u)$ 为用户 $u$ 交互过的物品集合。用户 $u$ 与用户 $v$ 之间的相似度可采用余弦相似度计算：

$$
\text{sim}(u, v) = \frac{|I(u) \cap I(v)|}{\sqrt{|I(u)| \cdot |I(v)|}}
$$

对于目标用户 $u$，首先找到与其最相似的 $K$ 个邻居 $N(u)$，然后对用户 $u$ 尚未交互过的物品 $j$ 进行评分预测：

$$
\hat{r}_{u,j} = \bar{r}_u + \frac{\sum_{v \in N(u)} \text{sim}(u, v) \cdot (r_{v,j} - \bar{r}_v)}{\sum_{v \in N(u)} |\text{sim}(u, v)|}
$$

其中，$\bar{r}_u$ 与 $\bar{r}_v$ 分别为用户 $u$ 和 $v$ 的平均评分。该公式通过去中心化处理，消除了不同用户评分尺度差异带来的影响。在隐式反馈场景中，可省略均值项，直接按相似用户交互物品的相似度加权求和。

### 5.1.3 Spark ALS 矩阵分解原理（模型协同过滤）

交替最小二乘法（Alternating Least Squares, ALS）是一种基于隐语义模型（Latent Factor Model）的矩阵分解技术，旨在将高维稀疏的用户-物品评分矩阵分解为两个低维稠密矩阵的乘积，从而挖掘用户与物品之间的潜在关联。

**1. 矩阵分解目标**

设用户-物品评分矩阵为 $\mathbf{R} \in \mathbb{R}^{m \times n}$，其中 $m$ 为用户数，$n$ 为物品数，矩阵中大量元素未知（稀疏）。ALS 试图找到用户隐因子矩阵 $\mathbf{U} \in \mathbb{R}^{m \times k}$ 与物品隐因子矩阵 $\mathbf{P} \in \mathbb{R}^{n \times k}$，使得：

$$
\mathbf{R} \approx \mathbf{U} \mathbf{P}^{\top}
$$

其中，$k$ 为隐因子维度（rank），$k \ll \min(m, n)$。矩阵 $\mathbf{U}$ 的每一行 $\mathbf{u}_u$ 代表用户 $u$ 的隐向量，矩阵 $\mathbf{P}$ 的每一行 $\mathbf{p}_i$ 代表物品 $i$ 的隐向量。用户 $u$ 对物品 $i$ 的预测评分可表示为：

$$
\hat{r}_{u,i} = \mathbf{u}_u^{\top} \mathbf{p}_i
$$

**2. 损失函数与正则化**

为了学习最优的隐因子矩阵，ALS 最小化以下带 L2 正则化的平方误差损失：

$$
\mathcal{L} = \sum_{(u,i) \in \mathcal{K}} \left( r_{u,i} - \mathbf{u}_u^{\top} \mathbf{p}_i \right)^2 + \lambda \left( \|\mathbf{u}_u\|^2 + \|\mathbf{p}_i\|^2 \right)
$$

其中，$\mathcal{K}$ 为已观测到的评分集合，$\lambda$ 为正则化参数，用于防止模型过拟合。

**3. 交替优化策略**

ALS 的核心思想是：固定其中一个矩阵，求解另一个矩阵的最优解，然后交替迭代。

当固定物品矩阵 $\mathbf{P}$ 时，每个用户 $u$ 的最优隐向量可通过求解一个岭回归（Ridge Regression）闭式解得到：

$$
\mathbf{u}_u = \left( \sum_{i \in I_u} \mathbf{p}_i \mathbf{p}_i^{\top} + \lambda \mathbf{I} \right)^{-1} \sum_{i \in I_u} r_{u,i} \mathbf{p}_i
$$

同理，当固定用户矩阵 $\mathbf{U}$ 时，每个物品 $i$ 的最优隐向量为：

$$
\mathbf{p}_i = \left( \sum_{u \in U_i} \mathbf{u}_u \mathbf{u}_u^{\top} + \lambda \mathbf{I} \right)^{-1} \sum_{u \in U_i} r_{u,i} \mathbf{u}_u
$$

通过交替固定 $\mathbf{U}$ 和 $\mathbf{P}$ 并迭代求解，损失函数 $\mathcal{L}$ 单调下降，最终收敛到局部最优解。Spark MLlib 的 ALS 实现利用分布式计算将不同用户/物品的隐向量求解并行化，从而能够高效处理千万级甚至亿级的评分数据。

---

## 5.2 算法选择

本系统的推荐算法设计并非追求单一模型的理论最优，而是依据两条业务线的数据特点、工程约束与演示需求进行综合取舍。

### 算法优势与适用场景对比

| 算法 | 核心优势 | 主要局限 | 适用场景 |
|------|----------|----------|----------|
| **TF-IDF 内容推荐** | 不依赖用户行为数据，对新物品和冷启动用户稳定；结果可解释性强 | 无法捕捉用户协同偏好，推荐多样性有限 | 物品元数据与文本丰富的场景；新用户/新物品较多的场景 |
| **邻近协同过滤（ItemCF/UserCF）** | 能够发现用户兴趣的协同模式，推荐结果具有较强的个性化 | 对数据稀疏性敏感；冷启动问题显著 | 拥有一定规模用户行为数据的闭环业务系统 |
| **Spark ALS 矩阵分解** | 能够处理大规模稀疏数据；隐因子模型表达能力更强 | 训练成本高；结果解释性较弱；对线上依赖较重 | 大规模用户-评分矩阵的离线建模与实验验证 |

### 针对本项目数据集的取舍

**1. 中文菜品业务线：ItemCF / UserCF + 演示数据**

中文菜品线的主要目标是支撑完整的站内业务闭环（注册、登录、浏览、收藏、评论、推荐）。然而，该业务线缺乏天然的大规模真实用户行为数据，若等待站内行为自然积累，在毕设周期内难以形成可演示的协同过滤效果。因此，本系统通过 `generate_demo_collects` 管理命令生成明确标注的演示型收藏数据，将其作为隐式反馈源，再基于 `Collect` 表构建 ItemCF 与 UserCF 离线产物。这一做法的定位是**工程演示能力验证**，而非真实线上效果论证。中文菜品线的协同过滤链路被收敛为"热门统计 + 基于收藏的轻量 CF"，既保证了页面可用性，又避免了过度复杂的工程投入。

**2. Yelp 餐厅业务线：TF-IDF 内容推荐作为主链路**

Yelp 数据集具备完整的商家元数据（名称、类别、城市、评分）和丰富的用户评论文本，天然适合构建内容推荐链路。与中文菜品线不同，Yelp 线不需要依赖站内积累的行为数据，即可通过离线 TF-IDF 构建稳定的物品相似度网络。内容推荐的另一大优势是**对新餐厅和弱行为用户的鲁棒性**：即使用户没有任何历史评分，系统仍可基于当前浏览餐厅的内容相似度为其推荐相关候选。因此，Yelp 线的默认推荐页采用了"最近评分行为 + 离线内容相似候选 + 热门兜底"的三段式策略，其中内容相似度是候选召回的核心基础设施。

**3. Spark ALS：大数据实验能力的补充**

项目后期为满足毕设对"大数据组件"的展示要求，引入了基于 Spark 的 ALS 矩阵分解模型。选择 ALS 而非其他深度学习模型的原因在于：ALS 是协同过滤领域中工程化最成熟、理论最清晰的矩阵分解方法，Spark MLlib 提供了开箱即用的分布式实现，能够在单机或集群环境下处理 Yelp 原始数据集中的数十万级评分记录。然而，ALS 更偏向"模型实验能力"，其训练依赖 Spark 环境，结果解释性不如内容推荐直观，且直接替换主链路会提高线上依赖和排障成本。因此，系统在架构上明确将 Spark ALS **收敛为离线实验能力**：通过 `build_yelp_spark_als` 命令离线训练模型并产出 `yelp_als_userrec.json`，再由独立的 ALS 实验推荐页进行展示，而默认的 Yelp 推荐页仍保持基于内容推荐的稳定链路不变。

---

## 5.3 算法实现

### 5.3.1 中文菜品协同过滤实现

中文菜品线的协同过滤实现围绕 `apps/foods/management/commands/build_food_collect_cf.py` 管理命令展开，其核心流程如下：

**1. 隐式反馈提取**

系统从 `Collect` 表中提取所有用户-菜品交互对，得到隐式反馈列表：

```python
interactions = list(
    Collect.objects.order_by("user_id", "food_id")
    .values_list("user_id", "food_id")
)
```

每条交互记录为一个二元组 `(user_id, food_id)`，用户对菜品的收藏行为被视作值为 1 的隐式正反馈。

**2. 离线构建 ItemCF**

交互数据被传递给 `apps.recommendations.collect_cf.item_cf_similarities` 函数。该函数首先构建两个倒排索引：`user_items`（用户→菜品集合）与 `item_users`（菜品→用户集合）。随后，遍历每个用户的交互物品列表，统计物品之间的共现次数 `co_counts`：

```python
score = count / sqrt(len(item_users[item_id]) * len(item_users[other_item_id]))
```

最终，对每个物品保留相似度最高的 Top-K 邻居，并序列化为 `food_itemcf.json`。

**3. 离线构建 UserCF**

同理，`user_cf_recommendations` 函数基于 `user_items` 索引计算用户之间的 Jaccard-like 相似度（共同交互物品数除以几何平均），为每个用户找出最相似的 Top-K 邻居，再聚合邻居交互过的、但目标用户未交互过的物品，按相似度加权排序后输出为 `food_usercf.json`。

**4. 在线消费与降级**

在线页面通过 `apps.foods.services` 读取上述 JSON 文件。`similar_foods_for_detail` 为详情页提供相似菜品推荐；`recommend_foods_by_usercf` 与 `recommend_foods_by_itemcf` 分别为用户生成个性化推荐列表。系统对文件缺失、候选菜品已下架等异常情况做了降级处理，确保页面稳定性。

### 5.3.2 内容推荐实现（基于 Yelp 数据集）

Yelp 内容推荐的离线构建链路固化在 `apps/recommendations/management/commands/build_yelp_content_recs.py` 中，数据流从原始 Yelp JSONL 文件到最终的相似度 JSON 产物，具体实现如下：

**1. 流式数据加载与餐厅过滤**

为避免一次性加载数 GB 的 review 文件导致内存溢出，系统采用流式读取策略：

```python
profiles = build_business_profiles(
    iter_json_lines(business_path),
    iter_json_lines(review_path, limit=review_line_limit),
    ...
)
```

`build_business_profiles` 首先扫描 `yelp_academic_dataset_business.json`，通过 `is_restaurant_business` 函数过滤出符合条件的餐厅：
- 类别中包含 `Restaurants` 或 `Cafe`；
- 排除 `Grocery`、`Pharmacy` 等非餐饮类别；
- 默认排除已关闭商家（`is_open=0`）；
- 要求具备经纬度信息；
- 评论数达到最小阈值（默认 `min_review_count=10`）。

随后，在第二次流式扫描 `yelp_academic_dataset_review.json` 时，仅保留已筛选餐厅对应的评论文本，且每一家餐厅最多聚合 `max_reviews_per_business=50` 条评论，从而控制单条文档的内存占用。

**2. 文档构建与文本预处理**

每家餐厅被封装为一个 `YelpBusinessProfile` 对象，其 `combined_text` 方法将餐厅名称、加权类别标签与聚合评论文本合并为单一文档：

```python
def combined_text(self, *, category_weight: int = 5) -> str:
    categories_text = preprocess_categories(self.categories)
    return " ".join(
        text
        for text in [
            self.name,
            (categories_text + " ") * max(category_weight, 0),
            self.aggregated_text,
        ]
        if text
    )
```

类别文本通过 `preprocess_categories` 进行规范化（小写化、去除特殊字符、空格替换为下划线），并被重复 `category_weight=5` 次以提升类别信息在 TF-IDF 中的权重，确保"Chinese"、"Italian"等标签对相似度计算产生更强的引导作用。

**3. TF-IDF 向量化与最近邻检索**

文档集合传入 `build_yelp_content_recommendations` 函数，由 `TfidfVectorizer` 进行向量化：

```python
vectorizer = TfidfVectorizer(
    max_features=5000,
    min_df=effective_min_df,
    max_df=effective_max_df,
    stop_words=BUSINESS_STOP_WORDS,
    ngram_range=(1, 2),
    token_pattern=r"(?u)\b[a-zA-Z_]{2,}\b",
    norm="l2",
)
```

关键参数说明：
- `max_features=5000`：限制特征词表大小，控制向量维度；
- `min_df=3` / `max_df=0.5`：过滤过于罕见和过于普遍的词语；
- `stop_words=BUSINESS_STOP_WORDS`：在英文停用词基础上，补充了餐饮领域常见但区分度低的泛情感词（如 delicious、amazing）和功能词（如 got、came、told）；
- `ngram_range=(1, 2)`：同时提取单字词（unigram）与连续双词（bigram），以捕捉 "fish taco"、"pad thai" 等食物短语；
- `norm="l2"`：对每行向量进行 L2 归一化，便于后续直接计算余弦相似度。

向量化完成后，系统使用 `NearestNeighbors(metric="cosine", algorithm="brute")` 为全部餐厅批量检索最近邻。为了避免一次性物化 $N \times N$ 的稠密相似度矩阵，查询以 `batch_size=1000` 为单位分批进行，计算结果中的余弦距离通过 `1.0 - distance` 转换为相似度分数。

**4. 离线产物输出**

最终生成两份产物：
- `yelp_content_itemcf.json`：餐厅到 Top-K 相似邻居的映射（用于详情页相似推荐、推荐页候选召回、相似度网络图）；
- `yelp_business_profiles.json`：过滤后餐厅的元数据与特征统计信息（用于调试与可视化）。

### 5.3.3 Spark ALS 实验实现

Spark ALS 链路由 `apps/recommendations/management/commands/build_yelp_spark_als.py` 管理命令触发，实际计算逻辑封装在 `apps/recommendations/spark_jobs/build_als.py` 中。该链路完全独立于 Web 请求链路，体现了"大数据离线批处理 + Django 在线轻量读取"的架构设计。

**1. 数据加载与餐厅过滤**

Spark 直接读取 `data/archive_4/` 目录下的原始 `yelp_academic_dataset_business.json` 与 `yelp_academic_dataset_review.json`：

```python
business_df = spark.read.json(str(business_path)).select("business_id", "categories")
review_df = spark.read.json(str(review_path)).select("user_id", "business_id", "stars")
```

通过 Spark SQL 的 `rlike` 正则过滤，保留餐饮类商家，并在评分数据上去除同一用户对同一商家的重复评分（`dropDuplicates`）。

**2. 数据规模控制**

由于 Yelp 原始数据规模庞大（评论数可达数百万条），系统通过 `_bound_ratings_df` 对训练数据进行截断控制，以保证 ALS 在毕设演示环境中的可运行性：
- `min_business_review_count=10`：过滤掉交互过少的冷门餐厅；
- `min_user_review_count=5`：过滤掉活跃度极低的边缘用户；
- `target_user_count=30_000`：仅保留评论数最多的前 3 万名用户；
- `target_review_count=300_000`：最终训练集上限为 30 万条评分记录。

**3. 索引编码与模型训练**

原始 `user_id` 与 `business_id` 为字符串类型，需通过 Spark MLlib 的 `StringIndexer` 转换为连续整数索引，分别映射为 `user_index` 与 `business_index`：

```python
user_indexer = StringIndexer(inputCol="user_id", outputCol="user_index", handleInvalid="skip").fit(ratings_df)
business_indexer = StringIndexer(inputCol="business_id", outputCol="business_index", handleInvalid="skip").fit(indexed_users)
```

随后调用 Spark MLlib 的 ALS 进行训练：

```python
model = als(
    userCol="user_index",
    itemCol="business_index",
    ratingCol="stars",
    rank=20,
    maxIter=10,
    regParam=0.1,
    coldStartStrategy="drop",
    nonnegative=True,
).fit(indexed_df)
```

参数说明：
- `rank=20`：隐因子维度为 20；
- `maxIter=10`：交替优化迭代 10 轮；
- `regParam=0.1`：L2 正则化系数为 0.1；
- `coldStartStrategy="drop"`：在预测阶段丢弃没有足够历史数据的用户/物品，避免产生 NaN；
- `nonnegative=True`：约束隐因子非负，增强结果可解释性。

**4. 推荐生成与产物合并**

训练完成后，调用 `model.recommendForAllUsers(top_k)` 为所有训练用户生成 Top-K 餐厅推荐。推荐结果最初以 Spark 分区文件形式输出，经过 `_merge_partitioned_recommendations` 函数合并为单一的 `yelp_als_userrec.json`，其结构为以原始 `user_id` 为键、候选列表为值的 JSON 对象，便于 Django 在线服务直接读取。

### 5.3.4 在线轻量重排实现

本系统最重要的工程原则之一是：将相似度计算、模型训练等重计算完全移出 Web 请求链路，在线阶段只保留"读取 + 过滤 + 轻量重排"。Yelp 主推荐页的实现充分体现了这一设计。

**1. 相似度缓存：`SimilarityCache`**

`apps.recommendations.services.similarity.SimilarityCache` 是一个进程级单例缓存，负责将离线 JSON 产物加载到内存，并通过文件修改时间（`st_mtime_ns`）实现热更新：

```python
class SimilarityCache:
    def get(self, path: str | Path) -> dict[str, list[RecommendationCandidate]]:
        mtime_ns = source.stat().st_mtime_ns
        if self._path == source and self._mtime_ns == mtime_ns:
            return self._data
        # 文件变更时重新加载
        self._data = self._load_json(source)
        ...
```

该缓存避免了每次请求都进行磁盘 I/O，同时保证离线命令更新产物后，Web 服务能在下次请求时自动感知并加载最新结果。

**2. 基于近期行为的候选重排：`rerank_from_recent_items`**

当用户访问"Yelp 为你推荐"页时，系统首先从其最近评分过的餐厅中提取种子物品列表：

```python
recent_business_ids = cls._recent_review_business_ids(user_id, limit=8)
```

随后调用 `rerank_from_recent_items`，将这些种子餐厅作为查询键，从 `yelp_content_itemcf.json` 中读取各自的相似邻居，并按时间衰减加权合并：

```python
for offset, item_id in enumerate(recent_item_ids):
    recency_weight = 1.0 / (offset + 1)
    for candidate in similarity.get(str(item_id), []):
        scores[candidate.item_id] += recency_weight * candidate.score
```

权重设计采用倒数衰减：`1/(offset+1)`，即越近的行为对最终推荐的影响越大。对于已评分过的餐厅（`exclude_seen=True`），系统自动将其从候选中剔除，避免重复推荐。

**3. 三段式推荐链路：`get_recent_recommendations`**

`YelpService.get_recent_recommendations` 构成了 Yelp 主推荐页的核心逻辑，可概括为以下三段式策略：

- **第一段：近期行为提取**。若用户存在近期评分记录，则以其为种子进入重排逻辑；
- **第二段：离线候选重排**。调用 `rerank_from_recent_items` 获取候选，再叠加一个轻量的 popularity 混合分：
  ```python
  blended_score = (recent_score * 0.75) + (popularity_score * 0.25)
  ```
  其中 `popularity_score = log1p(review_count) + stars * 0.1`，保证高评分、高热度的餐厅在相似候选中获得适度提升；
- **第三段：热门兜底**。若用户没有任何近期评分行为，或重排后候选为空，则无缝回退到 `get_popular_recommendations`，按 `review_count` 与 `stars` 排序返回热门餐厅。

这种"离线内容相似度 + 在线行为重排 + 热门兜底"的设计兼顾了个性化、可解释性与系统稳定性：
- 当用户有行为时，推荐结果与其最近兴趣强相关；
- 当用户无行为时，系统仍能提供稳定的热门内容；
- 整个请求链路仅涉及少量 ORM 查询与 JSON 内存读取，响应时间可控。

**4. 多场景产物复用**

同一份 `yelp_content_itemcf.json` 离线产物在系统中被多处复用：
- **餐厅详情页**：`YelpService.get_similar_businesses` 展示"相似餐厅"；
- **为你推荐页**：`get_recent_recommendations` 召回候选并进行重排；
- **数据可视化页**：`ChartService.get_similarity_network` 读取相似度映射，为 ECharts 网络图提供节点与边数据。

这种"一份离线产物、多场景在线消费"的模式，是本系统实现推荐工程化落地的关键设计之一。
