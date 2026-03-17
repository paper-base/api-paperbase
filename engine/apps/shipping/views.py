from decimal import Decimal

from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ShippingMethod, ShippingZone, ShippingRate
from .serializers import ShippingOptionSerializer


class ShippingOptionsView(APIView):
    """
    GET ?country=US&order_total=99.00
    Returns available shipping methods and estimated price for the given country and order total.
    """
    def get(self, request):
        country = (request.query_params.get('country') or '').strip().upper()
        order_total = request.query_params.get('order_total')
        try:
            order_total = Decimal(order_total) if order_total else None
        except Exception:
            order_total = None

        zones = ShippingZone.objects.filter(is_active=True)
        if country:
            zones = zones.filter(
                country_codes__icontains=country
            )  # simple: zone has "US" in comma-separated list
        zone_ids = list(zones.values_list('id', flat=True))

        methods = ShippingMethod.objects.filter(
            is_active=True
        ).prefetch_related('rates__shipping_zone')
        if zone_ids:
            methods = methods.filter(zones__id__in=zone_ids).distinct()
        else:
            # No zone filter: use methods that have rates with no zone restriction or all zones
            methods = methods.distinct()

        options = []
        for method in methods:
            for rate in method.rates.filter(is_active=True).select_related('shipping_zone'):
                if zone_ids and rate.shipping_zone_id not in zone_ids:
                    continue
                if order_total is not None:
                    if rate.min_order_total and order_total < rate.min_order_total:
                        continue
                    if rate.max_order_total and order_total > rate.max_order_total:
                        continue
                options.append({
                    'method_id': method.id,
                    'method_name': method.name,
                    'zone_id': rate.shipping_zone_id,
                    'zone_name': rate.shipping_zone.name,
                    'price': rate.price,
                    'rate_type': rate.rate_type,
                })
        return Response(ShippingOptionSerializer(options, many=True).data)
