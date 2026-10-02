"""Communication bot: subscribers write to the bot instead of a tipster's personal account.

User → bot (private chat)  → copied into a staff forum group, one topic per user
Staff / tipster → reply inside that topic → copied back to the user, sent by the bot
Every message is logged in the database; the group keeps the full visual history.

Routing: t.me/<bot>?start=<key> sends the user to the group bound with /bind <key>
(one group per tipster/community, or several keys in one shared group).
"""
import asyncio
import html
import logging
import os
import re
from collections import defaultdict

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message, ReactionTypeEmoji, ReplyParameters, User

import db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("support-bot")

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMINS = {int(x) for x in re.split(r"[,\s]+", os.getenv("ADMINS", "")) if x}
DEFAULT_ROUTE = os.getenv("DEFAULT_ROUTE", "main").lower()
WELCOME_TEXT = os.getenv("WELCOME_TEXT", "Hi! 👋 Write your question here — our team will reply in this chat.")
NOTE_PREFIX = os.getenv("NOTE_PREFIX", "//")
SIGN_REPLIES = os.getenv("SIGN_REPLIES", "0") == "1"
KEY_RE = re.compile(r"^[a-z0-9_-]{1,64}$")
CONTENT = ("text", "photo", "video", "document", "voice", "audio", "sticker", "animation",
           "video_note", "location", "contact", "poll", "dice", "venue")

private = Router()
private.message.filter(F.chat.type == ChatType.PRIVATE)
staff = Router()
staff.message.filter(F.chat.type == ChatType.SUPERGROUP)
_locks = defaultdict(asyncio.Lock)


def full_name(u: User) -> str:
    return " ".join(x for x in (u.first_name, u.last_name) if x) or str(u.id)


def topic_title(u: User, route: str) -> str:
    t = f"[{route}] {full_name(u)}" + (f" @{u.username}" if u.username else "") + f" · {u.id}"
    return t[:128]


def user_card(u: User, route: str) -> str:
    lines = [f"👤 <b>{html.escape(full_name(u))}</b>",
             f"@{u.username}" if u.username else "no username",
             f"ID: <code>{u.id}</code>",
             f"Route: <code>{html.escape(route)}</code>"]
    if u.language_code:
        lines.append(f"Language: {u.language_code}")
    lines.append(f'<a href="tg://user?id={u.id}">Open profile</a>')
    lines.append(f"\nAnything you write in this topic is sent to the user by the bot. "
                 f"Start with <code>{html.escape(NOTE_PREFIX)}</code> for an internal note. "
                 f"Reply to a message to answer it directly. /info · /ban · /unban")
    return "\n".join(lines)


def has_content(m: Message) -> bool:
    return any(getattr(m, k, None) for k in CONTENT)


async def ensure_topic(bot: Bot, chat_id: int, u: User, route: str, fresh: bool = False) -> int:
    async with _locks[(u.id, chat_id)]:
        if not fresh:
            t = await db.get_thread(u.id, chat_id)
            if t:
                return t
        topic = await bot.create_forum_topic(chat_id, topic_title(u, route))
        await db.set_thread(u.id, chat_id, topic.message_thread_id)
        await bot.send_message(chat_id, user_card(u, route), message_thread_id=topic.message_thread_id)
        return topic.message_thread_id


# ───────────────────────── user side ─────────────────────────

@private.message(CommandStart())
async def on_start(m: Message, command: CommandObject):
    key = (command.args or "").strip().lower()
    u = await db.get_user(m.from_user.id)
    if key and await db.get_route(key):
        route = key                                   # a new deep link moves the user to that tipster
    elif u and u["route"]:
        route = u["route"]
    else:
        route = DEFAULT_ROUTE
    await db.upsert_user(m.from_user.id, m.from_user.username, full_name(m.from_user), m.from_user.language_code, route)
    r = await db.get_route(route)
    await m.answer((r and r["welcome"]) or WELCOME_TEXT)


@private.message()
async def from_user(m: Message, bot: Bot):
    if not has_content(m):
        return
    fu = m.from_user
    u = await db.get_user(fu.id)
    if u and u["banned"]:
        return
    await db.upsert_user(fu.id, fu.username, full_name(fu), fu.language_code, None if u and u["route"] else DEFAULT_ROUTE)
    route_key = (u and u["route"]) or DEFAULT_ROUTE
    route = await db.get_route(route_key) or await db.get_route(DEFAULT_ROUTE)
    if not route:
        log.error("No route '%s' and no default route bound — run /bind %s in the staff group", route_key, DEFAULT_ROUTE)
        await m.answer("Sorry, support is not available right now. Please try again later.")
        return
    chat_id = route["chat_id"]

    reply = None
    if m.reply_to_message:
        row = await db.find_by_user_msg(fu.id, m.reply_to_message.message_id)
        if row and row["chat_id"] == chat_id:
            reply = ReplyParameters(message_id=row["group_msg_id"], allow_sending_without_reply=True)

    thread_id = await ensure_topic(bot, chat_id, fu, route["key"])
    sent = None
    for _ in range(3):
        try:
            sent = await bot.copy_message(chat_id, m.chat.id, m.message_id, message_thread_id=thread_id,
                                          reply_parameters=reply)
            break
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "closed" in err:
                await bot.reopen_forum_topic(chat_id, thread_id)
            elif "thread" in err or "topic" in err:     # topic was deleted → start a new one
                thread_id = await ensure_topic(bot, chat_id, fu, route["key"], fresh=True)
                reply = None
            else:
                log.exception("copy to staff failed")
                break
    if not sent:
        await m.answer("Sorry, this message could not be delivered. Please try sending it as text.")
        return
    await db.log_message(direction="in", user_id=fu.id, chat_id=chat_id, thread_id=thread_id,
                         user_msg_id=m.message_id, group_msg_id=sent.message_id,
                         content_type=m.content_type, text=m.text or m.caption)


