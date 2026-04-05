import requests
import time
from datetime import datetime, timezone
from typing import List

# 確保你的 models 與 utils 路徑正確
from models.match import StandardEvent
from models.orderbook import Orderbook, OrderLevel
from utils.team_mapping import TeamNameMapper

class LimitlessAPI:
    """Limitless 平台標準化介面 (支援 Not 反向盤口自動生成與套利)"""
    
    def __init__(self, name_mapper: TeamNameMapper):
        self.name = "Limitless"
        self.mapper = name_mapper
        
        self.base_url = "https://api.limitless.exchange"
        self.session = requests.Session()
        
        # Limitless 防爬蟲比較嚴格，一定要加上 User-Agent
        self.session.headers.update({
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"
        })

    
    # 1. 獲取賽事 (自動分頁與解析子盤口 Slug)
    
    def get_matches(self) -> List[StandardEvent]:
        print(f"\n[{self.name}] 開始獲取足球賽事資料...")
        
        standard_events = []
        limit = 25
        page = 1
        current_time = datetime.now(timezone.utc)
        
        try:
            while True:
                params = {"limit": limit, "page": page}
                print(f"[{self.name}] 正在抓取第 {page} 頁...")
                
                response = self.session.get(f"{self.base_url}/markets/active/49", params=params, timeout=10)
                response.raise_for_status()
                
                result = response.json()
                raw_events = result.get('data', result) if isinstance(result, dict) else result
                
                if not raw_events:
                    break

                for raw_event in raw_events:
                    try:
                        title = raw_event.get("title", "")
                        title_parts = title.split(",")
                        
                        # 1. 處理球隊名稱
                        match_segment = next((seg for seg in title_parts if "vs" in seg.lower()), "")
                        if not match_segment: continue 
                        
                        teams = match_segment.replace(" vs. ", " vs ").split(" vs ")
                        if len(teams) != 2: continue
                            
                        std_home = self.mapper.get_standard_name(teams[0].strip())
                        std_away = self.mapper.get_standard_name(teams[1].strip())
                        
                        # 2. 解析時間 (使用你原本嚴謹的雙重保險機制)
                        start_time = None
                        if len(title_parts) >= 3:
                            date_str = f"{title_parts[-2].strip()}, {title_parts[-1].strip()}"
                            try:
                                start_time = datetime.strptime(date_str, "%b %d, %Y").replace(tzinfo=timezone.utc)
                            except ValueError:
                                pass
                                
                        if start_time is None:
                            time_str = raw_event.get("expirationDate") or raw_event.get("endDate")
                            if time_str:
                                try:
                                    start_time = datetime.strptime(time_str.strip(), "%b %d, %Y").replace(tzinfo=timezone.utc)
                                except ValueError:
                                    try:
                                        start_time = datetime.fromisoformat(str(time_str).replace("Z", "+00:00"))
                                    except ValueError:
                                        start_time = current_time
                            else:
                                start_time = current_time
                                
                        if start_time.date() < current_time.date():
                            continue # 過濾舊比賽

                        #  3. 解析子盤口 (Child Markets) 的 Slug
                        token_mapping = {}
                        markets = raw_event.get("markets", [])
                        
                        for market in markets:
                            child_title = market.get("title", "")
                            child_slug = market.get("slug", "")
                            
                            if child_title and child_slug:
                                std_child_name = self.mapper.get_standard_name(child_title)
                                
                                # 🌟 [核心修改] 統一使用 Home, Away, Draw 標籤防呆判斷
                                if "Draw" in child_title or "Tie" in child_title or "draw" in std_child_name.lower():
                                    token_mapping["Draw"] = child_slug
                                    token_mapping["Not Draw"] = child_slug
                                elif std_child_name == std_home or std_child_name in std_home or std_home in std_child_name:
                                    token_mapping["Home"] = child_slug
                                    token_mapping["Not Home"] = child_slug
                                elif std_child_name == std_away or std_child_name in std_away or std_away in std_child_name:
                                    token_mapping["Away"] = child_slug
                                    token_mapping["Not Away"] = child_slug

                        # 4. 建立標準化物件
                        event = StandardEvent(
                            home_team=std_home,
                            away_team=std_away,
                            start_time=start_time,
                            platform=self.name,
                            platform_event_id=str(raw_event.get("slug")), 
                            market_type="moneyline",        
                            market_name=title, 
                            raw_data={
                                "token_mapping": token_mapping # 把 Home/Away 正反子盤口的 Slug 當鑰匙藏好！
                            } 
                        )
                        standard_events.append(event)
                        
                    except Exception as e:
                        continue

                if len(raw_events) < limit:
                    break
                    
                page += 1
                time.sleep(0.3)
                
        except Exception as e:
            print(f"[{self.name}] 抓取失敗: {e}")

        print(f"[{self.name}] 成功獲取 {len(standard_events)} 場標準化賽事！")
        return standard_events


    # 2. 獲取訂單簿 
    
    def get_orderbook(self, market_id: str, selection: str) -> Orderbook:
        """
        market_id: 這裡傳入的是子盤口的 Slug (來自 token_mapping)
        支援 Not 盤口的機率自動反轉
        """
        def get_buy_fee(p: float) -> float:
            """Taker Buy Fee: 0~0.5 為 3%，0.5~1.0 線性下降至 0.03% (0.0003)"""
            if p <= 0.5:
                return 0.03
            else:
                progress = (p - 0.5) / 0.5
                return 0.03 - (0.0297 * progress)

        def get_sell_fee(p: float) -> float:
            """Taker Sell Fee: 0~0.5 從 0% 升至 1.5%，0.5~1.0 降回 0%"""
            if p <= 0.5:
                return 0.015 * (p / 0.5)
            else:
                progress = (p - 0.5) / 0.5
                return 0.015 - (0.015 * progress)
            
        try:
            # 直接打子盤口的 Orderbook API，不用再查母盤口了！
            ob_url = f"{self.base_url}/markets/{market_id}/orderbook"
            response = self.session.get(ob_url, timeout=10)
            response.raise_for_status()
            ob_data = response.json()
            
            bids = []
            asks = []
            
            #  判斷這是不是一個「反向 (Not)」請求
            is_not_market = selection.startswith("Not ")
            
            # Limitless 的 USDC 精度是 6 位，所以 size 要除以 1,000,000
            for b in ob_data.get("bids", []):
                price_prob = float(b["price"])
                size = float(b["size"]) / 1000000.0
                FEE_RATE = get_sell_fee(price_prob)
                if 0 < price_prob < 1.0:
                    if is_not_market:
                        # 對手想買 Yes (Bid)，我們賣 Yes 給他 = 我們「買」No (Ask)
                        # 既然是我們「買」，成本就要加上手續費 (變貴)
                        raw_price = 1.0 - price_prob
                        adjusted_price = raw_price * (1 + FEE_RATE)
                        asks.append(OrderLevel(price=adjusted_price, size=size))
                    else:
                        # 正常 Bid，對手想買 Yes，我們「賣」Yes 給他
                        # 既然是我們「賣」，實拿獲利要扣掉手續費 (變少)
                        adjusted_price = price_prob * (1 - FEE_RATE)
                        bids.append(OrderLevel(price=adjusted_price, size=size))
                
            for a in ob_data.get("asks", []):
                price_prob = float(a["price"])
                size = float(a["size"]) / 1000000.0
                FEE_RATE = get_buy_fee(price_prob)
                if 0 < price_prob < 1.0:
                    if is_not_market:
                        # 對手想賣 Yes (Ask)，我們買 Yes = 我們「賣」No (Bid)
                        # 既然是我們「賣」，實拿獲利要扣掉手續費 (變少)
                        raw_price = 1.0 - price_prob
                        adjusted_price = raw_price * (1 - FEE_RATE)
                        bids.append(OrderLevel(price=adjusted_price, size=size))
                    else:
                        # 正常 Ask，對手想賣 Yes，我們「買」Yes
                        # 既然是我們「買」，成本就要加上手續費 (變貴)
                        adjusted_price = price_prob * (1 + FEE_RATE)
                        asks.append(OrderLevel(price=adjusted_price, size=size))
                        
            return Orderbook(
                platform=self.name,
                match_id="tbd", 
                market_id=market_id,
                selection=selection,
                bids=bids,
                asks=asks
            )
            
        except Exception as e:
            print(f"[{self.name}] 獲取 Orderbook 失敗 (Slug: {market_id[:15]}...): {e}")
            return Orderbook(platform=self.name, match_id="error", market_id=market_id, selection=selection)