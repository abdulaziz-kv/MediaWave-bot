#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import logging
import os
import time
import subprocess
import hashlib
import sys
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from yt_dlp import YoutubeDL
from concurrent.futures import ThreadPoolExecutor
import aiofiles
import aiofiles.os


# ---------------- FFmpeg tekshirish ----------------
def check_ffmpeg():
    """FFmpeg mavjudligini tekshirish"""
    try:
        # FFmpeg ni topishga urinish
        result = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True)
        if result.returncode == 0:
            logger.info("FFmpeg topildi: ffmpeg")
            return "ffmpeg"
    except FileNotFoundError:
        pass

    # Windows uchun umumiy joylar
    common_paths = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
        r"C:\Program Files (x86)\ffmpeg\bin\ffmpeg.exe",
        os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe"),
        os.path.join(os.getcwd(), "ffmpeg.exe"),
        os.path.join(os.getcwd(), "bin", "ffmpeg.exe"),
    ]

    for path in common_paths:
        if os.path.exists(path):
            logger.info(f"FFmpeg topildi: {path}")
            return path

    # imageio-ffmpeg ni tekshirish
    try:
        import imageio_ffmpeg
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
        logger.info(f"FFmpeg topildi (imageio): {ffmpeg_path}")
        return ffmpeg_path
    except ImportError:
        logger.warning("imageio-ffmpeg o'rnatilmagan")
    except Exception as e:
        logger.warning(f"imageio-ffmpeg xatolik: {e}")

    # Agar hech narsa topilmasa, foydalanuvchiga xabar berish
    logger.error("FFmpeg topilmadi! Audio yuklash ishlamaydi.")
    return None


# ---------------- Config ----------------
BOT_TOKEN = "8686276832:AAHs_28CUCUbCXOI0tg_ZLyrdPBCLZOX9Fc"
ADMIN_ID = 8686276832  # O'z Telegram ID ingizni yozing
ADMIN_USERNAME = "abdulaziz_kv"  # Admin username

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# FFmpeg ni tekshirish
FFMPEG_PATH = check_ffmpeg()
if FFMPEG_PATH:
    logger.info(f"✅ FFmpeg muvaffaqiyatli topildi: {FFMPEG_PATH}")
