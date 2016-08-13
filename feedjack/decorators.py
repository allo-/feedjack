from django.contrib.auth.decorators import login_required


def login_required_get_parameters(parameters):
    def decorator(view):
        def decorated(request, *args, **kwargs):
            for p in parameters:
                if p in request.GET:
                    return login_required(view)(request, *args, **kwargs)
            return view(request, *args, **kwargs)
        return decorated
    return decorator

