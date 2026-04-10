针对**电商美食推荐+Yelp数据+混合策略**，精简后的项目结构：

```
food-recsys/
├── 📁 notebooks/                    # 按"策略"而非"阶段"组织（更快定位）
│   ├── 01_yelp_data_audit.ipynb        # 检查Yelp的business/categories/review结构
│   ├── 02_cf_baseline.ipynb            # 纯协同过滤（UserCF/ItemCF/SVD对比）
│   ├── 03_content_analysis.ipynb         # 美食标签挖掘（categories, attributes）
│   ├── 04_hybrid_fusion.ipynb          # **关键**：加权融合/切换策略调参
│   └── 05_realtime_pipeline.ipynb        # 在线服务延迟测试（Redis预热策略）
│
├── 📁 src/
│   ├── 📁 recommenders/             # **核心：按策略类型分离**
│   │   ├── collaborative.py          # CF实现（矩阵分解、邻域模型）
│   │   ├── content_based.py          # 基于内容（TF-IDF标签、地理位置过滤）
│   │   ├── hybrid.py                 # **混合层**：加权融合、冷启动切换逻辑
│   │   └── realtime.py               # 实时召回（Session-based最近浏览）
│   │
│   ├── 📁 data/
│   │   ├── yelp_loader.py            # Yelp JSON解析（处理nested categories）
│   │   ├── feature_builder.py        # 用户画像（口味偏好向量）+ 商家特征
│   │   └── negative_sampler.py         # 电商负采样（同类别未交互商品）
│   │
│   └── 📁 serving/                  # **工程层：实时vs离线**
│       ├── offline_batch.py          # 批量计算全量推荐（Airflow调度）
│       ├── online_retrieval.py       # Flask/FastAPI实时接口（Top-K索引）
│       └── cache_manager.py          # Redis缓存热门+个性化结果
│
├── 📁 configs/
│   ├── hybrid_weights.yaml           # 冷启动/正常用户的融合权重配置
│   └── feature_specs.yaml            # Yelp字段映射（stars->rating, categories->tags）
│
├── 📁 scripts/
│   ├── build_offline_index.py        # 离线生成ItemCF相似度矩阵
│   ├── refresh_content_vectors.py    # 更新商家内容向量（菜品标签变化时）
│   └── start_api.py                  # 启动实时服务
│
└── 📁 data/
    ├── raw/yelp_academic_dataset/    # 原始Yelp数据（.gitignore）
    └── processed/
        ├── user_item_matrix.npz      # 协同过滤交互矩阵
        ├── item_content_vectors.pkl  # 商家内容特征
        └── hybrid_candidates.parquet # 预混候选池（实时服务直接读取）
```

---

**1. 混合策略的工程落地（hybrid.py）**
```python
# 不要过度抽象，直接实现"冷启动切换"逻辑
class FoodHybridRecommender:
    def recommend(self, user_id, context):
        if self.is_cold_start(user_id):          # 新用户
            return self.content.recommend(context['location'], context['mood'])
        elif context['realtime']:                 # 实时 browsing
            return self.realtime.recommend(user_id, context['recent_items'])
        else:                                     # 个性化主链路
            cf_results = self.cf.recommend(user_id)
            content_boost = self.content.recommend_by_taste(user_id)
            return self.fusion.weighted_merge(cf_results, content_boost, weights=[0.7, 0.3])
```

**2. Yelp数据特殊处理**
- `yelp_loader.py`重点处理**business.categories**（JSON数组展开为美食标签）和**attributes**（WiFi/Reservation等过滤条件）
- 地理位置在美食推荐中是强特征，需要在`content_based.py`中单独实现"距离衰减"逻辑

**3. 实时vs离线的资源分配**
- **离线**：用`scripts/build_offline_index.py`预计算ItemCF相似度（Yelp 10万商家量级可行），存储为numpy矩阵
- **实时**：`online_retrieval.py`只做Top-K索引查询+业务规则过滤（营业时间、配送范围），**不在线上做矩阵分解计算**

**4. 负采样策略（电商关键）**
在`negative_sampler.py`中实现**同类别负采样**（与用户历史浏览同category但未交互的商家），比全局负采样对美食推荐更有效。

**废弃项**：深度学习模型目录、复杂的实验追踪、特征存储抽象层——对于Yelp规模（百万级交互）的传统机器学习混合策略来说过重。