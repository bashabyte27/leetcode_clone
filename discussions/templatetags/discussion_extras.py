from django import template

register = template.Library()


@register.filter
def get_list(mapping, key):
    """dict.get(key, []) — maps ``replies_by_parent|get_list:comment.id``."""
    try:
        return mapping.get(key, [])
    except AttributeError:
        return []