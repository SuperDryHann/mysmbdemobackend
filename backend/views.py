from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def b2c_auth_test(request):
    print(request.user)
    return Response({"message": "Yo! Test succeeded!"})