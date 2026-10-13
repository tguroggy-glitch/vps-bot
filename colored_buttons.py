# ═══════════════════════════════════════════════════════════
#        ☁️  VISHAL CLOUD VPS BOT
#   Colored Inline Buttons via Bot API HTTP
#
#   Telegram officially supports button colors via the
#   'style' field in InlineKeyboardButton (Bot API v8.3+).
#
#   Source: https://core.telegram.org/api/bots/buttons#button-styles
#   Styles: "primary" (blue), "success" (green), "danger" (red)
# ═══════════════════════════════════════════════════════════

import json
import aiohttp
from typing import List, Optional, Union

import config

BOT_API_URL = f"https://api.telegram.org/bot{config.BOT_TOKEN}"

_session: Optional[aiohttp.ClientSession] = None


async def _get_session() -> aiohttp.ClientSession:
    global _session
    if _session and not _session.closed:
        return _session
    _session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
    return _session


def styled_button(
    text: str,
    callback_data: str = None,
    url: str = None,
    style: str = None,
) -> dict:
    """
    Create an inline button with optional color style.

    style values:
      "primary"  → blue  (main actions)
      "success"  → green (positive actions)
      "danger"   → red   (destructive actions)
      None       → default (transparent/grey)
    """
    btn = {"text": text}
    if callback_data:
        btn["callback_data"] = callback_data
    if url:
        btn["url"] = url
    if style in ("primary", "success", "danger"):
        btn["style"] = style
    return btn


def _build_reply_markup(reply_markup: List[List[dict]]) -> str:
    """Serialize inline keyboard to JSON string."""
    return json.dumps({"inline_keyboard": reply_markup})


async def send_message_colored(
    chat_id: Union[int, str],
    text: str,
    reply_markup: List[List[dict]] = None,
    parse_mode: str = "HTML",
) -> Optional[dict]:
    """Send a text message with colored inline keyboard."""
    session = await _get_session()
    payload = {
        "chat_id": str(chat_id),
        "text": text,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = _build_reply_markup(reply_markup)

    try:
        async with session.post(f"{BOT_API_URL}/sendMessage", data=payload) as resp:
            result = await resp.json()
            if resp.status == 200:
                return result.get("result")
            return None
    except Exception:
        return None


async def send_photo_colored(
    chat_id: Union[int, str],
    photo: str,
    caption: str = "",
    reply_markup: List[List[dict]] = None,
    parse_mode: str = "HTML",
) -> Optional[dict]:
    """Send a photo with colored inline keyboard."""
    session = await _get_session()
    payload = {
        "chat_id": str(chat_id),
        "photo": photo,
        "caption": caption,
        "parse_mode": parse_mode,
    }
    if reply_markup:
        payload["reply_markup"] = _build_reply_markup(reply_markup)

    try:
        async with session.post(f"{BOT_API_URL}/sendPhoto", data=payload) as resp:
            result = await resp.json()
            if resp.status == 200:
                return result.get("result")
            return None
    except Exception:
        return None


async def edit_message_colored(
    chat_id: Union[int, str],
    message_id: int,
    text: str = None,
    reply_markup: List[List[dict]] = None,
    parse_mode: str = "HTML",
) -> Optional[dict]:
    """Edit a message's text and/or inline keyboard with colored buttons."""
    session = await _get_session()

    if text:
        endpoint = "editMessageText"
        payload = {
            "chat_id": str(chat_id),
            "message_id": str(message_id),
            "text": text,
            "parse_mode": parse_mode,
        }
    else:
        endpoint = "editMessageReplyMarkup"
        payload = {
            "chat_id": str(chat_id),
            "message_id": str(message_id),
        }

    if reply_markup:
        payload["reply_markup"] = _build_reply_markup(reply_markup)

    try:
        async with session.post(f"{BOT_API_URL}/{endpoint}", data=payload) as resp:
            result = await resp.json()
            if resp.status == 200:
                return result.get("result")
            return None
    except Exception:
        return None


async def answer_callback(
    callback_query_id: str,
    text: str = None,
    show_alert: bool = False,
) -> None:
    """Answer a callback query."""
    session = await _get_session()
    payload = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
        payload["show_alert"] = str(show_alert).lower()
    try:
        async with session.post(f"{BOT_API_URL}/answerCallbackQuery", data=payload):
            pass
    except Exception:
        pass


async def close_session():
    """Close aiohttp session on shutdown."""
    global _session
    if _session and not _session.closed:
        await _session.close()
        _session = None
