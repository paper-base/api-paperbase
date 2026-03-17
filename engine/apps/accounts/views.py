from django.contrib.auth import get_user_model
from rest_framework import permissions, views, status
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from engine.apps.stores.models import StoreMembership

from .serializers import MeSerializer

User = get_user_model()


class StoreAwareTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Extend JWT payload with `active_store_id` claim.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        membership = (
            StoreMembership.objects.filter(user=user, is_active=True)
            .order_by("created_at")
            .first()
        )
        if membership:
            token["active_store_id"] = membership.store_id
        return token


class StoreAwareTokenObtainPairView(TokenObtainPairView):
    serializer_class = StoreAwareTokenObtainPairSerializer


class MeView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = MeSerializer(request.user, context={"request": request})
        return Response(serializer.data)


class SwitchStoreView(views.APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        store_id = request.data.get("store_id")
        if not store_id:
            return Response(
                {"detail": "store_id is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            membership = StoreMembership.objects.select_related("store").get(
                user=request.user,
                store_id=store_id,
                is_active=True,
            )
        except (StoreMembership.DoesNotExist, ValueError):
            return Response(
                {"detail": "You do not have access to this store."},
                status=status.HTTP_403_FORBIDDEN,
            )

        refresh = RefreshToken.for_user(request.user)
        refresh["active_store_id"] = membership.store_id
        access = refresh.access_token
        access["active_store_id"] = membership.store_id

        return Response(
            {"access": str(access), "refresh": str(refresh), "active_store_id": membership.store_id},
            status=status.HTTP_200_OK,
        )

