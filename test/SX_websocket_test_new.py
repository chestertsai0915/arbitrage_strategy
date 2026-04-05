import asyncio
import aiohttp
from centrifuge import (
    Client,
    ClientEventHandler,
    PublicationContext,
    SubscribedContext,
    SubscriptionEventHandler,
)

RELAYER_URL = "https://api.sx.bet"
WS_URL = "wss://realtime.sx.bet/connection/websocket"


TARGET_MARKET_HASH = "0xc3c13235c3bd1ce889204be5cd6e3666d15ddf13cb8e37dec859aa67c90683c3"

async def fetch_token():
    api_key = "c75330b7-7ad6-460f-9e2d-cf7a26d9b917"
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{RELAYER_URL}/user/realtime-token/api-key",
            headers={"x-api-key": api_key}
        ) as res:
            if res.status != 200:
                raise Exception(f"取得 Token 失敗，狀態碼: {res.status}")
            data = await res.json()
            return data["token"]

# === 1. 本地 Orderbook 狀態管理 (O(1) 更新速度) ===
class MarketState:
    def __init__(self, market_hash):
        self.market_hash = market_hash
        self.ready = False
        self.buffer = []
        self.local_orderbook = {}

    def apply_snapshot(self, orders_data):
        # 從 REST API 取回的資料通常包在 'data' 裡
        orders_list = orders_data.get("data", [])
        self.local_orderbook = {order["orderHash"]: order for order in orders_list}
        print(f"\n [Snapshot] 成功取得初始 Orderbook，目前共有 {len(self.local_orderbook)} 筆 ACTIVE 限價單。")

    def apply_update(self, update_data):
        # 官方文件：Payload is an array of order objects
        updates = update_data if isinstance(update_data, list) else [update_data]
        
        for order in updates:
            order_hash = order.get("orderHash")
            if not order_hash:
                continue
                
            status = order.get("status", "")
            maker_odds = int(order.get("percentageOdds", 0)) / (10 ** 20)
            
            # 若為 ACTIVE 則新增或更新
            if status == "ACTIVE":
                self.local_orderbook[order_hash] = order
                print(f" [新增/更新] 訂單 {order_hash[:8]}... | 賠率: {maker_odds:.4f} | 當前總單量: {len(self.local_orderbook)}")
            # 若為 INACTIVE (取消), FILLED (成交) 則從字典中剔除
            else:
                removed = self.local_orderbook.pop(order_hash, None)
                if removed:
                    print(f" [剔除] 訂單 {order_hash[:8]}... (狀態: {status}) | 當前總單量: {len(self.local_orderbook)}")

# === 2. 頻道訂閱與歷史補齊邏輯 ===
class OrderBookHandler(SubscriptionEventHandler):
    async def on_subscribed(self, ctx: SubscribedContext) -> None:
        print(f"\n 已成功訂閱單一盤口頻道: order_book:market_{self.state.market_hash}")
        
        # 官方文件建議：如果斷線重連成功，不需要重抓 Snapshot
        if getattr(ctx, 'was_recovering', False) and getattr(ctx, 'recovered', False):
            print(" 斷線重連成功，歷史資料已自動補齊。")
            self.state.ready = True
            return

        print(" 正在從 REST API 取得最新 Snapshot...")
        self.state.ready = False
        self.state.buffer.clear()

        # 抓取初始快照，加上 status=ACTIVE 確保只抓有效單
        async with aiohttp.ClientSession() as session:
            url = f"{RELAYER_URL}/orders?marketHashes={self.state.market_hash}&status=ACTIVE"
            async with session.get(url) as res:
                if res.status == 200:
                    orders_data = await res.json()
                    self.state.apply_snapshot(orders_data)
                else:
                    print(f" 取得 Snapshot 失敗: {res.status}")

        # 消化抓取快照期間卡在緩衝區的 WebSocket 推播
        for data in self.state.buffer:
            self.state.apply_update(data)
        self.state.buffer.clear()
        self.state.ready = True

    async def on_publication(self, ctx: PublicationContext) -> None:
        #  關鍵解包：避免 AttributeError
        raw_data = getattr(ctx, 'pub', ctx).data if hasattr(ctx, 'pub') else ctx.data
        
        if not self.state.ready:
            self.state.buffer.append(raw_data)
        else:
            self.state.apply_update(raw_data)

# === 3. 主連線監控 ===
class ConnectionEvents(ClientEventHandler):
    async def on_connected(self, ctx):
        print(" [系統] WebSocket 主連線成功！")
    async def on_disconnected(self, ctx):
        print(f" [系統] 伺服器斷線: {getattr(ctx, 'reason', '未知')}")

async def main():
    print("啟動 SX Bet Orderbook 引擎...")
    
    client = Client(WS_URL, events=ConnectionEvents(), get_token=fetch_token)
    await client.connect()
    
    # 初始化狀態與 Handler
    market_state = MarketState(TARGET_MARKET_HASH)
    handler = OrderBookHandler()
    handler.state = market_state
    
    channel_name = f"order_book:market_{TARGET_MARKET_HASH}"
    
    # 官方強烈建議：使用 positioned 與 recoverable 來實現斷線歷史補齊
    sub = client.new_subscription(
        channel_name, 
        events=handler,
        positioned=True, 
        recoverable=True
    )
    await sub.subscribe()
    
    await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n 已手動停止程式")