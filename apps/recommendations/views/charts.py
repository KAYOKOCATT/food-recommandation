""" 
图表API视图模块

提供四个图表数据的API端点：
1. 菜品分类统计 - /api/v1/charts/food-category-stats/
2. 用户行为趋势 - /api/v1/charts/user-activity-trend/
3. 餐厅地理分布 - /api/v1/charts/restaurant-geo/
4. 相似度网络图 - /api/v1/charts/similarity-network/

以及仪表板页面视图：
- /charts/dashboard/  数据可视化仪表板

响应格式统一为: {code: int, data: {}, msg: str}

依赖:
    - django.http.JsonResponse: JSON响应
    - django.shortcuts.render: 模板渲染
    - apps.recommendations.services.chart_service.ChartService: 数据服务
"""
# pylint: disable=broad-exception-caught
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render

from apps.recommendations.services.chart_service import ChartService


def api_response(code: int, msg: str, data: Any = None, status: int = 200) -> JsonResponse:
    """
    构建统一格式的API响应

    Args:
        code: 业务状态码，200表示成功
        msg: 响应消息
        data: 响应数据
        status: HTTP状态码

    Returns:
        JsonResponse: 格式化的JSON响应
    """
    return JsonResponse({
        "code": code,
        "msg": msg,
        "data": data
    }, status=status, json_dumps_params={"ensure_ascii": False})


class ChartView:
    """图表API视图类"""

    @staticmethod
    def dashboard(request: HttpRequest):
        """
        数据可视化仪表板页面

        GET /charts/dashboard/

        返回渲染的仪表板HTML页面
        """
        return render(request, 'charts/dashboard.html')

    @staticmethod
    def food_category_stats(request: HttpRequest) -> JsonResponse:
        """
        菜品分类统计API

        GET /api/v1/charts/food-category-stats/

        返回各菜品分类的平均价格和平均收藏数

        Response:
            {
                "code": 200,
                "msg": "success",
                "data": {
                    "categories": ["川菜", "粤菜", ...],
                    "avgPrices": [38.5, 45.2, ...],
                    "avgCollects": [12.3, 8.5, ...]
                }
            }
        """
        try:
            data = ChartService.get_food_category_stats()
            return api_response(code=200, msg="success", data=data)
        except Exception as e:
            return api_response(code=500, msg=f"数据获取失败: {str(e)}", data={}, status=500)

    @staticmethod
    def user_activity_trend(request: HttpRequest) -> JsonResponse:
        """
        用户行为趋势API

        GET /api/v1/charts/user-activity-trend/?days=30

        返回最近N天的用户注册、收藏、评论趋势

        Query Params:
            days: 统计天数，默认30，范围1-90

        Response:
            {
                "code": 200,
                "msg": "success",
                "data": {
                    "dates": ["2024-01-01", ...],
                    "registrations": [5, 8, ...],
                    "collects": [10, 15, ...],
                    "comments": [3, 6, ...]
                }
            }
        """
        try:
            # 获取并验证days参数
            days_str = request.GET.get("days", "30")
            try:
                days = int(days_str)
            except ValueError:
                return api_response(code=400, msg="days参数必须是整数", data={}, status=400)

            # 限制范围
            days = max(1, min(days, 90))

            data = ChartService.get_user_activity_trend(days=days)
            return api_response(code=200, msg="success", data=data)
        except Exception as e:
            return api_response(code=500, msg=f"数据获取失败: {str(e)}", data={}, status=500)

    @staticmethod
    def restaurant_geo(request: HttpRequest) -> JsonResponse:
        """
        餐厅地理分布API

        GET /api/v1/charts/restaurant-geo/?limit=1000

        返回餐厅的地理坐标、评分、评论数等信息

        Query Params:
            limit: 返回数据条数上限，默认1000，范围1-5000

        Response:
            {
                "code": 200,
                "msg": "success",
                "data": [
                    {
                        "name": "Restaurant Name",
                        "value": [longitude, latitude, stars, review_count],
                        "city": "City Name",
                        "categories": "..."
                    },
                    ...
                ]
            }
        """
        try:
            # 获取并验证limit参数
            limit_str = request.GET.get("limit", "1000")
            try:
                limit = int(limit_str)
            except ValueError:
                return api_response(code=400, msg="limit参数必须是整数", data={}, status=400)

            # 限制范围
            limit = max(1, min(limit, 5000))

            data = ChartService.get_restaurant_geo_data(limit=limit)
            return api_response(code=200, msg="success", data=data)
        except Exception as e:
            return api_response(code=500, msg=f"数据获取失败: {str(e)}", data={}, status=500)

    @staticmethod
    def similarity_network(request: HttpRequest) -> JsonResponse:
        """
        相似度网络图API

        GET /api/v1/charts/similarity-network/?limit=100&threshold=0.5

        返回推荐系统的相似度网络节点和边数据

        Query Params:
            limit: 节点数量上限，默认100，范围1-200
            threshold: 相似度阈值，默认0.5，范围0.1-1.0

        Response:
            {
                "code": 200,
                "msg": "success",
                "data": {
                    "nodes": [
                        {"id": "...", "name": "...", "category": "...", "symbolSize": 15}
                    ],
                    "links": [
                        {"source": "...", "target": "...", "value": 0.8}
                    ],
                    "categories": [
                        {"name": "..."}
                    ]
                }
            }
        """
        try:
            # 获取并验证参数
            limit_str = request.GET.get("limit", "100")
            threshold_str = request.GET.get("threshold", "0.5")

            try:
                limit = int(limit_str)
                threshold = float(threshold_str)
            except ValueError:
                return api_response(code=400, msg="参数格式错误", data={}, status=400)

            # 限制范围
            limit = max(1, min(limit, 200))
            threshold = max(0.1, min(threshold, 1.0))

            data = ChartService.get_similarity_network(
                limit=limit, similarity_threshold=threshold
            )
            return api_response(code=200, msg="success", data=data)
        except Exception as e:
            return api_response(code=500, msg=f"数据获取失败: {str(e)}", data={}, status=500)
