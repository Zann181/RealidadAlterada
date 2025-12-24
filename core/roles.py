ROLE_VENDEDOR = "VENDEDOR"
ROLE_CLIENTE = "CLIENTE"


def user_has_role(user, role_name):
    from django.db.models import Q

    if not user or not user.is_authenticated:
        return False
    normalized = (role_name or "").strip()
    if not normalized:
        return False

    candidates = {normalized}
    lower = normalized.lower()
    if lower.endswith("r"):
        candidates.add(f"{normalized}ES")
    elif lower.endswith("e"):
        candidates.add(f"{normalized}S")

    query = Q()
    for candidate in candidates:
        query |= Q(name__iexact=candidate)
    query |= Q(name__icontains=lower)
    return user.groups.filter(query).exists()
