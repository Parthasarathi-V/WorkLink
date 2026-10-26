def unread_notifications(request):
    user = getattr(request, "user", None)
    if user is not None and user.is_authenticated:
        return {"unread_count": user.notifications.filter(is_read=False).count()}
    return {"unread_count": 0}
