import asyncio
import httpx
from ably import AblyRealtime

SX_BET_API_KEY = "c75330b7-7ad6-460f-9e2d-cf7a26d9b917"
USDC_TOKEN = "0x6629Ce1Cf35Cc1329ebB4F63202F3f197b3F050B" 
marketHash="0x3cb0a7373c5b605f9b878c2ecf2240ee2dc5bebc4e34d450db76ef782d3d2324"
async def get_sx_token(token_params):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.sx.bet/user/token",
            headers={"X-Api-Key": SX_BET_API_KEY},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()

# 🌟 極簡回呼函數：不做任何處理，直接把原始 data 印出來！
def on_raw_message(message):
    print(f"\n📨 [收到原始資料! 來源頻道: {message.name}]")
    print(message.data)
    print("-" * 50)

async def main():
    print("🚀 啟動 SX Bet (Ably) 極簡暴力印出測試...")

    try:
        realtime = AblyRealtime(auth_callback=get_sx_token)
        await realtime.connection.once_async('connected')
        print("🌐 已成功連上 Ably 伺服器！")

        # 🎯 測試你的假設：只傳入 Token，看看是否為全域訂單簿廣播
        channel_name = f"order_book_v2:{USDC_TOKEN}:{marketHash}"
        channel = realtime.channels.get(channel_name)
        await channel.subscribe(on_raw_message)
        
        print(f"📡 已訂閱頻道: {channel_name}")
        print("⏳ 什麼都不解析，坐等原始 JSON 噴出來...\n")

        while True:
            await asyncio.sleep(1)
            
    except Exception as e:
        print(f"❌ 發生錯誤: {e}")
    finally:
        if 'realtime' in locals():
            await realtime.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 已手動停止程式")