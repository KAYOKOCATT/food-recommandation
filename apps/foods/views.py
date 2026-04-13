from typing import Any

from django.conf import settings
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import F, Q
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.users.models import User
from apps.users.session_auth import build_identity, require_identity
from .models import Collect, Comment, Foods
from .services import similar_foods_for_detail, recommend_foods_by_usercf, popular_foods, most_favorited_foods


def food_list(request) -> Any:
    foodlist = Foods.objects.all().order_by("id")

    foodtypes = Foods.objects.values("foodtype").distinct().order_by("foodtype")
    # 分类筛选
    selected_category = request.GET.get("category", 'all')
    search_query = request.GET.get("q", "").strip()

    if selected_category != 'all':
        foodlist = foodlist.filter(foodtype=selected_category)
    if search_query:
        foodlist = foodlist.filter(Q(foodname__icontains=search_query))

    items_per_page = 18
    paginator = Paginator(foodlist, items_per_page)

    page_number = request.GET.get('page', 1)
    #异常处理
    try:
        page_number = int(page_number)
        page_number = max(page_number, 1)
    except ValueError:
        page_number = 1

    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(paginator.num_pages)
    context = {
        "page_obj": page_obj,
        "foodtypes": foodtypes,
        "selected_category": selected_category,
        "search_query": search_query,
    }
    return render(request, "auth/food_list.html", context)


def detail(request, foodid: int):
    foodobj = get_object_or_404(Foods, id=foodid)
    commentlist = Comment.objects.filter(fid=foodid).order_by("-ctime")
    similarity_file = settings.BASE_DIR / "data" / "recommendations" / "food_itemcf.json"

    is_collect = False
    user_id = request.session.get("user_id")
    if user_id:
        is_collect = Collect.objects.filter(user_id=user_id, food=foodobj).exists()

    context = {
        "foodinfo": foodobj,
        "foodlist": food_list,
        "commentlist": commentlist,
        "is_collect": is_collect,  # 是否收藏
        "similar_foods": similar_foods_for_detail(foodid, similarity_file, top_k=6),
    }
    return render(request, "auth/food_detail.html", context)


def _session_user(request) -> User | None:
    return build_identity(request).user


@require_POST
def addcollect(request, foodid: int):
    identity = require_identity(request, allow_local_user=True, api=True)
    if isinstance(identity, JsonResponse):
        return identity
    user = identity.user

    foodobj = get_object_or_404(Foods, id=foodid)
    _, created = Collect.objects.get_or_create(user=user, food=foodobj)
    if created:
        Foods.objects.filter(id=foodobj.id).update(collect_count=F("collect_count") + 1)
    return JsonResponse({'status': 'success', 'message': '收藏成功'})


@require_POST
def removecollect(request, foodid: int):
    identity = require_identity(request, allow_local_user=True, api=True)
    if isinstance(identity, JsonResponse):
        return identity
    user = identity.user

    foodobj = get_object_or_404(Foods, id=foodid)
    deleted_count, _ = Collect.objects.filter(user=user, food=foodobj).delete()
    if deleted_count:
        Foods.objects.filter(id=foodobj.id, collect_count__gt=0).update(
            collect_count=F("collect_count") - 1
        )
    return JsonResponse({'status': 'success', 'message': '取消收藏成功'})


@require_POST
def comment(request, foodid: int):
    identity = require_identity(request, allow_local_user=True, api=True)
    if isinstance(identity, JsonResponse):
        return identity
    user = identity.user

    comment_text = request.POST.get("comment", "").strip()
    if not comment_text:
        return JsonResponse({'status': 'error', 'message': '评论内容不能为空'}, status=400)

    get_object_or_404(Foods, id=foodid)
    commentobj = Comment.objects.create(
        uid=user.id,
        fid=foodid,
        realname=user.username,
        content=comment_text,
        ctime=timezone.now(),
    )
    Foods.objects.filter(id=foodid).update(comment_count=F("comment_count") + 1)

    response_data = {
        "status": "success",
        "realname": user.username,
        "comment": comment_text,
        "ctime": timezone.localtime(commentobj.ctime).strftime("%Y-%m-%d %H:%M:%S"),
    }
    return JsonResponse(response_data)


def usercf_recommendations(request):
    """
    UserCF个性化推荐页面
    根据当前登录用户的收藏历史，展示基于相似用户的推荐菜品
    """
    identity = require_identity(request, allow_local_user=True)
    if isinstance(identity, JsonResponse):
        return identity
    if isinstance(identity, HttpResponse):
        return identity
    user_id = identity.user.id

    recommendation_file = settings.BASE_DIR / "data" / "recommendations" / "food_usercf.json"

    # 获取UserCF推荐结果
    recommendations = recommend_foods_by_usercf(user_id, recommendation_file, top_k=20)

    # 如果无推荐结果，重定向到首页（首页展示热门推荐）
    if not recommendations:
        return redirect("user_home")

    context = {
        "recommendations": recommendations,
        "user_id": user_id,
    }
    return render(request, "auth/usercf_recommendations.html", context)


def statistics_recommendations(request):
    """
    统计推荐页面（首页默认推荐）
    为冷启动用户展示基于统计的热门推荐内容
    无需登录即可访问
    """
    # 获取热门精选（综合排序）
    popular = popular_foods(limit=12)

    # 获取人气收藏（按收藏数排序）
    most_favorited = most_favorited_foods(limit=12)

    context = {
        "popular_foods": popular,
        "most_favorited_foods": most_favorited,
    }
    return render(request, "auth/statistics_recommendations.html", context)
