import yt_dlp
import os
import asyncio
from config import DOWNLOAD_PATH, logger


class MediaDownloader:
    def __init__(self):
        self.download_path = DOWNLOAD_PATH
        os.makedirs(self.download_path, exist_ok=True)

        # YANGI sozlamalar (hamma platforma uchun)
        self.ydl_opts = {
            'format': 'best[filesize<50M]/best',
            'outtmpl': f'{self.download_path}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'nocheckcertificate': True,
            # Instagram uchun muhim!
            'extractor_args': {
                'instagram': {
                    'login': '',  # Bo'sh qoldiring
                    'password': ''
                }
            },
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }

        # Audio sozlamalari
        self.audio_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
            'outtmpl': f'{self.download_path}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'extractor_args': {
                'instagram': {
                    'login': '',
                    'password': ''
                }
            },
            'headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        }

    async def download_video(self, url: str):
        """HAMMA video (YouTube, Instagram, TikTok)"""
        try:
            logger.info(f"Yuklanmoqda: {url}")

            loop = asyncio.get_event_loop()

            with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                # Video ma'lumotlarini olish
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

                if not info:
                    return None, "Video topilmadi"

                # Yuklab olish
                await loop.run_in_executor(None, lambda: ydl.download([url]))

                # Yuklangan faylni topish
                title = info.get('title', 'video')
                for file in os.listdir(self.download_path):
                    if title in file and os.path.getsize(os.path.join(self.download_path, file)) > 0:
                        return os.path.join(self.download_path, file), None

                return None, "Fayl topilmadi"

        except Exception as e:
            logger.error(f"Xatolik: {e}")
            return None, str(e)

    async def download_audio(self, url: str):
        """MP3 audio"""
        try:
            logger.info(f"Audio yuklanmoqda: {url}")

            loop = asyncio.get_event_loop()

            with yt_dlp.YoutubeDL(self.audio_opts) as ydl:
                info = await loop.run_in_executor(None, lambda: ydl.extract_info(url, download=False))

                if not info:
                    return None, "Video topilmadi"

                await loop.run_in_executor(None, lambda: ydl.download([url]))

                # MP3 faylni topish
                title = info.get('title', 'audio')
                for file in os.listdir(self.download_path):
                    if title in file and file.endswith('.mp3'):
                        return os.path.join(self.download_path, file), None

                return None, "MP3 topilmadi"

        except Exception as e:
            logger.error(f"Xatolik: {e}")
            return None, str(e)

    def cleanup(self, filepath: str):
        """Faylni o'chirish"""
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
        except:
            pass