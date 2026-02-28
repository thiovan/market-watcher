"""Admin-only middleware — restricts all bot commands to ADMIN_USER_ID."""

from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from config import settings

logger = logging.getLogger(__name__)


class AdminOnlyMiddleware(BaseMiddleware):
    """Reject messages and callbacks from non-admin users."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id = None

        if isinstance(event, Message):
            user_id = event.from_user.id if event.from_user else None
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id if event.from_user else None

        if user_id is None or user_id != settings.admin_user_id:
            logger.debug("Rejected request from unauthorized user: %s", user_id)
            return  # Silently ignore

        return await handler(event, data)
