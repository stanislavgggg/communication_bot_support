"""Communication bot: subscribers write to the bot instead of a tipster's / admin's personal account.

User → bot (private chat)  → copied into a staff forum group, one topic per user
Staff / tipster → reply inside that topic → copied back to the user, sent by the bot
Every message is logged in the database; the group keeps the full visual history.

Routing: t.me/<bot>?start=<key> sends the user to the group bound with /bind <key>
(one shared group for all channels, or one group per tipster).

Extras: #tags + status in topics, /stats per channel, /export to CSV / Google Sheet,
auto-reply outside working hours.
"""
import asyncio
import csv
import datetime as dt
import html
import io
import json
import logging
import os
import re
import statistics
from collections import defaultdict
from zoneinfo import ZoneInfo

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ChatType, ParseMode
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import BufferedInputFile, Message, ReactionTypeEmoji, ReplyParameters, User

import db
import texts as T

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("support-bot")

BOT_TOKEN = os.environ["BOT_TOKEN"]
ADMINS = {int(x) for x in re.split(r"[,\s]+", os.getenv("ADMINS", "")) if x}
DEFAULT_ROUTE = os.getenv("DEFAULT_ROUTE", "main").lower()
SYNC_PROFILE = os.getenv("SYNC_PROFILE", "1") == "1"      # set description / about / commands on start
if os.getenv("WELCOME_TEXT"):
    T.WELCOME["en"] = os.environ["WELCOME_TEXT"]           # env overrides the English default
NOTE_PREFIX = os.getenv("NOTE_PREFIX", "//")
SIGN_REPLIES = os.getenv("SIGN_REPLIES", "0") == "1"
KEY_RE = re.compile(r"^[a-z0-9_-]{1,64}$")
CONTENT = ("text", "photo", "video", "document", "voice", "audio", "sticker", "animation",
           "video_note", "location", "contact", "poll", "dice", "venue")

# working hours / auto-reply
WORK_TZ = ZoneInfo(os.getenv("WORK_TZ", "Europe/Vilnius"))
WORK_HOURS = os.getenv("WORK_HOURS", "").strip()          # "09:00-21:00"; empty = no auto-reply
WORK_DAYS = os.getenv("WORK_DAYS", "1-7")                  # ISO weekdays, "1-5" = Mon–Fri
REPLY_HOURS = os.getenv("REPLY_HOURS", "12")
AWAY_COOLDOWN_H = float(os.getenv("AWAY_COOLDOWN_HOURS", "6"))
if os.getenv("AWAY_TEXT"):
    T.AWAY["en"] = os.environ["AWAY_TEXT"]

# Google Sheet export (optional)
GOOGLE_SA_JSON = os.getenv("GOOGLE_SA_JSON", "").strip()   # service-account JSON (whole file content)
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
SHEET_SYNC_MINUTES = int(os.getenv("SHEET_SYNC_MINUTES", "0") or 0)

# tags: what staff types → stored name
TAG_ALIASES = {
    "жалоба": "complaint", "complaint": "complaint", "skundas": "complaint", "prituzba": "complaint",
    "вопрос": "question", "question": "question",
    "предложение": "suggestion", "suggestion": "suggestion",
    "спам": "spam", "spam": "spam",
    "решено": "resolved", "resolved": "resolved", "solved": "resolved", "done": "resolved",
    "открыто": "open", "open": "open", "reopen": "open",
}
STATUS_TAGS = {"resolved", "open"}
TAG_ICONS = [("complaint", "❗"), ("question", "❓"), ("suggestion", "💡"), ("spam", "🚫")]

private = Router()
private.message.filter(F.chat.type == ChatType.PRIVATE)
staff = Router()
staff.message.filter(F.chat.type == ChatType.SUPERGROUP)
_locks = defaultdict(asyncio.Lock)


# ───────────────────────── helpers ─────────────────────────

def full_name(u: User) -> str:
    return " ".join(x for x in (u.first_name, u.last_name) if x) or str(u.id)


