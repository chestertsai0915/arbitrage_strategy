import asyncio
import os
import random
import aiohttp
from centrifuge import (
    Client,
    ClientEventHandler,
    PublicationContext,
    SubscribedContext,
    SubscriptionEventHandler,
)
from dotenv import load_dotenv
from envs.got.Lib import json

# 自動尋找並載入同目錄下的 .env 檔案
load_dotenv()

RELAYER_URL = "https://api.sx.bet"
WS_URL = "wss://realtime.sx.bet/connection/websocket"

# 🌟 全域信號燈：限制同時間最多只能有 2 個快照請求在跑，避免激怒防火牆
snapshot_semaphore = asyncio.Semaphore(2)

# === 1. 單一盤口狀態管理 (加入 BBO 計算) ===
class SXMarketState:
    def __init__(self, market_hash, update_callback=None):
        self.market_hash = market_hash
        self.ready = False
        self.buffer = []
        self.local_orderbook = {}
        self.update_callback = update_callback  

    def apply_snapshot(self, orders_data):
        orders_list = orders_data.get("data", [])
        self.local_orderbook = {order["orderHash"]: order for order in orders_list}
        self._trigger_callback()

    def apply_update(self, update_data):
        updates = update_data if isinstance(update_data, list) else [update_data]
        changed = False
        
        for order in updates:
            order_hash = order.get("orderHash")
            if not order_hash:
                continue
                
            status = order.get("status", "")
            if status == "ACTIVE":
                self.local_orderbook[order_hash] = order
                changed = True
            else:
                if self.local_orderbook.pop(order_hash, None):
                    changed = True
                    
        if changed:
            self._trigger_callback()

    def _trigger_callback(self):
        if not self.update_callback: return

        best_outcome_1_cost, best_outcome_1_size = float('inf'), 0
        best_outcome_2_cost, best_outcome_2_size = float('inf'), 0

        for order in self.local_orderbook.values():
            # 1. 抓取機率 (Odds)
            percentage_odds_raw = float(order.get("percentageOdds", 0))
            maker_implied_prob = percentage_odds_raw / (10 ** 20)
            
            # 防呆避免除以 0
            if maker_implied_prob <= 0 or maker_implied_prob >= 1:
                continue
                
            taker_implied_prob = 1.0 - maker_implied_prob

            # 2. 計算原始剩餘金額 (Maker USDC)
            total_bet_size = float(order.get("totalBetSize", 0))
            fill_amount = float(order.get("fillAmount", 0))
            remaining_raw = total_bet_size - fill_amount
            
            if remaining_raw <= 0:
                continue
                
            remaining_maker_usdc = remaining_raw / (10 ** 6)
            
            # 3. 換算成對手盤 (Taker) 可以吃的實際深度
            taker_size = remaining_maker_usdc * (taker_implied_prob / maker_implied_prob)
            is_maker_outcome_one = order.get("isMakerBettingOutcomeOne", False)
            
            # 4. 價格比較與深度累加
            cost = taker_implied_prob
            if is_maker_outcome_one:
                if cost < best_outcome_2_cost:
                    best_outcome_2_cost = cost
                    best_outcome_2_size = taker_size
                elif cost == best_outcome_2_cost:
                    best_outcome_2_size += taker_size
            else:
                if cost < best_outcome_1_cost:
                    best_outcome_1_cost = cost
                    best_outcome_1_size = taker_size
                elif cost == best_outcome_1_cost:
                    best_outcome_1_size += taker_size

        bbo_data = {
            "platform": "SX_BET",
            "market_hash": self.market_hash,
            "buy_outcome_1_cost": best_outcome_1_cost if best_outcome_1_cost != float('inf') else None,
            "buy_outcome_1_size": best_outcome_1_size, 
            "buy_outcome_2_cost": best_outcome_2_cost if best_outcome_2_cost != float('inf') else None,
            "buy_outcome_2_size": best_outcome_2_size, 
            "total_active_orders": len(self.local_orderbook)
        }
        self.update_callback(bbo_data)

# === 2. Centrifuge 事件處理 ===
snapshot_semaphore = asyncio.Semaphore(3)

