from __future__ import annotations

import html
import logging
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ⚠️ Replace with your real token & group id
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
GROUP_CHAT_ID = -1001234567890

RATE_LIMIT_MAX_MESSAGES = 5
RATE_LIMIT_WINDOW_SECONDS = 10

logger = logging.getLogger(__name__)


def ensure_bot_data(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    """Provision shared bot data containers."""
    bot_data = context.application.bot_data
    bot_data.setdefault("blocked_users", set())
    bot_data.setdefault("rate_limiter", defaultdict(deque))
    bot_data.setdefault("info_message_map", {})
    bot_data.setdefault("user_info", {})
    return bot_data


def is_user_blocked(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    bot_data = ensure_bot_data(context)
    return user_id in bot_data["blocked_users"]


def add_user_to_blocklist(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> None:
    bot_data = ensure_bot_data(context)
    bot_data["blocked_users"].add(user_id)


def remove_user_from_blocklist(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Remove a user from the blocklist. Returns True if removed."""
    bot_data = ensure_bot_data(context)
    if user_id in bot_data["blocked_users"]:
        bot_data["blocked_users"].remove(user_id)
        return True
    return False


def track_rate_limit(context: ContextTypes.DEFAULT_TYPE, user_id: int) -> bool:
    """Return False if user exceeded rate limit."""
    bot_data = ensure_bot_data(context)
    history: deque = bot_data["rate_limiter"][user_id]
    now = datetime.utcnow()
    cutoff = now - timedelta(seconds=RATE_LIMIT_WINDOW_SECONDS)

    while history and history[0] < cutoff:
        history.popleft()

    if len(history) >= RATE_LIMIT_MAX_MESSAGES:
        return False

    history.append(now)
    return True


async def send_text(bot, chat_id: int, text: str) -> None:
    await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    await bot.send_message(chat_id=chat_id, text=text)


def resolve_message_payload(update_message) -> Optional[Dict[str, Any]]:
    msg = update_message
    if msg.text:
        return {
            "type": "text",
            "action": ChatAction.TYPING,
            "label": "📨 Message",
            "data": {"text": msg.text_html, "parse_mode": ParseMode.HTML},
        }
    if msg.photo:
        return {
            "type": "photo",
            "action": ChatAction.UPLOAD_PHOTO,
            "label": "📸 Photo",
            "data": {
                "photo": msg.photo[-1].file_id,
                "caption": msg.caption_html,
                "parse_mode": ParseMode.HTML,
            },
        }
    if msg.video:
        return {
            "type": "video",
            "action": ChatAction.UPLOAD_VIDEO,
            "label": "🎥 Video",
            "data": {
                "video": msg.video.file_id,
                "caption": msg.caption_html,
                "parse_mode": ParseMode.HTML,
            },
        }
    if msg.animation:
        return {
            "type": "animation",
            "action": ChatAction.UPLOAD_VIDEO,
            "label": "🎞 GIF",
            "data": {
                "animation": msg.animation.file_id,
                "caption": msg.caption_html,
                "parse_mode": ParseMode.HTML,
            },
        }
    if msg.document:
        return {
            "type": "document",
            "action": ChatAction.UPLOAD_DOCUMENT,
            "label": "📁 Document",
            "data": {
                "document": msg.document.file_id,
                "caption": msg.caption_html,
                "parse_mode": ParseMode.HTML,
            },
        }
    if msg.voice:
        return {
            "type": "voice",
            "action": ChatAction.RECORD_VOICE,
            "label": "🎙 Voice",
            "data": {
                "voice": msg.voice.file_id,
                "caption": msg.caption_html,
                "parse_mode": ParseMode.HTML,
            },
        }
    return None


async def send_payload(
    bot, chat_id: int, payload: Dict[str, Any], reply_to: Optional[int] = None
):
    action = payload["action"]
    await bot.send_chat_action(chat_id=chat_id, action=action)
    data = payload["data"].copy()

    # Clean empty captions
    if "caption" in data and data["caption"] is None:
        data.pop("caption", None)
        data.pop("parse_mode", None)

    if reply_to:
        data["reply_to_message_id"] = reply_to

    payload_type = payload["type"]
    if payload_type == "text":
        return await bot.send_message(chat_id=chat_id, **data)
    if payload_type == "photo":
        return await bot.send_photo(chat_id=chat_id, **data)
    if payload_type == "video":
        return await bot.send_video(chat_id=chat_id, **data)
    if payload_type == "animation":
        return await bot.send_animation(chat_id=chat_id, **data)
    if payload_type == "document":
        return await bot.send_document(chat_id=chat_id, **data)
    if payload_type == "voice":
        return await bot.send_voice(chat_id=chat_id, **data)
    raise ValueError("Unsupported payload type")


def build_info_text(message, label: str) -> str:
    user = message.from_user
    raw_username = f"@{user.username}" if user.username else "No username"
    username = html.escape(raw_username)
    full_name = html.escape(user.full_name)

    lines = [
        f"{label} from <b>{full_name}</b> ({username})",
        f"🆔 <code>{user.id}</code>",
    ]

    if message.caption_html:
        lines.append(f"💬 {message.caption_html}")
    elif message.text_html:
        lines.append(f"💬 {message.text_html}")

    return "\n".join(lines)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.effective_chat.type != "private":
            return
        await send_text(
            context.bot,
            update.effective_chat.id,
            "Welcome! Send any message and I'll forward it to the admins.",
        )
    except Exception as exc:
        logger.exception("Failed to handle /start: %s", exc)


async def handle_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    payload = resolve_message_payload(message)
    bot_data = ensure_bot_data(context)

    # Cache basic user info for admin views (/blocked)
    if user:
        bot_data["user_info"][user.id] = {
            "username": user.username,
            "full_name": user.full_name,
        }

    if not payload:
        await send_text(context.bot, message.chat.id, "⚠️ Unsupported content type.")
        return

    if is_user_blocked(context, user.id):
        await send_text(
            context.bot,
            message.chat.id,
            "🚫 You have been blocked and cannot send messages.",
        )
        return

    if not track_rate_limit(context, user.id):
        await send_text(
            context.bot,
            message.chat.id,
            "⚠️ You are sending messages too quickly. Please slow down.",
        )
        return

    try:
        info_text = build_info_text(message, payload["label"])
        keyboard = InlineKeyboardMarkup(
            [[InlineKeyboardButton("🚫 Block User", callback_data=f"block:{user.id}")]]
        )
        await context.bot.send_chat_action(
            chat_id=GROUP_CHAT_ID, action=ChatAction.TYPING
        )
        info_message = await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=info_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
        bot_data["info_message_map"][info_message.message_id] = user.id

        await send_payload(
            context.bot,
            GROUP_CHAT_ID,
            payload,
            reply_to=info_message.message_id,
        )

        await send_text(
            context.bot,
            message.chat.id,
            "✅ Delivered to the group. Await their reply here.",
        )
    except Exception as exc:
        logger.exception("Failed to forward private message: %s", exc)
        await send_text(context.bot, message.chat.id, "❌ Failed to send your message.")


async def handle_group_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    bot_data = ensure_bot_data(context)
    reply_to = message.reply_to_message

    if not reply_to:
        return

    user_id = bot_data["info_message_map"].get(reply_to.message_id)
    if not user_id:
        await send_text(
            context.bot,
            message.chat.id,
            "⚠️ Please reply directly to the bot's info message.",
        )
        return

    if is_user_blocked(context, user_id):
        await send_text(
            context.bot, message.chat.id, "ℹ️ That user is currently blocked."
        )
        return

    payload = resolve_message_payload(message)
    if not payload:
        await send_text(context.bot, message.chat.id, "⚠️ Unsupported reply type.")
        return

    try:
        await send_text(context.bot, user_id, "📩 Reply from the group chat:")
        await send_payload(context.bot, user_id, payload)
        await send_text(context.bot, message.chat.id, "✅ Reply delivered.")

        # 🧹 Clean up mapping once the reply has been successfully delivered
        bot_data["info_message_map"].pop(reply_to.message_id, None)
    except Exception as exc:
        logger.exception("Failed to deliver reply: %s", exc)
        await send_text(context.bot, message.chat.id, "❌ Could not deliver the reply.")


async def handle_block_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """You said everyone in the group is admin, so no admin-check here."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("block:"):
        return

    try:
        await query.answer()
        user_id = int(query.data.split(":", maxsplit=1)[1])
        add_user_to_blocklist(context, user_id)
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text(f"🚫 User {user_id} has been blocked.")
    except Exception as exc:
        logger.exception("Failed to block user: %s", exc)
        await query.answer("Failed to block user.", show_alert=True)


async def handle_unblock_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline 'Unblock' button presses."""
    query = update.callback_query
    if not query or not query.data or not query.data.startswith("unblock:"):
        return

    try:
        admin_id = query.from_user.id
        member = await context.bot.get_chat_member(
            chat_id=GROUP_CHAT_ID, user_id=admin_id
        )
        if member.status not in ("administrator", "creator"):
            await query.answer("Permission denied.", show_alert=True)
            return

        user_id = int(query.data.split(":", maxsplit=1)[1])
        removed = remove_user_from_blocklist(context, user_id)
        if removed:
            await query.answer()
            await query.message.reply_text(f"✅ User {user_id} has been unblocked.")
        else:
            await query.answer("User not found in blocklist.", show_alert=True)
    except Exception as exc:
        logger.exception("Failed to unblock user via callback: %s", exc)
        await query.answer("Failed to unblock user.", show_alert=True)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explain how the bot works and its limitations."""
    try:
        chat = update.effective_chat
        user = update.effective_user

        # Base text for everyone
        base_text = (
            "ℹ️ <b>Zapata Support Bot</b>\n\n"
            "• <b>What I do</b>\n"
            "  - I forward your private messages (text, photos, videos, GIFs, documents, voice notes) "
            "to a support group.\n"
            "  - Replies from the group are delivered back to you here.\n\n"
            "• <b>Supported content</b>\n"
            "  - Text messages\n"
            "  - Photos (with captions)\n"
            "  - Videos (with captions)\n"
            "  - GIFs / animations\n"
            "  - Documents and files\n"
            "  - Voice messages\n\n"
            "• <b>Limitations & safety</b>\n"
            "  - Anti-spam: sending too many messages too quickly will temporarily stop forwarding.\n"
            "  - Blocked users: the support team can block abusive users.\n"
            "    Blocks are stored in memory and reset if the bot restarts.\n\n"
        )

        extra = ""

        if chat.type == "private":
            extra = (
                "• <b>How to use (you)</b>\n"
                "  - Just send me a message here in private.\n"
                "  - Wait for the group’s reply, which will appear in this chat.\n"
            )
        elif chat.type in ("group", "supergroup"):
            # If this user is an admin, show admin help too
            try:
                member = await context.bot.get_chat_member(
                    chat_id=GROUP_CHAT_ID, user_id=user.id
                )
                if member.status in ("administrator", "creator"):
                    extra = (
                        "• <b>Admin tools</b>\n"
                        "  - Reply to the bot's info message to answer a user.\n"
                        "  - Press \"🚫 Block User\" under an info message to block them.\n"
                        "  - Use /blocked to see the current blocklist and unblock via buttons.\n"
                        "  - Use /unblock &lt;user_id&gt; to unblock manually.\n"
                    )
            except Exception:
                # If we can't resolve admin status, just show base text
                pass

        text = base_text + extra

        await context.bot.send_chat_action(
            chat_id=chat.id, action=ChatAction.TYPING
        )
        await chat.send_message(text=text, parse_mode=ParseMode.HTML)
    except Exception as exc:
        logger.exception("Failed to send /help: %s", exc)


async def blocked_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: list blocked users and provide inline Unblock buttons."""
    try:
        bot_data = ensure_bot_data(context)
        requester = update.effective_user

        member = await context.bot.get_chat_member(
            chat_id=GROUP_CHAT_ID, user_id=requester.id
        )
        if member.status not in ("administrator", "creator"):
            await send_text(
                context.bot,
                update.effective_chat.id,
                "🚫 You don't have permission to use this command.",
            )
            return

        blocked_users = bot_data["blocked_users"]
        user_info = bot_data["user_info"]

        if not blocked_users:
            await send_text(
                context.bot,
                update.effective_chat.id,
                "✅ No users are currently blocked.",
            )
            return

        lines = ["🚫 <b>Blocked users</b>:"]
        keyboard_rows = []
        for uid in sorted(blocked_users):
            info = user_info.get(uid, {})
            username = info.get("username")
            full_name = info.get("full_name")

            label_parts = [str(uid)]
            if full_name or username:
                pretty = []
                if full_name:
                    pretty.append(html.escape(full_name))
                if username:
                    pretty.append(html.escape(f"@{username}"))
                label_parts.append(f"({', '.join(pretty)})")

            label = " ".join(label_parts)
            lines.append(f"• <code>{label}</code>")
            keyboard_rows.append(
                [
                    InlineKeyboardButton(
                        text=f"Unblock {uid}", callback_data=f"unblock:{uid}"
                    )
                ]
            )

        text = "\n".join(lines)
        keyboard = InlineKeyboardMarkup(keyboard_rows)

        await context.bot.send_chat_action(
            chat_id=update.effective_chat.id, action=ChatAction.TYPING
        )
        await update.effective_chat.send_message(
            text=text, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
    except Exception as exc:
        logger.exception("Failed to handle /blocked: %s", exc)


async def unblock_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin-only: /unblock <user_id> to remove from blocklist."""
    try:
        requester = update.effective_user
        member = await context.bot.get_chat_member(
            chat_id=GROUP_CHAT_ID, user_id=requester.id
        )
        if member.status not in ("administrator", "creator"):
            await send_text(
                context.bot,
                update.effective_chat.id,
                "🚫 You don't have permission to use this command.",
            )
            return

        if not context.args:
            await send_text(
                context.bot,
                update.effective_chat.id,
                "Usage: /unblock <user_id>",
            )
            return

        try:
            user_id = int(context.args[0])
        except ValueError:
            await send_text(
                context.bot,
                update.effective_chat.id,
                "User ID must be a number.",
            )
            return

        removed = remove_user_from_blocklist(context, user_id)
        if removed:
            await send_text(
                context.bot,
                update.effective_chat.id,
                f"✅ User {user_id} has been unblocked.",
            )
        else:
            await send_text(
                context.bot,
                update.effective_chat.id,
                "User not found in blocklist.",
            )
    except Exception as exc:
        logger.exception("Failed to handle /unblock: %s", exc)


def main() -> None:
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        level=logging.INFO,
    )
    application = ApplicationBuilder().token(TOKEN).build()

    # Commands
    application.add_handler(
        CommandHandler("start", start, filters.ChatType.PRIVATE)
    )
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("blocked", blocked_command))
    application.add_handler(CommandHandler("unblock", unblock_command))

    # Messages
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND,
            handle_private_message,
        )
    )
    application.add_handler(
        MessageHandler(filters.ChatType.GROUPS & filters.REPLY, handle_group_reply)
    )

    # Callbacks
    application.add_handler(
        CallbackQueryHandler(handle_block_callback, pattern=r"^block:")
    )
    application.add_handler(
        CallbackQueryHandler(handle_unblock_callback, pattern=r"^unblock:")
    )

    application.run_polling()


if __name__ == "__main__":
    main()
