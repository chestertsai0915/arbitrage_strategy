import asyncio
import itertools
from core.arbitrage_engine import check_all_arbitrage
# 把三個 Connector 從你的模組包裡面叫出來
from platforms_websocket_connnect import SXBetConnector, PolyConnector, LimitlessConnector
import os
from dotenv import load_dotenv

# 自動尋找並載入同目錄下的 .env 檔案
load_dotenv()

SX_API_KEY = os.environ.get("SX_bet")

#  這裡示範加入了 LIMITLESS 的假資料格式，實戰時會用轉換工具自動生成
MATCH_MAPPING = {
    "real_madrid_bayern_munich_2026-04-07": {
        "title": "Real Madrid vs FC Bayern Munich",
        "outcomes": ["Away", "Home", "Draw"],
        "SX_BET": {
            "Away": "0x0613cea110f26815d01f74e3c1c7333158c86eeb1ce06a897b6f283d4e1a8bd0",           
            "Home": "0x918f3bbf6879059d12f526da3aa0b11ed219b87026988e636c667ae65f7593fe",   
            "Draw": "0x4c286058ae42b644e3b34b6548168bbdddede7495cc574663e6b5bbe7045bbc9",
        },
        "POLY": {
            "Home": "19596230505334905503321726547378309060167788245319748292157531175114826139084",
            "Away": "99949662063403569895321097192043694236016212986254553767097648841549016857591",
            "Draw": "18822812066819800310928467826996124926526029026598480680953086271904576052367",
        },
        "LIMITLESS": {
            # 這裡放 Limitless 抓下來的 slug，先用假字串佔位示範
            "Home": "real-madrid-1774342805684",
            "Away": "bayern-munchen-1774342805691",
            "Draw": "draw-1774342805696",
        }
    }
}

price_memory = {}
for match_id, match_data in MATCH_MAPPING.items():
    price_memory[match_id] = {outcome: {} for outcome in match_data["outcomes"]}

def arbitrage_callback(bbo_data):
    platform = bbo_data["platform"]
    incoming_hash = str(bbo_data["market_hash"])
    
    target_match, target_outcome = None, None
    for match_id, match_data in MATCH_MAPPING.items():
        if platform == "SX_BET":
            for outcome, m_hash in match_data.get("SX_BET", {}).items():
                if m_hash == incoming_hash:
                    target_match, target_outcome = match_id, outcome
                    break
        elif platform == "POLY":
            for outcome, m_hash in match_data.get("POLY", {}).items():
                if m_hash == incoming_hash:
                    target_match, target_outcome = match_id, outcome
                    break
        elif platform == "LIMITLESS":
            for outcome, m_hash in match_data.get("LIMITLESS", {}).items():
                if m_hash == incoming_hash:
                    target_match, target_outcome = match_id, outcome
                    break
                    
    if not target_match or not target_outcome:
        return

    # 寫入記憶體
    price_memory[target_match][target_outcome][platform] = {
        "yes_price": bbo_data.get("buy_outcome_1_cost"), 
        "yes_size": bbo_data.get("buy_outcome_1_size", 0),
        "no_price": bbo_data.get("buy_outcome_2_cost"), 
        "no_size": bbo_data.get("buy_outcome_2_size", 0)
    }
    
    #  呼叫外部的套利引擎，並把記憶體跟設定檔傳給它
    check_all_arbitrage(target_match, MATCH_MAPPING, price_memory)

async def main():
    print(" 啟動三大平台 (SX/POLY/LIMITLESS) 雙核心套利引擎...")
    tasks = []
    
    for match_id, match_data in MATCH_MAPPING.items():
        if "SX_BET" in match_data:
            for outcome, m_hash in match_data["SX_BET"].items():
                tasks.append(SXBetConnector(SX_API_KEY, m_hash, arbitrage_callback).start())
            
        if "POLY" in match_data:
            for outcome, token_id in match_data["POLY"].items():
                tasks.append(PolyConnector(token_id, arbitrage_callback).start())
                
        if "LIMITLESS" in match_data:
            for outcome, slug in match_data["LIMITLESS"].items():
                tasks.append(LimitlessConnector(slug, arbitrage_callback).start())
            
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n 已手動停止程式")