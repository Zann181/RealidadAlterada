from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def querystring(context, **kwargs):
    """
    Returns the current querystring with updated params.

    Usage:
      ?{% querystring page=2 %}
      ?{% querystring per_page=50 page=1 %}
      ?{% querystring page=None %}  # remove key
    """
    request = context.get("request")
    if request is None:
        return ""

    query = request.GET.copy()
    for key, value in kwargs.items():
        if value is None or value == "":
            query.pop(key, None)
            continue
        if isinstance(value, (list, tuple, set)):
            query.setlist(key, [str(item) for item in value])
        else:
            query[key] = str(value)
    return query.urlencode()

