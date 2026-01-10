"""Bot handlers module."""

from src.bot.handlers.command import (
    start_handler,
    help_handler,
    settings_handler,
    goal_handler,
    goals_handler,
    remind_handler,
    reminders_handler,
)
from src.bot.handlers.message import message_handler
from src.bot.handlers.admin import (
    approve_handler,
    reject_handler,
    pending_handler,
    stats_handler,
)
from src.bot.handlers.error import error_handler

__all__ = [
    "start_handler",
    "help_handler",
    "settings_handler",
    "goal_handler",
    "goals_handler",
    "remind_handler",
    "reminders_handler",
    "message_handler",
    "approve_handler",
    "reject_handler",
    "pending_handler",
    "stats_handler",
    "error_handler",
]
