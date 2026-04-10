from django.apps import AppConfig


class UserAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.users'  # 必须是完整的 Python 路径
    verbose_name = '用户管理'
    label = 'users'
