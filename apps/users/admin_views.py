from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.foods.models import Collect, Comment, Foods
from apps.foods.ingestion import (
    crawl_to_csv,
    csv_snapshot,
    delete_csv,
    import_csv_to_foods,
)
from apps.recommendations.models import YelpBusiness, YelpReview
from apps.users.admin_forms import (
    CollectAdminForm,
    CommentAdminForm,
    FoodCrawlForm,
    FoodImportForm,
    FoodsAdminForm,
    UserAdminForm,
    YelpBusinessAdminForm,
    YelpReviewAdminForm,
)
from apps.users.models import User
from apps.users.session_auth import SessionIdentity, require_identity


@dataclass(frozen=True)
class ResourceConfig:
    key: str
    label: str
    menu_group: str
    model: type
    form_class: type
    list_url_name: str
    create_url_name: str
    edit_url_name: str
    delete_url_name: str
    columns: list[tuple[str, Callable[[Any], str]]]
    filter_builder: Callable[[HttpRequest, QuerySet], QuerySet]


def admin_home(request: HttpRequest) -> HttpResponse:
    identity = _require_admin(request)
    if isinstance(identity, HttpResponse):
        return identity

    cards = [
        {
            "group": "用户与认证",
            "items": [_card("用户", User.objects.count(), "admin_user_list")],
        },
        {
            "group": "中文菜品数据",
            "items": [
                _card("菜品", Foods.objects.count(), "admin_food_list"),
                _card("收藏", Collect.objects.count(), "admin_collect_list"),
                _card("评论", Comment.objects.count(), "admin_comment_list"),
                _card("数据采集", 0, "admin_food_ingestion"),
            ],
        },
        {
            "group": "Yelp 数据",
            "items": [
                _card("商家", YelpBusiness.objects.count(), "admin_yelp_business_list"),
                _card("评论", YelpReview.objects.count(), "admin_yelp_review_list"),
            ],
        },        
    ]
    return render(
        request,
        "auth/admin/dashboard.html",
        {
            "admin_user": identity.user,
            "cards": cards,
        },
    )


def user_list(request: HttpRequest) -> HttpResponse:
    return _render_list(request, USER_CONFIG)


def user_create(request: HttpRequest) -> HttpResponse:
    return _render_form(request, USER_CONFIG)


def user_edit(request: HttpRequest, object_id: int) -> HttpResponse:
    return _render_form(request, USER_CONFIG, object_id=object_id)


def user_delete(request: HttpRequest, object_id: int) -> HttpResponse:
    return _delete_object(request, USER_CONFIG, object_id)


def food_list(request: HttpRequest) -> HttpResponse:
    return _render_list(request, FOOD_CONFIG)


def food_create(request: HttpRequest) -> HttpResponse:
    return _render_form(request, FOOD_CONFIG)


def food_edit(request: HttpRequest, object_id: int) -> HttpResponse:
    return _render_form(request, FOOD_CONFIG, object_id=object_id)


def food_delete(request: HttpRequest, object_id: int) -> HttpResponse:
    return _delete_object(request, FOOD_CONFIG, object_id)


def collect_list(request: HttpRequest) -> HttpResponse:
    return _render_list(request, COLLECT_CONFIG)


def collect_create(request: HttpRequest) -> HttpResponse:
    return _render_form(request, COLLECT_CONFIG)


def collect_edit(request: HttpRequest, object_id: int) -> HttpResponse:
    return _render_form(request, COLLECT_CONFIG, object_id=object_id)


def collect_delete(request: HttpRequest, object_id: int) -> HttpResponse:
    return _delete_object(request, COLLECT_CONFIG, object_id)


def comment_list(request: HttpRequest) -> HttpResponse:
    return _render_list(request, COMMENT_CONFIG)


def comment_create(request: HttpRequest) -> HttpResponse:
    return _render_form(request, COMMENT_CONFIG)


def comment_edit(request: HttpRequest, object_id: int) -> HttpResponse:
    return _render_form(request, COMMENT_CONFIG, object_id=object_id)


def comment_delete(request: HttpRequest, object_id: int) -> HttpResponse:
    return _delete_object(request, COMMENT_CONFIG, object_id)


def yelp_business_list(request: HttpRequest) -> HttpResponse:
    return _render_list(request, YELP_BUSINESS_CONFIG)


