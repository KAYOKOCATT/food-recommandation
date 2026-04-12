"""
图表数据服务模块

提供图表数据聚合和格式化服务，支持四种图表类型：
1. 菜品分类统计 - 价格和收藏数分析
2. 用户行为趋势 - 时间序列数据
3. 餐厅地理分布 - Yelp数据地图展示
4. 相似度网络图 - 推荐关系可视化

依赖：
    - django.db.models: ORM聚合查询
    - pathlib: 文件路径处理
    - json: JSON数据读取
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from django.conf import settings
from django.db.models import Avg, Count, DateField
from django.db.models.functions import Cast, TruncDate

from apps.foods.models import Collect, Comment, Foods
from apps.users.models import User


class ChartService:
    """图表数据服务类"""

    DATA_DIR = settings.BASE_DIR / "data" / "recommendations"
    US_STATES = {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA",
        "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD",
        "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ",
        "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC",
        "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
        "DC",
    }

    @classmethod
    def get_food_category_stats(cls) -> dict[str, Any]:
        """
        获取菜品分类统计数据

        按菜品类型聚合，计算平均价格和平均收藏数

        Returns:
            dict: {
                "categories": ["川菜", "粤菜", ...],
                "avgPrices": [38.5, 45.2, ...],
                "avgCollects": [12.3, 8.5, ...]
            }
        """
        stats = (
            Foods.objects.values("foodtype")
            .annotate(avg_price=Avg("price"), avg_collects=Avg("collect_count"))
            .order_by("-avg_collects")
        )

        categories = []
        avg_prices = []
        avg_collects = []

        for item in stats:
            categories.append(item["foodtype"])
            avg_prices.append(round(float(item["avg_price"]), 2))
            avg_collects.append(round(float(item["avg_collects"]), 2))

        return {
            "categories": categories,
            "avgPrices": avg_prices,
            "avgCollects": avg_collects,
        }

    @classmethod
    def get_user_activity_trend(cls, days: int = 30) -> dict[str, Any]:
        """
        获取用户行为时间趋势数据

        统计最近N天的新用户注册、收藏、评论数量

        Args:
            days: 统计天数，默认30天

        Returns:
            dict: {
                "dates": ["2024-01-01", ...],
                "registrations": [5, 8, ...],
                "collects": [10, 15, ...],
                "comments": [3, 6, ...]
            }
        """
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days - 1)

        # 生成日期列表
        date_list = [
            (start_date + timedelta(days=i)).strftime("%Y-%m-%d")
            for i in range(days)
        ]

        # 查询每日新用户注册
        user_stats = (
            User.objects.annotate(date=Cast("regtime", DateField()))
            .filter(date__gte=start_date)
            .values("date")
            .annotate(count=Count("id"))
        )
        user_dict = {str(item["date"]): item["count"] for item in user_stats}

        # 查询每日新增收藏
        collect_stats = (
            Collect.objects.annotate(date=Cast("added_time", DateField()))
            .filter(date__gte=start_date)
            .values("date")
            .annotate(count=Count("id"))
        )
        collect_dict = {str(item["date"]): item["count"] for item in collect_stats}

        # 查询每日新增评论
        comment_stats = (
            Comment.objects.annotate(date=Cast("ctime", DateField()))
            .filter(date__gte=start_date)
            .values("date")
            .annotate(count=Count("id"))
        )
        comment_dict = {str(item["date"]): item["count"] for item in comment_stats}

        # 组装数据
        registrations = [user_dict.get(d, 0) for d in date_list]
        collects = [collect_dict.get(d, 0) for d in date_list]
        comments = [comment_dict.get(d, 0) for d in date_list]

        return {
            "dates": date_list,
            "registrations": registrations,
            "collects": collects,
            "comments": comments,
        }

    @classmethod
    def get_restaurant_geo_data(cls, limit: int = 1000) -> list[dict[str, Any]]:
        """
        获取餐厅地理分布数据

        从Yelp业务数据文件中读取餐厅位置、评分等信息

        Args:
            limit: 返回数据条数上限，默认1000

        Returns:
            list: [
                {
                    "name": "Restaurant Name",
                    "value": [longitude, latitude, stars, review_count],
                    "city": "City Name"
                },
                ...
            ]
        """
        file_path = cls.DATA_DIR / "yelp_business_profiles.json"

        if not file_path.exists():
            return []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            profiles = data.get("profiles", [])
            result = []

            for item in profiles:
                if item.get("state") not in cls.US_STATES:
                    continue

                longitude = item.get("longitude")
                latitude = item.get("latitude")
                if longitude is None or latitude is None:
                    continue

                result.append({
                    "name": item.get("name", ""),
                    "value": [
                        longitude,
                        latitude,
                        item.get("stars", 0),
                        item.get("review_count", 0),
                    ],
                    "city": item.get("city", ""),
                    "state": item.get("state", ""),
                    "categories": item.get("categories", ""),
                })
                if len(result) >= limit:
                    break

            return result
        except (json.JSONDecodeError, KeyError, IOError):
            return []

    @classmethod
    def get_similarity_network(  # pylint: disable=too-many-locals,too-many-nested-blocks
        cls, limit: int = 100, similarity_threshold: float = 0.5
    ) -> dict[str, Any]:
        """
        获取推荐相似度网络数据

        从相似度文件中构建节点和边的关系图

        Args:
            limit: 节点数量上限，默认100
            similarity_threshold: 相似度阈值，默认0.5

        Returns:
            dict: {
                "nodes": [{"id": "...", "name": "...", "category": "..."}],
                "links": [{"source": "...", "target": "...", "value": 0.8}]
            }
        """
        similarity_path = cls.DATA_DIR / "yelp_content_itemcf.json"
        profiles_path = cls.DATA_DIR / "yelp_business_profiles.json"

        if not similarity_path.exists() or not profiles_path.exists():
            return {"nodes": [], "links": []}

        try:
            # 加载业务信息（用于获取名称和分类）
            with open(profiles_path, "r", encoding="utf-8") as f:
                profiles_data = json.load(f)

            # 构建业务ID到信息的映射
            business_info: dict[str, dict[str, Any]] = {}
            for item in profiles_data.get("profiles", []):
                business_id = item.get("business_id", "")
                if business_id:
                    # 从categories中提取主分类
                    categories = item.get("categories", "")
                    main_category = categories.split(",")[0].strip() if categories else "Other"
                    business_info[business_id] = {
                        "name": item.get("name", business_id),
                        "category": main_category,
                        "review_count": item.get("review_count", 0),
                    }

            # 加载相似度数据
            with open(similarity_path, "r", encoding="utf-8") as f:
                similarity_data = json.load(f)

            nodes: list[dict[str, Any]] = []
            links: list[dict[str, Any]] = []
            node_ids: set[str] = set()
            link_ids: set[frozenset[str]] = set()
            category_colors: dict[str, int] = {}
            color_index = 0

            # 选择前limit个业务作为节点
            business_ids = list(similarity_data.keys())[:limit]

            for business_id in business_ids:
                if business_id not in node_ids:
                    info = business_info.get(
                        business_id,
                        {"name": business_id, "category": "Unknown"},
                    )
                    category = info["category"]

                    # 为分类分配颜色索引
                    if category not in category_colors:
                        category_colors[category] = color_index
                        color_index += 1

                    nodes.append({
                        "id": business_id,
                        "name": info["name"],
                        "category": category,
                        "symbolSize": cls._network_symbol_size(info.get("review_count", 0)),
                    })
                    node_ids.add(business_id)

                # 添加相似度边
                for candidate in similarity_data.get(business_id, []):
                    target_id = candidate.get("business_id", "")
                    score = candidate.get("score", 0)

                    if target_id and score >= similarity_threshold:
                        # 确保目标节点也在列表中
                        if target_id not in node_ids and len(nodes) < limit:
                            info = business_info.get(
                                target_id,
                                {"name": target_id, "category": "Unknown"},
                            )
                            category = info["category"]

                            if category not in category_colors:
                                category_colors[category] = color_index
                                color_index += 1

                            nodes.append({
                                "id": target_id,
                                "name": info["name"],
                                "category": category,
                                "symbolSize": cls._network_symbol_size(info.get("review_count", 0)),
                            })
                            node_ids.add(target_id)

                        link_id = frozenset((business_id, target_id))
                        if target_id in node_ids and link_id not in link_ids:
                            links.append({
                                "source": business_id,
                                "target": target_id,
                                "value": round(score, 3),
                            })
                            link_ids.add(link_id)

            return {
                "nodes": nodes,
                "links": links,
                "categories": [{"name": cat} for cat in category_colors],
            }
        except (json.JSONDecodeError, KeyError, IOError):
            return {"nodes": [], "links": [], "categories": []}

    @staticmethod
    def _network_symbol_size(review_count: Any) -> int:
        """根据真实评论数生成稳定的网络节点大小。"""
        try:
            count = int(review_count)
        except (TypeError, ValueError):
            count = 0
        return max(10, min(30, 10 + count // 50))