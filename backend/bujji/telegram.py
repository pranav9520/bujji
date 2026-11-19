"""Optional Telegram interface, restricted to explicitly allowlisted private chats."""
import asyncio
import os
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import httpx
from . import providers
from .reminders import due_utc
from .store import now


def authorized(message, allowed):
    user = str(message.get('from', {}).get('id', ''))
    chat = message.get('chat', {})
    return user in allowed and chat.get('type') == 'private' and str(chat.get('id')) == user


async def handle(text, user, store, tz):
    if text.startswith('/remember '):
        content = text[10:].strip()[:2000]
        if not content:
            return 'Usage: /remember a preference'
        store.remember(content, 'telegram-explicit')
        return 'Saved that memory.'
    if text == '/memories':
        return '\n'.join(m['content'] for m in store.rows('SELECT content FROM memories ORDER BY updated DESC LIMIT 10')) or 'No memories yet.'
    if text.startswith('/remind '):
        try:
            date, title = text[8:].split(' | ', 1)
            due = due_utc(date, tz)
            if due <= datetime.now(timezone.utc) or not title.strip():
                raise ValueError()
            store.execute('INSERT OR IGNORE INTO reminders(title,due,recurrence,created) VALUES(?,?,?,?)', (title.strip()[:500], due.isoformat(), 'none', now()))
            return f'Reminder saved for {due.astimezone(ZoneInfo(tz)).isoformat()}: {title.strip()}'
        except (ValueError, TypeError):
            return 'Usage: /remind 2026-12-01T19:00:00+05:30 | Submit assignment. Time must be in the future.'
    if text == '/reminders':
        return '\n'.join(f"#{r['id']} {r['title']} — {r['due']}" for r in store.rows("SELECT * FROM reminders WHERE status='pending' ORDER BY due LIMIT 20")) or 'No pending reminders.'
    if text.startswith('/cancel '):
        try:
            item = int(text.split()[1])
        except (ValueError, IndexError):
            return 'Usage: /cancel reminder_id'
        with store.db() as db:
            count = db.execute("UPDATE reminders SET status='cancelled' WHERE id=? AND status='pending'", (item,)).rowcount
        return 'Reminder cancelled.' if count else 'No pending reminder with that ID.'
    if text.startswith('/'):
        return 'Bujji: /remember text, /memories, /remind ISO-time | title, /reminders, /cancel ID. Other text chats with your daily model. File transfers use the authenticated web app.'
    session = f'telegram-{user}'
    try:
        result = await providers.reply(store.messages(session) + [{'role': 'user', 'content': text[:8000]}], store.rows('SELECT * FROM memories ORDER BY updated DESC LIMIT 10'))
        store.message(session, 'user', text[:8000])
        store.message(session, 'assistant', result['text'])
        return result['text'][:4000]
    except providers.ProviderError as exc:
        return str(exc)


async def poll(store, tz):
    token = os.getenv('TELEGRAM_BOT_TOKEN', '')
    allowed = {x.strip() for x in os.getenv('TELEGRAM_ALLOWED_USERS', '').split(',') if x.strip().isdigit()}
    if not token or not allowed:
        return
    url = 'https://api.telegram.org/bot' + token
    async with httpx.AsyncClient(timeout=35, trust_env=False) as client:
        while True:
            try:
                response = await client.post(url + '/getUpdates', json={'offset': store.state('tg-offset', 0), 'timeout': 20, 'allowed_updates': ['message']})
                response.raise_for_status()
                data = response.json()
                if not data.get('ok'):
                    raise ValueError()
                for update in data.get('result', []):
                    message = update.get('message', {})
                    user = str(message.get('from', {}).get('id', ''))
                    store.set_state('tg-offset', update['update_id'] + 1)
                    if not authorized(message, allowed):
                        continue
                    if not message.get('text'):
                        continue
                    answer = await handle(message['text'], user, store, tz)
                    sent = await client.post(url + '/sendMessage', json={'chat_id': user, 'text': answer})
                    sent.raise_for_status()
                    store.audit('telegram-reply', 'sent' if sent.json().get('ok') else 'failed')
                for notification in store.rows('SELECT * FROM notifications ORDER BY id LIMIT 100'):
                    for user in allowed:
                        key = f"tg-notification-{user}-{notification['id']}"
                        if store.state(key):
                            continue
                        sent = await client.post(url + '/sendMessage', json={'chat_id': user, 'text': notification['content'][:4000]})
                        sent.raise_for_status()
                        if not sent.json().get('ok'):
                            raise ValueError()
                        store.set_state(key, True)
                await asyncio.sleep(1)
            except (httpx.HTTPError, ValueError, KeyError, OSError):
                store.audit('telegram', 'connection/delivery failed; retrying')
                await asyncio.sleep(10)
