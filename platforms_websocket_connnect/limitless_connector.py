import asyncio
import socketio

class LimitlessConnector:
    def __init__(self, market_slug, on_update_callback):
        """
        :param market_slug: Limitless 子盤口的 Slug (例如 ucl-rma1-bay1-2026-04-07-rma1)
        :param on_update_callback: 價格更新時要呼叫的主程式函數
        """
        self.market_slug = str(market_slug)
        self.on_update_callback = on_update_callback
        
        # 🌟 升級：維護本地端訂單簿 (Price -> Size)
        self.bids = {}
        self.asks = {}
        
        # 記憶體：存放最新的 BBO (Best Bid & Offer) 狀態
        self.current_state = {
            "ask_price": None, "ask_size": 0,
            "bid_price": None, "bid_size": 0
        }

    def _get_buy_fee_rate(self, p: float) -> float:
        """
        模擬 Limitless 動態買入手續費率 (Taker Fee)：
        0.0 ~ 0.5 維持 3% (0.03)
        0.5 ~ 1.0 線性下降至 0.03% (0.0003)
        """
        if p <= 0.5:
            return 0.03
        else:
            progress = (p - 0.5) / 0.5
            return 0.03 - (0.0297 * progress)

    def _trigger_callback(self):
        """將最新價格加上手續費後，標準化傳遞給核心引擎"""
        if not self.on_update_callback: 
            return

        ask_p = self.current_state["ask_price"]
        bid_p = self.current_state["bid_price"]

        buy_yes_cost = None
        if ask_p and 0 < ask_p < 1:
            fee_rate = self._get_buy_fee_rate(ask_p)
            buy_yes_cost = ask_p * (1 + fee_rate)

        buy_no_cost = None
        if bid_p and 0 < bid_p < 1:
            raw_no_price = 1.0 - bid_p
            fee_rate = self._get_buy_fee_rate(raw_no_price)
            buy_no_cost = raw_no_price * (1 + fee_rate)

        # 打包成標準格式丟給 main.py
        bbo_data = {
            "platform": "LIMITLESS",
            "market_hash": self.market_slug, 
            "buy_outcome_1_cost": buy_yes_cost,   # 買 Yes 的真實成本
            "buy_outcome_1_size": self.current_state["ask_size"],
            "buy_outcome_2_cost": buy_no_cost,    # 買 No 的真實成本
            "buy_outcome_2_size": self.current_state["bid_size"],
            "total_active_orders": len(self.asks) + len(self.bids)
        }
        self.on_update_callback(bbo_data)

    async def start(self):
        """啟動 Socket.IO 連線並在背景持續運行"""
        sio = socketio.AsyncClient(logger=False, engineio_logger=False)

        @sio.event(namespace='/markets')
        async def connect():
            print(f"🌐 [LIMITLESS] WebSocket 連線成功！(Slug: {self.market_slug[:15]}...)")
            subscribe_payload = {"marketSlugs": [self.market_slug]}
            await sio.emit('subscribe_market_prices', subscribe_payload, namespace='/markets')

        @sio.event(namespace='/markets')
        async def disconnect():
            print(f"❌ [LIMITLESS] 連線斷開，等待重連... (Slug: {self.market_slug[:15]}...)")

        @sio.on('orderbookUpdate', namespace='/markets')
        async def on_orderbook_update(data):
            incoming_slug = data.get("marketSlug")
            if incoming_slug != self.market_slug:
                return

            ob = data.get("orderbook", {})
            bids = ob.get("bids", [])
            asks = ob.get("asks", [])
            
            # 🌟 將收到的資料更新進本地字典
            if asks:
                for ask in asks:
                    p = float(ask["price"])
                    s = float(ask["size"]) / 1000000.0
                    if s <= 0:
                        self.asks.pop(p, None)
                    else:
                        self.asks[p] = s

            if bids:
                for bid in bids:
                    p = float(bid["price"])
                    s = float(bid["size"]) / 1000000.0
                    if s <= 0:
                        self.bids.pop(p, None)
                    else:
                        self.bids[p] = s

            # 🌟 從字典中抓出真正的 BBO
            best_ask_price = min(self.asks.keys()) if self.asks else None
            best_ask_size = self.asks[best_ask_price] if best_ask_price else 0

            best_bid_price = max(self.bids.keys()) if self.bids else None
            best_bid_size = self.bids[best_bid_price] if best_bid_price else 0

            # 如果 BBO 有任何變動，才通知大腦
            if (self.current_state["ask_price"] != best_ask_price or 
                self.current_state["ask_size"] != best_ask_size or
                self.current_state["bid_price"] != best_bid_price or
                self.current_state["bid_size"] != best_bid_size):
                
                self.current_state["ask_price"] = best_ask_price
                self.current_state["ask_size"] = best_ask_size
                self.current_state["bid_price"] = best_bid_price
                self.current_state["bid_size"] = best_bid_size
                
                self._trigger_callback()

        # 連線守護迴圈 (自動重連機制)
        while True:
            try:
                await sio.connect('wss://ws.limitless.exchange', namespaces=['/markets'], transports=['websocket'])
                await sio.wait()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"⚠️ [LIMITLESS] 連線發生錯誤: {e}，5秒後重試...")
                await asyncio.sleep(5)

# === 單獨測試用 ===
if __name__ == "__main__":
    def dummy_callback(data):
        buy_1_cost = data['buy_outcome_1_cost']
        buy_1_size = data['buy_outcome_1_size']
        buy_2_cost = data['buy_outcome_2_cost']
        buy_2_size = data['buy_outcome_2_size']
        
        print(f"📢 [回報] Limitless 最新報價:")
        if buy_1_cost:
            print(f"   🟢 買 Yes 成本: {buy_1_cost:.4f} | 深度: {buy_1_size:.2f} USDC")
        if buy_2_cost:
            print(f"   🔴 買 No  成本: {buy_2_cost:.4f} | 深度: {buy_2_size:.2f} USDC")
        print("-" * 40)

    async def test():
        connector = LimitlessConnector("real-madrid-1774342805684", dummy_callback)
        await connector.start()

    asyncio.run(test())