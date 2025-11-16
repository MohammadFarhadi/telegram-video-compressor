import asyncio
import subprocess
import tempfile
import os
from pathlib import Path

from telegram import Update, Message
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# bot token here
def load_bot_token() -> str:
    """
    Load bot token from either:
    1) BOT_TOKEN environment variable (for server / future deploy)
    2) keys/token.txt file relative to this bot.py (for local dev)
    """
    # 1) اول از env بخون (به درد سرور و هاست می‌خوره)
    env_token = os.getenv("BOT_TOKEN")
    if env_token:
        return env_token.strip()

    # 2) بعد از فایل محلی: ./keys/token.txt کنار bot.py
    base_dir = Path(__file__).parent          # پوشه‌ای که bot.py توشه
    token_path = base_dir / "keys" / "token.txt"

    if not token_path.exists():
        raise RuntimeError(
            f"token.txt not found at {token_path}!\n"
            "Create a file 'keys/token.txt' next to bot.py and put your bot token in it."
        )

    token = token_path.read_text(encoding="utf-8").strip()
    if not token:
        raise RuntimeError("token.txt is empty! Put your bot token inside it.")

    return token



BOT_TOKEN = load_bot_token()


# ---------- Utility: run ffmpeg to compress video ----------
def compress_video(input_path: Path, output_path: Path) -> None:
    """
    Run ffmpeg to compress a video.

    - scale=-2:720   → keep aspect ratio, max height = 720
    - libx264        → common H.264 codec
    - -crf 28        → quality factor (higher = more compression, lower quality)
    - veryfast       → faster encoding( faster means less compression)
    - aac            → audio codec
    """
    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_path),
        "-vf", "scale=-2:720",
        "-c:v", "libx264",
        "-crf", "29",
        "-preset", "slow",
        "-c:a", "aac",

        str(output_path),
    ]
    subprocess.run(cmd, check=True)


# ---------- Helper: extract video file from a message ----------
def get_video_from_message(message: Message):
    """
    Given a Telegram message, return (file_obj, file_name) if it contains a video,
    or (None, None) otherwise.
    """
    # Case 1: Normal video
    if message.video:
        file_obj = message.video
        file_name = message.video.file_name or "input.mp4"
        return file_obj, file_name

    # Case 2: Document that is actually a video
    if message.document and message.document.mime_type and message.document.mime_type.startswith("video/"):
        file_obj = message.document
        file_name = message.document.file_name or "input.mp4"
        return file_obj, file_name

    # No video
    return None, None


# ---------- /start command ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "سلام 👋\n"
        "من یک ربات فشرده‌ساز ویدیو هستم.\n"
        "روش استفاده:\n"
        "1️⃣ یک ویدیو بفرست.\n"
        "2️⃣ روی همون ویدیو Reply بزن و بنویس: /compress\n"
        "من نسخه‌ی کم‌حجم‌ترش رو برمی‌گردونم. 🎬"
    )


# ---------- /compress command ----------
async def compress_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message = update.message
    if message is None:
        return

    # 1️⃣ اول سعی می‌کنیم خود همین پیام ویدیو داشته باشه
    media_obj, file_name = get_video_from_message(message)

    # 2️⃣ اگر خود پیام ویدیو نداشت، می‌ریم سراغ پیامی که بهش ریپلای شده
    if media_obj is None and message.reply_to_message:
        media_obj, file_name = get_video_from_message(message.reply_to_message)

    # 3️⃣ اگر هنوز هم ویدیو نداریم، به کاربر بگو چی‌کار باید بکنه
    if media_obj is None:
        await message.reply_text(
            "برای استفاده از /compress باید یا:\n"
            "📌 همون پیامی که می‌فرستی خودش ویدیو داشته باشه (با کپشن /compress)،\n"
            "یا این‌که روی یک ویدیو Reply کنی و /compress رو بفرستی. 🙂"
        )
        return

    await message.reply_text("✅ ویدیو رو گرفتم، دارم فشرده‌اش می‌کنم...")

    # اینجا media_obj یا video هست یا document (ویدئویی)
    file_obj = await media_obj.get_file()

    # بقیه مثل قبل 👇
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        input_path = tmpdir_path / file_name
        output_path = tmpdir_path / f"compressed_{file_name}"

        # دانلود از سرور تلگرام
        await file_obj.download_to_drive(custom_path=input_path)

        # اجرای ffmpeg
        try:
            compress_video(input_path, output_path)
        except subprocess.CalledProcessError:
            await message.reply_text("❌ یک مشکلی در حین فشرده‌سازی پیش اومد.")
            return

        original_size = input_path.stat().st_size / (1024 * 1024)
        compressed_size = output_path.stat().st_size / (1024 * 1024)

        await message.reply_video(
            video=output_path.open("rb"),
            caption=(
                "🎬 این هم نسخه‌ی فشرده‌شده.\n"
                f"حجم قبلی: {original_size:.2f} MB\n"
                f"حجم جدید: {compressed_size:.2f} MB"
            ),
        )


# ---------- Main entry ----------
def main() -> None:
    # اینجا دیگه async نیست
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("compress", compress_command))

    print("Bot is running... Press Ctrl+C to stop.")
    # اینجا هم بدون await
    app.run_polling()


if __name__ == "__main__":
    main()
