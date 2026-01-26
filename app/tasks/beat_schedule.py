from celery.schedules import crontab

beat_schedule = {
    "schedule-upcoming-session-notifications": {
        "task": "app.domains.notifications.tasks.schedule_upcoming_session_notifications",
        "schedule": crontab(minute="*/10"),
        "args": (24,),
    },
    "dispatch-due-notifications": {
        "task": "app.domains.notifications.tasks.dispatch_due_notifications",
        "schedule": crontab(minute="*"),
        "args": (200,),
    },
}
