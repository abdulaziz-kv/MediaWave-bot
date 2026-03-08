#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode
from yt_dlp import YoutubeDL
from concurrent.futures import ThreadPoolExecutor

# ---------------- Config ----------------
BOT_TOKEN = "8686276832:AAHs_28CUCUbCXOI0tg_ZLyrdPBCLZOX9Fc"
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ---------------- Media Downloader ----------------
class MediaDownloader:
    def __init__(self):
        self.ffmpeg_path = "ffmpeg"  # Linux/Windows uchun
        if not os.path.exists("downloads"):
            os.mkdir("downloads")
        self.executor = ThreadPoolExecutor()

    async def download_video(self, url):
        opts = {'format': 'best', 'outtmpl': 'downloads/%(title)s.%(ext)s', 'ffmpeg_location': self.ffmpeg_path}
        return await asyncio.get_event_loop().run_in_executor(self.executor, lambda: self._sync_download(url, opts))

    async def download_audio(self, url):
        opts = {
            'format': 'bestaudio/best',
            'outtmpl': 'downloads/%(title)s.%(ext)s',
            'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
            'ffmpeg_location': "ffmpeg"
        }
        return await asyncio.get_event_loop().run_in_executor(self.executor, lambda: self._sync_download(url, opts, is_audio=True))

    def _sync_download(self, url, opts, is_audio=False):
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                filepath = ydl.prepare_filename(info)
                if is_audio:
                    filepath = os.path.splitext(filepath)[0] + ".mp3"
                return filepath, None
        except Exception as e:
            return None, str(e)

    def cleanup(self, path):
        if os.path.exists(path):
            os.remove(path)

downloader = MediaDownloader()

# ---------------- URL Validator ----------------
def validate_url(url):
    return any(x in url for x in ["youtube.com", "youtu.be", "instagram.com", "tiktok.com"])

# ---------------- Commands ----------------
@dp.message(Command('start'))
async def start_cmd(message: Message):
    await message.answer(
        """
🌊 <b>MediaWave Bot</b>

YouTube va Instagram videolarini tez yuklab oling!

<b>🔹 Qanday ishlatish:</b>
Menga video linkini yuboring, men avtomatik yuklab beraman

<b>🔹 Qo'llab-quvvatlanadi:</b>
▶️ YouTube (video/shorts)
📸 Instagram (reels/post)
🎵 TikTok

<b>🔹 Buyruqlar:</b>
/video [link] - Video yuklash
/audio [link] - MP3 audio yuklash
/help - Yordam

<b>📥 Link yuboring va media yuklab oling!</b>
""", parse_mode=ParseMode.HTML)

@dp.message(Command('help'))
async def help_cmd(message: Message):
    await message.answer(
        """
🔍 <b>MediaWave Bot - Yordam</b>

<b>📌 Qanday ishlatish:</b>
1. YouTube/Instagram/TikTok linkini yuboring
2. Bot avtomatik video yuklab beradi

<b>📝 Misollar:</b>
• https://youtube.com/watch?v=...
• https://youtu.be/...
• https://instagram.com/reel/...
• https://tiktok.com/@user/video/...

<b>⚙️ Buyruqlar:</b>
/start - Botni ishga tushirish
/help - Bu yordam xabari
/video [link] - Video yuklash

<b>⚠️ Eslatma:</b>
• Maksimal fayl hajmi: 50 MB
• Mualliflik huquqi bilan himoyalangan kontentni yuklamang
""", parse_mode=ParseMode.HTML)

@dp.message(Command('video'))
async def video_cmd(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Iltimos, video linkini yozing!\nMisol: `/video https://youtube.com/...`", parse_mode=ParseMode.MARKDOWN)
        return
    await process_video(message, args[1])

@dp.message(Command('audio'))
async def audio_cmd(message: Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("❌ Iltimos, video linkini yozing!\nMisol: `/audio https://youtube.com/...`", parse_mode=ParseMode.MARKDOWN)
        return
    await process_audio(message, args[1])

# ---------------- Message Handler ----------------
@dp.message()
async def handle_message(message: Message):
    url = message.text.strip()
    if not validate_url(url):
        await message.answer("❌ Noto‘g‘ri link. Faqat YouTube, Instagram, TikTok linklarini yuboring.")
        return
    await process_video(message, url)

# ---------------- Processing ----------------
async def process_video(message: Message, url: str):
    status = await message.answer("⏳ Video yuklanmoqda...")
    filepath, error = await downloader.download_video(url)
    if error:
        await status.edit_text(f"❌ Xatolik: {error}")
        return
    if not os.path.exists(filepath):
        await status.edit_text("❌ Video topilmadi.")
        return
    if os.path.getsize(filepath) > 50*1024*1024:
        await status.edit_text("❌ Fayl hajmi 50 MB dan katta.")
        downloader.cleanup(filepath)
        return
    await status.edit_text("📤 Video yuborilmoqda...")
    await message.answer_video(FSInputFile(filepath), caption="✅ Video tayyor!\n🌊 @MediaWavesBot")
    await status.delete()
    downloader.cleanup(filepath)

async def process_audio(message: Message, url: str):
    status = await message.answer("⏳ Audio yuklanmoqda...")
    filepath, error = await downloader.download_audio(url)
    if error:
        await status.edit_text(f"❌ Xatolik: {error}")
        return
    if not os.path.exists(filepath):
        await status.edit_text("❌ Audio topilmadi.")
        return
    if os.path.getsize(filepath) > 50*1024*1024:
        await status.edit_text("❌ Fayl hajmi 50 MB dan katta.")
        downloader.cleanup(filepath)
        return
    await status.edit_text("📤 Audio yuborilmoqda...")
    await message.answer_audio(FSInputFile(filepath), caption="✅ Audio tayyor!\n🌊 @MediaWavesBot")
    await status.delete()
    downloader.cleanup(filepath)

# ---------------- Run Bot ----------------
async def main():
    logger.info("Bot ishga tushmoqda...")
    info = await bot.get_me()
    logger.info(f"Bot: @{info.username} (ID: {info.id})")

    # Polling ishlatamiz, webhook yo‘q
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to‘xtatildi")
    except Exception as e:
        logger.error(f"Kutilmagan xatolik: {e}")