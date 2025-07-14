from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes


TOKEN = "YOUR_TELEGRAM_BOT_TOKEN"
group_id = "YOUR_GROUP_ID"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Welcome to Zapata Bot! Send me any message and I'll forward it to the group.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    user_id = update.message.chat_id
    username = update.message.from_user.username or "NoUsername"

    try:
        info_msg = await context.bot.send_message(
            chat_id=group_id,
            text=f"📨 Message from: @{username} (ID: {user_id})"
        )
        await context.bot.send_message(
            chat_id=group_id,
            text=user_message,
            reply_to_message_id=info_msg.message_id
        )
        await update.message.reply_text("✅ Your message was sent successfully.")
    except Exception as e:
        await update.message.reply_text("❌ Failed to send to the group!")
        print(e)

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    username = update.message.from_user.username or "NoUsername"
    photo = update.message.photo[-1].file_id
    

    try:
        info_msg = await context.bot.send_message(
            chat_id=group_id,
            text=f"📸 Photo from: @{username} (ID: {user_id})"
        )
        await context.bot.send_photo(
            chat_id=group_id,
            photo=photo,
            reply_to_message_id=info_msg.message_id
        )
        await update.message.reply_text("✅ Your photo was sent successfully.")
    except Exception as e:
        await update.message.reply_text("❌ Failed to send to the group!")
        print(e)

async def handle_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    username = update.message.from_user.username or "NoUsername"
    video = update.message.video.file_id
    

    try:
        info_msg = await context.bot.send_message(
            chat_id=group_id,
            text=f"🎥 Video from: @{username} (ID: {user_id})"
        )
        await context.bot.send_video(
            chat_id=group_id,
            video=video,
            reply_to_message_id=info_msg.message_id
        )
        await update.message.reply_text("✅ Your video was sent successfully.")
    except Exception as e:
        await update.message.reply_text("❌ Failed to send to the group!")
        print(e)

async def handle_animation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    username = update.message.from_user.username or "NoUsername"
    animation = update.message.animation.file_id
    

    try:
        info_msg = await context.bot.send_message(
            chat_id=group_id,
            text=f"🎞 GIF from: @{username} (ID: {user_id})"
        )
        await context.bot.send_animation(
            chat_id=group_id,
            animation=animation,
            reply_to_message_id=info_msg.message_id
        )
        await update.message.reply_text("✅ Your GIF was sent successfully.")
    except Exception as e:
        await update.message.reply_text("❌ Failed to send to the group!")
        print(e)

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.chat_id
    username = update.message.from_user.username or "NoUsername"
    document = update.message.document.file_id
    

    try:
        info_msg = await context.bot.send_message(
            chat_id=group_id,
            text=f"📁 File from: @{username} (ID: {user_id})"
        )
        await context.bot.send_document(
            chat_id=group_id,
            document=document,
            reply_to_message_id=info_msg.message_id
        )
        await update.message.reply_text("✅ Your file was sent successfully.")
    except Exception as e:
        await update.message.reply_text("❌ Failed to send to the group!")
        print(e)

async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update.message.reply_to_message:
            return await update.message.reply_text("⚠️ Please reply to the user-info message.")

        replied_message = update.message.reply_to_message

        if not replied_message.text:
            return
        
        info_prefixes = ["📨", "📸", "🎥", "🎞", "📁"]
        is_info_message = any(replied_message.text.startswith(prefix) for prefix in info_prefixes)

        if not is_info_message:
            return

        user_id_text = replied_message.text.split("ID: ")[-1].split(")")[0]
        user_id = int(user_id_text.strip())

        if update.message.text:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📩 Reply from group:\n\n{update.message.text}"
            )
        elif update.message.photo:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=update.message.photo[-1].file_id,
                caption="📩 Reply from group"
            )
        elif update.message.video:
            await context.bot.send_video(
                chat_id=user_id,
                video=update.message.video.file_id,
                caption="📩 Reply from group"
            )
        elif update.message.animation:
            await context.bot.send_animation(
                chat_id=user_id,
                animation=update.message.animation.file_id,
                caption="📩 Reply from group"
            )
        elif update.message.document:
            await context.bot.send_document(
                chat_id=user_id,
                document=update.message.document.file_id,
                caption="📩 Reply from group"
            )

        await update.message.reply_text("✅ Your reply was delivered.")

    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text("❌ Failed to send!")


async def handle_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ This format is not supported.")

if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    handlers = [
        CommandHandler("start", start),
        MessageHandler(filters.REPLY, handle_reply),
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message),
        MessageHandler(filters.PHOTO, handle_photo),
        MessageHandler(filters.VIDEO, handle_video),
        MessageHandler(filters.ANIMATION, handle_animation),
        MessageHandler(filters.Document.ALL, handle_document),
        MessageHandler(filters.ALL, handle_unknown)
    ]

    for handler in handlers:
        app.add_handler(handler)

    print("✅ Bot is running!")
    app.run_polling()