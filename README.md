# 🤖 Zapata Bot

**Zapata Bot** is a Telegram bot that forwards user messages to a specific group and allows the group to reply back to users. It supports text, photos, videos, documents, and GIFs.

## 🚀 Features

- Forward messages and media from users to a group
- Allow group replies via message reply
- Supports text, photo, video, GIF, and document types

## ⚙️ Setup

1. Get your bot token from [BotFather](https://t.me/BotFather)
2. Get the group ID (e.g., using [RawDataBot](https://t.me/RawDataBot))
3. Update the config:

```python
TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
group_id = "YOUR_GROUP_ID"
````

4. Install dependencies:

```bash
pip install python-telegram-bot --upgrade
```

5. Run the bot:

```bash
python zapata.py
```

## 📝 License

MIT License

