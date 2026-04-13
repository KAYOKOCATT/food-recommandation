from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login, name='login'),
    path('login/yelp-demo/', views.login_yelp_demo, name='login_yelp_demo'),
    path('login/admin-demo/', views.login_admin_demo, name='login_admin_demo'),
    path('logout/', views.logout, name='logout'),
    path('register/', views.register, name='register'),
    path('home/', views.user_index, name='user_home'),
    path('home/wordclouds/<str:kind>/', views.home_wordcloud_image, name='home_wordcloud_image'),
    path('profile/', views.user_view, name='user_profile'),
    path('password/', views.change_password, name='change_password'),

]
