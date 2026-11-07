from django import template

register = template.Library()


@register.filter
def duration(minutes):
    """45 → "45 min", 110 → "1 h 50 min", 360 → "6 h"."""
    try:
        minutes = int(minutes or 0)
    except (TypeError, ValueError):
        return ""
    hours, mins = divmod(minutes, 60)
    if not hours:
        return f"{mins} min"
    return f"{hours} h {mins} min" if mins else f"{hours} h"


@register.filter
def two_digits(value):
    try:
        return f"{int(value):02d}"
    except (TypeError, ValueError):
        return value


@register.filter
def option_letter(index):
    """forloop.counter (1-based) → A, B, C …"""
    try:
        return "ABCDEFGH"[int(index) - 1]
    except (TypeError, ValueError, IndexError):
        return ""


@register.filter
def get_item(mapping, key):
    try:
        return mapping.get(key)
    except AttributeError:
        return None
