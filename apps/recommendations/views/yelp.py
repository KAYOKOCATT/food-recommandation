from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.recommendations.models import YelpBusiness
from apps.recommendations.services import YelpService
from apps.users.models import User


def yelp_business_list(request: HttpRequest) -> HttpResponse:
    page_raw = request.GET.get("page", "1")
    q = request.GET.get("q", "")
    city = request.GET.get("city", "")
    try:
        page = int(page_raw)
    except ValueError:
        page = 1
    page_obj = YelpService.list_businesses(page=page, q=q, city=city)

    return render(
        request,
        "recommendations/yelp_business_list.html",
        {
            "page_obj": page_obj,
            "search_query": q,
            "selected_city": city,
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
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return User.objects.filter(id=user_id).first()


@require_POST
def submit_yelp_review(request: HttpRequest, business_id: str) -> JsonResponse:
    user = _session_user(request)
    if user is None:
        return JsonResponse({"status": "error", "message": "请先登录"}, status=401)

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
