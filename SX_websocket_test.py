import asyncio
import httpx
from ably import AblyRealtime

SX_BET_API_KEY = "c75330b7-7ad6-460f-9e2d-cf7a26d9b917"
USDC_TOKEN = "0x6629Ce1Cf35Cc1329ebB4F63202F3f197b3F050B" 

# 🎯 你的「目標賽事清單」 (未來可從 matcher.py 動態傳入多個 Hash)
TARGET_MARKETS = [
    "0x3cb0a7373c5b605f9b878c2ecf2240ee2dc5bebc4e34d450db76ef782d3d2324",
    # 你可以把剛剛螢幕上印出的那些熱門 Hash 貼幾個進來測試！
]

async def get_sx_token(token_params):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.sx.bet/user/token",
            headers={"X-Api-Key": SX_BET_API_KEY},
            timeout=10.0
        )
        response.raise_for_status()
        return response.json()

def on_best_odds_message(message):
    events = message.data
    if not isinstance(events, list):
        events = [events]
        
    for event in events:
        incoming_hash = event.get("marketHash")
        
        # 🛡️ 核心過濾器：如果這場比賽不是我們關心的，直接跳過！
        if incoming_hash not in TARGET_MARKETS:
            continue
            
        # 只有目標賽事，才會進到這裡進行解析與套利計算
        raw_percentage = int(event.get("percentageOdds", 0))
        maker_odds = raw_percentage / (10 ** 20)
        is_maker_outcome_one = event.get("isMakerBettingOutcomeOne")
        taker_cost = 1.0 - maker_odds
        
        target = "[選項 2]" if is_maker_outcome_one else "[選項 1]"
        print(f"\n [鎖定目標!] 盤口: {incoming_hash[:10]}...")
        print(f"    立即買入 {target} (Best Ask): 成本 {taker_cost:.4f}")

async def main():
    print("🚀 啟動 SX Bet (Ably) 狙擊過濾引擎...")

    try:
        realtime = AblyRealtime(auth_callback=get_sx_token)
        await realtime.connection.once_async('connected')
        print("🌐 已成功連上 Ably 伺服器！")

        # 訂閱全域最佳賠率廣播
        channel_name = f"best_odds:{USDC_TOKEN}"
        channel = realtime.channels.get(channel_name)
        
        await channel.subscribe(on_best_odds_message)
        print(f"📡 已訂閱廣播頻道: {channel_name}")
        print(f"🛡️ 啟動過濾器，僅監聽 {len(TARGET_MARKETS)} 場目標賽事...\n")

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