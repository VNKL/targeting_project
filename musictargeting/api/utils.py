from musictargeting.api.models import User
from musictargeting.api.serializers import UserSerializer


def my_jwt_response_handler(token, user=None, request=None):
    user = User.objects.get(username=user)
    return {
        'token': token,
        'user': UserSerializer(user, context={'request': request}).data
    }