def yelp_business_create(request: HttpRequest) -> HttpResponse:
    return _render_form(request, YELP_BUSINESS_CONFIG)


def yelp_business_edit(request: HttpRequest, object_id: int) -> HttpResponse:
    return _render_form(request, YELP_BUSINESS_CONFIG, object_id=object_id)


def yelp_business_delete(request: HttpRequest, object_id: int) -> HttpResponse:
    return _delete_object(request, YELP_BUSINESS_CONFIG, object_id)


def yelp_review_list(request: HttpRequest) -> HttpResponse:
    return _render_list(request, YELP_REVIEW_CONFIG)


def yelp_review_create(request: HttpRequest) -> HttpResponse:
    return _render_form(request, YELP_REVIEW_CONFIG)


def yelp_review_edit(request: HttpRequest, object_id: int) -> HttpResponse:
    return _render_form(request, YELP_REVIEW_CONFIG, object_id=object_id)


def yelp_review_delete(request: HttpRequest, object_id: int) -> HttpResponse:
    return _delete_object(request, YELP_REVIEW_CONFIG, object_id)


def food_ingestion(request: HttpRequest) -> HttpResponse:
    identity = _require_admin(request)
    if isinstance(identity, HttpResponse):
        return identity

    crawl_form = FoodCrawlForm()
    import_form = FoodImportForm()
    if request.method == "POST":
        action = request.POST.get("action", "")
        try:
            if action == "crawl":
                crawl_form = FoodCrawlForm(request.POST)
                if crawl_form.is_valid():
                    result = crawl_to_csv(
                        crawl_form.cleaned_data["source_url"],
                        crawl_form.cleaned_data["page_count"],
                    )
                    messages.success(
                        request,
                        f"抓取完成：共写入 {result.row_count} 条记录到 {result.csv_path.name}。",
                    )
                    return redirect("admin_food_ingestion")
            elif action == "import":
                import_form = FoodImportForm(request.POST)
                if import_form.is_valid():
                    result = import_csv_to_foods(
                        clear_existing=bool(import_form.cleaned_data["clear_existing"])
                    )
                    extra = ""
                    if result.cleared_count:
                        extra = f"，导入前已清空 {result.cleared_count} 条旧菜品"
                    messages.success(
                        request,
                        f"导入完成：新增 {result.created_count} 条菜品{extra}。",
                    )
                    return redirect("admin_food_ingestion")
            elif action == "delete_csv":
                deleted = delete_csv()
                if deleted:
                    messages.success(request, "CSV 文件已删除。")
                else:
                    messages.info(request, "CSV 文件不存在，无需删除。")
                return redirect("admin_food_ingestion")
            else:
                messages.error(request, "未知操作。")
        except Exception as exc:  # pylint: disable=broad-except
            messages.error(request, f"操作失败：{exc}")

    context = {
        "menu_group": "中文菜品数据",
        "csv_info": csv_snapshot(),
        "crawl_form": crawl_form,
        "import_form": import_form,
        "food_count": Foods.objects.count(),
    }
    return render(request, "auth/admin/food_ingestion.html", context)


def _render_list(request: HttpRequest, config: ResourceConfig) -> HttpResponse:
    identity = _require_admin(request)
    if isinstance(identity, HttpResponse):
        return identity

    queryset = config.filter_builder(request, _base_queryset(config))
    page_obj = Paginator(queryset, 12).get_page(request.GET.get("page", 1))
    rows = [
        {
            "cells": [renderer(obj) for _, renderer in config.columns],
            "edit_url": reverse(config.edit_url_name, args=[obj.pk]),
            "delete_url": reverse(config.delete_url_name, args=[obj.pk]),
        }
        for obj in page_obj.object_list
    ]
    return render(
        request,
        "auth/admin/resource_list.html",
        {
            "resource_label": config.label,
            "menu_group": config.menu_group,
            "columns": [label for label, _ in config.columns],
            "rows": rows,
            "page_obj": page_obj,
            "create_url": reverse(config.create_url_name),
            "filters": _build_filters(config.key, request),
        },
    )


