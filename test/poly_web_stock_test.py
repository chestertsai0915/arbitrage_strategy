import asyncio
import websockets
import json

async def connect_polymarket_ws():
    # Polymarket 的即時行情 WebSocket 端點
    ws_url = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
    
   
    # 這些 ID 就是你之前從 get_matches() 的 token_mapping 中拿到的那一串數字
    token_ids = ["109940065291344497319355224033988120605581393008537107444137609474099428417028"] 

    # 建立非同步連線
    async with websockets.connect(ws_url) as websocket:
        print(" 成功連線至 Polymarket WebSocket!")

        # 1. 準備訂閱訊息 (Payload)
        subscribe_msg = {
            "assets_ids": token_ids,
            "type": "market",
            "custom_feature_enabled": True  
        }

        # 2. 發送訂閱請求
        await websocket.send(json.dumps(subscribe_msg))
        print(f" 已送出訂閱請求，等待市場數據推播...\n")

        # 3. 持續接收伺服器推播的資料
        try:
            while True:
                response = await websocket.recv()
                data = json.loads(response)

                # Polymarket 傳回來的資料可能是單一物件，也可能是陣列 (多個事件)
                events = data if isinstance(data, list) else [data]

                for event in events:
                    event_type = event.get("event_type")
                    
                    # 情況 A：完整訂單簿快照 (通常在剛連線成功時會收到第一次)
                    if event.get("bids") is not None and event.get("asks") is not None:
                        print("\n [完整訂單簿快照 Book Snapshot]")
                        print(f"   最高買價 (Bids) 前 2 筆: {event['bids'][-1]}")
                        print(f"   最低賣價 (Asks) 前 2 筆: {event['asks'][-1]}")

                    # 情況 B：訂單簿深度更新 (有人新掛單、撤單或成交導致數量改變)
                    elif event.get("price_changes"):
                        pass

                    # 情況 C：最佳買賣價變動 (做套利引擎最需要的即時訊號！)
                    elif event_type == "best_bid_ask":
                        print("\n [最佳買賣價更新]")
                        print(f"   - 買方最高出價 (Best Bid): {event.get('best_bid')}")
                        print(f"   - 賣方最低開價 (Best Ask): {event.get('best_ask')}")
                    
                    # 情況 D：其他事件 (例如 tick_size_change)
                    elif event_type:
                        # 為了畫面乾淨，這邊先不印出其他瑣碎事件
                        pass 

        except websockets.exceptions.ConnectionClosed:
            print("\n WebSocket 連線已斷開 (可能因為網路不穩或伺服器重置)")
        except Exception as e:
            print(f"\n 發生錯誤: {e}")

if __name__ == "__main__":
    # 執行非同步事件迴圈
    try:
        asyncio.run(connect_polymarket_ws())
    except KeyboardInterrupt:
        print("\n 已手動停止程式")