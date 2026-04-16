import asyncio
import socketio

class LimitlessConnector:
    def __init__(self, market_slugs, on_update_callback):
        self.market_slugs = list(market_slugs) if not isinstance(market_slugs, list) else market_slugs
        self.on_update_callback = on_update_callback

        self._last_version = {slug: -1 for slug in self.market_slugs}
        self._current_state = {slug: None for slug in self.market_slugs}

    def _get_buy_fee_rate(self, p: float) -> float:
        if p <= 0.5:
            return 0.03
        else:
            progress = (p - 0.5) / 0.5
            return 0.03 - (0.0297 * progress)

    def _process_orderbook(self, slug, data):
        version = data.get("version", 0)

        # 舊封包直接丟棄
        if version <= self._last_version[slug]:
            return
        self._last_version[slug] = version

        ob = data.get("orderbook", {})
        asks_raw = ob.get("asks", [])
        bids_raw = ob.get("bids", [])

        # 每次都是全量，直接重建
        asks = {}
        for a in asks_raw:
            p = float(a["price"])
            s = float(a["size"]) / 1000000
            if s > 0:
                asks[p] = s

        bids = {}
        for b in bids_raw:
            p = float(b["price"])
            s = float(b["size"]) / 1000000
            if s > 0:
                bids[p] = s

        best_ask = min(asks.keys()) if asks else None
        best_bid = max(bids.keys()) if bids else None

        if best_ask is None or best_bid is None:
            return

        # Sanity check：ask 必須大於 bid
        if best_ask <= best_bid:
            print(f" [SANITY] {slug} orderbook 倒掛 ask={best_ask} <= bid={best_bid}，略過")
            return

        buy_yes_cost = best_ask * (1 + self._get_buy_fee_rate(best_ask))

        raw_no_price = 1.0 - best_bid
        buy_no_cost = raw_no_price * (1 + self._get_buy_fee_rate(raw_no_price))

        # Sanity check：yes + no 加總合理範圍
        total = buy_yes_cost + buy_no_cost
        if not (0.97 <= total <= 1.13):
            print(f"[SANITY] {slug} yes+no={total:.4f} 不合理，略過")
            return

        new_state = {
            "platform": "LIMITLESS",
            "market_hash": slug,
            "buy_outcome_1_cost": buy_yes_cost,
            "buy_outcome_1_size": asks[best_ask],
            "buy_outcome_2_cost": buy_no_cost,
            "buy_outcome_2_size": bids[best_bid],
            "total_active_orders": len(asks) + len(bids),
        }

        # 狀態沒變就不觸發
        if new_state == self._current_state[slug]:
            return

        self._current_state[slug] = new_state
        self.on_update_callback(new_state)

    async def start(self):
        sio = socketio.AsyncClient(logger=False, engineio_logger=False)

        @sio.event(namespace='/markets')
        async def connect():
            print(f"[LIMITLESS] 連線成功，監聽 {len(self.market_slugs)} 個盤口")
            for slug in self.market_slugs:
                self._last_version[slug] = -1
                self._current_state[slug] = None
            await sio.emit('subscribe_market_prices', {"marketSlugs": self.market_slugs}, namespace='/markets')

        @sio.event(namespace='/markets')
        async def disconnect():
            print("[LIMITLESS] 連線斷開")

        @sio.on('orderbookUpdate', namespace='/markets')
        async def on_orderbook_update(data):
            slug = data.get("marketSlug")
            if slug not in self.market_slugs:
                return
            self._process_orderbook(slug, data)

        while True:
            try:
                await sio.connect(
                    'wss://ws.limitless.exchange',
                    namespaces=['/markets'],
                    transports=['websocket']
                )
                await sio.wait()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[LIMITLESS] 連線錯誤: {e}，5 秒後重試...")
                await asyncio.sleep(5)


# === 單獨測試用 ===
if __name__ == "__main__":
    def dummy_callback(data):
        import json
        print(f"📢 [回報] Limitless 最新報價:")
        print(json.dumps(data, indent=4, ensure_ascii=False))
        print("-" * 60)

    async def test():
        connector = LimitlessConnector(["bayern-munchen-1775034007384"], dummy_callback)
        try:
            await connector.start()
        finally:
            await asyncio.sleep(0.25)

    asyncio.run(test())