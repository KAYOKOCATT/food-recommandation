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
from datetime import date, datetime
from typing import Any
from django.http import JsonResponse
from django.shortcuts import render
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from mypy.exportjson import Json

from apps.users.models import User
from .models import Foods, Comment, Collect


def food_list(request) -> Any:
    foodlist = Foods.objects.all()

    foodtypes = Foods.objects.values("foodtype").distinct()
    # 分类筛选
    selected_category = request.GET.get("category", 'all')

    if selected_category != 'all':
        foodlist = foodlist.filter(foodtype=selected_category)

    items_per_page = 18
    paginator = Paginator(foodlist, items_per_page)

    page_number = request.GET.get('page', 1)
    #异常处理
    try:
        page_number = int(page_number)
        if page_number < 1:
            page_number = 1
    except ValueError:
        page_number = 1

    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(paginator.num_pages)
    return render(request, "auth/food_list.html", {"page_obj": page_obj, "foodtypes": foodtypes, "selected_category": selected_category})

def detail(request, foodid: int = None):
    foodobj = Foods.objects.get(id=foodid)
    
    commentlist = Comment.objects.filter(fid=foodid)
    
    is_collect = False
    user_id = request.session.get("user_id")
    if user_id:
        is_collect = Collect.objects.filter(user_id=user_id, food=foodobj).exists()
        
    context = {
        "foodinfo": foodobj,
        "foodlist":food_list,
        "commentlist":commentlist,
        "is_collect":is_collect,#是否收藏
    }
    return render(request, "auth/food_detail.html", context)

def addcollect(request, foodid: int = None):
    if request.method == "POST":
        user_id =request.session.get("user_id")
        user = User.objects.get(id=user_id)
        foodobj = Foods.objects.get(id=foodid)
        if not Collect.objects.filter(user_id=user_id, food=foodobj).exists():
            collect_item = Collect(user=user, food=foodobj)
            collect_item.save()
        return JsonResponse({'status':'success','message':'收藏成功'})
    return JsonResponse({'status':'error','message':'收藏失败'},status=400)

def removecollect(request, foodid: int = None):
    if request.method == "POST":
        user_id =request.session.get("user_id")
        user = User.objects.get(id=user_id)
        foodobj = Foods.objects.get(id=foodid)
        if Collect.objects.filter(user_id=user_id, food=foodobj).exists():
            collect_item = Collect.objects.filter(user_id=user_id, food=foodobj).first()
            collect_item.delete()
        return JsonResponse({'status':'success','message':'取消收藏成功'})
    return JsonResponse({'status':'error','message':'取消收藏失败'},status=400)

def comment(request, foodid: int = None):
    if request.method == "POST":
        uid =request.session.get("user_id")
        user = User.objects.get(id=uid)
        realname = user.username
        comment_text = request.POST.get("comment",'')
        
        commentdata={
            "uid":uid,
            "fid":foodid,
            "realname":realname,
            "content":comment_text,
            "ctime":datetime.now(),
        }
        commentobj = Comment(**commentdata)
        commentobj.save()
        
        response_data = {
            "status":"success",
            "realname":realname,
            "comment":comment_text,
            "ctime":commentobj.ctime.strftime("%Y-%m-%d %H:%M:%S"),
        }
        return JsonResponse(response_data)
    return JsonResponse({'status':'error'},status=400)