def _render_form(
    request: HttpRequest,
    config: ResourceConfig,
    *,
    object_id: int | None = None,
) -> HttpResponse:
    identity = _require_admin(request)
    if isinstance(identity, HttpResponse):
        return identity

    instance = get_object_or_404(config.model, pk=object_id) if object_id is not None else None
    old_food_ids = _related_food_ids(instance)

    if request.method == "POST":
        form = config.form_class(request.POST, instance=instance)
        if form.is_valid():
            obj = form.save()
            _sync_related_food_counts(config.key, old_food_ids | _related_food_ids(obj))
            messages.success(request, f"{config.label}已保存。")
            return redirect(config.list_url_name)
    else:
        form = config.form_class(instance=instance)

    return render(
        request,
        "auth/admin/resource_form.html",
        {
            "resource_label": config.label,
            "menu_group": config.menu_group,
            "form": form,
            "list_url": reverse(config.list_url_name),
            "is_edit": object_id is not None,
        },
    )


def _delete_object(request: HttpRequest, config: ResourceConfig, object_id: int) -> HttpResponse:
    identity = _require_admin(request)
    if isinstance(identity, HttpResponse):
        return identity

    if request.method != "POST":
        return redirect(config.list_url_name)

    instance = get_object_or_404(config.model, pk=object_id)
    affected_food_ids = _related_food_ids(instance)
    instance.delete()
    _sync_related_food_counts(config.key, affected_food_ids)
    messages.success(request, f"{config.label}已删除。")
    return redirect(config.list_url_name)


def _base_queryset(config: ResourceConfig) -> QuerySet:
    if config.key == "users":
        return User.objects.order_by("-regtime", "-id")
    if config.key == "foods":
        return Foods.objects.order_by("id")
    if config.key == "collects":
        return Collect.objects.select_related("user", "food").order_by("-added_time", "-id")
    if config.key == "comments":
        return Comment.objects.order_by("-ctime", "-id")
    if config.key == "yelp_businesses":
        return YelpBusiness.objects.order_by("-review_count", "name")
    return YelpReview.objects.select_related("user", "business").order_by("-review_date", "-id")


def _build_filters(resource_key: str, request: HttpRequest) -> list[dict[str, Any]]:
    q = request.GET.get("q", "")
    shared = [{"name": "q", "label": "关键词", "value": q, "type": "text"}]
    if resource_key == "users":
        shared.append(
            {
                "name": "source",
                "label": "来源",
                "value": request.GET.get("source", ""),
                "type": "select",
                "options": [("", "全部"), ("local", "local"), ("yelp", "yelp")],
            }
        )
    elif resource_key == "foods":
        shared.append(
            {
                "name": "foodtype",
                "label": "分类",
                "value": request.GET.get("foodtype", ""),
                "type": "text",
            }
        )
    elif resource_key == "collects":
        shared.extend(
            [
                {"name": "user_id", "label": "用户 ID", "value": request.GET.get("user_id", ""), "type": "text"},
                {"name": "food_id", "label": "菜品 ID", "value": request.GET.get("food_id", ""), "type": "text"},
            ]
        )
    elif resource_key == "comments":
        shared.extend(
            [
                {"name": "uid", "label": "用户 ID", "value": request.GET.get("uid", ""), "type": "text"},
                {"name": "fid", "label": "菜品 ID", "value": request.GET.get("fid", ""), "type": "text"},
            ]
        )
    elif resource_key == "yelp_businesses":
        shared.extend(
            [
                {"name": "state", "label": "州", "value": request.GET.get("state", ""), "type": "text"},
                {
                    "name": "is_open",
                    "label": "营业状态",
                    "value": request.GET.get("is_open", ""),
                    "type": "select",
                    "options": [("", "全部"), ("1", "营业中"), ("0", "已关闭")],
                },
            ]
        )
    elif resource_key == "yelp_reviews":
        shared.extend(
            [
                {"name": "user_id", "label": "用户 ID", "value": request.GET.get("user_id", ""), "type": "text"},
                {"name": "business_id", "label": "商家 ID", "value": request.GET.get("business_id", ""), "type": "text"},
                {"name": "source", "label": "来源", "value": request.GET.get("source", ""), "type": "text"},
            ]
        )
    return shared


