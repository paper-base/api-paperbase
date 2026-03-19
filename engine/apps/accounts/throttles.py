"""Custom throttle scopes for authentication endpoints."""
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    scope = "auth_token"


class RegisterRateThrottle(AnonRateThrottle):
    scope = "auth_register"


class PasswordResetRateThrottle(AnonRateThrottle):
    scope = "auth_reset"
