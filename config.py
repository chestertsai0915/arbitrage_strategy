import os
from dotenv import load_dotenv

# 自動載入 .env 檔案中的環境變數
load_dotenv()

# ==========================================
# ⚙️ 1. 平台連線設定 (Platform Settings)
# ==========================================
# 只要把不想跑的平台從這個陣列中註解掉，整個系統就會自動略過它
ACTIVE_PLATFORMS = [
    "SX_BET", 
    "POLY", 
    "LIMITLESS"
]

# REST API 名稱與 WebSocket 內部代號的對應表
PLATFORM_NAME_MAPPING = {
    "SX_BET": "SX_BET",
    "Polymarket": "POLY",
    "Limitless": "LIMITLESS"
}