def _filter_users(request: HttpRequest, queryset: QuerySet) -> QuerySet:
    q = request.GET.get("q", "").strip()
    source = request.GET.get("source", "").strip()
    if q:
        queryset = queryset.filter(
            Q(username__icontains=q) | Q(email__icontains=q) | Q(phone__icontains=q)
        )
    if source:
        queryset = queryset.filter(source=source)
    return queryset


def _filter_foods(request: HttpRequest, queryset: QuerySet) -> QuerySet:
    q = request.GET.get("q", "").strip()
    foodtype = request.GET.get("foodtype", "").strip()
    if q:
        queryset = queryset.filter(Q(foodname__icontains=q) | Q(recommend__icontains=q))
    if foodtype:
        queryset = queryset.filter(foodtype__icontains=foodtype)
    return queryset


def _filter_collects(request: HttpRequest, queryset: QuerySet) -> QuerySet:
    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(Q(user__username__icontains=q) | Q(food__foodname__icontains=q))
    if request.GET.get("user_id", "").strip():
        queryset = queryset.filter(user_id=request.GET["user_id"].strip())
    if request.GET.get("food_id", "").strip():
        queryset = queryset.filter(food_id=request.GET["food_id"].strip())
    return queryset


def _filter_comments(request: HttpRequest, queryset: QuerySet) -> QuerySet:
    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(Q(realname__icontains=q) | Q(content__icontains=q))
    if request.GET.get("uid", "").strip():
        queryset = queryset.filter(uid=request.GET["uid"].strip())
    if request.GET.get("fid", "").strip():
        queryset = queryset.filter(fid=request.GET["fid"].strip())
    return queryset


def _filter_yelp_businesses(request: HttpRequest, queryset: QuerySet) -> QuerySet:
    q = request.GET.get("q", "").strip()
    state = request.GET.get("state", "").strip()
    is_open = request.GET.get("is_open", "").strip()
    if q:
        queryset = queryset.filter(Q(name__icontains=q) | Q(categories__icontains=q) | Q(city__icontains=q))
    if state:
        queryset = queryset.filter(state__icontains=state)
    if is_open in {"0", "1"}:
        queryset = queryset.filter(is_open=(is_open == "1"))
    return queryset


def _filter_yelp_reviews(request: HttpRequest, queryset: QuerySet) -> QuerySet:
    q = request.GET.get("q", "").strip()
    if q:
        queryset = queryset.filter(
            Q(review_id__icontains=q) | Q(text__icontains=q) | Q(business__name__icontains=q)
        )
    if request.GET.get("user_id", "").strip():
        queryset = queryset.filter(user_id=request.GET["user_id"].strip())
    if request.GET.get("business_id", "").strip():
        queryset = queryset.filter(business__business_id__icontains=request.GET["business_id"].strip())
    if request.GET.get("source", "").strip():
        queryset = queryset.filter(source__icontains=request.GET["source"].strip())
    return queryset


def _related_food_ids(instance: Any | None) -> set[int]:
    if instance is None:
        return set()
    if isinstance(instance, Collect):
        return {instance.food_id}
    if isinstance(instance, Comment):
        return {instance.fid}
    return set()


def _sync_related_food_counts(resource_key: str, food_ids: set[int]) -> None:
    if resource_key not in {"collects", "comments"} or not food_ids:
        return

    collect_counts = {
        item["food_id"]: item["count"]
        for item in Collect.objects.filter(food_id__in=food_ids)
        .values("food_id")
        .annotate(count=Count("id"))
    }
    comment_counts = {
        item["fid"]: item["count"]
        for item in Comment.objects.filter(fid__in=food_ids)
        .values("fid")
        .annotate(count=Count("id"))
    }
    for food in Foods.objects.filter(id__in=food_ids):
        food.collect_count = collect_counts.get(food.id, 0)
        food.comment_count = comment_counts.get(food.id, 0)
        food.save(update_fields=["collect_count", "comment_count"])


def _card(label: str, count: int, url_name: str) -> dict[str, Any]:
    return {"label": label, "count": count, "url_name": url_name}


def _require_admin(request: HttpRequest) -> SessionIdentity | HttpResponse:
    return require_identity(request, allow_admin=True)


