from django.core.paginator import Paginator


DEFAULT_PER_PAGE_OPTIONS = (10, 20, 50, 100)


def paginate_queryset(
    request,
    queryset,
    *,
    page_param="page",
    per_page_param="per_page",
    per_page_default=20,
    per_page_options=DEFAULT_PER_PAGE_OPTIONS,
    per_page_max=200,
):
    per_page_raw = request.GET.get(per_page_param)
    per_page = per_page_default
    if per_page_raw:
        try:
            per_page = int(per_page_raw)
        except (TypeError, ValueError):
            per_page = per_page_default

    if per_page_options and per_page not in per_page_options:
        per_page = per_page_default

    if per_page <= 0:
        per_page = per_page_default
    if per_page_max and per_page > per_page_max:
        per_page = per_page_max

    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get(page_param) or 1
    page_obj = paginator.get_page(page_number)

    return {
        "paginator": paginator,
        "page_obj": page_obj,
        "is_paginated": page_obj.has_other_pages(),
        "per_page": per_page,
        "per_page_options": per_page_options or (),
        "page_param": page_param,
        "per_page_param": per_page_param,
    }

