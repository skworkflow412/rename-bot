import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import logging
from time import time

# Logging setup
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(message)s")

# Bot credentials
API_ID = "28597362"  # Replace with your API_ID
API_HASH = "594f16e2cf9a6173bdf7a1cca942d94c"  # Replace with your API_HASH
BOT_TOKEN = "7819689442:AAGyEI1CecfaeWzK6VeBRFyKz0McZsPUmBs"  # Replace with your bot token

# List of authorized user IDs
AUTHORIZED_USERS = [7846681671]  # Replace with Telegram user IDs

# Initialize the bot
app = Client(
    "rename_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    in_memory=True
)

# Temporary directory for downloads
DOWNLOAD_DIR = "downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# User file tracking
uploaded_files = {}


@app.on_message(filters.command("start"))
async def start_command(client, message):
    user_id = message.from_user.id

    if user_id not in AUTHORIZED_USERS:
        await message.reply_text("You are not authorized to use this bot.")
        return

    username = message.from_user.username or f"user_{user_id}"
    user_folder = os.path.join(DOWNLOAD_DIR, username)

    os.makedirs(user_folder, exist_ok=True)
    uploaded_files[user_id] = {"folder": user_folder, "files": []}

    await message.reply_text(
        f"Welcome, {message.from_user.first_name}!\n"
        f"Your folder has been created: `{username}`.\nSend me a file to rename.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Help", callback_data="help")]]
        )
    )


@app.on_message(filters.document)
async def handle_document(client, message):
    user_id = message.from_user.id

    if user_id not in AUTHORIZED_USERS:
        await message.reply_text("You are not authorized to use this bot.")
        return

    user_folder = uploaded_files.get(user_id, {}).get("folder")
    if not user_folder:
        username = message.from_user.username or f"user_{user_id}"
        user_folder = os.path.join(DOWNLOAD_DIR, username)
        os.makedirs(user_folder, exist_ok=True)
        uploaded_files[user_id] = {"folder": user_folder, "files": []}

    if message.document.file_size > 2 * 1024 * 1024 * 1024:
        await message.reply_text("File size exceeds 2GB limit!")
        return

    file_name = message.document.file_name
    file_path = os.path.join(user_folder, file_name)
    download_message = await message.reply_text(f"Downloading `{file_name}`...")

    try:
        start_time = time()
        downloaded_file_path = await client.download_media(
            message.document,
            file_name=file_path,
            progress=progress_callback,
            progress_args=(download_message, start_time)
        )
        uploaded_files[user_id]["files"].append(downloaded_file_path)
        await download_message.edit_text(
            f"File `{file_name}` downloaded successfully!\nUse `/rename <new_filename>` to rename it."
        )
    except Exception as e:
        await download_message.edit_text(f"Error downloading file: {str(e)}")


@app.on_message(filters.command("rename"))
async def rename_file(client, message):
    user_id = message.from_user.id

    if user_id not in AUTHORIZED_USERS:
        await message.reply_text("You are not authorized to use this bot.")
        return

    if user_id not in uploaded_files or not uploaded_files[user_id]["files"]:
        await message.reply_text("You have not uploaded any files to rename.")
        return

    if " " not in message.text:
        await message.reply_text("Please provide a new filename. Usage: `/rename <new_filename>`")
        return

    try:
        new_filename = message.text.split(" ", 1)[1]
        old_filepath = uploaded_files[user_id]["files"].pop(0)

        if not os.path.exists(old_filepath):
            await message.reply_text("The file no longer exists.")
            return

        new_filepath = os.path.join(uploaded_files[user_id]["folder"], new_filename)
        os.rename(old_filepath, new_filepath)

        if os.path.getsize(new_filepath) > 2 * 1024 * 1024 * 1024:
            await message.reply_text("The renamed file exceeds Telegram's 2GB upload limit.")
            return

        upload_message = await message.reply_text(f"Uploading `{new_filename}`...")
        start_time = time()

        try:
            await client.send_document(
                chat_id=message.chat.id,
                document=new_filepath,
                caption=f"Here is your renamed file: `{new_filename}`",
                progress=progress_callback,
                progress_args=(upload_message, start_time)
            )
            await upload_message.delete()
        except Exception as e:
            await message.reply_text(f"Error uploading file: {str(e)}")

    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")


@app.on_callback_query()
async def handle_callback_query(client, callback_query):
    if callback_query.data == "help":
        await callback_query.message.reply_text(
            "Commands:\n"
            "/start - Start the bot\n"
            "/rename <new_filename> - Rename a file\n"
        )


async def progress_callback(current, total, message, start_time):
    now = time()
    elapsed = now - start_time
    percentage = (current / total) * 100
    speed = current / elapsed if elapsed > 0 else 0
    time_remaining = (total - current) / speed if speed > 0 else 0

    progress_text = (
        f"Progress: {percentage:.2f}%\n"
        f"Downloaded/Uploaded: {current / (1024 * 1024):.2f} MB / {total / (1024 * 1024):.2f} MB\n"
        f"Speed: {speed / (1024 * 1024):.2f} MB/s\n"
        f"ETA: {time_remaining:.2f} seconds"
    )

    try:
        await message.edit_text(progress_text)
    except Exception as e:
        logging.error(f"Error updating progress: {e}")


async def run_bot():
    await app.start()
    print("Bot is running. Press Ctrl+C to stop.")
    await asyncio.Event().wait()


if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        print("Bot stopped.")
