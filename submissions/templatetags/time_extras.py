from django import template
register = template.Library()

@register.filter
def mmss(seconds):
    """Format seconds as MM:SS for display."""
    if seconds is None:
        return "—"
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"
