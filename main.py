import time

# 匯入各平台 API
from platforms import AVAILABLE_PLATFORMS

# 匯入核心工具 (依據你的資料夾結構，若放在 utils 請自行更改)

from utils.team_mapping import TeamNameMapper

# 匯入配對引擎
# 假設你已經將兩階段配對邏輯存放在 core/matcher.py 中
from core.matcher import MatchEngine 

def main():  
    print("  Total Search")
    
    # 步驟 1：初始化系統工具與平台
    
    mapper = TeamNameMapper()
    
    # 初始化配對引擎：門檻 70 分，至少需要 2 個平台重疊
    match_engine = MatchEngine(threshold=70.0, min_platforms=2)
    
    # 註冊我們要掃描的平台
    mapper = TeamNameMapper()
    
    # 動態實例化所有在 __init__.py 註冊過的平台！
    platforms = [PlatformClass(mapper) for PlatformClass in AVAILABLE_PLATFORMS]

   
    # 步驟 2：第一階段 - 盤前靜態資料收集
    
    all_events = []
    for api in platforms:
        try:
            events = api.get_matches()
            all_events.extend(events)
        except Exception as e:
            print(f" {api.name} 獲取賽事失敗: {e}")

  
    # 步驟 3：安檢過濾 - 只保留安全的套利標的
   
    # 1. 確保是獨贏盤 (moneyline)
    # 2. 確保我們有成功解析出子盤口的鑰匙 (token_mapping)
    moneyline_events = [
        e for e in all_events 
        if e.market_type == "moneyline" and e.raw_data.get("token_mapping")
    ]
    
    print(f"\n 總計獲取 {len(all_events)} 場比賽。")
    print(f" 過濾後剩下 {len(moneyline_events)} 場高品質 Moneyline (獨贏盤) 賽事準備進行配對。")

    
    # 步驟 4：啟動 AI 配對引擎，尋找 Overlap
   
    overlapping_matches = match_engine.match_events(moneyline_events)

    if not overlapping_matches:
        print("\n 目前沒有找到任何跨平台交集的比賽。程式結束。")
        return

   
    # 步驟 5：[未實作] 針對交集比賽計算套利
    
    print("\n" + "=" * 60)
    print("  準備進入套利分析階段 (目前僅展示架構)")
    print("=" * 60)

    for match_id, grouped_events in overlapping_matches:
        platform_names = [e.platform for e in grouped_events]
        #print(f"\n 鎖定交集比賽: {match_id}")
        #print(f"   參與平台: {platform_names}")
        
        # ---------------------------------------------------------
        # [TODO: Orderbook 獲取與套利計算]
        # 
        # 未來實作邏輯如下：
        # 
        # 1. 建立非同步任務 (asyncio.gather) 或執行緒池 (ThreadPoolExecutor)
        #    理由：如果循序抓 Orderbook，等抓到第 2 個平台時，第 1 個平台的價格可能已經變了。
        # 
        # 2. 遍歷該比賽所有的下注選項 (例如：主勝、客勝、平手)
        #    利用 grouped_events 中各自的 event.raw_data["token_mapping"] 拿出對應的 API 查詢鑰匙。
        # 
        # 3. 呼叫各自的 api.get_orderbook(鑰匙, 選項) 獲取即時深度。
        # 
        # 4. 進行雙邊套利數學計算 (以隱含機率 Implied Probability 為例)：
        #    假設平台 A 的 "主勝" Best Ask 為 0.40 (代表 40%)
        #    假設平台 B 的 "客勝+平手 (或是 Not 主勝)" Best Ask 為 0.55 (代表 55%)
        #    
        #    總成本 = 0.40 + 0.55 = 0.95
        #    if 總成本 < 1.0:
        #        print("發現套利機會！預期利潤率為:", (1.0 - 0.95) * 100, "%")
        #        
        # 5. 滑價與深度檢查 (Slippage & Size Check)：
        #    呼叫 orderbook 模型的 get_vwap_ask(預計下注金額)
        #    確保這兩個 Best Ask 的 size 夠大，能吃下我們的資金且不會滑價。
        # ---------------------------------------------------------
        
        # 這裡只是為了看結果暫停一下，正式上線時會移除
        time.sleep(0.1)

    print("\n 第一階段：跨平台賽事捕捉與配對系統，順利執行完畢！")

if __name__ == "__main__":
    main()