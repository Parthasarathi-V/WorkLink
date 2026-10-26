from django import template

register = template.Library()

_GOOD = {"APPROVED", "PUBLISHED", "JOINED", "ACCEPTED", "CONFIRMED", "RESOLVED", "FREE_PLACEMENT", "PAID"}
_BAD = {"REJECTED", "DECLINED", "REMOVED", "DISMISSED", "DISPUTED", "WITHDRAWN", "CLOSED", "EXPIRED"}
_WARN = {"PENDING", "NEEDS_CORRECTION", "DUE", "OPEN", "UNDER_REVIEW", "DRAFT", "PAUSED", "WAITING_FOR_RESPONSE"}


@register.filter
def badge(value):
    value = str(value)
    if value in _GOOD:
        return "text-bg-success"
    if value in _BAD:
        return "text-bg-danger"
    if value in _WARN:
        return "text-bg-warning"
    return "text-bg-secondary"
