import asyncio
import websockets
import json
import traceback
import random
class PolyConnector:
    #  1. 改接收 asset_ids (List)
    def __init__(self, asset_ids, on_update_callback):
        self.asset_ids = list(asset_ids) 
        self.on_update_callback = on_update_callback
        
        #  2. 升級字典結構：針對每個 ID 都有獨立的訂單簿
        self.bids = {aid: {} for aid in self.asset_ids}
        self.asks = {aid: {} for aid in self.asset_ids}

    async def start(self):
        ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        #  3. 把整個 List 丟給伺服器
        subscribe_msg = {
            "assets_ids": self.asset_ids,
            "type": "market",
            "custom_feature_enabled": True
        }

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            "Origin": "https://polymarket.com"
        }

        while True:
            try:
                #  2. 隨機抖動延遲 (錯開連線時間)
                await asyncio.sleep(random.uniform(0.1, 2.0))
                
                #  3. 把 headers 塞進連線請求裡
                async with websockets.connect(ws_url, additional_headers=headers) as websocket:
                    print(f"[POLY] WebSocket 連線成功！(監聽 {len(self.asset_ids)} 個盤口)")
                    await websocket.send(json.dumps(subscribe_msg))

                    while True:
                        response = await websocket.recv()
                        data = json.loads(response)
                        events = data if isinstance(data, list) else [data]
                        changed = False

                        for event in events:
                            incoming_asset_id = str(event.get("asset_id", ""))
                            if incoming_asset_id not in self.asset_ids:
                                continue

                            aid = incoming_asset_id # 簡寫
                            changed = False

                            if "asks" in event and event["asks"]:
                                for ask in event["asks"]:
                                    p = float(ask.get("price", 0)) if isinstance(ask, dict) else float(ask[0])
                                    s = float(ask.get("size", 0)) if isinstance(ask, dict) else float(ask[1])
                                    if s <= 0:
                                        self.asks[aid].pop(p, None)
                                    else:
                                        self.asks[aid][p] = s
                                changed = True

                            if "bids" in event and event["bids"]:
                                for bid in event["bids"]:
                                    p = float(bid.get("price", 0)) if isinstance(bid, dict) else float(bid[0])
                                    s = float(bid.get("size", 0)) if isinstance(bid, dict) else float(bid[1])
                                    if s <= 0:
                                        self.bids[aid].pop(p, None)
                                    else:
                                        self.bids[aid][p] = s
                                changed = True

                            if changed:
                                self._trigger_callback(aid)

            except websockets.exceptions.ConnectionClosed:
                # 使用 \r 避免洗版
                print(f"\r [POLY] 連線斷開，5秒後重連... (共 {len(self.asset_ids)} 個盤口)       ")
                await asyncio.sleep(5)
            except Exception as e:
                # 4. 刪除 traceback.print_exc()，改成乾淨單行錯誤提示！
                print(f"\r [POLY] 連線受阻 ({type(e).__name__})，5秒後重試... (共 {len(self.asset_ids)} 個盤口)       ")
                await asyncio.sleep(5)

    def _trigger_callback(self, aid):
        if not self.on_update_callback: return

        best_ask_price = min(self.asks[aid].keys()) if self.asks[aid] else None
        best_ask_size = self.asks[aid][best_ask_price] if best_ask_price else 0

        best_bid_price = max(self.bids[aid].keys()) if self.bids[aid] else None
        best_bid_size = self.bids[aid][best_bid_price] if best_bid_price else 0

        bbo_data = {
            "platform": "POLY",
            "market_hash": aid,
            "buy_outcome_1_cost": best_ask_price,
            "buy_outcome_1_size": best_ask_size,
            "buy_outcome_2_cost": (1.0 - best_bid_price) if best_bid_price else None,
            "buy_outcome_2_size": best_bid_size,
            "total_active_orders": len(self.asks[aid]) + len(self.bids[aid])
        }
        self.on_update_callback(bbo_data)

# === 單獨測試用 ===
if __name__ == "__main__":
    def dummy_callback(data):
        buy_1_cost = data.get('buy_outcome_1_cost')
        buy_1_size = data.get('buy_outcome_1_size', 0)
        buy_2_cost = data.get('buy_outcome_2_cost')
        buy_2_size = data.get('buy_outcome_2_size', 0)
        
        print(f" [回報測試] Poly 最新報價:")
        if buy_1_cost:
            print(f"    買 Yes 成本: {buy_1_cost:.4f} | 深度: {buy_1_size:.2f} 份")
        if buy_2_cost:
            print(f"   買 No  成本: {buy_2_cost:.4f} | 深度: {buy_2_size:.2f} 份")
        print("-" * 40)

    async def test():
        connector = PolyConnector(["39767095656649264630783425438372390895789661081321391574823969191181185605477"], dummy_callback)
        await connector.start()

    asyncio.run(test())