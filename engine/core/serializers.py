from django.core.exceptions import ImproperlyConfigured
from rest_framework import serializers


class SafeModelSerializer(serializers.ModelSerializer):
    """
    ModelSerializer subclass that blocks accidental exposure of the internal
    ``id`` (integer primary key) in API responses.

    Any serializer inheriting from this class will raise
    ``ImproperlyConfigured`` at class-creation time if ``"id"`` appears in
    ``Meta.fields``.

    If a serializer genuinely needs to include ``id`` (rare — only for
    internal-only endpoints that are never exposed externally), set
    ``Meta.allow_id = True`` to opt out of the check.
    """

    class Meta:
        abstract = True

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        meta = getattr(cls, "Meta", None)
        if meta is None:
            return
        allow_id = getattr(meta, "allow_id", False)
        if allow_id:
            return
        fields = getattr(meta, "fields", None)
        if fields and isinstance(fields, (list, tuple)) and "id" in fields:
            raise ImproperlyConfigured(
                f"{cls.__qualname__} includes 'id' in Meta.fields. "
                f"Use 'public_id' instead to avoid leaking internal PKs. "
                f"If this is intentional, set Meta.allow_id = True."
            )
