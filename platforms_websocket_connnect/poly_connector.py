import asyncio
import websockets
import json
import traceback

class PolyConnector:
    def __init__(self, asset_id, on_update_callback):
        """
        :param asset_id: 單一賽果的 Token ID
        """
        self.asset_id = str(asset_id)
        self.on_update_callback = on_update_callback
        
        #  升級：使用字典來維護完整的本地訂單簿 (Price -> Size)
        self.bids = {}
        self.asks = {}

    async def start(self):
        ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
        subscribe_msg = {
            "assets_ids": [self.asset_id],
            "type": "market",
            "custom_feature_enabled": True
        }

        while True:
            try:
                async with websockets.connect(ws_url) as websocket:
                    print(f" [POLY] WebSocket 連線成功！(Token: {self.asset_id[:8]}...)")
                    await websocket.send(json.dumps(subscribe_msg))

                    while True:
                        response = await websocket.recv()
                        data = json.loads(response)
                        events = data if isinstance(data, list) else [data]
                        changed = False

                        for event in events:
                            incoming_asset_id = str(event.get("asset_id", ""))
                            if incoming_asset_id != self.asset_id:
                                continue

                            #  處理 Asks (賣方訂單) 更新 
                            if "asks" in event and event["asks"]:
                                for ask in event["asks"]:
                                    p = float(ask.get("price", 0)) if isinstance(ask, dict) else float(ask[0])
                                    s = float(ask.get("size", 0)) if isinstance(ask, dict) else float(ask[1])
                                    
                                    if s <= 0:
                                        # Size 為 0 代表該價位的訂單被取消或吃光了，從字典中移除
                                        self.asks.pop(p, None)
                                    else:
                                        # 更新或新增該價位的深度
                                        self.asks[p] = s
                                changed = True

                            #  處理 Bids (買方訂單) 更新 
                            if "bids" in event and event["bids"]:
                                for bid in event["bids"]:
                                    p = float(bid.get("price", 0)) if isinstance(bid, dict) else float(bid[0])
                                    s = float(bid.get("size", 0)) if isinstance(bid, dict) else float(bid[1])
                                    
                                    if s <= 0:
                                        self.bids.pop(p, None)
                                    else:
                                        self.bids[p] = s
                                changed = True

                        # 只要訂單簿有變動，就觸發計算與回報
                        if changed:
                            self._trigger_callback()

            except websockets.exceptions.ConnectionClosed:
                print(f" [POLY] 連線斷開，5秒後重連... (Token: {self.asset_id[:8]}...)")
                await asyncio.sleep(5)
            except Exception as e:
                print(f" [POLY] 發生錯誤: {e}")
                traceback.print_exc()
                await asyncio.sleep(5)

    def _trigger_callback(self):
        if not self.on_update_callback: return

     
        # 賣方最低價 (Best Ask) -> 我們買 Yes 的成本
        best_ask_price = min(self.asks.keys()) if self.asks else None
        best_ask_size = self.asks[best_ask_price] if best_ask_price else 0

        # 買方最高價 (Best Bid) -> 我們買 No 的對手價
        best_bid_price = max(self.bids.keys()) if self.bids else None
        best_bid_size = self.bids[best_bid_price] if best_bid_price else 0

        # === 核心轉換邏輯 ===
        buy_yes_cost = best_ask_price
        buy_no_cost = (1.0 - best_bid_price) if best_bid_price else None

        bbo_data = {
            "platform": "POLY",
            "market_hash": self.asset_id,
            "buy_outcome_1_cost": buy_yes_cost,
            "buy_outcome_1_size": best_ask_size,
            "buy_outcome_2_cost": buy_no_cost,
            "buy_outcome_2_size": best_bid_size,
            "total_active_orders": len(self.asks) + len(self.bids)
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
        connector = PolyConnector("19596230505334905503321726547378309060167788245319748292157531175114826139084", dummy_callback)
        await connector.start()

    asyncio.run(test())