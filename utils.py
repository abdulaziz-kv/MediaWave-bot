import re
import os
import aiofiles
import urllib.parse
from config import SUPPORTED_SITES, logger


def validate_url(url: str) -> bool:
    """URL ni tekshirish"""
    try:
        url = url.lower().strip()

        # Qo'llab-quvvatlanadigan saytlar
        supported = [
            'youtube.com', 'youtu.be', 'm.youtube.com', 'youtube.com/shorts',
            'instagram.com', 'instagr.am', 'instagram.com/reel', 'instagram.com/p',
            'tiktok.com', 'vm.tiktok.com', 'tiktok.com/@'
        ]

        for site in supported:
            if site in url:
                return True

        return False

    except:
        return False
def extract_video_id(url: str) -> str:
    """URL dan video ID ajratib olish"""
    # YouTube
    youtube_match = re.search(r'(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\s]+)', url)
    if youtube_match:
        return youtube_match.group(1)

    # Instagram
    instagram_match = re.search(r'instagram\.com\/(?:p|reel)\/([^\/\?]+)', url)
    if instagram_match:
        return instagram_match.group(1)

    # TikTok
    tiktok_match = re.search(r'tiktok\.com\/@[\w.]+\/video\/(\d+)', url)
    if tiktok_match:
        return tiktok_match.group(1)

    return None


async def save_file(filename: str, data: bytes):
    """Faylni saqlash"""
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    async with aiofiles.open(filename, 'wb') as f:
        await f.write(data)


def clean_filename(filename: str) -> str:
    """Fayl nomidan maxsus belgilarni olib tashlash"""
    # Windows uchun maxsus belgilarni olib tashlash
    illegal_chars = r'[<>:"/\\|?*]'
    return re.sub(illegal_chars, '', filename)