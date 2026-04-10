from .models import User

def user_info(request):
    current_user = None
    user_id = request.session.get('user_id')
    if user_id:
        current_user = User.objects.filter(id=user_id).first()
    return {
        'user_info': current_user
        }
