from django.urls import path

from .views import CouponApplyView

urlpatterns = [
    path("apply/", CouponApplyView.as_view(), name="coupon-apply"),
]
