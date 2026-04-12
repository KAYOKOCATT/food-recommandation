"""
图表数据服务模块

提供图表数据聚合和格式化服务，支持四种图表类型：
1. 菜品分类统计 - 价格和收藏数分析
2. 用户行为趋势 - 时间序列数据
3. 餐厅地理分布 - Yelp数据地图展示
4. 相似度网络图 - 推荐关系可视化

运行时数据边界：
    - ORM 负责业务展示与统计查询
    - JSON 仅负责离线相似度候选
"""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from django.conf import settings
from django.db.models import Avg, Count, DateField
from django.db.models.functions import Cast

from apps.foods.models import Collect, Comment, Foods
from apps.recommendations.models import YelpBusiness
from apps.recommendations.services.similarity import (
    RecommendationCandidate,
    similarity_cache,
)
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

        从数据库读取餐厅位置、评分等信息

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
        queryset = (
            YelpBusiness.objects.filter(
                state__in=cls.US_STATES,
                longitude__isnull=False,
                latitude__isnull=False,
            )
            .order_by("-review_count", "-stars", "name")
            .values(
                "name",
                "longitude",
                "latitude",
                "stars",
                "review_count",
                "city",
                "state",
                "categories",
            )[: max(limit, 1)]
        )
        return [
            {
                "name": item["name"],
                "value": [
                    item["longitude"],
                    item["latitude"],
                    item["stars"],
                    item["review_count"],
                ],
                "city": item["city"],
                "state": item["state"],
                "categories": item["categories"],
            }
            for item in queryset
        ]

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
        similarity_data = cls._safe_similarity_mapping(
            cls.DATA_DIR / "yelp_content_itemcf.json"
        )
        if not similarity_data:
            return {"nodes": [], "links": [], "categories": []}

        nodes: list[dict[str, Any]] = []
        links: list[dict[str, Any]] = []
        node_ids: set[str] = set()
        link_ids: set[frozenset[str]] = set()
        category_order: dict[str, int] = {}
        business_ids = list(similarity_data.keys())[:limit]

        candidate_ids = set(business_ids)
        for business_id in business_ids:
            for candidate in similarity_data.get(business_id, []):
                if candidate.score >= similarity_threshold:
                    candidate_ids.add(candidate.item_id)

        business_info = cls._get_business_metadata(candidate_ids)

        for business_id in business_ids:
            source_info = business_info.get(business_id)
            if source_info is None:
                continue
            cls._append_network_node(
                nodes,
                node_ids,
                category_order,
                business_id,
                source_info,
            )

            for candidate in similarity_data.get(business_id, []):
                if candidate.score < similarity_threshold:
                    continue
                target_info = business_info.get(candidate.item_id)
                if target_info is None:
                    continue
                if candidate.item_id not in node_ids and len(nodes) < limit:
                    cls._append_network_node(
                        nodes,
                        node_ids,
                        category_order,
                        candidate.item_id,
                        target_info,
                    )

                link_id = frozenset((business_id, candidate.item_id))
                if candidate.item_id in node_ids and link_id not in link_ids:
                    links.append({
                        "source": business_id,
                        "target": candidate.item_id,
                        "value": round(candidate.score, 3),
                    })
                    link_ids.add(link_id)

        return {
            "nodes": nodes,
            "links": links,
            "categories": [{"name": cat} for cat in category_order],
        }

    @classmethod
    def _safe_similarity_mapping(
        cls,
        path: Path,
    ) -> dict[str, list[RecommendationCandidate]]:
        try:
            return similarity_cache.get(path)
        except (OSError, ValueError):
            return {}

    @classmethod
    def _get_business_metadata(
        cls,
        business_ids: set[str],
    ) -> dict[str, dict[str, Any]]:
        if not business_ids:
            return {}

        businesses = YelpBusiness.objects.filter(business_id__in=business_ids).values(
            "business_id",
            "name",
            "categories",
            "review_count",
        )
        metadata: dict[str, dict[str, Any]] = {}
        for item in businesses:
            categories = item["categories"] or ""
            metadata[item["business_id"]] = {
                "name": item["name"],
                "category": categories.split(",")[0].strip() if categories else "Other",
                "review_count": item["review_count"],
            }
        return metadata

    @classmethod
    def _append_network_node(
        cls,
        nodes: list[dict[str, Any]],
        node_ids: set[str],
        category_order: dict[str, int],
        business_id: str,
        info: dict[str, Any],
    ) -> None:
        category = info["category"]
        if category not in category_order:
            category_order[category] = len(category_order)
        nodes.append({
            "id": business_id,
            "name": info["name"],
            "category": category,
            "symbolSize": cls._network_symbol_size(info.get("review_count", 0)),
        })
        node_ids.add(business_id)

    @staticmethod
    def _network_symbol_size(review_count: Any) -> int:
        """根据真实评论数生成稳定的网络节点大小。"""
        try:
            count = int(review_count)
        except (TypeError, ValueError):
            count = 0
        return max(10, min(30, 10 + count // 50))