else:
    logger.warning("⚠️ FFmpeg topilmadi! Audio yuklash ishlamaydi.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ---------------- URL Cache ----------------
class URLCache:
    """URL larni qisqa ID bilan saqlash"""

    def __init__(self):
        self.cache = {}  # {short_id: full_url}
        self.reverse_cache = {}  # {full_url: short_id}
        self.expiry = {}  # {short_id: expiry_time}
        self.cache_duration = 3600  # 1 soat

    def shorten(self, url):
        """URL ni qisqartirish"""
        # Agar URL allaqachon keshda bo'lsa
        if url in self.reverse_cache:
            short_id = self.reverse_cache[url]
            self.expiry[short_id] = time.time() + self.cache_duration
            return short_id

        # Yangi qisqa ID yaratish
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        short_id = f"id_{url_hash}"

        # Keshga saqlash
        self.cache[short_id] = url
        self.reverse_cache[url] = short_id
        self.expiry[short_id] = time.time() + self.cache_duration

        # Eski keshlarni tozalash
        self.cleanup()

        return short_id

    def get_url(self, short_id):
        """Qisqa ID dan URL ni olish"""
        if short_id in self.cache:
            # Muddati o'tmagan bo'lsa
            if time.time() < self.expiry.get(short_id, 0):
                return self.cache[short_id]
            else:
                # Muddati o'tgan bo'lsa o'chirish
                del self.cache[short_id]
                self.reverse_cache = {v: k for k, v in self.cache.items()}
        return None

    def cleanup(self):
        """Muddati o'tgan keshlarni tozalash"""
        current_time = time.time()
        expired = [sid for sid, exp in self.expiry.items() if current_time > exp]
        for sid in expired:
            if sid in self.cache:
                url = self.cache[sid]
                del self.cache[sid]
                if url in self.reverse_cache:
                    del self.reverse_cache[url]
            if sid in self.expiry:
                del self.expiry[sid]


url_cache = URLCache()


# ---------------- MediaDownloader ----------------
class MediaDownloader:
    def __init__(self):
        self.ffmpeg_path = FFMPEG_PATH
        self.download_dir = "downloads"
        self.temp_dir = "temp"

        # Papkalarni yaratish
        for folder in [self.download_dir, self.temp_dir]:
            if not os.path.exists(folder):
                os.makedirs(folder)
                logger.info(f"{folder} papkasi yaratildi")

        self.executor = ThreadPoolExecutor(max_workers=4)
        self.downloaded_videos = {}
        self.user_stats = {}
        self.today_requests = 0
        self.last_reset = datetime.now().date()

        # yt-dlp ni yangilash
        self.update_yt_dlp()

    def update_yt_dlp(self):
        """yt-dlp ni yangilash"""
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "yt-dlp"],
                           capture_output=True, text=True)
            logger.info("✅ yt-dlp yangilandi")
        except Exception as e:
            logger.error(f"❌ yt-dlp yangilashda xatolik: {e}")

    def update_stats(self):
        """Kunlik statistikani yangilash"""
        today = datetime.now().date()
        if today != self.last_reset:
            self.today_requests = 0
            self.last_reset = today
            logger.info("Kunlik statistika reset qilindi")

    def format_duration(self, seconds):
        """Vaqtni formatlash (float yoki int bo'lishi mumkin)"""
        if not seconds:
            return "Noma'lum"

        try:
            # Float ni int ga aylantirish
            seconds = int(float(seconds))
            minutes = seconds // 60
            secs = seconds % 60
            return f"{minutes}:{secs:02d}"
        except:
            return "Noma'lum"

    async def get_video_info(self, url):
        """Video ma'lumotlarini olish (yuklamasdan)"""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
        }

        try:
            loop = asyncio.get_event_loop()
            with YoutubeDL(opts) as ydl:
                info = await loop.run_in_executor(
                    self.executor,
                    lambda: ydl.extract_info(url, download=False)
                )

                # Instagram/TikTok uchun maxsus
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]

                return {
                    'title': info.get('title', 'Unknown')[:100],
                    'url': url,
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', info.get('channel', info.get('creator', 'Unknown')))[:100],
                    'views': info.get('view_count', 0),
                    'likes': info.get('like_count', 0),
                    'id': info.get('id', ''),
                    'platform': self.get_platform(url),
                    'thumbnail': info.get('thumbnail', '')
                }, None
        except Exception as e:
            logger.error(f"Video info olishda xatolik: {e}")
            return None, str(e)

    def get_platform(self, url):
        """Platformani aniqlash"""
        url_lower = url.lower()
        if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
            return 'youtube'
        elif 'instagram.com' in url_lower:
            return 'instagram'
        elif 'tiktok.com' in url_lower:
            return 'tiktok'
        elif 'facebook.com' in url_lower or 'fb.watch' in url_lower:
            return 'facebook'
        elif 'twitter.com' in url_lower or 'x.com' in url_lower:
            return 'twitter'
        else:
            return 'other'

    async def download_video(self, url, chat_id=None):
        """Video yuklash"""
        platform = self.get_platform(url)

        # Asosiy sozlamalar
        opts = {
            'outtmpl': f'{self.download_dir}/%(title)s_%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'restrictfilenames': True,
        }

        # Platformaga qarab format sozlamalari
        if platform == 'youtube':
            opts['format'] = 'best[filesize<50M]/best'
        else:
            opts['format'] = 'best'
            opts['headers'] = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                lambda: self._sync_download(url, opts, chat_id, platform)
            )
            return result
        except Exception as e:
            logger.error(f"Video yuklashda xatolik: {e}")
            return None, str(e)

    async def download_audio(self, url):
        """Audio yuklash"""
        if not self.ffmpeg_path:
            return None, "FFmpeg topilmadi! Audio yuklash uchun FFmpeg o'rnatish kerak."

        platform = self.get_platform(url)

        opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'{self.download_dir}/%(title)s_%(id)s.%(ext)s',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192'
            }],
            'ffmpeg_location': self.ffmpeg_path,
            'quiet': True,
            'no_warnings': True,
            'restrictfilenames': True,
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                lambda: self._sync_download(url, opts, is_audio=True, platform=platform)
            )
            return result
        except Exception as e:
            logger.error(f"Audio yuklashda xatolik: {e}")
            return None, str(e)

    def _sync_download(self, url, opts, chat_id=None, platform='other', is_audio=False):
        """Sinxron yuklash"""
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)

                # Playlist/entry uchun
                if 'entries' in info and info['entries']:
                    info = info['entries'][0]

                filepath = ydl.prepare_filename(info)

                if is_audio:
                    filepath = os.path.splitext(filepath)[0] + ".mp3"
                elif chat_id:
                    self.downloaded_videos[chat_id] = {
                        'title': info.get('title', 'Unknown'),
                        'url': url,
                        'video_path': filepath,
                        'timestamp': time.time(),
                        'video_id': info.get('id', ''),
                        'platform': platform
                    }

                logger.info(f"✅ Yuklandi: {os.path.basename(filepath)} ({platform})")
                return filepath, None

        except Exception as e:
            logger.error(f"❌ Yuklashda xatolik ({platform}): {e}")
            return None, str(e)

    async def cleanup(self, path):
        """Faylni o'chirish"""
        try:
            if os.path.exists(path):
                await aiofiles.os.remove(path)
                logger.info(f"🗑 Fayl o'chirildi: {os.path.basename(path)}")

                for chat_id, data in list(self.downloaded_videos.items()):
                    if data.get('video_path') == path:
                        del self.downloaded_videos[chat_id]
                        break
        except Exception as e:
            logger.error(f"Fayl o'chirishda xatolik: {e}")

    async def cleanup_old_files(self, hours=24):
        """Eski fayllarni tozalash"""
        try:
            current_time = time.time()
            cleaned_count = 0

            for filename in os.listdir(self.download_dir):
                filepath = os.path.join(self.download_dir, filename)
                if os.path.isfile(filepath):
                    file_time = os.path.getctime(filepath)
                    if current_time - file_time > hours * 3600:
                        await aiofiles.os.remove(filepath)
                        cleaned_count += 1
                        logger.info(f"🗑 Eski fayl tozalandi: {filename}")

            if cleaned_count > 0:
                logger.info(f"✅ Tozalash yakunlandi: {cleaned_count} fayl o'chirildi")
            return cleaned_count

        except Exception as e:
            logger.error(f"Tozalashda xatolik: {e}")
            return 0

    async def get_stats(self):
        """Statistika olish"""
        self.update_stats()

        try:
            total_files = 0
            total_size = 0

            for filename in os.listdir(self.download_dir):
                filepath = os.path.join(self.download_dir, filename)
                if os.path.isfile(filepath):
                    total_files += 1
                    total_size += os.path.getsize(filepath)

            total_size_mb = total_size / (1024 * 1024)

            return {
                'users': len(self.user_stats),
                'files': total_files,
                'size_mb': total_size_mb,
                'today_requests': self.today_requests,
                'active_downloads': len(self.downloaded_videos)
            }
        except Exception as e:
            logger.error(f"Statistika olishda xatolik: {e}")
            return {
                'users': len(self.user_stats),
                'files': 0,
                'size_mb': 0,
                'today_requests': self.today_requests,
                'active_downloads': len(self.downloaded_videos)
            }


