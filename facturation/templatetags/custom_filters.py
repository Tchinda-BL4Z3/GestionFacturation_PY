from django import template

register = template.Library()

@register.filter
def divide_by(value, arg):
    try:
        return float(value) / float(arg)
    except (ValueError, ZeroDivisionError, TypeError):
        return 0