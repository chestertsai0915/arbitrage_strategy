import time
import asyncio
import os
from dotenv import load_dotenv
from utils.paper_trader import PaperTrader
# 匯入各平台 API (REST 靜態爬蟲用)
import logging
from platforms import AVAILABLE_PLATFORMS

# 匯入配對引擎與工具
from utils.team_mapping import TeamNameMapper
from core.matcher import MatchEngine 

#  匯入動態 WebSocket 套件與套利大腦
from platforms_websocket_connnect import CONNECTOR_MAP
from core.arbitrage_engine import check_all_arbitrage

# 載入環境變數 (API Key)
load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("arbitrage_bot.log", encoding='utf-8'), # 存檔
        # 這裡刻意不加 StreamHandler，為了保持你終端機儀表板的乾淨
    ]
)

# 讓底層套件閉嘴，只記錄我們自己發出的重要訊息或嚴重崩潰
logging.getLogger('asyncio').setLevel(logging.CRITICAL)
logging.getLogger('websockets').setLevel(logging.CRITICAL)
logging.getLogger('centrifuge').setLevel(logging.CRITICAL)
def generate_match_mapping(overlapping_matches):
    """將配對好的賽事轉換成 WebSocket 引擎專用的字典格式"""
    match_mapping = {}
    
    for cluster_id, events in overlapping_matches:
        # 使用第一筆資料建立標題
        first_event = events[0]
        title = f"{first_event.home_team} vs {first_event.away_team}"
        
        # 建立這場比賽的專屬設定檔
        match_mapping[cluster_id] = {
            "title": title,
            "outcomes": ["Home", "Away", "Draw"], # 標準化的三大選項
        }
        
        # 掃描這場比賽底下所有平台的資料
        for event in events:
            # 轉換平台名稱，對齊 CONNECTOR_MAP 的 Key
            platform_key = event.platform.upper().replace(" ", "_")
            if platform_key == "SX_BET":
                platform_key = "SX_BET"
            elif platform_key == "POLYMARKET":
                platform_key = "POLY"
            elif platform_key == "LIMITLESS":
                platform_key = "LIMITLESS"
                
            # 把爬蟲抓到的鑰匙 (token_mapping) 塞進去
            match_mapping[cluster_id][platform_key] = event.raw_data.get("token_mapping", {})
            
    return match_mapping


async def start_trading_engine(match_mapping, paper_trader=None):
    """啟動 WebSocket 監聽網與核心套利引擎"""
    print("\n" + "=" * 60)
    print(" 啟動多平台即時套利監控網 (WebSocket & Arbitrage Engine)")
    print("=" * 60)
    
    price_memory = {}
    for match_id, match_data in match_mapping.items():
        price_memory[match_id] = {outcome: {} for outcome in match_data["outcomes"]}

   
    # 監控儀表板狀態
    
    expected_pipes = {"SX_BET": 0, "POLY": 0, "LIMITLESS": 0}
    active_pipes = {"SX_BET": set(), "POLY": set(), "LIMITLESS": set()}

    def arbitrage_callback(bbo_data):
        platform = bbo_data["platform"]
        incoming_hash = str(bbo_data["market_hash"])
        
        #  只要收到報價，就把這個 Hash 標記為「活躍中」
        if platform in active_pipes:
            active_pipes[platform].add(incoming_hash)
        
        target_match, target_outcome = None, None
        
        for match_id, match_data in match_mapping.items():
            if platform in match_data:
                for outcome_key, m_hash in match_data[platform].items():
                    if m_hash == incoming_hash:
                        target_match = match_id
                        target_outcome = outcome_key.replace("Not ", "")
                        break
            if target_match:
                break
                
        if not target_match or not target_outcome:
            return

        price_memory[target_match][target_outcome][platform] = {
            "yes_price": bbo_data.get("buy_outcome_1_cost"), 
            "yes_size": bbo_data.get("buy_outcome_1_size", 0),
            "no_price": bbo_data.get("buy_outcome_2_cost"), 
            "no_size": bbo_data.get("buy_outcome_2_size", 0)
        }
        
        check_all_arbitrage(target_match, match_mapping, price_memory, paper_trader)

   
    #  新增：獨立的背景任務 (每 0.5 秒刷新一次畫面)
   
    async def dashboard_task():
        while True:
            sx = f"{len(active_pipes['SX_BET'])}/{expected_pipes['SX_BET']}"
            poly = f"{len(active_pipes['POLY'])}/{expected_pipes['POLY']}"
            lim = f"{len(active_pipes['LIMITLESS'])}/{expected_pipes['LIMITLESS']}"
            
            # 使用 \r 讓這行字永遠固定在終端機最下方
            print(f"\r [管線健康度] SX: {sx} 條 | Poly: {poly} 條 | Limitless: {lim} 條 ", end="", flush=True)
            await asyncio.sleep(0.5)

    # 平台 ID 集中打包 (Multiplexing)
    
    platform_targets = {"SX_BET": set(), "POLY": set(), "LIMITLESS": set()}

    # 1. 蒐集所有需要監聽的 Hash/Slug，集中到 Set 裡面去重複
    for match_id, match_data in match_mapping.items():
        for platform_name in ["SX_BET", "POLY", "LIMITLESS"]:
            if platform_name in match_data:
                platform_targets[platform_name].update(match_data[platform_name].values())

    tasks = []
    sx_api_key = os.environ.get("SX_bet")

    # 2. 每個平台「只建立 1 個」Connector，把幾百個 ID 一次傳進去！
    if platform_targets["SX_BET"]:
        hashes = list(platform_targets["SX_BET"])
        expected_pipes["SX_BET"] = len(hashes)
        tasks.append(CONNECTOR_MAP["SX_BET"](sx_api_key, hashes, arbitrage_callback).start())

    if platform_targets["POLY"]:
        hashes = list(platform_targets["POLY"])
        expected_pipes["POLY"] = len(hashes)
        tasks.append(CONNECTOR_MAP["POLY"](hashes, arbitrage_callback).start())

    if platform_targets["LIMITLESS"]:
        hashes = list(platform_targets["LIMITLESS"])
        expected_pipes["LIMITLESS"] = len(hashes)
        tasks.append(CONNECTOR_MAP["LIMITLESS"](hashes, arbitrage_callback).start())

    if not tasks:
        print(" 沒有找到可監聽的目標。")
        return

    # 把背景儀表板任務也加進去一起跑
    tasks.append(dashboard_task())

    #  現在這裡只會有 4 個 Task (3 個平台主連線 + 1 個儀表板)！
    await asyncio.gather(*tasks)