# ───────────────────────── staff side ─────────────────────────

@staff.message(Command("bind"))
async def cmd_bind(m: Message, command: CommandObject, bot: Bot):
    if m.from_user.id not in ADMINS:
        return
    key = (command.args or "").strip().lower()
    if not KEY_RE.match(key):
        await m.reply("Usage: <code>/bind key</code> — latin letters, digits, _ or -, e.g. <code>/bind mario</code>")
        return
    chat = await bot.get_chat(m.chat.id)
    if not chat.is_forum:
        await m.reply("Turn on <b>Topics</b> in the group settings first, then run /bind again.")
        return
    await db.set_route(key, m.chat.id, m.chat.title)
    me = await bot.me()
    await m.reply(f"✅ Route <code>{key}</code> → this group.\nLink for users: https://t.me/{me.username}?start={key}")


@staff.message(Command("welcome"))
async def cmd_welcome(m: Message, command: CommandObject):
    if m.from_user.id not in ADMINS:
        return
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) < 2 or not await db.get_route(parts[0].lower()):
        await m.reply("Usage: <code>/welcome key Text the user sees after /start</code>")
        return
    await db.set_welcome(parts[0].lower(), parts[1])
    await m.reply(f"✅ Welcome text for <code>{html.escape(parts[0].lower())}</code> saved.")


@staff.message(Command("routes"))
async def cmd_routes(m: Message, bot: Bot):
    if m.from_user.id not in ADMINS:
        return
    me = await bot.me()
    rows = await db.list_routes()
    if not rows:
        await m.reply("No routes yet. Run <code>/bind key</code> in a forum group.")
        return
    await m.reply("\n".join(f"• <code>{r['key']}</code> → {html.escape(r['title'] or str(r['chat_id']))} — "
                            f"https://t.me/{me.username}?start={r['key']}" for r in rows))


async def _topic_user(m: Message):
    if not m.message_thread_id or not await db.is_staff_chat(m.chat.id):
        return None
    return await db.user_by_thread(m.chat.id, m.message_thread_id)


@staff.message(Command("ban", "unban"))
async def cmd_ban(m: Message, command: CommandObject):
    uid = await _topic_user(m)
    if not uid:
        return
    banned = command.command == "ban"
    await db.set_banned(uid, banned)
    await m.reply("🚫 User banned — their messages are ignored." if banned else "✅ User unbanned.")


@staff.message(Command("info"))
async def cmd_info(m: Message):
    uid = await _topic_user(m)
    if not uid:
        return
    u = await db.get_user(uid) or {}
    c = await db.message_counts(uid)
    await m.reply(f"ID <code>{uid}</code> · @{u.get('username') or '—'} · route <code>{u.get('route')}</code>\n"
                  f"First seen: {u.get('created_at')} UTC · last: {u.get('last_seen')} UTC\n"
                  f"Messages: {c.get('in', 0)} from user, {c.get('out', 0)} from team"
                  + (" · 🚫 banned" if u.get("banned") else ""))


@staff.message(F.message_thread_id)
async def from_staff(m: Message, bot: Bot):
    if not m.from_user or m.from_user.is_bot or not has_content(m):
        return
    text = m.text or m.caption or ""
    if text.startswith(NOTE_PREFIX) or text.startswith("/"):
        return                                         # internal note / unknown command — never sent
    uid = await _topic_user(m)
    if not uid:
        return
    u = await db.get_user(uid)
    if u and u["banned"]:
        await m.reply("User is banned — /unban first.")
        return

    reply = None
    rt = m.reply_to_message
    if rt and not rt.forum_topic_created:
        row = await db.find_by_group_msg(m.chat.id, rt.message_id)
        if row and row["user_msg_id"]:
            reply = ReplyParameters(message_id=row["user_msg_id"], allow_sending_without_reply=True)
    try:
        if SIGN_REPLIES and m.text:
            sent = await bot.send_message(uid, f"{m.html_text}\n\n— <i>{html.escape(m.from_user.first_name)}</i>",
                                          reply_parameters=reply)
        else:
            sent = await bot.copy_message(uid, m.chat.id, m.message_id, reply_parameters=reply)
    except TelegramForbiddenError:
        await m.reply("⚠️ Not delivered: the user blocked the bot.")
        return
    except TelegramBadRequest as e:
        await m.reply(f"⚠️ Not delivered: {html.escape(str(e))}")
        return
    await db.log_message(direction="out", user_id=uid, chat_id=m.chat.id, thread_id=m.message_thread_id,
                         user_msg_id=sent.message_id, group_msg_id=m.message_id, staff_id=m.from_user.id,
                         staff_name=full_name(m.from_user), content_type=m.content_type, text=text or None)
    try:
        await bot.set_message_reaction(m.chat.id, m.message_id, [ReactionTypeEmoji(emoji="👍")])
    except Exception:
        pass                                           # reactions may be disabled in the group


async def main():
    await db.init()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_routers(private, staff)
    if not ADMINS:
        log.warning("ADMINS is empty — nobody can run /bind")
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
