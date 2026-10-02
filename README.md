# Support / communication bot for Telegram channels

Subscribers write to the bot (contact in every channel description) → each user gets a topic
in one staff forum group → the team replies in the topic → the bot sends the reply.
Nobody has to answer from a personal account; every conversation and user is stored.

## Setup
1. @BotFather → token. `/setjoingroups` → Enable.
2. Supergroup → turn on **Topics** → add the bot as **admin** with **Manage topics**.
3. Railway: service from this folder + **Postgres** plugin; variables from `.env.example`.
   Start command: `python bot.py`.
4. In the group, for every channel: `/bind <key> <lang>` → each gives a link
   `https://t.me/<bot>?start=<key>` — put it in that channel's description:
   `/bind betcroatia hr` · `/bind luckyguru lt` · `/bind luckylatvia lv` · `/bind betbulgaria bg`
   · `/bind apuestasguru es` · `/bind luckyguruarab ar`
   The channel's welcome and auto-reply are then in its language automatically.
   Only if you want a different text: `/welcome key …` / `/away key …` (`-` resets).
5. Bot profile (description, About, menu) is set in all languages on every start from `texts.py`
   (en, lt, lv, hr, bg, es, ru, ar; Serbian/Bosnian users get Croatian). `/syncprofile` re-applies.
   Edit texts in `texts.py` and redeploy. Have native speakers check the translations.

## In a user's topic
- write → goes to the user; reply to a message → user sees it as a reply
- `// text` → internal note
- `#жалоба` `#вопрос` `#предложение` `#спам` → tags; `#решено` / `#открыто` → status
  (EN works too: #complaint #question #resolved…; any other `#word` = custom tag).
  Tag messages are never sent. The topic title gets ❗ ❓ 💡 or ✅; a resolved ticket reopens
  automatically when the user writes again.
- `/info` · `/ban` · `/unban`

## Reports
- `/stats [days]` — per channel bound to this group: new users, active, messages,
  ❗ complaints, ❓ questions, 💡 suggestions, ✅ resolved, ⏳ unanswered, ⏱ median first reply.
  Admins: `/stats 30 all`.
- `/export [days|all] [key]` (admins) — `users.csv` + `messages.csv` in the chat,
  plus tabs `users` / `messages` in the Google Sheet if configured.

## Google Sheet
Google Cloud → service account → JSON key → paste into `GOOGLE_SA_JSON`.
Share the sheet with the service-account e-mail as Editor, put its ID into `GOOGLE_SHEET_ID`.
`SHEET_SYNC_MINUTES=60` keeps it updated automatically.

## Limits
- Edits and deletions are not synced.
- Broadcasts: the bot can only message users who started it (all users in the base did).
- Albums arrive as separate messages.
