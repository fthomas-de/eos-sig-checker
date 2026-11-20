from django import template

register = template.Library()


@register.filter
def client_text(value, texts):
    """value in the reader's client language, where client_text.display found it."""
    return texts.get(value, value) if texts else value
