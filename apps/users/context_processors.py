from tkinter import N

from test.test_reprlib import r

from .models import User

def user_info(request):
    user_info = None
    user_id = request.session.get('user_id')
    if user_id:
        user_info = User.objects.filter(id=user_id).first()
    return {
        'user_info': user_info
        }