downloader = MediaDownloader()


# ---------------- URL Validator ----------------
def validate_url(url):
    platforms = [
        "youtube.com", "youtu.be", "m.youtube.com",
        "instagram.com", "instagr.am",
        "tiktok.com", "vm.tiktok.com",
        "facebook.com", "fb.watch",
        "twitter.com", "x.com",
        "reddit.com"
    ]
    return any(x in url.lower() for x in platforms)


# ---------------- Inline Keyboard ----------------
def get_main_keyboard():
    """Asosiy menyu tugmalari"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📹 Video yuklash", callback_data="menu_video"),
            InlineKeyboardButton(text="🎵 Audio yuklash", callback_data="menu_audio")
        ],
        [
            InlineKeyboardButton(text="❓ Yordam", callback_data="menu_help"),
            InlineKeyboardButton(text="👤 Admin", callback_data="menu_admin")
        ],
        [
            InlineKeyboardButton(text="📊 Statistika", callback_data="menu_stats"),
            InlineKeyboardButton(text="🌐 Kanal", url="https://t.me/MediaWavesBot")
        ]
    ])
    return keyboard


def get_media_keyboard(url: str):
    """Video/audio yuklagandan keyin ko'rsatiladigan tugmalar (qisqa ID bilan)"""
    # URL ni qisqartirish
    short_id = url_cache.shorten(url)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 Audioni yuklash", callback_data=f"a_{short_id}"),
            InlineKeyboardButton(text="📋 Ma'lumot", callback_data=f"i_{short_id}")
        ],
        [
            InlineKeyboardButton(text="👤 Admin", callback_data="contact_admin"),
            InlineKeyboardButton(text="🏠 Menyu", callback_data="back_to_menu")
        ]
    ])
    return keyboard


