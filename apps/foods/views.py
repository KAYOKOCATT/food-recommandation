"""
菜品相关视图模块
处理菜品相关的 HTTP 请求，包括列表查询等。
依赖：
    - django.shortcuts.render: 渲染 HTML 模板
    - django.http: HTTP 响应类
路由配置：
    # urls.py
    from django.urls import path
    from apps.foods.views import food_list
    urlpatterns = [
        path('list/', food_list, name='food_list'),
    ]
"""

from django.shortcuts import render
from django.http import HttpRequest, JsonResponse
from typing import Any
from .models import Foods


def food_list(request: HttpRequest) -> Any:
    """
    菜品列表视图 - 查询 myapp_foods 表

    返回：
        渲染的 HTML 页面，包含所有菜品数据
    """
    # 查询所有菜品
    foods = Foods.objects.all().order_by('-id')

    # 统计信息
    total_count = foods.count()

    return render(request, 'foods/list.html', {
        'foods': foods,
        'total_count': total_count,
    })


def food_list_api(request: HttpRequest) -> JsonResponse:
    """
    菜品列表 API - 返回 JSON 数据

    用于前端 AJAX 请求获取菜品列表
    """
    # 查询所有菜品
    foods = Foods.objects.all().order_by('-id')

    # 转换为字典列表
    food_list = []
    for food in foods:
        food_list.append({
            'id': food.id,
            'foodname': food.foodname,
            'foodtype': food.foodtype,
            'recommand': food.recommand,
            'imgurl': food.imgurl,
            'price': str(food.price),  # Decimal 需要转字符串
        })

    return JsonResponse({
        'code': 200,
        'msg': '查询成功',
        'data': {
            'foods': food_list,
            'total': len(food_list),
        }
    })