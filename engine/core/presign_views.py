import os
import uuid

import boto3
from django.conf import settings
from rest_framework import serializers as drf_serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from config.permissions import DenyAPIKeyAccess, IsPlatformSuperuserOrStoreAdmin
from engine.core.tenancy import require_valid_store_context

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB hard limit

ENTITY_FOLDERS = {
    "product": "products",
    "blog": "blogs",
    "banner": "banners",
    "category": "categories",
    "support": "support",
}


class PresignUploadRequestSerializer(drf_serializers.Serializer):
    filename = drf_serializers.CharField(required=False, allow_blank=True, default="")
    content_type = drf_serializers.CharField()
    entity = drf_serializers.ChoiceField(choices=tuple(ENTITY_FOLDERS.keys()))
    file_size = drf_serializers.IntegerField(min_value=0, max_value=MAX_FILE_SIZE)
    entity_public_id = drf_serializers.CharField(required=False, allow_blank=True, default="")
    is_gallery = drf_serializers.BooleanField(required=False, default=False)

    def validate_content_type(self, value: str) -> str:
        content_type = (value or "").strip().lower()
        if content_type not in ALLOWED_CONTENT_TYPES:
            raise drf_serializers.ValidationError("Invalid file type.")
        return content_type


class PresignUploadView(APIView):
    permission_classes = [DenyAPIKeyAccess, IsPlatformSuperuserOrStoreAdmin]

    # IMPORTANT: R2 bucket must have the following CORS rule configured
    # in the Cloudflare dashboard for direct browser uploads to work:
    #
    # [
    #   {
    #     "AllowedOrigins": ["https://your-admin-domain.com"],
    #     "AllowedMethods": ["PUT"],
    #     "AllowedHeaders": ["Content-Type", "Content-Length"],
    #     "MaxAgeSeconds": 3000
    #   }
    # ]
    #
    # Without this, browsers will block the direct PUT to R2 (CORS error).

    def post(self, request):
        payload = PresignUploadRequestSerializer(data=request.data)
        payload.is_valid(raise_exception=True)
        data = payload.validated_data

        store, _ = require_valid_store_context(request)

        # Tenant namespace is derived from proven active store context.
        tenant_id = store.public_id
        folder = ENTITY_FOLDERS[data["entity"]]
        ext = os.path.splitext(data.get("filename", ""))[1].lower().lstrip(".") or "jpg"
        unique = uuid.uuid4().hex
        entity_public_id = (data.get("entity_public_id") or "").strip()
        is_gallery = data.get("is_gallery", False)
        # DB key must not include storage location prefix; Django storage adds it when resolving URLs.
        if data["entity"] == "product" and entity_public_id:
            if is_gallery:
                db_key = f"tenants/{tenant_id}/products/{entity_public_id}/gallery/{unique}.{ext}"
            else:
                db_key = f"tenants/{tenant_id}/products/{entity_public_id}/main_{unique}.{ext}"
        elif data["entity"] == "blog" and entity_public_id:
            db_key = f"tenants/{tenant_id}/blogs/{entity_public_id}/featured_{unique}.{ext}"
        elif data["entity"] == "category" and entity_public_id:
            db_key = f"tenants/{tenant_id}/categories/{entity_public_id}.{ext}"
        else:
            db_key = f"tenants/{tenant_id}/{folder}/{unique}.{ext}"
        # Bucket key includes storage location prefix for direct browser PUT.
        bucket_key = f"media/{db_key}"

        client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            region_name=getattr(settings, "AWS_S3_REGION_NAME", "auto"),
        )
        presigned_url = client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.AWS_STORAGE_BUCKET_NAME,
                "Key": bucket_key,
                "ContentType": data["content_type"],
                "ContentLength": data["file_size"],
            },
            ExpiresIn=300,
        )
        return Response({"url": presigned_url, "key": db_key})
