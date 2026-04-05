针对你的电商/美食/电影混合推荐场景（Yelp数据集），推荐这个**精简实用**的目录结构：

```
yelp-hybrid-rec/
├── 📁 notebooks/                      # 策略探索（按场景命名，不用编号）
│   ├── eda_yelp_exploration.ipynb     # 用户/商家分布、地理热力图
│   ├── cf_matrix_factorization.ipynb # 协同过滤调参（SVD/ALS）
│   ├── content_geo_features.ipynb     # 基于内容（类别+位置特征）
│   ├── hybrid_fusion_exp.ipynb        # 混合权重实验（CF vs Content 配比）
│   └── cold_start_strategy.ipynb      # 新用户/新商家策略验证
│
├── 📁 src/                          # 核心引擎（按用户分类维度组织）
│   ├── 📁 offline/                  # 离线大规模计算
│   │   ├── cf_engine.py             # 协同过滤（UserCF/ItemCF/SVD）
│   │   ├── content_indexer.py       # 内容特征索引（TF-IDF/类别向量）
│   │   ├── knowledge_rules.py       # 基于知识的规则（如"午餐推快餐"）
│   │   └── candidate_generator.py   # 各策略候选集生成（Top-K召回）
│   │
│   ├── 📁 realtime/                 # 实时轻量服务
│   │   ├── user_state.py            # 用户实时行为缓存（最近浏览）
│   │   ├── context_detector.py      # 上下文识别（时间/位置/天气）
│   │   └── hot_reRanker.py          # 实时热门加权（解决冷启动）
│   │
│   ├── 📁 hybrid/                   # 混合策略层（核心）
│   │   ├── fusion_router.py         # 分流逻辑：新用户→Content，活跃用户→CF
│   │   ├── weight_blender.py        # 结果融合（加权/级联/特征组合）
│   │   └── strategy_config.py       # 场景配置（美食vs电影不同权重）
│   │
│   ├── 📁 data/                     # Yelp数据处理
│   │   ├── yelp_loader.py           # 解析yelp_academic_dataset
│   │   └── feature_builder.py       # 拼接用户画像+商家特征
│   │
│   └── 📁 evaluation/               # 离线评估（支持多策略对比）
│       ├── metrics.py               # Precision@K, Recall@K, Coverage
│       └── ab_test_simulator.py     # 策略离线A/B模拟
│
├── 📁 configs/                      # 场景化配置（对应你的"推荐原则"分类）
│   ├── food_recommend.yaml          # 美食场景：Content权重高（口味匹配），CF权重中
│   └── fallback.yaml                # 冷启动兜底：基于统计的热门+地理近邻
│
├── 📁 data/                         # 数据目录（gitignore）
│   ├── raw/                         # Yelp原始JSON（business, user, review）
│   ├── cache/                       # 协同过滤矩阵、Embedding缓存
│   └── candidates/                  # 离线生成的候选集（每日更新）
│
└── 📁 api/                          # 实时接口（FastAPI/Flask）
    └── recommend_service.py         # /recommend?user_id=&lat=&lon=&time=
```

### 关键精简设计

**1. 匹配你的分类体系**
- **离线/实时** → `offline/` vs `realtime/` 两个目录
- **个性化/统计** → `hybrid/fusion_router.py` 中实现分流逻辑（新用户走统计热门，老用户走个性化）
- **相似度/知识/模型** → 分别在 `cf_engine.py` / `knowledge_rules.py` / `content_indexer.py`
- **数据源** → `data/` 中统一处理Yelp的人口统计、商家内容、行为评分

**2. Notebooks 精简原则**
- 不用数字编号，按**业务场景**命名（`cold_start_strategy` 比 `05_cold_start_v2` 直观）
- 每个notebook验证一个**可落地的策略**，确认有效后将核心类移入 `src/`，notebook保留可视化分析部分

**3. Hybrid层是核心**
美食和电影推荐策略差异很大：
```python
# configs/food_recommend.yaml
strategy_weights:
  cf: 0.3          # 美食小众，协同过滤效果有限
  content: 0.6     # 口味、价格、位置匹配更重要
  knowledge: 0.1   # 用餐时间规则

# configs/movie_recommend.yaml  
strategy_weights:
  cf: 0.7          # 电影大众口味，协同过滤主导
  content: 0.2     # 类型、演员
  knowledge: 0.1   # 节假日推荐特定类型
```

**4. Yelp数据集适配**
- `content_geo_features.ipynb` 重点处理**地理位置**（Yelp特色）+ **商家类别**混合特征
- `user_state.py` 利用Yelp的`tip`和`checkin`数据做**实时意图**捕捉

**避免过度工程**：没有深度学习目录（TwoTower/DeepFM），没有复杂MLOps。CF用`surprise`库，Content用`scikit-learn`，混合层纯Python逻辑，适合Yelp规模的学术数据集快速落地。