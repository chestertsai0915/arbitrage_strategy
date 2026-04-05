import asyncio
import os
import aiohttp
from centrifuge import (
    Client,
    ClientEventHandler,
    PublicationContext,
    SubscribedContext,
    SubscriptionEventHandler,
)

import os
from dotenv import load_dotenv

# 自動尋找並載入同目錄下的 .env 檔案
load_dotenv()




RELAYER_URL = "https://api.sx.bet"
WS_URL = "wss://realtime.sx.bet/connection/websocket"

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
                # Maker 買 Outcome 1 (買 Yes)，代表我們要吃他的單等於買 No
                if cost < best_outcome_2_cost:
                    best_outcome_2_cost = cost
                    best_outcome_2_size = taker_size
                elif cost == best_outcome_2_cost:
                    best_outcome_2_size += taker_size # 如果價格一樣，深度要疊加！
            else:
                # Maker 買 Outcome 2 (買 No)，代表我們要吃他的單等於買 Yes
                if cost < best_outcome_1_cost:
                    best_outcome_1_cost = cost
                    best_outcome_1_size = taker_size
                elif cost == best_outcome_1_cost:
                    best_outcome_1_size += taker_size # 如果價格一樣，深度疊加！

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

# 2. Centrifuge 事件處理 
class SXOrderBookHandler(SubscriptionEventHandler):
    async def on_subscribed(self, ctx: SubscribedContext) -> None:
        if getattr(ctx, 'was_recovering', False) and getattr(ctx, 'recovered', False):
            self.state.ready = True
            return

        self.state.ready = False
        self.state.buffer.clear()

        async with aiohttp.ClientSession() as session:
            url = f"{RELAYER_URL}/orders?marketHashes={self.state.market_hash}&status=ACTIVE"
            async with session.get(url) as res:
                if res.status == 200:
                    orders_data = await res.json()
                    self.state.apply_snapshot(orders_data)

        for data in self.state.buffer:
            self.state.apply_update(data)
        self.state.buffer.clear()
        self.state.ready = True

    async def on_publication(self, ctx: PublicationContext) -> None:
        raw_data = getattr(ctx, 'pub', ctx).data if hasattr(ctx, 'pub') else ctx.data
        if not self.state.ready:
            self.state.buffer.append(raw_data)
        else:
            self.state.apply_update(raw_data)

class SXConnectionEvents(ClientEventHandler):
    async def on_connected(self, ctx):
        print(" [SX_BET] WebSocket 連線成功！")
    async def on_disconnected(self, ctx):
        print(f" [SX_BET] 伺服器斷線: {getattr(ctx, 'reason', '未知')}")

# === 3. 模組主體 Connector ===
class SXBetConnector:
    def __init__(self, api_key, market_hash, on_update_callback):
        self.api_key = api_key
        self.market_hash = market_hash
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
        """啟動連接器並在背景持續運行"""
        # 加上提示，方便 debug
        print(f" [SX_BET] 準備啟動連線，正在獲取 Token... (Hash: {self.market_hash[:8]}...)") 
        
        self.client = Client(WS_URL, events=SXConnectionEvents(), get_token=self._fetch_token)
        await self.client.connect()
        
        market_state = SXMarketState(self.market_hash, self.on_update_callback)
        handler = SXOrderBookHandler()
        handler.state = market_state
        
        channel_name = f"order_book:market_{self.market_hash}"
        sub = self.client.new_subscription(channel_name, events=handler, positioned=True, recoverable=True)
        await sub.subscribe()

# === 單獨測試用 ===
if __name__ == "__main__":
    def dummy_callback(data):
        buy_1_cost = data.get('buy_outcome_1_cost')
        buy_1_size = data.get('buy_outcome_1_size', 0)
        buy_2_cost = data.get('buy_outcome_2_cost')
        buy_2_size = data.get('buy_outcome_2_size', 0)
        
        print(f" [回報測試] SX Bet 最新報價:")
        if buy_1_cost:
            print(f"    買 Yes 成本: {buy_1_cost:.4f} | 深度: {buy_1_size:.2f} USDC")
        if buy_2_cost:
            print(f"    買 No  成本: {buy_2_cost:.4f} | 深度: {buy_2_size:.2f} USDC")
        print("-" * 40)

    async def test():
        # 如果環境變數沒有設定，給一個預設的備用字串避免報錯
        API_KEY  = os.environ.get("SX_bet")
        TARGET_HASH = "0x0613cea110f26815d01f74e3c1c7333158c86eeb1ce06a897b6f283d4e1a8bd0"
        
        connector = SXBetConnector(API_KEY, TARGET_HASH, dummy_callback)
        print(" 啟動 SX Bet 測試連線...")
        await connector.start()
        
        await asyncio.Future()

    try:
        asyncio.run(test())
    except KeyboardInterrupt:
        print("\n 已手動停止程式")