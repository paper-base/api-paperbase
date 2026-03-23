from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403,F401


def _require_env(name: str) -> str:
    value = os.getenv(name, "").strip()  # noqa: F405
    if not value:
        raise ImproperlyConfigured(f"Missing required environment variable: {name}")
    return value


DEBUG = False

SECRET_KEY = _require_env("SECRET_KEY")
SIMPLE_JWT["SIGNING_KEY"] = SECRET_KEY  # noqa: F405

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")  # noqa: F405
if not ALLOWED_HOSTS:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set in production.")

# Production DB: explicit Postgres configuration with strict env validation.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _require_env("DB_NAME"),
        "USER": _require_env("DB_USER"),
        "PASSWORD": _require_env("DB_PASSWORD"),
        "HOST": _require_env("DB_HOST"),
        "PORT": _require_env("DB_PORT"),
    }
}

_channel_redis = _require_env("CHANNEL_LAYER_REDIS_URL")
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [_channel_redis]},
    }
}

_cache_redis_url = _require_env("CACHE_REDIS_URL")
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": _cache_redis_url,
    },
    TENANT_RESOLUTION_CACHE_ALIAS: {  # noqa: F405
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": _cache_redis_url,
    },
}

CELERY_BROKER_URL = _require_env("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)  # noqa: F405
CELERY_TASK_ALWAYS_EAGER = False

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")  # noqa: F405

CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