def get_admin_contact_keyboard():
    """Admin bilan bog'lanish tugmalari"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📝 Xabar yozish", url=f"https://t.me/{ADMIN_USERNAME}"),
            InlineKeyboardButton(text="📞 Admin", url=f"tg://user?id={ADMIN_ID}")
        ],
        [
            InlineKeyboardButton(text="🏠 Asosiy menyu", callback_data="back_to_menu")
        ]
    ])
    return keyboard


def get_back_keyboard():
    """Ortga qaytish tugmasi"""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Ortga", callback_data="back_to_menu")]
    ])
    return keyboard


# ---------------- Commands ----------------
@dp.message(Command('start'))
async def start_cmd(message: Message):
    user = message.from_user
    user_id = user.id

    if user_id not in downloader.user_stats:
        downloader.user_stats[user_id] = {
            'first_seen': datetime.now(),
            'username': user.username,
            'first_name': user.first_name,
            'requests': 0,
            'last_active': datetime.now()
        }

    downloader.user_stats[user_id]['last_active'] = datetime.now()

    ffmpeg_status = "✅ Audio yuklash tayyor" if FFMPEG_PATH else "❌ Audio yuklash uchun FFmpeg o'rnatilmagan"

    welcome_text = f"""
🌊 <b>MediaWave Bot</b> ga xush kelibsiz, {user.first_name}!

Men YouTube, Instagram va boshqa platformalardan video va audio yuklab beraman.

<b>🔹 Qanday ishlatish:</b>
• Menga <b>to'g'ridan-to'g'ri video linkini yuboring</b>
• Bot avtomatik video yuklab beradi
• Video tagidagi tugmalar orqali audio va ma'lumot oling

<b>🔹 Qo'llab-quvvatlanadi:</b>
▶️ YouTube (video/shorts)
📸 Instagram (reels/post)
🎵 TikTok
📘 Facebook
🐦 Twitter/X

<b>📊 Statistika:</b>
• Foydalanuvchilar: {len(downloader.user_stats)}
• Bot: @MediaWavesBot
• {ffmpeg_status}

<b>❓ Muammo bo'lsa:</b>
Admin bilan bog'lanish uchun 👤 Admin tugmasini bosing
"""

    await message.answer(welcome_text, parse_mode=ParseMode.HTML, reply_markup=get_main_keyboard())


@dp.message(Command('help'))
async def help_cmd(message: Message):
    ffmpeg_status = "✅ Audio yuklash mumkin" if FFMPEG_PATH else "❌ Audio yuklash vaqtincha ishlamayapti (FFmpeg kerak)"

    help_text = f"""