USER_CONFIG = ResourceConfig(
    key="users",
    label="用户",
    menu_group="用户与认证",
    model=User,
    form_class=UserAdminForm,
    list_url_name="admin_user_list",
    create_url_name="admin_user_create",
    edit_url_name="admin_user_edit",
    delete_url_name="admin_user_delete",
    columns=[
        ("ID", lambda obj: str(obj.id)),
        ("用户名", lambda obj: obj.username),
        ("来源", lambda obj: obj.source),
        ("邮箱", lambda obj: obj.email or "-"),
        ("手机号", lambda obj: obj.phone or "-"),
    ],
    filter_builder=_filter_users,
)

FOOD_CONFIG = ResourceConfig(
    key="foods",
    label="菜品",
    menu_group="中文菜品数据",
    model=Foods,
    form_class=FoodsAdminForm,
    list_url_name="admin_food_list",
    create_url_name="admin_food_create",
    edit_url_name="admin_food_edit",
    delete_url_name="admin_food_delete",
    columns=[
        ("ID", lambda obj: str(obj.id)),
        ("菜名", lambda obj: obj.foodname),
        ("分类", lambda obj: obj.foodtype),
        ("价格", lambda obj: f"{obj.price}"),
        ("收藏/评论", lambda obj: f"{obj.collect_count} / {obj.comment_count}"),
    ],
    filter_builder=_filter_foods,
)

COLLECT_CONFIG = ResourceConfig(
    key="collects",
    label="收藏",
    menu_group="中文菜品数据",
    model=Collect,
    form_class=CollectAdminForm,
    list_url_name="admin_collect_list",
    create_url_name="admin_collect_create",
    edit_url_name="admin_collect_edit",
    delete_url_name="admin_collect_delete",
    columns=[
        ("ID", lambda obj: str(obj.id)),
        ("用户", lambda obj: obj.user.username),
        ("菜品", lambda obj: obj.food.foodname),
        ("收藏时间", lambda obj: obj.added_time.strftime("%Y-%m-%d %H:%M") if obj.added_time else "-"),
    ],
    filter_builder=_filter_collects,
)

COMMENT_CONFIG = ResourceConfig(
    key="comments",
    label="评论",
    menu_group="中文菜品数据",
    model=Comment,
    form_class=CommentAdminForm,
    list_url_name="admin_comment_list",
    create_url_name="admin_comment_create",
    edit_url_name="admin_comment_edit",
    delete_url_name="admin_comment_delete",
    columns=[
        ("ID", lambda obj: str(obj.id)),
        ("用户 ID", lambda obj: str(obj.uid)),
        ("菜品 ID", lambda obj: str(obj.fid)),
        ("昵称", lambda obj: obj.realname),
        ("内容", lambda obj: obj.content[:40]),
    ],
    filter_builder=_filter_comments,
)

YELP_BUSINESS_CONFIG = ResourceConfig(
    key="yelp_businesses",
    label="Yelp 商家",
    menu_group="Yelp 数据",
    model=YelpBusiness,
    form_class=YelpBusinessAdminForm,
    list_url_name="admin_yelp_business_list",
    create_url_name="admin_yelp_business_create",
    edit_url_name="admin_yelp_business_edit",
    delete_url_name="admin_yelp_business_delete",
    columns=[
        ("ID", lambda obj: str(obj.id)),
        # ("业务 ID", lambda obj: obj.business_id),
        ("名称", lambda obj: obj.name),
        ("城市/州", lambda obj: f"{obj.city or '-'} / {obj.state or '-'}"),
        ("评分", lambda obj: f"{obj.stars}"),
    ],
    filter_builder=_filter_yelp_businesses,
)

YELP_REVIEW_CONFIG = ResourceConfig(
    key="yelp_reviews",
    label="Yelp 评论",
    menu_group="Yelp 数据",
    model=YelpReview,
    form_class=YelpReviewAdminForm,
    list_url_name="admin_yelp_review_list",
    create_url_name="admin_yelp_review_create",
    edit_url_name="admin_yelp_review_edit",
    delete_url_name="admin_yelp_review_delete",
    columns=[
        ("ID", lambda obj: str(obj.id)),
        ("评论 ID", lambda obj: obj.review_id),
        ("商家", lambda obj: obj.business.name),
        ("用户", lambda obj: obj.user.username),
        ("评分", lambda obj: f"{obj.stars}"),
    ],
    filter_builder=_filter_yelp_reviews,
)
