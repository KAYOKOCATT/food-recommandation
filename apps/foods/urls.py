from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.food_list, name='food_list'),
    path('detail/<int:foodid>/', views.detail, name='food_detail'),
    path('recommendations/usercf/', views.usercf_recommendations, name='usercf_recommendations'),
    path('recommendations/statistics/', views.statistics_recommendations, name='statistics_recommendations'),

    path('addcollect/<int:foodid>/', views.addcollect, name='addcollect'),
    path('removecollect/<int:foodid>/', views.removecollect, name='removecollect'),
    path('comment/<int:foodid>/', views.comment, name='comment'),

]
