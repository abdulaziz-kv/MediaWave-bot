import os
from dotenv import load_dotenv
import logging

# .env faylini yuklash
load_dotenv()

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Bot konfiguratsiyasi
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id]

# Yuklab olish sozlamalari
DOWNLOAD_PATH = 'downloads'
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB (Telegram chegarasi)

# Qo'llab-quvvatlanadigan platformalar
SUPPORTED_SITES = [
    'youtube.com', 'youtu.be',
    'instagram.com',
    'tiktok.com'
]