def main():  
    print(" 啟動 Total Search 賽事掃描引擎")
    trader = PaperTrader(initial_balance=200000000.0, max_bet_per_trade=400.0)
    # 步驟 1：初始化系統工具與平台
    mapper = TeamNameMapper()
    match_engine = MatchEngine(threshold=80.0, min_platforms=2)
    platforms = [PlatformClass(mapper) for PlatformClass in AVAILABLE_PLATFORMS]

    # 步驟 2：盤前靜態資料收集
    all_events = []
    for api in platforms:
        try:
            events = api.get_matches()
            all_events.extend(events)
        except Exception as e:
            print(f" {api.name} 獲取賽事失敗: {e}")

    # 步驟 3：安檢過濾
    moneyline_events = [
        e for e in all_events 
        if e.market_type == "moneyline" and e.raw_data.get("token_mapping")
    ]
    
    print(f"\n 總計獲取 {len(all_events)} 場比賽。")
    print(f" 過濾後剩下 {len(moneyline_events)} 場高品質 Moneyline (獨贏盤) 賽事準備進行配對。")

    # 步驟 4：啟動配對，尋找 Overlap
    overlapping_matches = match_engine.match_events(moneyline_events)

   
    if not overlapping_matches:
        print("\n 目前沒有找到任何跨平台交集的比賽。程式結束。")
        return
    
    

    
    #  防呆：資料清洗 (Data Cleansing) 全域濾網
  
    clean_matches = []
    cleaned_count = 0
    
    # 1. 遍歷每一場交集賽事，並直接將 Tuple 解包為 match_name (0) 和 events_data (1)
    for match_name, events_data in overlapping_matches:
        valid_events = []
        
        # 判斷 events_data 是字典還是陣列，統一轉成可迭代的 List
        # 如果是字典 {"SX_BET": obj, "POLY": obj}，就取 .values()
        # 如果已經是陣列 [obj1, obj2]，就直接用
        event_list = events_data.values() if isinstance(events_data, dict) else events_data
        
        # 2. 檢查這場比賽底下的「每一個平台物件」
        for event_obj in event_list:
            raw_data = getattr(event_obj, "raw_data", {}) or {}
            tokens = raw_data.get("token_mapping", {})
            
            # 嚴格檢查這家平台的 3-Way 是否完整
            if tokens:
                if "Home" not in tokens or "Away" not in tokens or "Draw" not in tokens:
                    plat_name = getattr(event_obj, "platform", "Unknown")
                    print(f"🧹 [資料清洗] 剔除殘缺盤口: {plat_name} - {match_name}")
                    cleaned_count += 1
                    continue # 剔除這家平台，直接換檢查下一家
                    
            # 如果這家平台是健康的，加進保留名單
            valid_events.append(event_obj)
            
        # 3. 如果清洗完後，這場比賽剩下的健康平台還有 2 家(含)以上，才保留這場比賽
        if len(valid_events) >= 2:
            #  記得把資料「重新包裝回原本的 Tuple 格式」塞回去，這樣後面的程式才不會報錯！
            # 如果你原本的 events_data 是字典，這裡可能需要轉回字典，
            # 但通常配對引擎後面的 generate_match_mapping 吃陣列也沒問題。
            clean_matches.append((match_name, valid_events))

    # 用清洗過後的乾淨資料，覆蓋掉原本的資料
    overlapping_matches = clean_matches
    
    print(f"\n 資料清洗完畢！共攔截了 {cleaned_count} 個殘缺盤口。")
    print(f" 準備將 {len(overlapping_matches)} 場 100% 健康交集賽事送入引擎...")
    #  測試模式：限制只跑前 10 筆交集賽事
    overlapping_matches = clean_matches
    total_matches = len(overlapping_matches)
    overlapping_matches = overlapping_matches
    print(f"\n 總共找到 {total_matches} 場交集賽事，目前限制只測試前 {len(overlapping_matches)} 場...")

    #  步驟 5：動態轉換設定檔
    match_mapping = generate_match_mapping(overlapping_matches)
    print(f" 成功轉換 {len(match_mapping)} 場交集賽事，準備載入大腦...")

    #  步驟 6：啟動非同步套利監控
    try:
        asyncio.run(start_trading_engine(match_mapping, paper_trader=trader))
    except KeyboardInterrupt:
        print("\n 已手動停止套利系統")


if __name__ == "__main__":
    main()