def topic_title(name, username, uid, route, icon="") -> str:
    t = f"[{route}] {name}" + (f" @{username}" if username else "") + f" · {uid}"
    return ((icon + " ") if icon else "") + t[:120]


def user_card(u: User, route: str) -> str:
    lines = [f"👤 <b>{html.escape(full_name(u))}</b>",
             f"@{u.username}" if u.username else "no username",
             f"ID: <code>{u.id}</code>",
             f"Route: <code>{html.escape(route)}</code>"]
    if u.language_code:
        lines.append(f"Language: {u.language_code}")
    lines.append(f'<a href="tg://user?id={u.id}">Open profile</a>')
    lines.append(f"\nAnything you write here is sent to the user by the bot.\n"
                 f"<code>{html.escape(NOTE_PREFIX)} text</code> — internal note · "
                 f"<code>#жалоба</code> <code>#вопрос</code> <code>#решено</code> — tags (not sent)\n"
                 f"/info · /ban · /unban")
    return "\n".join(lines)


def has_content(m: Message) -> bool:
    return any(getattr(m, k, None) for k in CONTENT)


def utcnow():
    return dt.datetime.utcnow()


async def react(bot: Bot, m: Message, emoji: str):
    try:
        await bot.set_message_reaction(m.chat.id, m.message_id, [ReactionTypeEmoji(emoji=emoji)])
    except Exception:
        pass                                           # reactions may be disabled in the group


async def ensure_topic(bot: Bot, chat_id: int, u: User, route: str, fresh: bool = False) -> int:
    async with _locks[(u.id, chat_id)]:
        if not fresh:
            t = await db.get_thread(u.id, chat_id)
            if t:
                return t
        topic = await bot.create_forum_topic(chat_id, topic_title(full_name(u), u.username, u.id, route))
        await db.set_thread(u.id, chat_id, topic.message_thread_id)
        await db.set_status(u.id, chat_id, "open")
        await bot.send_message(chat_id, user_card(u, route), message_thread_id=topic.message_thread_id)
        return topic.message_thread_id


async def refresh_topic_title(bot: Bot, uid: int, chat_id: int, thread_id: int):
    u = await db.get_user(uid) or {}
    th = await db.get_thread_row(uid, chat_id) or {}
    tags = await db.thread_tags(uid, chat_id)
    icon = "✅" if th.get("status") == "resolved" else next((i for t, i in TAG_ICONS if t in tags), "")
    name = topic_title(u.get("name") or uid, u.get("username"), uid, u.get("route") or "?", icon)
    try:
        await bot.edit_forum_topic(chat_id, thread_id, name=name)
    except TelegramBadRequest:
        pass                                           # TOPIC_NOT_MODIFIED


# ── working hours ──
def _hm(s):
    h, m = s.strip().split(":")
    return int(h) * 60 + int(m)


def _days(s):
    out = set()
    for part in s.replace(" ", "").split(","):
        if "-" in part:
            a, b = map(int, part.split("-"))
            out.update(range(a, b + 1))
        elif part:
            out.add(int(part))
    return out or set(range(1, 8))


HOURS = tuple(_hm(x) for x in WORK_HOURS.split("-")) if WORK_HOURS else None
DAYS = _days(WORK_DAYS)


def is_open(now: dt.datetime) -> bool:
    if not HOURS:
        return True
    if now.isoweekday() not in DAYS:
        return False
    m, (a, b) = now.hour * 60 + now.minute, HOURS
    return a <= m < b if a < b else (m >= a or m < b)


