from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('register/', views.register, name='register'),
    path('user_index/', views.user_index, name='user_index'),
    
    path('user_view/',views.user_view,name='user_view'),
    path('change_password/',views.change_password,name='change_password'),

]
