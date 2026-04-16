import asyncio
import os
import time
import aiohttp
from centrifuge import Client, ClientEventHandler, SubscriptionEventHandler
from dotenv import load_dotenv
import json

load_dotenv()

RELAYER_URL = "https://api.sx.bet"
WS_URL = "wss://realtime.sx.bet/connection/websocket"

snapshot_semaphore = asyncio.Semaphore(2)


# ==========================================
# 1. 核心狀態機
# ==========================================
class SXMarketState:
    def __init__(self, market_hash, update_callback=None):
        self.market_hash = market_hash
        self.update_callback = update_callback
        self.is_ready = False
        self.buffer = []
        self.orders = {}

    # --- 快照來源的欄位名稱 ---
    def _is_valid_snapshot_order(self, order) -> bool:
        if order.get("orderStatus") != "ACTIVE":
            return False
        expiry = order.get("apiExpiry")
        if expiry and time.time() > int(expiry):
            return False
        total = float(order.get("totalBetSize", 0))
        filled = float(order.get("fillAmount", 0))
        return (total - filled) > 0

    # --- WS update 來源的欄位名稱 ---
    def _is_valid_ws_order(self, order) -> bool:
        if order.get("status") != "ACTIVE":
            return False
        expiry = order.get("apiExpiry")
        if expiry and time.time() > int(expiry):
            return False
        total = float(order.get("totalBetSize", 0))
        filled = float(order.get("fillAmount", 0))
        return (total - filled) > 0

    def apply_snapshot(self, snapshot_data):
        self.orders = {}
        for order in snapshot_data.get("data", []):
            if order.get("orderHash") and self._is_valid_snapshot_order(order):
                self.orders[order["orderHash"]] = order
        self._calculate_and_emit_bbo()

    def process_ws_update(self, raw_data):
        if not self.is_ready:
            self.buffer.append(raw_data)
            return

        updates = raw_data if isinstance(raw_data, list) else [raw_data]
        changed = False

        for order in updates:
            order_hash = order.get("orderHash")
            if not order_hash:
                continue

            if self._is_valid_ws_order(order):
                self.orders[order_hash] = order
                changed = True
            else:
                if self.orders.pop(order_hash, None) is not None:
                    changed = True

        if changed:
            self._calculate_and_emit_bbo()

    def flush_buffer(self):
        if not self.buffer:
            return
        for data in self.buffer:
            self.process_ws_update(data)
        self.buffer.clear()

    def _calculate_and_emit_bbo(self):
        if not self.update_callback:
            return

        current_time = time.time()
        best_o1_cost, best_o1_size = float('inf'), 0.0
        best_o2_cost, best_o2_size = float('inf'), 0.0

        for order_hash, order in list(self.orders.items()):

            # 過期清除（兼容毫秒/秒）
            expiry = order.get("apiExpiry")
            if expiry:
                expiry_val = int(expiry)
                if expiry_val > 9_999_999_999:
                    expiry_val /= 1000.0
                if current_time > expiry_val:
                    del self.orders[order_hash]
                    continue

            # 剩餘數量
            total = float(order.get("totalBetSize", 0))
            filled = float(order.get("fillAmount", 0))
            remaining_raw = total - filled
            if remaining_raw <= 0:
                del self.orders[order_hash]
                continue

            # 機率換算
            pct_odds = float(order.get("percentageOdds", 0))
            maker_prob = pct_odds / (10 ** 20)
            if not (0 < maker_prob < 1):
                continue

            taker_prob = 1.0 - maker_prob
            remaining_usdc = remaining_raw / (10 ** 6)
            taker_size = remaining_usdc * (taker_prob / maker_prob)

            # 灰塵訂單過濾
            if taker_size < 1.0:
                continue

            cost = taker_prob
            is_maker_o1 = order.get("isMakerBettingOutcomeOne", False)

            if is_maker_o1:
                if cost < best_o2_cost:
                    best_o2_cost, best_o2_size = cost, taker_size
                elif cost == best_o2_cost:
                    best_o2_size += taker_size
            else:
                if cost < best_o1_cost:
                    best_o1_cost, best_o1_size = cost, taker_size
                elif cost == best_o1_cost:
                    best_o1_size += taker_size

        yes = best_o1_cost if best_o1_cost != float('inf') else None
        no = best_o2_cost if best_o2_cost != float('inf') else None

        # Sanity check
        if yes and no:
            total_cost = yes + no
            if not (0.95 <= total_cost <= 1.10):
                print(f"⚠️  [SANITY] {self.market_hash[:8]} yes+no={total_cost:.4f}，略過")
                return

        self.update_callback({
            "platform": "SX_BET",
            "market_hash": self.market_hash,
            "buy_outcome_1_cost": yes,
            "buy_outcome_1_size": best_o1_size,
            "buy_outcome_2_cost": no,
            "buy_outcome_2_size": best_o2_size,
            "total_active_orders": len(self.orders),
        })


