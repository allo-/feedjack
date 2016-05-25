from django import template
register = template.Library()

@register.simple_tag
def urlparams(url_params, exclude):
    # we use & as separator, because is cannot be part of a key,
    # as & is the separator in urls, too.
    exclude = exclude.split("&")
    result=""
    for key, values in url_params.items():
        if key in exclude:
            continue
        for value in values:
            result += "&"+key+"="+value
    return result
