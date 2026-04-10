from django.urls import path
from . import views

urlpatterns = [
    path('list/', views.food_list, name='food_list'),
    path('detail/<int:foodid>/', views.detail, name='food_detail'),
    
    path('addcollect/<int:foodid>/', views.addcollect, name='addcollect'),
    path('removecollect/<int:foodid>/', views.removecollect, name='removecollect'),

]