🔍 <b>MediaWave Bot - Yordam</b>

<b>📌 Qanday ishlatish:</b>
1. <b>To'g'ridan-to'g'ri link yuboring</b>
2. Bot avtomatik video yuklab beradi
3. Video tagidagi tugmalar orqali:
   • 🎵 Audio yuklash
   • 📋 Video ma'lumoti
   • 👤 Admin bilan bog'lanish

<b>📝 Misollar:</b>
• https://youtube.com/watch?v=...
• https://youtu.be/...
• https://instagram.com/reel/...
• https://tiktok.com/@user/video/...

<b>⚙️ Buyruqlar:</b>
/start - Botni ishga tushirish
/help - Bu yordam xabari
/stats - Statistika (faqat admin)
/clean - Fayllarni tozalash (faqat admin)

<b>🎯 Holat:</b>
• {ffmpeg_status}

<b>⚠️ Eslatma:</b>
• Maksimal fayl hajmi: 50 MB
• Instagram/TikTok videolari ba'zida yuklanmasligi mumkin

<b>📞 Admin:</b> @{ADMIN_USERNAME}
"""
    await message.answer(help_text, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())


@dp.message(Command('stats'))
async def stats_cmd(message: Message):
    """Admin uchun statistika"""
    user_id = message.from_user.id

    if user_id != ADMIN_ID:
        await message.answer("❌ Bu buyruq faqat admin uchun!")
        return

    stats = await downloader.get_stats()

    stats_text = f"""
📊 <b>Bot statistikasi</b>

<b>👥 Foydalanuvchilar:</b> {stats['users']}
<b>📁 Yuklangan fayllar:</b> {stats['files']}
<b>💾 Hajmi:</b> {stats['size_mb']:.2f} MB
<b>🕐 Bugungi so'rovlar:</b> {stats['today_requests']}
<b>⚡ Aktiv yuklamalar:</b> {stats['active_downloads']}

<b>🎯 FFmpeg:</b> {"✅ Bor" if FFMPEG_PATH else "❌ Yo'q"}
<b>👤 Admin:</b> @{ADMIN_USERNAME}
<b>🤖 Bot:</b> @MediaWavesBot
<b>🕐 Oxirgi yangilanish:</b> {datetime.now().strftime('%Y-%m-%d %H:%M')}
"""
    await message.answer(stats_text, parse_mode=ParseMode.HTML)


@dp.message(Command('clean'))
async def clean_cmd(message: Message):
    """Eski fayllarni tozalash (admin)"""
    user_id = message.from_user.id

    if user_id != ADMIN_ID:
        await message.answer("❌ Bu buyruq faqat admin uchun!")
        return

    status = await message.answer("🧹 Fayllar tozalanmoqda...")

    try:
        cleaned = await downloader.cleanup_old_files(24)
        await status.edit_text(f"✅ {cleaned} ta eski fayl tozalandi!")
    except Exception as e:
        await status.edit_text(f"❌ Xatolik: {str(e)}")


# ---------------- Callback Handlers ----------------
@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    action = callback.data
    user_id = callback.from_user.id

    if user_id not in downloader.user_stats:
        downloader.user_stats[user_id] = {
            'first_seen': datetime.now(),
            'username': callback.from_user.username,
            'first_name': callback.from_user.first_name,
            'requests': 0,
            'last_active': datetime.now()
        }
    else:
        downloader.user_stats[user_id]['last_active'] = datetime.now()
        downloader.user_stats[user_id]['requests'] += 1

    if action == "back_to_menu":
        await callback.message.edit_text(
            "🌊 <b>Asosiy menyu</b>\n\nKerakli bo'limni tanlang:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_main_keyboard()
        )

    elif action == "menu_video":
        await callback.message.edit_text(
            "📹 <b>Video yuklash</b>\n\n"
            "Menga to'g'ridan-to'g'ri video linkini yuboring.\n\n"
            "Misol: https://youtube.com/watch?v=...",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard()
        )

    elif action == "menu_audio":
        status_text = "🎵 <b>Audio yuklash</b>\n\nMenga video linkini yuboring, men avtomatik audio yuklab beraman.\n\n"
        if not FFMPEG_PATH:
            status_text += "\n⚠️ <b>Ogohlantirish:</b> FFmpeg topilmadi! Audio yuklash ishlamasligi mumkin."

        await callback.message.edit_text(
            status_text + "\nMisol: https://youtube.com/watch?v=...",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard()
        )

    elif action == "menu_help":
        await help_cmd(callback.message)

    elif action == "menu_admin" or action == "contact_admin":
        await callback.message.edit_text(
            f"👤 <b>Admin bilan bog'lanish</b>\n\n"
            f"Muammo yuz berdi yoki savolingiz bormi?\n"
            f"Admin bilan bog'lanishingiz mumkin:\n\n"
            f"• Username: @{ADMIN_USERNAME}\n"
            f"• ID: {ADMIN_ID}\n\n"
            f"Pastdagi tugmalar orqali xabar yozishingiz mumkin:",
            parse_mode=ParseMode.HTML,
            reply_markup=get_admin_contact_keyboard()
        )

    elif action == "menu_stats":
        user_data = downloader.user_stats.get(user_id, {})
        stats_text = f"""
