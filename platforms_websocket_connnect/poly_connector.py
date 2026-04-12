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
                                    p_raw = float(ask.get("price", 0)) if isinstance(ask, dict) else float(ask[0])
                                    s_raw = float(ask.get("size", 0)) if isinstance(ask, dict) else float(ask[1])
                                    p = round(float(p_raw), 4)
                                    s = float(s_raw)
                                    if s <= 0:
                                        self.asks[aid].pop(p, None)
                                    else:
                                        self.asks[aid][p] = s
                                changed = True

                            if "bids" in event and event["bids"]:
                                for bid in event["bids"]:
                                    p_raw = bid.get("price", 0) if isinstance(bid, dict) else bid[0]
                                    s_raw = bid.get("size", 0) if isinstance(bid, dict) else bid[1]
                                    
                                    p = round(float(p_raw), 4)
                                    s = float(s_raw)

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
        while True:
            best_ask_price = min(self.asks[aid].keys()) if self.asks[aid] else None
            best_bid_price = max(self.bids[aid].keys()) if self.bids[aid] else None

            # 如果一邊空了，就不可能倒掛，安全過關
            if best_ask_price is None or best_bid_price is None:
                break
                
            # 正常情況下，買價 (Bid) 必須小於 賣價 (Ask)
            if best_bid_price < best_ask_price:
                break # 狀態健康，跳出檢查
                
            #  發生倒掛
            # 代表這兩個極端價格中必定有漏接刪除封包的幽靈，直接將它們從記憶體抹除！
            self.asks[aid].pop(best_ask_price, None)
            self.bids[aid].pop(best_bid_price, None)
            # 迴圈會繼續檢查下一組最佳價格，直到訂單簿恢復正常！
        # 
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
        connector = PolyConnector(["96898772129585101925877684695807771447728395559096872684551711473773297707732"], dummy_callback)
        await connector.start()

    asyncio.run(test())