# === 2. Centrifuge 事件處理 ===
class SXOrderBookHandler(SubscriptionEventHandler):
    def __init__(self):
        super().__init__()
        self.state = None

    async def on_subscribed(self, ctx) -> None:
        # 🌟 核心修正：接待員瞬間處理完畢，把耗時的快照工作丟給「背景任務」去排隊！
        # 絕對不能在這裡面 await 睡覺或排隊，否則 WebSocket 會斷線！
        asyncio.create_task(self._fetch_snapshot_bg(ctx))

    async def _fetch_snapshot_bg(self, ctx):
        """這是在背景默默排隊拿快照的員工，不會卡住主連線"""
        print(f"   🟢 [SX] 頻道訂閱成功，背景排隊拿快照: {self.state.market_hash[:8]}...")

        if getattr(ctx, 'was_recovering', False) and getattr(ctx, 'recovered', False):
            self.state.ready = True
            return

        self.state.ready = False
        self.state.buffer.clear()

        # 這裡的排隊就不會影響到 WebSocket 了
        async with snapshot_semaphore:
            await asyncio.sleep(0.3) # 每秒最多送 3~4 個請求，安全度過防火牆
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{RELAYER_URL}/orders?marketHashes={self.state.market_hash}&status=ACTIVE"
                    
                    for attempt in range(3):
                        async with session.get(url) as res:
                            if res.status == 200:
                                orders_data = await res.json()
                                self.state.apply_snapshot(orders_data)
                                break
                            elif res.status == 429:
                                print(f"   ⚠️ [SX] 快照限流等待中 ({self.state.market_hash[:8]})...")
                                await asyncio.sleep(3) 
                            else:
                                print(f"   ⚠️ [SX] 快照拉取失敗 ({self.state.market_hash[:8]})，狀態碼: {res.status}")
                                break
            except Exception as e:
                print(f"   ⚠️ [SX] 快照請求發生錯誤: {e}")

        # 套用這段時間內積壓的 WebSocket 即時更新
        for data in self.state.buffer:
            self.state.apply_update(data)
        self.state.buffer.clear()
        self.state.ready = True

    async def on_error(self, ctx) -> None:
        err_msg = getattr(ctx.error, 'message', str(ctx.error))
        print(f"   ❌ [SX] 頻道訂閱失敗 ({self.state.market_hash[:8]}): {err_msg}")

    async def on_publication(self, ctx) -> None:
        raw_data = getattr(ctx, 'pub', ctx).data if hasattr(ctx, 'pub') else ctx.data
        # 如果背景員工還沒拿完快照，就先存在 buffer 裡
        if not self.state.ready:
            self.state.buffer.append(raw_data)
        else:
            self.state.apply_update(raw_data)

class SXConnectionEvents(ClientEventHandler):
    async def on_connected(self, ctx):
        print(" 🌐 [SX_BET] WebSocket 主連線成功！")
    async def on_disconnected(self, ctx):
        print(f" ❌ [SX_BET] 伺服器斷線: {getattr(ctx, 'reason', '未知')}")

# === 3. 模組主體 Connector ===
class SXBetConnector:
    def __init__(self, api_key, market_hashes, on_update_callback):
        self.api_key = api_key
        self.market_hashes = list(market_hashes)
        self.on_update_callback = on_update_callback
        self.client = None

    async def _fetch_token(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{RELAYER_URL}/user/realtime-token/api-key",
                headers={"x-api-key": self.api_key}
            ) as res:
                if res.status != 200:
                    raise Exception(f"SX Token 取得失敗: {res.status}")
                data = await res.json()
                return data["token"]

    async def start(self):
        print(f"🔄 [SX_BET] 準備啟動分片連線，共 {len(self.market_hashes)} 個盤口需要監聽...") 

        # 核心升級：設定每個 WebSocket 連線最多只負責 50 個盤口
        MAX_SUBS_PER_CLIENT = 50

        # 定義一個「分身」的任務函數
        async def setup_client(hashes_batch, batch_index):
            client = Client(WS_URL, events=SXConnectionEvents(), get_token=self._fetch_token)
            await client.connect()
            
            # 終極降速：不要再用 gather 併發了，我們「一個一個」排隊訂閱
            for m_hash in hashes_batch:
                market_state = SXMarketState(m_hash, self.on_update_callback)
                handler = SXOrderBookHandler()
                handler.state = market_state
                
                channel_name = f"order_book:market_{m_hash}"
                sub = client.new_subscription(channel_name, events=handler, positioned=True, recoverable=True)
                
                try:
                    await sub.subscribe()
                except Exception as e:
                    print(f"    ⚠️ [SX] 訂閱異常 ({m_hash[:8]}): {e}")
                    
                # 每個頻道訂閱完，強制程式喝口水 0.3 秒
                await asyncio.sleep(0.3)
                
            print(f"✅ [SX_BET] 第 {batch_index+1} 號分身連線完成 (負責 {len(hashes_batch)} 個頻道)")
            
            while True:
                await asyncio.sleep(3600)

        client_tasks = []
        for i in range(0, len(self.market_hashes), MAX_SUBS_PER_CLIENT):
            batch = self.market_hashes[i:i + MAX_SUBS_PER_CLIENT]
            batch_index = i // MAX_SUBS_PER_CLIENT
            client_tasks.append(setup_client(batch, batch_index))
            
        # 同時發動所有的分身連線！
        await asyncio.gather(*client_tasks)

# === 單獨測試用 ===
if __name__ == "__main__":
    def dummy_callback(data):
        print(f"\n📢 [回報測試] SX Bet 完整原始報價資料:")
        # 使用 json.dumps 將整個 dict 格式化，indent=4 會讓它自動縮排，方便閱讀
        try:
            formatted_data = json.dumps(data, indent=4, ensure_ascii=False)
            print(formatted_data)
        except Exception as e:
            # 如果 data 裡面有無法 JSON 序列化的物件，退回使用普通 print
            print(data)
        print("-" * 60)

    async def test():
        API_KEY  = os.environ.get("SX_bet")
        TARGET_HASH = "0x77ece77b79e2fca34ba7a51c5e855485661a3f0a36ec12505200586067543d02"
        
        # 🌟 記得這裡要包成陣列傳入
        connector = SXBetConnector(API_KEY, [TARGET_HASH], dummy_callback)
        print(" 啟動 SX Bet 測試連線...")
        await connector.start()
        
        await asyncio.Future()

    try:
        # Windows 環境下如果 asyncio 報錯，可以取消註解下面這行
        # asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        asyncio.run(test())
    except KeyboardInterrupt:
        print("\n 已手動停止程式")