📊 <b>Foydalanuvchi statistikasi</b>

<b>👤 Sizning ID:</b> {user_id}
<b>📝 So'rovlar:</b> {user_data.get('requests', 0)}
<b>🕐 Birinchi marta:</b> {user_data.get('first_seen', datetime.now()).strftime('%Y-%m-%d %H:%M')}
<b>🕐 Oxirgi faol:</b> {user_data.get('last_active', datetime.now()).strftime('%Y-%m-%d %H:%M')}

<b>📊 Umumiy:</b>
• Foydalanuvchilar: {len(downloader.user_stats)}
• Bot: @MediaWavesBot
"""
        await callback.message.edit_text(
            stats_text,
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard()
        )

    elif action.startswith(("a_", "i_")):
        # Qisqa ID dan URL ni olish
        action_type, short_id = action.split('_', 1)
        url = url_cache.get_url(short_id)

        if not url:
            await callback.answer("❌ Bu link muddati o'tgan yoki mavjud emas!", show_alert=True)
            return

        if action_type == "a":
            if not FFMPEG_PATH:
                await callback.answer("❌ FFmpeg topilmadi! Audio yuklash ishlamaydi.", show_alert=True)
                return
            await callback.answer("🎵 Audio yuklanmoqda...")
            await process_audio(callback.message, url, is_callback=True)

        elif action_type == "i":
            await callback.answer("ℹ️ Ma'lumot olinmoqda...")
            await show_video_info(callback.message, url)

    await callback.answer()


# ---------------- Message Handler ----------------
@dp.message()
async def handle_message(message: Message):
    """Barcha xabarlarni qayta ishlash"""
    url = message.text.strip()
    user_id = message.from_user.id

    if user_id in downloader.user_stats:
        downloader.user_stats[user_id]['requests'] = downloader.user_stats[user_id].get('requests', 0) + 1
        downloader.user_stats[user_id]['last_active'] = datetime.now()

    downloader.today_requests += 1
    downloader.update_stats()

    if not validate_url(url):
        await message.answer(
            "❌ Noto‘g‘ri link. Faqat YouTube, Instagram, TikTok, Facebook, Twitter linklarini yuboring.\n\n"
            "Misol: https://youtube.com/watch?v=...",
            reply_markup=get_back_keyboard()
        )
        return

    await process_video(message, url)


# ---------------- Processing ----------------
async def process_video(message: Message, url: str, is_callback: bool = False):
    """Video yuklash va yuborish"""
    status = await message.answer("⏳ Video yuklanmoqda...")

    info, error = await downloader.get_video_info(url)
    if error:
        await status.edit_text(f"❌ Xatolik: {error}\n\nAdmin bilan bog'laning: @{ADMIN_USERNAME}")
        return

    filepath, error = await downloader.download_video(url, message.chat.id)

    if error:
        await status.edit_text(f"❌ Xatolik: {error}\n\nAdmin bilan bog'laning: @{ADMIN_USERNAME}")
        return

    if not os.path.exists(filepath):
        await status.edit_text("❌ Video topilmadi.")
        return

    file_size = os.path.getsize(filepath)
    if file_size > 50 * 1024 * 1024:
        await status.edit_text("❌ Fayl hajmi 50 MB dan katta.")
        await downloader.cleanup(filepath)
        return

    await status.edit_text("📤 Video yuborilmoqda...")

    # Duration ni formatlash
    duration_str = downloader.format_duration(info['duration'])
    caption = f"✅ <b>{info['title'][:100]}</b>\n\n📹 Video tayyor!\n👤 {info['uploader']} | ⏱ {duration_str}"

    try:
        await message.answer_video(
            FSInputFile(filepath),
            caption=caption,
            parse_mode=ParseMode.HTML,
            reply_markup=get_media_keyboard(url)
        )

        await status.delete()

    except Exception as e:
        await status.edit_text(f"❌ Video yuborishda xatolik: {str(e)[:100]}")
        await downloader.cleanup(filepath)
        return

    if is_callback and isinstance(message, CallbackQuery):
        try:
            await message.message.delete()
        except:
            pass


async def process_audio(message: Message, url: str, is_callback: bool = False):
    """Audio yuklash va yuborish"""
    status = await message.answer("⏳ Audio yuklanmoqda...")

    info, error = await downloader.get_video_info(url)
    if error:
        await status.edit_text(f"❌ Xatolik: {error}\n\nAdmin bilan bog'laning: @{ADMIN_USERNAME}")
        return

    filepath, error = await downloader.download_audio(url)

    if error:
        await status.edit_text(f"❌ Xatolik: {error}\n\nAdmin bilan bog'laning: @{ADMIN_USERNAME}")
        return

    if not os.path.exists(filepath):
        await status.edit_text("❌ Audio topilmadi.")
        return

    if os.path.getsize(filepath) > 50 * 1024 * 1024:
        await status.edit_text("❌ Fayl hajmi 50 MB dan katta.")
        await downloader.cleanup(filepath)
        return

    await status.edit_text("📤 Audio yuborilmoqda...")

    caption = f"✅ <b>{info['title'][:100]}</b>\n\n🎵 Audio tayyor!"

    try:
        await message.answer_audio(
            FSInputFile(filepath),
            caption=caption,
            parse_mode=ParseMode.HTML,
            title=info['title'][:60],
            performer=info['uploader'][:60] if info['uploader'] else "MediaWave",
            reply_markup=get_media_keyboard(url)
        )

        await status.delete()

    except Exception as e:
        await status.edit_text(f"❌ Audio yuborishda xatolik: {str(e)[:100]}")
        await downloader.cleanup(filepath)
        return

    await downloader.cleanup(filepath)

    if is_callback and isinstance(message, CallbackQuery):
        try:
            await message.message.delete()
        except:
            pass


async def show_video_info(message: Message, url: str):
    """Video haqida ma'lumot ko'rsatish"""
    info, error = await downloader.get_video_info(url)

    if error:
        await message.answer(
            f"❌ Ma'lumot olishda xatolik: {error}",
            reply_markup=get_back_keyboard()
        )
        return

    # Duration ni formatlash
    duration_str = downloader.format_duration(info['duration'])

    # Ko'rishlar va like larni formatlash
    views = f"{info['views']:,}" if info['views'] and info['views'] > 0 else "Noma'lum"
    likes = f"{info['likes']:,}" if info['likes'] and info['likes'] > 0 else "Noma'lum"

    info_text = f"""
