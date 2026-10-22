from django.contrib.auth import get_user_model

from .models import AuditEvent, Notification


def notify(user, title, message="", link=""):
    if user is None:
        return None
    return Notification.objects.create(recipient=user, title=title, message=message, link=link)


def notify_staff(title, message="", link=""):
    User = get_user_model()
    for staff in User.objects.filter(is_staff=True, is_active=True):
        Notification.objects.create(recipient=staff, title=title, message=message, link=link)


def audit(actor, action, entity, summary=""):
    """Record a sensitive action. `entity` is a model instance."""
    return AuditEvent.objects.create(
        actor=actor if getattr(actor, "pk", None) else None,
        action=action,
        entity_type=entity.__class__.__name__,
        entity_id=str(entity.pk),
        safe_summary=summary[:500],
    )
