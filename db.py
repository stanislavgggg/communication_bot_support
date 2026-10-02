"""Storage: routes (start-param → staff group), users, user↔topic threads, full message log.

DATABASE_URL empty  → SQLite file data/bot.db (local testing)
DATABASE_URL set    → Postgres (Railway plugin), postgres:// URLs are converted automatically
"""
import datetime as dt
import os
import pathlib

from sqlalchemy import (BigInteger, Boolean, Column, DateTime, Integer, MetaData, String, Table, Text,
                        delete, func, insert, select, update)
from sqlalchemy.ext.asyncio import create_async_engine


def _url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        pathlib.Path("data").mkdir(exist_ok=True)
        return "sqlite+aiosqlite:///data/bot.db"
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://"):]
    return url


engine = create_async_engine(_url(), pool_pre_ping=True)
md = MetaData()

routes = Table(
    "routes", md,
    Column("key", String(64), primary_key=True),          # deep-link param: t.me/<bot>?start=<key>
    Column("chat_id", BigInteger, nullable=False),        # staff forum group
    Column("title", String(255)),
    Column("welcome", Text),
)
users = Table(
    "users", md,
    Column("user_id", BigInteger, primary_key=True),
    Column("username", String(64)),
    Column("name", String(255)),
    Column("lang", String(16)),
    Column("route", String(64)),
    Column("banned", Boolean, nullable=False, default=False),
    Column("created_at", DateTime),
    Column("last_seen", DateTime),
)
threads = Table(
    "threads", md,
    Column("user_id", BigInteger, primary_key=True),
    Column("chat_id", BigInteger, primary_key=True),
    Column("thread_id", Integer, nullable=False),
)
messages = Table(
    "messages", md,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("created_at", DateTime),
    Column("direction", String(3)),        # in = user → staff, out = staff → user
    Column("user_id", BigInteger, index=True),
    Column("chat_id", BigInteger),         # staff group
    Column("thread_id", Integer),
    Column("user_msg_id", Integer),        # message id in the user's private chat
    Column("group_msg_id", Integer),       # message id in the staff group
    Column("staff_id", BigInteger),
    Column("staff_name", String(255)),
    Column("content_type", String(32)),
    Column("text", Text),
)


def now():
    return dt.datetime.utcnow()


async def init():
    async with engine.begin() as c:
        await c.run_sync(md.create_all)


async def _one(stmt):
    async with engine.connect() as c:
        r = (await c.execute(stmt)).mappings().first()
        return dict(r) if r else None


async def _all(stmt):
    async with engine.connect() as c:
        return [dict(r) for r in (await c.execute(stmt)).mappings()]


async def _exec(*stmts):
    async with engine.begin() as c:
        for s in stmts:
            await c.execute(s)


# ── routes ──
async def get_route(key):
    return await _one(select(routes).where(routes.c.key == key)) if key else None


async def set_route(key, chat_id, title):
    if await get_route(key):
        await _exec(update(routes).where(routes.c.key == key).values(chat_id=chat_id, title=title))
    else:
        await _exec(insert(routes).values(key=key, chat_id=chat_id, title=title))


async def set_welcome(key, text):
    await _exec(update(routes).where(routes.c.key == key).values(welcome=text))


async def list_routes():
    return await _all(select(routes).order_by(routes.c.key))


async def is_staff_chat(chat_id):
    return await _one(select(routes.c.key).where(routes.c.chat_id == chat_id).limit(1)) is not None


# ── users ──
async def get_user(user_id):
    return await _one(select(users).where(users.c.user_id == user_id))


async def upsert_user(user_id, username, name, lang, route=None):
    vals = dict(username=username, name=name, lang=lang, last_seen=now())
    if await get_user(user_id):
        if route:
            vals["route"] = route
        await _exec(update(users).where(users.c.user_id == user_id).values(**vals))
    else:
        await _exec(insert(users).values(user_id=user_id, route=route, banned=False, created_at=now(), **vals))


async def set_banned(user_id, banned):
    await _exec(update(users).where(users.c.user_id == user_id).values(banned=banned))


# ── topics ──
async def get_thread(user_id, chat_id):
    r = await _one(select(threads.c.thread_id).where(threads.c.user_id == user_id, threads.c.chat_id == chat_id))
    return r["thread_id"] if r else None


async def set_thread(user_id, chat_id, thread_id):
    await _exec(
        delete(threads).where(threads.c.user_id == user_id, threads.c.chat_id == chat_id),
        insert(threads).values(user_id=user_id, chat_id=chat_id, thread_id=thread_id),
    )


async def user_by_thread(chat_id, thread_id):
    r = await _one(select(threads.c.user_id).where(threads.c.chat_id == chat_id, threads.c.thread_id == thread_id))
    return r["user_id"] if r else None


# ── message log ──
async def log_message(**kw):
    kw.setdefault("created_at", now())
    await _exec(insert(messages).values(**kw))


async def find_by_group_msg(chat_id, group_msg_id):
    return await _one(select(messages).where(messages.c.chat_id == chat_id, messages.c.group_msg_id == group_msg_id))


async def find_by_user_msg(user_id, user_msg_id):
    return await _one(select(messages).where(messages.c.user_id == user_id, messages.c.user_msg_id == user_msg_id))


async def message_counts(user_id):
    rows = await _all(select(messages.c.direction, func.count().label("n"))
                      .where(messages.c.user_id == user_id).group_by(messages.c.direction))
    return {r["direction"]: r["n"] for r in rows}
