# Support / tipster communication bot

Users write to the bot → each user gets their own topic in a staff forum group →
staff or tipsters reply in the topic → the bot sends the reply to the user.
Tipsters never use their personal Telegram accounts; every conversation is logged.

## Setup
1. @BotFather → /newbot → token. `/setjoingroups` → Enable.
2. Create a Telegram **supergroup**, turn on **Topics**.
3. Add the bot as **admin** with **Manage topics** permission.
4. Deploy (Railway): new service from this folder, add the **Postgres** plugin,
   set variables from `.env.example` (`DATABASE_URL=${{Postgres.DATABASE_URL}}`).
   Start command: `python bot.py`.
5. In the group, an admin writes `/bind main` → the bot replies with the user link.

## One group per tipster
Create a group per tipster/community, add the tipster + the bot, run `/bind mario`.
Put `https://t.me/<bot>?start=mario` in the channel instead of the tipster's @username.
Add yourself to every group to see all conversations.
Several keys can also point to one shared group.

## Staff commands (inside a user's topic)
- just write → sent to the user (text, photos, voice, files, stickers…)
- reply to a message → the user sees it as a reply
- `// text` → internal note, never sent
- `/info` · `/ban` · `/unban`

Admin commands in any bound group: `/bind key`, `/welcome key text`, `/routes`.

## Limits
- Edits and deletions are not synced (send a correction instead).
- Everyone in a tipster's group sees all of that route's conversations.
- Albums arrive as separate messages.
