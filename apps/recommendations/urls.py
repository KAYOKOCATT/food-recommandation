"""
推荐系统URL配置

图表API路由:
- /api/v1/charts/food-category-stats/     菜品分类统计
- /api/v1/charts/user-activity-trend/     用户行为趋势
- /api/v1/charts/restaurant-geo/          餐厅地理分布
- /api/v1/charts/similarity-network/      相似度网络图
"""
from django.urls import path

from apps.recommendations.views.charts import ChartView
from apps.recommendations.views.yelp import (
    submit_yelp_review,
    yelp_business_detail,
    yelp_business_list,
    yelp_recommendations,
)

app_name = "recommendations"

urlpatterns = [
    # 仪表板页面
    path("charts/dashboard/", ChartView.dashboard, name="dashboard"),
    path("yelp/restaurants/", yelp_business_list, name="yelp_business_list"),
    path("yelp/recommendations/", yelp_recommendations, name="yelp_recommendations"),
    path(
        "yelp/restaurants/<str:business_id>/",
        yelp_business_detail,
        name="yelp_business_detail",
    ),
    path(
        "yelp/restaurants/<str:business_id>/review/",
        submit_yelp_review,
        name="submit_yelp_review",
    ),
    # 图表API
    path("charts/food-category-stats/", ChartView.food_category_stats, name="food_category_stats"),
    path("charts/user-activity-trend/", ChartView.user_activity_trend, name="user_activity_trend"),
    path("charts/restaurant-geo/", ChartView.restaurant_geo, name="restaurant_geo"),
    path("charts/similarity-network/", ChartView.similarity_network, name="similarity_network"),
]
