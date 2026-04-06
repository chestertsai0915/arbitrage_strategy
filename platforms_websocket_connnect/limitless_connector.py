import asyncio
import random
import socketio

class LimitlessConnector:
    def __init__(self, market_slugs, on_update_callback):
        self.market_slugs = list(market_slugs)
        self.on_update_callback = on_update_callback
        
        self.bids = {slug: {} for slug in self.market_slugs}
        self.asks = {slug: {} for slug in self.market_slugs}
        self.current_state = {slug: {"ask_price": None, "ask_size": 0, "bid_price": None, "bid_size": 0} for slug in self.market_slugs}

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

    def _trigger_callback(self, slug):
        if not self.on_update_callback: return

        ask_p = self.current_state[slug]["ask_price"]
        bid_p = self.current_state[slug]["bid_price"]

        buy_yes_cost = None
        if ask_p and 0 < ask_p < 1:
            fee_rate = self._get_buy_fee_rate(ask_p)
            buy_yes_cost = ask_p * (1 + fee_rate)

        buy_no_cost = None
        if bid_p and 0 < bid_p < 1:
            raw_no_price = 1.0 - bid_p
            fee_rate = self._get_buy_fee_rate(raw_no_price)
            buy_no_cost = raw_no_price * (1 + fee_rate)

        bbo_data = {
            "platform": "LIMITLESS",
            "market_hash": slug, 
            "buy_outcome_1_cost": buy_yes_cost, 
            "buy_outcome_1_size": self.current_state[slug]["ask_size"],
            "buy_outcome_2_cost": buy_no_cost,
            "buy_outcome_2_size": self.current_state[slug]["bid_size"],
            "total_active_orders": len(self.asks[slug]) + len(self.bids[slug])
        }
        self.on_update_callback(bbo_data)

    async def start(self):
        sio = socketio.AsyncClient(logger=False, engineio_logger=False)

        @sio.event(namespace='/markets')
        async def connect():
            print(f" [LIMITLESS] WebSocket 主連線成功！監聽 {len(self.market_slugs)} 個盤口")
            #  把清單整包丟出去
            await sio.emit('subscribe_market_prices', {"marketSlugs": self.market_slugs}, namespace='/markets')

        @sio.event(namespace='/markets')
        async def disconnect():
            print(f" [LIMITLESS] 連線斷開，等待重連... (Slug: {self.market_slug[:15]}...)")

        @sio.on('orderbookUpdate', namespace='/markets')
        async def on_orderbook_update(data):
            slug = data.get("marketSlug")
            if slug not in self.market_slugs:
                return

            ob = data.get("orderbook", {})
            bids = ob.get("bids", [])
            asks = ob.get("asks", [])
            
            if asks:
                for ask in asks:
                    p = float(ask["price"])
                    s = float(ask["size"]) / 1000000.0
                    if s <= 0: self.asks[slug].pop(p, None)
                    else: self.asks[slug][p] = s

            if bids:
                for bid in bids:
                    p = float(bid["price"])
                    s = float(bid["size"]) / 1000000.0
                    if s <= 0: self.bids[slug].pop(p, None)
                    else: self.bids[slug][p] = s

            best_ask_price = min(self.asks[slug].keys()) if self.asks[slug] else None
            best_ask_size = self.asks[slug][best_ask_price] if best_ask_price else 0

            best_bid_price = max(self.bids[slug].keys()) if self.bids[slug] else None
            best_bid_size = self.bids[slug][best_bid_price] if best_bid_price else 0

            state = self.current_state[slug]
            if (state["ask_price"] != best_ask_price or state["ask_size"] != best_ask_size or
                state["bid_price"] != best_bid_price or state["bid_size"] != best_bid_size):
                
                state["ask_price"] = best_ask_price
                state["ask_size"] = best_ask_size
                state["bid_price"] = best_bid_price
                state["bid_size"] = best_bid_size
                
                self._trigger_callback(slug)

        # 連線守護迴圈 (自動重連機制)
        while True:
            try:
                await sio.connect('wss://ws.limitless.exchange', namespaces=['/markets'], transports=['websocket'])
                await sio.wait()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f" [LIMITLESS] 連線發生錯誤: {e}，5秒後重試...")
                await asyncio.sleep(5)

# === 單獨測試用 ===
if __name__ == "__main__":
    def dummy_callback(data):
        buy_1_cost = data['buy_outcome_1_cost']
        buy_1_size = data['buy_outcome_1_size']
        buy_2_cost = data['buy_outcome_2_cost']
        buy_2_size = data['buy_outcome_2_size']
        
        print(f" [回報] Limitless 最新報價:")
        if buy_1_cost:
            print(f"    買 Yes 成本: {buy_1_cost:.4f} | 深度: {buy_1_size:.2f} USDC")
        if buy_2_cost:
            print(f"    買 No  成本: {buy_2_cost:.4f} | 深度: {buy_2_size:.2f} USDC")
        print("-" * 40)

    async def test():
        connector = LimitlessConnector("real-madrid-1774342805684", dummy_callback)
        await connector.start()

    asyncio.run(test())