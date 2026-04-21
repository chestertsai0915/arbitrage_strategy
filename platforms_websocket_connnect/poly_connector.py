import asyncio
import websockets
import json
import random

class PolyConnector:
    def __init__(self, asset_ids, on_update_callback):
        self.asset_ids = list(asset_ids)
        self.on_update_callback = on_update_callback
        
        # 共享狀態字典
        self.bids = {aid: {} for aid in self.asset_ids}
        self.asks = {aid: {} for aid in self.asset_ids}
        self._last_state = {aid: None for aid in self.asset_ids}

    def _parse_level(self, level):
        """統一解析 {price, size} dict 或 [price, size] list 兩種格式"""
        if isinstance(level, dict):
            return float(level["price"]), float(level["size"])
        return float(level[0]), float(level[1])

    def _trigger_callback(self, aid):
        if not self.on_update_callback:
            return

        # 清除倒掛 (bid >= ask) 的殭屍價位
        while True:
            best_ask = min(self.asks[aid]) if self.asks[aid] else None
            best_bid = max(self.bids[aid]) if self.bids[aid] else None
            if best_ask is None or best_bid is None or best_bid < best_ask:
                break
            self.asks[aid].pop(best_ask, None)
            self.bids[aid].pop(best_bid, None)

        best_ask = min(self.asks[aid]) if self.asks[aid] else None
        best_bid = max(self.bids[aid]) if self.bids[aid] else None

        yes_cost = best_ask
        no_cost = round(1.0 - best_bid, 6) if best_bid is not None else None

        new_state = (yes_cost, self.asks[aid].get(best_ask, 0),
                     no_cost, self.bids[aid].get(best_bid, 0))

        # 狀態沒變就不觸發
        if new_state == self._last_state[aid]:
            return
        self._last_state[aid] = new_state

        self.on_update_callback({
            "platform": "POLY",
            "market_hash": aid,
            "buy_outcome_1_cost": yes_cost,
            "buy_outcome_1_size": self.asks[aid].get(best_ask, 0),
            "buy_outcome_2_cost": no_cost,
            "buy_outcome_2_size": self.bids[aid].get(best_bid, 0),
            "total_active_orders": len(self.asks[aid]) + len(self.bids[aid]),
        })

    def _process_event(self, event):
        aid = str(event.get("asset_id", ""))
        if aid not in self.asset_ids:
            return

        event_type = event.get("event_type", "")

        # book snapshot：全量重建
        if event_type == "book":
            self.asks[aid] = {}
            self.bids[aid] = {}

        changed = False

        for level in event.get("asks", []):
            p, s = self._parse_level(level)
            p = round(p, 4)
            if s <= 0:
                self.asks[aid].pop(p, None)
            else:
                self.asks[aid][p] = s
            changed = True

        for level in event.get("bids", []):
            p, s = self._parse_level(level)
            p = round(p, 4)
            if s <= 0:
                self.bids[aid].pop(p, None)
            else:
                self.bids[aid][p] = s
            changed = True

        if changed:
            self._trigger_callback(aid)

    # 🌟 核心升級：建立獨立的「分身」連線任務
    async def setup_client(self, hashes_batch, batch_index):
        ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Origin": "https://polymarket.com",
        }
        
        while True:
            try:
                # 隨機錯開連線時間，避免瞬間爆發被封 IP
                await asyncio.sleep(random.uniform(0.1, 2.0))
                
                async with websockets.connect(
                    ws_url,
                    additional_headers=headers,
                    ping_interval=20,
                    ping_timeout=20,
                    max_size=None,
                ) as ws:
                    
                    # 重連時只清空「這個分身」負責的舊狀態
                    for aid in hashes_batch:
                        self.asks[aid] = {}
                        self.bids[aid] = {}
                        self._last_state[aid] = None
                        
                    # 一次只送出 50 個訂閱 (Polymarket 單一連線的極限)
                    await ws.send(json.dumps({
                        "assets_ids": hashes_batch,
                        "type": "market",
                    }))
                    
                    # 降低印出頻率，保持畫面乾淨
                    if batch_index % 5 == 0:
                        print(f"✅ [POLY] 節點 {batch_index+1} 成功連線並訂閱 {len(hashes_batch)} 個盤口")
                    
                    while True:
                        raw = await ws.recv()
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue

                        events = data if isinstance(data, list) else [data]
                        for event in events:
                            self._process_event(event)

            except websockets.exceptions.ConnectionClosed:
                await asyncio.sleep(3)
            except Exception:
                await asyncio.sleep(3)

    async def start(self):
        print(f"🔄 [POLY] 準備啟動分片連線，共 {len(self.asset_ids)} 個盤口需要監聽...")
        
        # 🌟 強制設定：每個 WebSocket 連線最多只負責 50 個盤口
        MAX_SUBS_PER_CLIENT = 50
        client_tasks = []

        for i in range(0, len(self.asset_ids), MAX_SUBS_PER_CLIENT):
            batch = self.asset_ids[i:i + MAX_SUBS_PER_CLIENT]
            batch_index = i // MAX_SUBS_PER_CLIENT
            # 將切割好的 50 個 ID 丟給獨立的分身連線
            client_tasks.append(self.setup_client(batch, batch_index))
            
        # 同時發動所有的分身！
        await asyncio.gather(*client_tasks)

# === 單獨測試用 ===
if __name__ == "__main__":
    def dummy_callback(data):
        print(json.dumps(data, indent=4, ensure_ascii=False))
        print("-" * 60)

    async def test():
        connector = PolyConnector(
            ["61748753503141854225539924235995178690958401963102840700211097813412855973585"],
            dummy_callback,
        )
        await connector.start()

    asyncio.run(test())