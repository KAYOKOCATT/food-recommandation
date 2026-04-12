
from typing import Dict, Optional

from .models import User

def user_info(request) -> Dict[str, Optional[User]]:
    """获取用户信息"""
    user_id = request.session.get('user_id')
    current_user = None
    
    if user_id:
        current_user = User.objects.filter(id=user_id).first()
    
    return {
        'user_info': current_user
    }
