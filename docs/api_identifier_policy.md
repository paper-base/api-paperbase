# API identifier policy

## Rules

- **Do not** expose Django integer primary keys in JSON request or response bodies under the key `id` for domain resources.
- **Do** use `public_id` (prefixed opaque strings, e.g. `usr_`, `ord_`, `str_`) for external references, URLs, and client state.
- **Opaque tokens** that are not PKs (e.g. 2FA `challenge_public_id`, which maps to the stored `challenge_id` column) are exposed as `*_public_id` in JSON for consistency.

## Helpers

- [`SafeModelSerializer`](../engine/core/serializers.py) raises at class creation time if `Meta.fields` includes `"id"`. Prefer subclassing it for new `ModelSerializer` classes and set `Meta.allow_id = True` only for rare internal-only endpoints.

## Ongoing audit

Periodically search the codebase for:

- `"id"` in serializer `Meta.fields` and `to_representation` overrides
- Raw `Response({"id": ...})` using model `.pk`

Product list endpoints and legacy code may still use `id` as an alias for `public_id`; prefer renaming those response keys to `public_id` when touching those serializers.
