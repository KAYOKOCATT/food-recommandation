from django.urls import path

from . import admin_views

urlpatterns = [
    path("home/", admin_views.admin_home, name="admin_home"),
    path("users/", admin_views.user_list, name="admin_user_list"),
    path("users/create/", admin_views.user_create, name="admin_user_create"),
    path("users/<int:object_id>/edit/", admin_views.user_edit, name="admin_user_edit"),
    path("users/<int:object_id>/delete/", admin_views.user_delete, name="admin_user_delete"),
    path("foods/", admin_views.food_list, name="admin_food_list"),
    path("foods/create/", admin_views.food_create, name="admin_food_create"),
    path("foods/<int:object_id>/edit/", admin_views.food_edit, name="admin_food_edit"),
    path("foods/<int:object_id>/delete/", admin_views.food_delete, name="admin_food_delete"),
    path("collects/", admin_views.collect_list, name="admin_collect_list"),
    path("collects/create/", admin_views.collect_create, name="admin_collect_create"),
    path("collects/<int:object_id>/edit/", admin_views.collect_edit, name="admin_collect_edit"),
    path("collects/<int:object_id>/delete/", admin_views.collect_delete, name="admin_collect_delete"),
    path("comments/", admin_views.comment_list, name="admin_comment_list"),
    path("comments/create/", admin_views.comment_create, name="admin_comment_create"),
    path("comments/<int:object_id>/edit/", admin_views.comment_edit, name="admin_comment_edit"),
    path("comments/<int:object_id>/delete/", admin_views.comment_delete, name="admin_comment_delete"),
    path("yelp-businesses/", admin_views.yelp_business_list, name="admin_yelp_business_list"),
    path("yelp-businesses/create/", admin_views.yelp_business_create, name="admin_yelp_business_create"),
    path("yelp-businesses/<int:object_id>/edit/", admin_views.yelp_business_edit, name="admin_yelp_business_edit"),
    path("yelp-businesses/<int:object_id>/delete/", admin_views.yelp_business_delete, name="admin_yelp_business_delete"),
    path("yelp-reviews/", admin_views.yelp_review_list, name="admin_yelp_review_list"),
    path("yelp-reviews/create/", admin_views.yelp_review_create, name="admin_yelp_review_create"),
    path("yelp-reviews/<int:object_id>/edit/", admin_views.yelp_review_edit, name="admin_yelp_review_edit"),
    path("yelp-reviews/<int:object_id>/delete/", admin_views.yelp_review_delete, name="admin_yelp_review_delete"),
]
