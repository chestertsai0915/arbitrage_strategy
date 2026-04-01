import time
import json
import os
from datetime import datetime

# 匯入各平台 API
from platforms import AVAILABLE_PLATFORMS
# 匯入核心工具
from utils.team_mapping import TeamNameMapper
# 匯入配對引擎
from core.matcher import MatchEngine 

# ==========================================
# JSON 自定義編碼器 (處理物件與時間格式轉換)
# ==========================================
class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        # 處理自定義的 Python class 物件 (例如 MatchedEvent 或 Event)
        if hasattr(obj, '__dict__'):
            return obj.__dict__
        # 處理 datetime 時間格式
        elif isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def overlap():  
    print("🔍 啟動 Total Search 跨平台掃描...")
    
    # 步驟 1：初始化系統工具與平台
    mapper = TeamNameMapper()
    
    # 初始化配對引擎：門檻 70 分，至少需要 2 個平台重疊
    match_engine = MatchEngine(threshold=70.0, min_platforms=2)
    
    # 動態實例化所有在 __init__.py 註冊過的平台！
    platforms = [PlatformClass(mapper) for PlatformClass in AVAILABLE_PLATFORMS]

    # 步驟 2：第一階段 - 盤前靜態資料收集
    all_events = []
    for api in platforms:
        try:
            events = api.get_matches()
            all_events.extend(events)
        except Exception as e:
            print(f"⚠️ {api.name} 獲取賽事失敗: {e}")

    # 步驟 3：安檢過濾 - 只保留安全的套利標的
    # 1. 確保是獨贏盤 (moneyline)
    # 2. 確保我們有成功解析出子盤口的鑰匙 (token_mapping)
    moneyline_events = [
        e for e in all_events 
        if e.market_type == "moneyline" and e.raw_data.get("token_mapping")
    ]
    
    print(f"\n📊 總計獲取 {len(all_events)} 場比賽。")
    print(f"🎯 過濾後剩下 {len(moneyline_events)} 場高品質 Moneyline (獨贏盤) 賽事準備進行配對。")

    # 步驟 4：啟動 AI 配對引擎，尋找 Overlap
    overlapping_matches = match_engine.match_events(moneyline_events)

    # ==========================================
    # 步驟 5：將配對結果儲存為 JSON 檔案 (供 WebSocket 引擎使用)
    # ==========================================
    filename = "overlapping_matches.json"
    
    if overlapping_matches:
        try:
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(overlapping_matches, f, cls=CustomEncoder, indent=4, ensure_ascii=False)
            
            filepath = os.path.abspath(filename)
            print(f"\n💾 成功！已將 {len(overlapping_matches)} 場配對賽事完整存入: {filepath}")
            
        except Exception as e:
            print(f"\n❌ 儲存 JSON 時發生錯誤: {e}")
    else:
        print("\n⚠️ 本次掃描未發現重疊賽事，未產生 JSON 檔案。")

    # 回傳結果，保持函數彈性
    return overlapping_matches

if __name__ == "__main__":
    overlap()