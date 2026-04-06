from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.food_list, name='food_list'),
    path('list/api/', views.food_list_api, name='food_list_api'),

]
