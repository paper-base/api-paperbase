"""
Central source of truth for checkout field requirements.
All validation reads from here. No inline variant checks anywhere else.
"""

MINIMAL_REQUIRED_FIELDS = {"shipping_name", "phone", "shipping_zone", "district"}
EXTENDED_REQUIRED_FIELDS = {
    "shipping_name",
    "phone",
    "email",
    "shipping_zone",
    "district",
    "shipping_address",
}


def get_required_checkout_fields(checkout_settings) -> set[str]:
    if checkout_settings is None:
        return EXTENDED_REQUIRED_FIELDS
    if checkout_settings.customer_form_variant == "minimal":
        return MINIMAL_REQUIRED_FIELDS
    return EXTENDED_REQUIRED_FIELDS


def is_field_required(field_name: str, checkout_settings) -> bool:
    return field_name in get_required_checkout_fields(checkout_settings)
