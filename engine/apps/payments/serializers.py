from rest_framework import serializers
from .models import PaymentMethod, Payment


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = ['id', 'name', 'method_type']


class PaymentInitiateSerializer(serializers.Serializer):
    order_id = serializers.UUIDField()
    payment_method_id = serializers.IntegerField()

    def validate_payment_method_id(self, value):
        if not PaymentMethod.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError('Payment method not found.')
        return value
