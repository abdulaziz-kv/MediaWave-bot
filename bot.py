#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import os  ########### QO'SHILDI ###########
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode

from config import BOT_TOKEN, ADMIN_IDS, logger
from utils import validate_url, extract_video_id
from downloader import MediaDownloader

# Bot va dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
downloader = MediaDownloader()


# /start komandasi
@dp.message(Command('start'))
async def cmd_start(message: Message):
    """Start komandasi"""
    welcome_text = """
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
    """
    await message.answer(welcome_text, parse_mode=ParseMode.HTML)


# /help komandasi
@dp.message(Command('help'))
async def cmd_help(message: Message):
    """Yordam komandasi"""
    help_text = """
🔍 <b>MediaWave Bot - Yordam</b>

<b>📌 Qanday ishlatish:</b>
1. YouTube/Instagram/TikTok linkini yuboring
2. Bot avtomatik video yuklab beradi
3. Agar audio kerak bo'lsa, /audio buyrug'ini ishlating

<b>📝 Misollar:</b>
• https://youtube.com/watch?v=...
• https://youtu.be/...
• https://instagram.com/reel/...
• https://tiktok.com/@user/video/...

<b>⚙️ Buyruqlar:</b>
/start - Botni ishga tushirish
/help - Bu yordam xabari
/video [link] - Video yuklash
/audio [link] - MP3 yuklash

<b>⚠️ Eslatma:</b>
• Maksimal fayl hajmi: 50 MB
• Mualliflik huquqi bilan himoyalangan kontentni yuklamang
    """
    await message.answer(help_text, parse_mode=ParseMode.HTML)


# /video komandasi
@dp.message(Command('video'))
async def cmd_video(message: Message):
    """Video yuklash"""
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer("❌ Iltimos, video linkini ham yozing!\nMisol: `/video https://youtube.com/...`",
                             parse_mode=ParseMode.MARKDOWN)
        return

    url = args[1]
    await process_video(message, url)


# /audio komandasi
@dp.message(Command('audio'))
async def cmd_audio(message: Message):
    """Audio (MP3) yuklash"""
    args = message.text.split(maxsplit=1)

    if len(args) < 2:
        await message.answer("❌ Iltimos, video linkini ham yozing!\nMisol: `/audio https://youtube.com/...`",
                             parse_mode=ParseMode.MARKDOWN)
        return

    url = args[1]
    await process_audio(message, url)


# Link yuborilganda (avtomatik video)
@dp.message()
async def handle_message(message: Message):
    """Xabarlarni qayta ishlash"""
    url = message.text.strip()

    # URL tekshirish
    if not validate_url(url):
        await message.answer(
            "❌ Noto'g'ri link yoki qo'llab-quvvatlanmaydigan platforma.\nFaqat YouTube, Instagram va TikTok linklarini yuboring.")
        return

    # Avtomatik video yuklash
    await process_video(message, url)


async def process_video(message: Message, url: str):
    """Video yuklab yuborish"""
    status_msg = await message.answer("⏳ Video yuklanmoqda... Bu biroz vaqt olishi mumkin.")

    try:
        # Yuklab olish
        filepath, error = await downloader.download_video(url)

        if error:
            await status_msg.edit_text(f"❌ Xatolik: {error}")
            return

        if not filepath or not os.path.exists(filepath):
            await status_msg.edit_text("❌ Video yuklab olishda xatolik yuz berdi.")
            return

        # Fayl hajmini tekshirish
        file_size = os.path.getsize(filepath)
        if file_size > 50 * 1024 * 1024:
            await status_msg.edit_text(
                "❌ Fayl hajmi 50 MB dan katta. Telegram bunday katta fayllarni qo'llab-quvvatlamaydi.")
            downloader.cleanup(filepath)
            return

        # Videoni yuborish
        await status_msg.edit_text("📤 Video yuborilmoqda...")

        video = FSInputFile(filepath)
        await message.answer_video(
            video=video,
            caption="✅ Video tayyor!\n\n🌊 @MediaWaveBot"
        )

        # Tozalash
        await status_msg.delete()
        downloader.cleanup(filepath)

    except Exception as e:
        logger.error(f"Video processing error: {e}")
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")


async def process_audio(message: Message, url: str):
    """Audio (MP3) yuklab yuborish"""
    status_msg = await message.answer("⏳ Audio yuklanmoqda... Bu biroz vaqt olishi mumkin.")

    try:
        # Yuklab olish
        filepath, error = await downloader.download_audio(url)

        if error:
            await status_msg.edit_text(f"❌ Xatolik: {error}")
            return

        if not filepath or not os.path.exists(filepath):
            await status_msg.edit_text("❌ Audio yuklab olishda xatolik yuz berdi.")
            return

        # Fayl hajmini tekshirish
        file_size = os.path.getsize(filepath)
        if file_size > 50 * 1024 * 1024:
            await status_msg.edit_text(
                "❌ Fayl hajmi 50 MB dan katta. Telegram bunday katta fayllarni qo'llab-quvvatlamaydi.")
            downloader.cleanup(filepath)
            return

        # Audioni yuborish
        await status_msg.edit_text("📤 Audio yuborilmoqda...")

        audio = FSInputFile(filepath)
        await message.answer_audio(
            audio=audio,
            caption="✅ Audio tayyor!\n\n🌊 @MediaWaveBot"
        )

        # Tozalash
        await status_msg.delete()
        downloader.cleanup(filepath)

    except Exception as e:
        logger.error(f"Audio processing error: {e}")
        await status_msg.edit_text(f"❌ Xatolik yuz berdi: {str(e)}")


# Botni ishga tushirish
async def main():
    """Asosiy funksiya"""
    logger.info("Bot ishga tushmoqda...")

    # Bot haqida ma'lumot
    bot_info = await bot.get_me()
    logger.info(f"Bot: @{bot_info.username} (ID: {bot_info.id})")

    # Pollingni boshlash
    await dp.start_polling(bot)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to'xtatildi")
    except Exception as e:
        logger.error(f"Kutilmagan xatolik: {e}")