def opens_label(now: dt.datetime, lang=None) -> str:
    a = HOURS[0]
    for i in range(8):
        c = (now + dt.timedelta(days=i)).replace(hour=a // 60, minute=a % 60, second=0, microsecond=0)
        if c > now and c.isoweekday() in DAYS:
            hm = c.strftime("%H:%M")
            return hm if c.date() == now.date() else T.pick(T.WEEKDAYS, lang)[c.weekday()] + " " + hm
    return ""


class _Safe(dict):
    def __missing__(self, k):
        return "{" + k + "}"


async def maybe_away(bot: Bot, m: Message, u_row, route, chat_id, thread_id):
    now = dt.datetime.now(WORK_TZ)
    if is_open(now):
        return
    last = (u_row or {}).get("last_away_at")
    if last and (utcnow() - last).total_seconds() < AWAY_COOLDOWN_H * 3600:
        return
    lang = T.norm(route.get("lang")) or T.norm(m.from_user.language_code)
    tpl = route.get("away_text") or T.pick(T.AWAY, lang)
    try:
        text = tpl.format_map(_Safe(reply_hours=REPLY_HOURS, opens=opens_label(now, lang)))
    except (ValueError, IndexError):
        text = tpl
    sent = await m.answer(text)
    await db.mark_away(m.from_user.id)
    await db.log_message(direction="bot", user_id=m.from_user.id, chat_id=chat_id, thread_id=thread_id,
                         user_msg_id=sent.message_id, content_type="text", text=text)
    await bot.send_message(chat_id, "🌙 Auto-reply sent (outside working hours).",
                           message_thread_id=thread_id, disable_notification=True)


# ───────────────────────── user side ─────────────────────────

@private.message(CommandStart())
async def on_start(m: Message, command: CommandObject):
    key = (command.args or "").strip().lower()
    u = await db.get_user(m.from_user.id)
    if key and await db.get_route(key):
        route = key                                   # a new deep link moves the user to that channel
    elif u and u["route"]:
        route = u["route"]
    else:
        route = DEFAULT_ROUTE
    await db.upsert_user(m.from_user.id, m.from_user.username, full_name(m.from_user), m.from_user.language_code, route)
    r = await db.get_route(route) or {}
    await m.answer(r.get("welcome") or T.pick(T.WELCOME, r.get("lang"), m.from_user.language_code))


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
        await m.answer(T.pick(T.UNAVAILABLE, fu.language_code))
        return
    chat_id = route["chat_id"]

    reply = None
    if m.reply_to_message:
        row = await db.find_by_user_msg(fu.id, m.reply_to_message.message_id)
        if row and row["chat_id"] == chat_id and row["group_msg_id"]:
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
        await m.answer(T.pick(T.FAILED, route.get("lang"), fu.language_code))
        return
    await db.log_message(direction="in", user_id=fu.id, chat_id=chat_id, thread_id=thread_id,
                         user_msg_id=m.message_id, group_msg_id=sent.message_id,
                         content_type=m.content_type, text=m.text or m.caption)

    th = await db.get_thread_row(fu.id, chat_id) or {}
    if th.get("status") == "resolved":                # user wrote again → ticket reopens
        await db.set_status(fu.id, chat_id, "open")
        await refresh_topic_title(bot, fu.id, chat_id, thread_id)
    await maybe_away(bot, m, u, route, chat_id, thread_id)


# ───────────────────────── staff side: admin commands ─────────────────────────

HELP = (
    "<b>In a user's topic</b>\n"
    "• just write → sent to the user (reply to a message to answer it directly)\n"
    f"• <code>{html.escape(NOTE_PREFIX)} text</code> → internal note\n"
    "• <code>#жалоба</code> <code>#вопрос</code> <code>#предложение</code> <code>#спам</code> → tag; "
    "<code>#решено</code> / <code>#открыто</code> → status (any other #word is stored as a custom tag)\n"
    "• /info · /ban · /unban\n\n"
    "<b>Anywhere in the group</b>\n"
    "• /stats [days] — per channel (admins: <code>/stats 30 all</code>)\n\n"
    "<b>Admins</b>\n"
    "• /bind key lang · /lang key lang · /routes\n"
    "• /welcome key text · /away key text — custom text instead of the language default "
    "(<code>-</code> resets)\n"
    "• /syncprofile — re-apply bot description / about in all languages\n"
    "• /export [days|all] [key] — CSV files + Google Sheet if configured"
)


@staff.message(Command("help"))
async def cmd_help(m: Message):
    if await db.is_staff_chat(m.chat.id) or m.from_user.id in ADMINS:
        await m.reply(HELP)


@staff.message(Command("bind"))
async def cmd_bind(m: Message, command: CommandObject, bot: Bot):
    if m.from_user.id not in ADMINS:
        return
    args = (command.args or "").lower().split()
    key = args[0] if args else ""
    lang = T.norm(args[1]) if len(args) > 1 else None
    if not KEY_RE.match(key) or (len(args) > 1 and not lang):
        await m.reply("Usage: <code>/bind key lang</code>, e.g. <code>/bind betcroatia hr</code>\n"
                      f"key: latin letters, digits, _ or - · lang: {', '.join(T.LANGS)}")
        return
    chat = await bot.get_chat(m.chat.id)
    if not chat.is_forum:
        await m.reply("Turn on <b>Topics</b> in the group settings first, then run /bind again.")
        return
    await db.set_route(key, m.chat.id, m.chat.title)
    if lang:
        await db.set_lang(key, lang)
    r = await db.get_route(key)
    me = await bot.me()
    await m.reply(f"✅ Route <code>{key}</code> → this group · language <code>{r.get('lang') or 'auto'}</code>\n"
                  f"Link for users: https://t.me/{me.username}?start={key}\n\n"
                  f"Welcome they will see:\n<i>{html.escape(r.get('welcome') or T.pick(T.WELCOME, r.get('lang')))}</i>")


@staff.message(Command("lang"))
async def cmd_lang(m: Message, command: CommandObject):
    if m.from_user.id not in ADMINS:
        return
    args = (command.args or "").lower().split()
    if len(args) != 2 or not await db.get_route(args[0]) or not (T.norm(args[1]) or args[1] == "auto"):
        await m.reply(f"Usage: <code>/lang key lang</code> — {', '.join(T.LANGS)} or <code>auto</code> "
                      "(auto = the user's Telegram language)")
        return
    await db.set_lang(args[0], None if args[1] == "auto" else T.norm(args[1]))
    await m.reply(f"✅ <code>{html.escape(args[0])}</code> → {html.escape(args[1])}")


@staff.message(Command("welcome", "away"))
async def cmd_texts(m: Message, command: CommandObject):
    if m.from_user.id not in ADMINS:
        return
    parts = (command.args or "").split(maxsplit=1)
    if len(parts) < 2 or not await db.get_route(parts[0].lower()):
        hint = "Text the user sees after /start" if command.command == "welcome" else \
            "Text outside working hours. Placeholders: {reply_hours} {opens}"
        await m.reply(f"Usage: <code>/{command.command} key {html.escape(hint)}</code>")
        return
    key, value = parts[0].lower(), (None if parts[1].strip() == "-" else parts[1])
    await (db.set_welcome if command.command == "welcome" else db.set_away_text)(key, value)
    await m.reply(f"✅ {command.command} text for <code>{html.escape(key)}</code> "
                  f"{'reset to default' if value is None else 'saved'}.")


@staff.message(Command("routes"))
async def cmd_routes(m: Message, bot: Bot):
    if m.from_user.id not in ADMINS:
        return
    me = await bot.me()
    rows = await db.list_routes()
    if not rows:
        await m.reply("No routes yet. Run <code>/bind key</code> in a forum group.")
        return
    await m.reply("\n".join(f"• <code>{r['key']}</code> [{r.get('lang') or 'auto'}"
                            f"{', custom welcome' if r.get('welcome') else ''}{', custom away' if r.get('away_text') else ''}]"
                            f" → {html.escape(r['title'] or str(r['chat_id']))} — "
                            f"https://t.me/{me.username}?start={r['key']}" for r in rows))


# ── /stats ──
def _dur(sec):
    if sec is None:
        return "—"
    m = int(sec // 60)
    return f"{m // 60}h {m % 60:02d}m" if m >= 60 else f"{m}m"


async def build_stats(days: int, only_chat=None) -> str:
    since = utcnow() - dt.timedelta(days=days)
    rts = await db.list_routes()
    if only_chat is not None:
        rts = [r for r in rts if r["chat_id"] == only_chat]
    users = await db.all_users()
    route_of = {u["user_id"]: u["route"] for u in users}
    blank = lambda: dict(new=0, active=set(), msgs=0, complaint=set(), question=set(), suggestion=set(),
                         resolved=0, waiting=0, resp=[])
    per = {r["key"]: blank() for r in rts}
    for u in users:
        if u["route"] in per and u["created_at"] and u["created_at"] >= since:
            per[u["route"]]["new"] += 1
    by_user = defaultdict(list)
    for x in await db.messages_since(since):
        if x["direction"] in ("in", "out"):
            by_user[x["user_id"]].append(x)
    for uid, xs in by_user.items():
        s = per.get(route_of.get(uid))
        if s is None:
            continue
        waiting_since = None
        for x in xs:
            if x["direction"] == "in":
                s["msgs"] += 1
                s["active"].add(uid)
                waiting_since = waiting_since or x["created_at"]
            elif waiting_since:
                s["resp"].append((x["created_at"] - waiting_since).total_seconds())
                waiting_since = None
        if xs[-1]["direction"] == "in":
            s["waiting"] += 1
    for t in await db.tags_since(since):
        s = per.get(route_of.get(t["user_id"]))
        if s is None:
            continue
        if t["tag"] in ("complaint", "question", "suggestion"):
            s[t["tag"]].add(t["user_id"])
        elif t["tag"] == "resolved":
            s["resolved"] += 1
    if not per:
        return "No channels bound to this group."
    lines = [f"📊 <b>Last {days} days</b> (by channel)\n"]
    total = blank()
    for key in sorted(per):
        s = per[key]
        for k in ("new", "msgs", "resolved", "waiting"):
            total[k] += s[k]
        for k in ("active", "complaint", "question", "suggestion"):
            total[k] |= s[k]
        total["resp"] += s["resp"]
        lines.append(_stat_line(key, s))
    if len(per) > 1:
        lines.append("\n" + _stat_line("TOTAL", total))
    lines.append("\n<i>new = first contact · active = wrote · ⏳ = last message is unanswered · "
                 "⏱ = median first reply</i>")
    return "\n".join(lines)


def _stat_line(key, s):
    med = statistics.median(s["resp"]) if s["resp"] else None
    return (f"<b>{html.escape(key)}</b>: {s['new']} new · {len(s['active'])} active · {s['msgs']} msgs · "
            f"❗{len(s['complaint'])} ❓{len(s['question'])} 💡{len(s['suggestion'])} · ✅{s['resolved']} · "
            f"⏳{s['waiting']} · ⏱{_dur(med)}")


@staff.message(Command("stats"))
async def cmd_stats(m: Message, command: CommandObject):
    if not await db.is_staff_chat(m.chat.id) and m.from_user.id not in ADMINS:
        return
    args = (command.args or "").split()
    days = next((int(a) for a in args if a.isdigit()), 7)
    everything = "all" in args and m.from_user.id in ADMINS
    await m.reply(await build_stats(days, None if everything else m.chat.id))


# ── /export ──
def _s(v):
    return "" if v is None else v.strftime("%Y-%m-%d %H:%M") if isinstance(v, dt.datetime) else v


async def export_tables(since=None, key=None):
    users = await db.all_users()
    msgs = await db.messages_since(since)
    all_msgs = msgs if since is None else await db.messages_since(None)
    tags = await db.tags_since(None)
    threads = await db.all_threads()
    uinfo = {u["user_id"]: u for u in users}
    counts = defaultdict(lambda: {"in": 0, "out": 0})
    for x in all_msgs:
        if x["direction"] in ("in", "out"):
            counts[x["user_id"]][x["direction"]] += 1
    utags = defaultdict(set)
    for t in tags:
        if t["tag"] not in STATUS_TAGS:
            utags[t["user_id"]].add(t["tag"])
    status = {}
    for th in threads:
        status[th["user_id"]] = th.get("status") or ""
    keep = lambda uid: key is None or (uinfo.get(uid) or {}).get("route") == key
    active = {x["user_id"] for x in msgs}
    u_rows = [["user_id", "username", "name", "language", "channel", "first_seen_utc", "last_seen_utc",
               "msgs_from_user", "msgs_from_team", "tags", "status", "banned", "telegram_link"]]
    for u in users:
        uid = u["user_id"]
        if not keep(uid) or (since and uid not in active and (u["created_at"] or since) < since):
            continue
        u_rows.append([uid, u["username"] or "", u["name"] or "", u["lang"] or "", u["route"] or "",
                       _s(u["created_at"]), _s(u["last_seen"]), counts[uid]["in"], counts[uid]["out"],
                       "; ".join(sorted(utags[uid])), status.get(uid, ""), "yes" if u["banned"] else "",
                       f"tg://user?id={uid}"])
    m_rows = [["time_utc", "user_id", "username", "channel", "direction", "staff", "type", "text"]]
    for x in msgs:
        uid = x["user_id"]
        if not keep(uid):
            continue
        u = uinfo.get(uid) or {}
        m_rows.append([_s(x["created_at"]), uid, u.get("username") or "", u.get("route") or "", x["direction"],
                       x["staff_name"] or "", x["content_type"] or "", (x["text"] or "")[:5000]])
    return {"users": u_rows, "messages": m_rows}


def _csv(rows) -> bytes:
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue().encode("utf-8-sig")         # BOM so Excel opens Cyrillic/Lithuanian correctly


def _push_sheets(tables):
    import gspread
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_info(json.loads(GOOGLE_SA_JSON),
                                                  scopes=["https://www.googleapis.com/auth/spreadsheets"])
    sh = gspread.authorize(creds).open_by_key(GOOGLE_SHEET_ID)
    for name, rows in tables.items():
        try:
            ws = sh.worksheet(name)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(name, rows=max(len(rows), 100), cols=max(len(rows[0]), 10))
        ws.clear()
        ws.update(values=[[str(c) for c in r] for r in rows], range_name="A1", raw=False)
    return sh.url


@staff.message(Command("export"))
async def cmd_export(m: Message, command: CommandObject, bot: Bot):
    if m.from_user.id not in ADMINS:
        return
    args = [a.lower() for a in (command.args or "").split()]
    days = next((int(a) for a in args if a.isdigit()), None)
    key = next((a for a in args if not a.isdigit() and a != "all"), None)
    since = utcnow() - dt.timedelta(days=days) if days else None
    tables = await export_tables(since, key)
    tag = (key or "all") + (f"_{days}d" if days else "") + "_" + utcnow().strftime("%Y%m%d")
    for name, rows in tables.items():
        await bot.send_document(m.chat.id, BufferedInputFile(_csv(rows), f"{name}_{tag}.csv"),
                                message_thread_id=m.message_thread_id,
                                caption=f"{name}: {len(rows) - 1} rows")
    if GOOGLE_SA_JSON and GOOGLE_SHEET_ID:
        try:
            url = await asyncio.to_thread(_push_sheets, tables)
            await m.reply(f"✅ Google Sheet updated: {url}")
        except Exception as e:
            log.exception("sheet export failed")
            await m.reply(f"⚠️ Google Sheet export failed: {html.escape(str(e))[:300]}")


async def sheet_sync_loop():
    while True:
        await asyncio.sleep(SHEET_SYNC_MINUTES * 60)
        try:
            await asyncio.to_thread(_push_sheets, await export_tables())
            log.info("Google Sheet synced")
        except Exception:
            log.exception("scheduled sheet sync failed")


# ───────────────────────── staff side: inside a topic ─────────────────────────

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
    th = await db.get_thread_row(uid, m.chat.id) or {}
    tags = sorted(t for t in await db.thread_tags(uid, m.chat.id) if t not in STATUS_TAGS)
    await m.reply(f"ID <code>{uid}</code> · @{u.get('username') or '—'} · channel <code>{u.get('route')}</code>\n"
                  f"First seen: {_s(u.get('created_at'))} UTC · last: {_s(u.get('last_seen'))} UTC\n"
                  f"Messages: {c.get('in', 0)} from user, {c.get('out', 0)} from team\n"
                  f"Status: {th.get('status') or 'open'} · tags: {', '.join(tags) or '—'}"
                  + (" · 🚫 banned" if u.get("banned") else ""))


async def apply_tags(bot: Bot, m: Message, uid: int):
    found = [TAG_ALIASES.get(t.lower(), t.lower()) for t in re.findall(r"#([\w-]+)", m.text or "")]
    if not found:
        return
    for t in dict.fromkeys(found):
        await db.add_tag(uid, m.chat.id, t, m.from_user.id)
        if t in STATUS_TAGS:
            await db.set_status(uid, m.chat.id, t)
    await refresh_topic_title(bot, uid, m.chat.id, m.message_thread_id)
    await react(bot, m, "✍")


@staff.message(F.message_thread_id)
async def from_staff(m: Message, bot: Bot):
    if not m.from_user or m.from_user.is_bot or not has_content(m):
        return
    text = m.text or m.caption or ""
    if text.startswith("/"):
        return                                         # unknown command — never sent
    uid = await _topic_user(m)
    if not uid:
        return
    if m.text and m.text.lstrip().startswith("#"):
        await apply_tags(bot, m, uid)                 # tag message — internal
        return
    if text.startswith(NOTE_PREFIX):
        return                                         # internal note
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
    await react(bot, m, "👍")


async def sync_profile(bot: Bot) -> str:
    """Bot description / about / menu command in every language; only changed fields are sent."""
    from aiogram.types import BotCommand
    done, failed = [], []
    targets = [(None, "en")] + [(l, l) for l in T.LANGS if l != "en"] + [(a, T.ALIASES[a]) for a in ("sr", "bs")]
    for code, src in targets:
        try:
            cur = await bot.get_my_description(language_code=code)
            if cur.description != T.DESCRIPTION[src]:
                await bot.set_my_description(T.DESCRIPTION[src], language_code=code)
            cur = await bot.get_my_short_description(language_code=code)
            if cur.short_description != T.SHORT[src]:
                await bot.set_my_short_description(T.SHORT[src], language_code=code)
            await bot.set_my_commands([BotCommand(command="start", description=T.START_CMD[src])], language_code=code)
            done.append(code or "default")
        except Exception as e:                       # e.g. a code Telegram does not accept
            failed.append(f"{code}: {e}")
        await asyncio.sleep(0.3)                     # stay well below rate limits
    log.info("profile synced: %s%s", ", ".join(done), (" · failed: " + "; ".join(failed)) if failed else "")
    return f"✅ Profile synced: {', '.join(done)}" + (f"\n⚠️ {html.escape('; '.join(failed))}" if failed else "")


@staff.message(Command("syncprofile"))
async def cmd_syncprofile(m: Message, bot: Bot):
    if m.from_user.id in ADMINS:
        await m.reply(await sync_profile(bot))


async def main():
    await db.init()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.include_routers(private, staff)
    if not ADMINS:
        log.warning("ADMINS is empty — nobody can run /bind")
    if SYNC_PROFILE:
        asyncio.create_task(sync_profile(bot))
    if SHEET_SYNC_MINUTES and GOOGLE_SA_JSON and GOOGLE_SHEET_ID:
        asyncio.create_task(sheet_sync_loop())
    await bot.delete_webhook(drop_pending_updates=False)
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


if __name__ == "__main__":
    asyncio.run(main())
