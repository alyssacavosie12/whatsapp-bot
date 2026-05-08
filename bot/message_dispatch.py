"""Outbound dispatch for planned bot responses."""

from __future__ import annotations

from collections.abc import Callable

from bot.message_models import ResponsePlan

SendMessage = Callable[[str, str], object]
NotifyTeam = Callable[[str], object]


def dispatch_response_plan(
    sender_id: str,
    response_plan: ResponsePlan,
    *,
    send_message: SendMessage,
    notify_team: NotifyTeam,
) -> None:
    """Send all outbound actions from a response plan."""
    if response_plan.reply_text:
        send_message(sender_id, response_plan.reply_text)

    if response_plan.team_notification:
        notify_team(response_plan.team_notification)
