import asyncio
import socketio

#  替換成你想測試的 Limitless 子盤口 Slug
TARGET_SLUG = "real-madrid-1774342805684" 

# 建立非同步的 Socket.IO 客戶端
# 官方要求明確指定 transports=['websocket']
sio = socketio.AsyncClient(logger=False, engineio_logger=False)

# === 註冊事件監聽器 (注意：Namespace 是 '/markets') ===

@sio.event(namespace='/markets')
async def connect():
    print(" [Limitless] 成功連線至 WebSocket 伺服器！")
    
    # 連線成功後，發送訂閱請求
    subscribe_payload = {
        "marketSlugs": [TARGET_SLUG]
    }
    
    # 透過 emit 發送訂閱事件
    await sio.emit('subscribe_market_prices', subscribe_payload, namespace='/markets')
    print(f" 已送出訂閱請求，監聽盤口: {TARGET_SLUG}...")

@sio.event(namespace='/markets')
async def disconnect():
    print(" [Limitless] 連線已斷開")

#  監聽官方文件提到的 'orderbookUpdate' 事件
@sio.on('orderbookUpdate', namespace='/markets')
async def on_orderbook_update(data):
    # 資料結構解析
    slug = data.get("marketSlug")
    timestamp = data.get("timestamp")
    ob = data.get("orderbook", {})
    
    bids = ob.get("bids", [])
    asks = ob.get("asks", [])
    
    print(f"\n [更新推播] 盤口: {slug} | 時間: {timestamp}")
    
    if bids:
        best_bid = bids[0]
        print(f"    最高買價 (Best Bid): {best_bid['price']} | 數量: {best_bid['size']}")
    else:
        print("    最高買價 (Best Bid): 尚無訂單")
        
    if asks:
        best_ask = asks[0]
        print(f"    最低賣價 (Best Ask): {best_ask['price']} | 數量: {best_ask['size']}")
    else:
        print("    最低賣價 (Best Ask): 尚無訂單")

# === 主連線邏輯 ===
async def main():
    print(" 啟動 Limitless WebSocket 測試連線...")
    
    try:
        # 連線至官方指定的 URL 與 Namespace
        await sio.connect(
            'wss://ws.limitless.exchange', 
            namespaces=['/markets'],
            transports=['websocket']
        )
        # 保持程式運行直到斷開連線
        await sio.wait()
        
    except Exception as e:
        print(f" 連線發生錯誤: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n 已手動停止程式")