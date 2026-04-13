from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.recommendations.models import YelpBusiness
from apps.recommendations.services import YelpService
from apps.users.models import User
from apps.users.session_auth import build_identity, require_identity


def yelp_business_list(request: HttpRequest) -> HttpResponse:
    page_raw = request.GET.get("page", "1")
    q = request.GET.get("q", "")
    city = request.GET.get("city", "")
    is_open_only = request.GET.get("is_open") == "1"
    try:
        page = int(page_raw)
    except ValueError:
        page = 1
    page_obj = YelpService.list_businesses(
        page=page,
        q=q,
        city=city,
        is_open_only=is_open_only,
    )

    return render(
        request,
        "recommendations/yelp_business_list.html",
        {
            "page_obj": page_obj,
            "search_query": q,
            "selected_city": city,
            "is_open_only": is_open_only,
        },
    )


def yelp_business_detail(request: HttpRequest, business_id: str) -> HttpResponse:
    business = get_object_or_404(YelpBusiness, business_id=business_id)
    current_user = _session_user(request)
    return render(
        request,
        "recommendations/yelp_business_detail.html",
        {
            "business": business,
            "similar_businesses": YelpService.get_similar_businesses(business.business_id, top_k=6),
            "recent_reviews": YelpService.get_recent_reviews(business, limit=5),
            "current_user": current_user,
        },
    )


def _session_user(request: HttpRequest) -> User | None:
    return build_identity(request).user


@require_POST
def submit_yelp_review(request: HttpRequest, business_id: str) -> JsonResponse:
    identity = require_identity(
        request,
        allow_local_user=True,
        allow_yelp_demo_user=True,
        api=True,
    )
    if isinstance(identity, JsonResponse):
        return identity
    user = identity.user

    business = get_object_or_404(YelpBusiness, business_id=business_id)
    stars_raw = request.POST.get("stars", "").strip()
    comment_text = request.POST.get("comment", "").strip()

    try:
        stars = float(stars_raw)
    except ValueError:
        return JsonResponse({"status": "error", "message": "评分格式不正确"}, status=400)

    if stars < 1.0 or stars > 5.0:
        return JsonResponse({"status": "error", "message": "评分必须在1到5之间"}, status=400)

    review = YelpService.create_local_review(
        business=business,
        user_id=user.id,
        stars=stars,
        text=comment_text,
    )
    return JsonResponse(
        {
            "status": "success",
            "message": "评分已提交",
            "review": {
                "username": user.username,
                "stars": review.stars,
                "comment": review.text,
                "review_date": review.review_date.strftime("%Y-%m-%d %H:%M:%S")
                if review.review_date
                else "",
                "source": review.source,
            },
        }
    )


def yelp_recommendations(request: HttpRequest) -> HttpResponse:
    identity = require_identity(
        request,
        allow_local_user=True,
        allow_yelp_demo_user=True,
    )
    if isinstance(identity, JsonResponse):
        return identity
    if isinstance(identity, HttpResponse):
        return identity

    recommendations, has_recent_activity = YelpService.get_recent_recommendations(
        identity.user.id,
        top_k=12,
    )
    return render(
        request,
        "recommendations/yelp_recommendations.html",
        {
            "recommendations": recommendations,
            "has_recent_activity": has_recent_activity,
        },
    )


def yelp_als_recommendations(request: HttpRequest) -> HttpResponse:
    identity = require_identity(
        request,
        allow_local_user=True,
        allow_yelp_demo_user=True,
    )
    if isinstance(identity, JsonResponse):
        return identity
    if isinstance(identity, HttpResponse):
        return identity

    recommendations = YelpService.get_als_recommendations(
        identity.user.id,
        top_k=12,
    )
    if recommendations:
        return render(
            request,
            "recommendations/yelp_als_recommendations.html",
            {
                "recommendations": recommendations,
                "used_fallback": False,
            },
        )

    return render(
        request,
        "recommendations/yelp_als_recommendations.html",
        {
            "recommendations": YelpService.get_popular_recommendations(top_k=12),
            "used_fallback": True,
        },
    )
