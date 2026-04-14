from __future__ import annotations

from rest_framework import serializers


class FraudCheckRequestSerializer(serializers.Serializer):
    phone = serializers.CharField()