# ==========================================
# 2. 頻道處理器
# ==========================================
class SXSubscriptionHandler(SubscriptionEventHandler):
    def __init__(self, market_state: SXMarketState):
        super().__init__()
        self.state = market_state

    async def on_subscribed(self, ctx) -> None:
        asyncio.create_task(self._sync_snapshot())

    async def _sync_snapshot(self):
        market_hash = self.state.market_hash
        print(f"🟢 [SX] 訂閱成功，準備同步快照 ({market_hash[:8]}...)")

        self.state.is_ready = False
        self.state.buffer.clear()

        async with snapshot_semaphore:
            await asyncio.sleep(0.3)
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{RELAYER_URL}/orders?marketHashes={market_hash}&status=ACTIVE"
                    for attempt in range(3):
                        try:
                            async with session.get(
                                url,
                                timeout=aiohttp.ClientTimeout(total=10)
                            ) as res:
                                if res.status == 200:
                                    orders_data = await res.json()
                                    self.state.buffer.clear()
                                    self.state.apply_snapshot(orders_data)
                                    break
                                elif res.status == 429:
                                    print(f"⚠️  [SX] 快照被限流，等待重試 ({attempt+1}/3)")
                                    await asyncio.sleep(3)
                                else:
                                    print(f"⚠️  [SX] 快照 HTTP {res.status}，重試 ({attempt+1}/3)")
                                    await asyncio.sleep(1)
                        except asyncio.TimeoutError:
                            print(f"⚠️  [SX] 快照請求逾時，重試 ({attempt+1}/3)")
                            await asyncio.sleep(1)
            except Exception as e:
                print(f"⚠️  [SX] 快照 session 錯誤 ({market_hash[:8]}): {e}")

        self.state.flush_buffer()
        self.state.is_ready = True

    async def on_error(self, ctx) -> None:
        err_msg = getattr(ctx.error, 'message', str(ctx.error))
        print(f"❌ [SX] 頻道異常 ({self.state.market_hash[:8]}): {err_msg}")

    async def on_publication(self, ctx) -> None:
        raw_data = getattr(ctx, 'pub', ctx).data if hasattr(ctx, 'pub') else ctx.data
        self.state.process_ws_update(raw_data)


# ==========================================
# 3. 連線管理
# ==========================================
class SXClientEvents(ClientEventHandler):
    async def on_connected(self, ctx):
        print("🌐 [SX_BET] WebSocket 主連線成功！")

    async def on_disconnected(self, ctx):
        print(f"❌ [SX_BET] 伺服器斷線: {getattr(ctx, 'reason', '未知')}")


class SXBetConnector:
    def __init__(self, api_key, market_hashes, on_update_callback):
        self.api_key = api_key
        self.market_hashes = list(market_hashes)
        self.on_update_callback = on_update_callback

    async def _fetch_token(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{RELAYER_URL}/user/realtime-token/api-key",
                headers={"x-api-key": self.api_key},
                timeout=aiohttp.ClientTimeout(total=10)
            ) as res:
                if res.status != 200:
                    raise Exception(f"SX Token 取得失敗 (狀態碼: {res.status})")
                data = await res.json()
                return data["token"]

    async def start(self):
        MAX_SUBS_PER_CLIENT = 150
        print(f"🔄 [SX_BET] 啟動，共 {len(self.market_hashes)} 個盤口")

        async def launch_worker(batch, batch_id):
            client = Client(WS_URL, events=SXClientEvents(), get_token=self._fetch_token)
            await client.connect()

            for m_hash in batch:
                state = SXMarketState(m_hash, self.on_update_callback)
                handler = SXSubscriptionHandler(state)
                sub = client.new_subscription(
                    f"order_book:market_{m_hash}",
                    events=handler,
                    positioned=True,
                    recoverable=True
                )
                try:
                    await sub.subscribe()
                except Exception as e:
                    print(f"⚠️  [SX] 訂閱失敗 ({m_hash[:8]}): {e}")

                await asyncio.sleep(0.1)

            print(f"✅ [SX_BET] 節點 {batch_id} 就緒 ({len(batch)} 個頻道)")
            while True:
                await asyncio.sleep(3600)

        workers = [
            launch_worker(self.market_hashes[i:i + MAX_SUBS_PER_CLIENT], (i // MAX_SUBS_PER_CLIENT) + 1)
            for i in range(0, len(self.market_hashes), MAX_SUBS_PER_CLIENT)
        ]
        await asyncio.gather(*workers)


# ==========================================
# 4. 單獨測試
# ==========================================
if __name__ == "__main__":
    def test_callback(data):
        print(f"\n📢 [SX_BET 最新盤口狀態回報]")
        print(json.dumps(data, indent=4, ensure_ascii=False))
        print("-" * 50)

    async def main_test():
        API_KEY = os.environ.get("SX_bet")
        if not API_KEY:
            print("❌ 找不到 SX_bet API_KEY")
            return

        TEST_HASHES = [
            "0x945fa842e5a9ebb45f25f1c072af249ee2c637d8df0c0a0a084274e3c077cdef"
        ]
        connector = SXBetConnector(API_KEY, TEST_HASHES, test_callback)
        await connector.start()

    try:
        asyncio.run(main_test())
    except KeyboardInterrupt:
        print("\n⏹️ 已手動停止")