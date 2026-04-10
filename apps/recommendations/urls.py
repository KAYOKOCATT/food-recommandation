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

app_name = "recommendations"

urlpatterns = [
    # 仪表板页面
    path("charts/dashboard/", ChartView.dashboard, name="dashboard"),
    # 图表API
    path("charts/food-category-stats/", ChartView.food_category_stats, name="food_category_stats"),
    path("charts/user-activity-trend/", ChartView.user_activity_trend, name="user_activity_trend"),
    path("charts/restaurant-geo/", ChartView.restaurant_geo, name="restaurant_geo"),
    path("charts/similarity-network/", ChartView.similarity_network, name="similarity_network"),
]
