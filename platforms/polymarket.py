import requests
import json
import time
from datetime import datetime, timezone
from typing import List

# 確保你的 models 與 utils 路徑正確
from models.match import StandardEvent
from models.orderbook import Orderbook, OrderLevel
from utils.team_mapping import TeamNameMapper

class PolymarketAPI:
    """Polymarket 平台標準化介面 (結合 Gamma 賽事抓取與 CLOB 訂單簿)"""
    
    def __init__(self, name_mapper: TeamNameMapper):
        self.name = "Polymarket"
        self.mapper = name_mapper
        
        # API 網址與設定
        self.gamma_api_url = "https://gamma-api.polymarket.com/events"
        self.clob_api_url = "https://clob.polymarket.com/book"
        self.required_tag_ids = {"1", "100639", "100350"}
        self.limit_per_page = 500
        
        # 使用 Session 加速 HTTP 連線
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    
    # 1. 獲取賽事
    
    def get_matches(self) -> List[StandardEvent]:
        print(f"\n[{self.name}] 開始使用 `offset` 參數自動翻頁抓取資料...")
        
        standard_events = []
        offset = 0
        page_count = 1
        current_time = datetime.now(timezone.utc)
        
        try:
            while True:
                params = {
                    "active": "true",
                    "closed": "false",
                    "tag_id": "100350", 
                    "limit": self.limit_per_page,
                    "offset": offset
                }
                
                print(f"[{self.name}] 正在抓取第 {page_count} 頁 (Offset: {offset})...")
                response = self.session.get(self.gamma_api_url, params=params, timeout=10)
                response.raise_for_status()
                raw_events = response.json()
                
                if not raw_events:
                    print(f"[{self.name}] 這一頁為空，抓取完畢！")
                    break

                for raw_event in raw_events:
                    # 1. 標籤過濾 (Tag Filtering)
                    event_tag_ids = set()
                    for tag in raw_event.get('tags', []):
                        if isinstance(tag, dict):
                            event_tag_ids.add(str(tag.get('id')))
                            
                    if not self.required_tag_ids.issubset(event_tag_ids):
                        continue

                    # 2. 名稱與時間解析
                    title = raw_event.get("title", "").replace(" vs. ", " vs ").replace(" - More Markets", "")
                    if " vs " not in title:
                        continue
                        
                    parts = title.split(" vs ")
                    std_home = self.mapper.get_standard_name(parts[0])
                    std_away = self.mapper.get_standard_name(parts[1])
                    
                    time_str = raw_event.get("endDate")
                    if not time_str: continue
                    
                    try:
                        start_time = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
                    except ValueError:
                        continue 
                        
                    if start_time < current_time:
                        continue # 過濾舊比賽
                        
                    markets = raw_event.get("markets", [])
                    token_mapping = {} 
                    
                    # 針對這場比賽底下的所有盤口 (通常是 主勝、平手、客勝) 進行迴圈
                    for market in markets:
                        # 取得這個盤口的選項名稱，例如 "SV Werder Bremen" 或 "Draw (...)"
                        selection_name = market.get("groupItemTitle")
                        
                        if not selection_name:
                            continue
                            
                        # 取得 Tokens 字串並安全轉為陣列
                        raw_tokens = market.get("clobTokenIds", "[]")
                        clob_token_ids = json.loads(raw_tokens) if isinstance(raw_tokens, str) else raw_tokens
                        
                        # 我們只要買 "Yes" (會不會發生)，也就是陣列的第 0 個 Token
                        if isinstance(clob_token_ids, list) and len(clob_token_ids) > 0:
                            yes_token = clob_token_ids[0]
                            
                            # 如果是 Draw，我們稍微清理一下名稱，讓它乾淨一點
                            if "Draw" in selection_name:
                                token_mapping["Draw"] = yes_token
                            else:
                                # 把標準化後的隊名當作 Key (推薦做法，方便後續比對)
                                std_selection_name = self.mapper.get_standard_name(selection_name)
                                token_mapping[std_selection_name] = yes_token

                    # 4. 建立標準化事件
                    event = StandardEvent(
                        home_team=std_home,
                        away_team=std_away,
                        start_time=start_time,
                        platform=self.name,
                        platform_event_id=str(raw_event.get("id")),
                        market_type="moneyline",        
                        market_name=raw_event.get("title"), 
                        raw_data={
                            "original": raw_event,
                            "token_mapping": token_mapping # 把三個 Token 鑰匙都存起來
                        } 
                    )
                    standard_events.append(event)
                    
                if len(raw_events) < self.limit_per_page:
                    print(f"[{self.name}] 已經到達最後一頁，抓取完畢！")
                    break
                    
                offset += self.limit_per_page
                page_count += 1
                time.sleep(0.3)
                
            print(f"\n[{self.name}] 成功獲取 {len(standard_events)} 場標準化賽事！")
            return standard_events
            
        except Exception as e:
            print(f"[{self.name}] 獲取賽事失敗: {e}")
            return standard_events

   
    # 2. 獲取訂單簿
    
    def get_orderbook(self, token_id: str, selection: str) -> Orderbook:
        """傳入 Token ID，取得即時訂單簿，並轉換為統一格式 (Decimal Odds)"""
        try:
            response = self.session.get(self.clob_api_url, params={"token_id": token_id}, timeout=10)
            response.raise_for_status()
            book_data = response.json()
            
            bids = []
            asks = []
            
            # 直接塞進去，反正 __post_init__ 會幫我們排好
            for b in book_data.get("bids", []):
                bids.append(OrderLevel(price=float(b["price"]), size=float(b["size"])))
                    
            for a in book_data.get("asks", []):
                asks.append(OrderLevel(price=float(a["price"]), size=float(a["size"])))
                    
            return Orderbook(
                platform=self.name,
                match_id="tbd", 
                market_id=token_id,
                selection=selection,
                bids=bids,
                asks=asks
            )
        except Exception as e:
            print(f"[{self.name}] 獲取 Orderbook 失敗 (Token: {token_id}): {e}")
            return Orderbook(platform=self.name, match_id="error", market_id=token_id, selection=selection)