📹 <b>Video ma'lumotlari</b>

<b>🎬 Nomi:</b> {info['title']}
<b>👤 Yuklagan:</b> {info['uploader']}
<b>⏱ Davomiyligi:</b> {duration_str}
<b>👁 Ko'rishlar:</b> {views}
<b>❤️ Layklar:</b> {likes}
<b>🆔 ID:</b> {info['id']}
<b>📱 Platforma:</b> {info.get('platform', 'Noma\'lum').title()}

<b>🔗 Qisqa link:</b> {url[:80]}...

<b>📥 Yuklab olish:</b>
• Video uchun tugmalardan foydalaning
• Audio formatida ham yuklab olishingiz mumkin

<b>❓ Muammo:</b> @{ADMIN_USERNAME}
"""

    await message.answer(
        info_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_media_keyboard(url)
    )


# ---------------- Scheduled Tasks ----------------
async def scheduled_cleanup():
    """Har soatda eski fayllarni tozalash"""
    while True:
        try:
            await asyncio.sleep(3600)  # 1 soat
            # Fayllarni tozalash
            cleaned = await downloader.cleanup_old_files(24)
            if cleaned > 0:
                logger.info(f"🧹 Avtomatik tozalash: {cleaned} fayl o'chirildi")

            # URL keshlarini tozalash
            url_cache.cleanup()

        except Exception as e:
            logger.error(f"Avtomatik tozalashda xatolik: {e}")


# ---------------- Run Bot ----------------
# ---------------- Run Bot ----------------
async def delete_webhook():
    """Webhook ni o'chirish"""
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook o'chirildi")
        return True
    except Exception as e:
        logger.error(f"❌ Webhook o'chirishda xatolik: {e}")
        return False


