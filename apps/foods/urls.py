from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.food_list, name='food_list'),

]