async def main():
    logger.info("🚀 Bot ishga tushmoqda...")

    try:
        # 1. AVVAL WEBHOOK NI O'CHIRISH (ENG MUHIM!)
        await delete_webhook()

        # 2. Bot ma'lumotlarini olish
        bot_info = await bot.get_me()
        logger.info(f"🤖 Bot: @{bot_info.username} (ID: {bot_info.id})")
        logger.info(f"👤 Admin: @{ADMIN_USERNAME} (ID: {ADMIN_ID})")

        # 3. FFmpeg ni tekshirish
        if FFMPEG_PATH:
            logger.info(f"✅ FFmpeg topildi: {FFMPEG_PATH}")
        else:
            logger.warning("⚠️ FFmpeg topilmadi! Audio yuklash ishlamaydi.")

        # 4. Papkalarni tekshirish
        for folder in [downloader.download_dir, downloader.temp_dir]:
            if os.path.exists(folder):
                file_count = len([f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))])
                logger.info(f"📁 {folder}: {file_count} fayl")

        # 5. Scheduled task ni ishga tushirish
        asyncio.create_task(scheduled_cleanup())

        # 6. Health check server (Render uchun)
        try:
            from fastapi import FastAPI
            import uvicorn
            import threading

            app = FastAPI()

            @app.get("/")
            @app.get("/healthz")
            @app.get("/health")
            async def health_check():
                return {"status": "alive", "bot": "MediaWave", "time": datetime.now().isoformat()}

            def run_web_server():
                uvicorn.run(app, host="0.0.0.0", port=10000)

            threading.Thread(target=run_web_server, daemon=True).start()
            logger.info("✅ Health check server ishga tushdi (port 10000)")
        except Exception as e:
            logger.warning(f"⚠️ Health check server ishga tushmadi: {e}")

        # 7. POLLING NI BOSHLASH (WEBHOOK O'CHIRILGANDAN KEYIN)
        logger.info("✅ Bot ishga tushdi. Polling boshlanmoqda...")
        await dp.start_polling(bot)

    except Exception as e:
        logger.error(f"❌ Bot ishga tushirishda xatolik: {e}")
        raise


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot to‘xtatildi")
    except Exception as e:
        logger.error(f"❌ Kutilmagan xatolik: {e}")