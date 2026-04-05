import asyncio
import itertools

from sx_connector import SXBetConnector
from poly_connector import PolyConnector
from limitless_connector import LimitlessConnector  
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

# 升級記憶體結構：同時存放 Yes (outcome_1) 與 No (outcome_2) 的報價與深度
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
        elif platform == "LIMITLESS": #  讓大腦認得 Limitless 傳來的 slug
            for outcome, m_hash in match_data.get("LIMITLESS", {}).items():
                if m_hash == incoming_hash:
                    target_match, target_outcome = match_id, outcome
                    break
                    
    if not target_match or not target_outcome:
        return

    # 將 Yes(買) 和 No(反買) 同時寫入記憶體
    price_memory[target_match][target_outcome][platform] = {
        "yes_price": bbo_data.get("buy_outcome_1_cost"), 
        "yes_size": bbo_data.get("buy_outcome_1_size", 0),
        "no_price": bbo_data.get("buy_outcome_2_cost"), 
        "no_size": bbo_data.get("buy_outcome_2_size", 0)
    }
    
    # 每次價格跳動，同時檢查兩種策略！
    check_all_arbitrage(target_match)

def check_all_arbitrage(match_id):
    match_data = MATCH_MAPPING[match_id]
    outcomes = match_data["outcomes"]
    
    best_2way_cost = float('inf')
    best_3way_cost = float('inf')
    
    
    #  策略一：2-Way 雙邊對沖 (Team vs Not Team)
    for outcome in outcomes:
        platforms_available = list(price_memory[match_id][outcome].keys())
        
        # 產生該選項在不同平台的交叉組合 (例如: SX 買 Yes, Poly 買 No, 或 Limitless 買 No)
        for plat_A, plat_B in itertools.product(platforms_available, repeat=2):
            if plat_A == plat_B: continue # 避免同平台對沖
            
            pA_data = price_memory[match_id][outcome][plat_A]
            pB_data = price_memory[match_id][outcome][plat_B]
            
            yes_price = pA_data.get("yes_price")
            no_price = pB_data.get("no_price")
            
            if yes_price and no_price:
                cost_2way = yes_price + no_price
                if cost_2way < best_2way_cost:
                    best_2way_cost = cost_2way
                
                #  觸發 2-Way 套利
                if cost_2way < 1.0:
                    roi = ((1.0 / cost_2way) - 1.0) * 100
                    max_size = min(pA_data.get("yes_size", 0), pB_data.get("no_size", 0))
                    profit = max_size * (roi / 100)
                    
                    print(f"\n [2-Way 套利機會出現!] 賽事: {match_data['title']} | 選項: {outcome} ")
                    print(f" 總成本: {cost_2way:.4f} | ROI: +{roi:.2f}% | Max Size: {max_size:.2f} U | 淨利: {profit:.2f} U")
                    print(f"    在 {plat_A:<9} 買入 [Yes] | 成本: {yes_price:.4f}")
                    print(f"    在 {plat_B:<9} 買入 [No ] | 成本: {no_price:.4f}")
                    print("-" * 50)


    #  策略二：3-Way 傳統套利 (主 vs 客 vs 和)
   
    prices_by_outcome = [price_memory[match_id][outcome] for outcome in outcomes]
    if all(platform_prices for platform_prices in prices_by_outcome):
        platforms_available = [list(p.keys()) for p in prices_by_outcome]
        
        # itertools 會自動算出 3 個平台所有的交叉組合 (3x3x3 = 27 種配對)
        for combo in itertools.product(*platforms_available):
            cost_3way = 0.0
            sizes = []
            valid = True
            
            for i, outcome in enumerate(outcomes):
                plat = combo[i]
                yes_price = price_memory[match_id][outcome][plat].get("yes_price")
                yes_size = price_memory[match_id][outcome][plat].get("yes_size", 0)
                
                if not yes_price:
                    valid = False
                    break
                cost_3way += yes_price
                sizes.append(yes_size)
                
            if valid:
                if cost_3way < best_3way_cost:
                    best_3way_cost = cost_3way
                    
                #  觸發 3-Way 套利
                if cost_3way < 1.0:
                    roi = ((1.0 / cost_3way) - 1.0) * 100
                    max_size = min(sizes)
                    profit = max_size * (roi / 100)
                    
                    print(f"\n [3-Way 套利機會出現!] 賽事: {match_data['title']} ")
                    print(f" 總成本: {cost_3way:.4f} | ROI: +{roi:.2f}% | Max Size: {max_size:.2f} U | 淨利: {profit:.2f} U")
                    for i, outcome in enumerate(outcomes):
                        plat = combo[i]
                        p = price_memory[match_id][outcome][plat].get("yes_price")
                        print(f"    在 {plat:<9} 買入 [{outcome:<15}] (Yes) | 成本: {p:.4f}")
                    print("-" * 50)

  
    #  更新動態監控儀表板
   
    if best_2way_cost >= 1.0 and best_3way_cost >= 1.0:
        c2 = best_2way_cost if best_2way_cost != float('inf') else 0.0
        c3 = best_3way_cost if best_3way_cost != float('inf') else 0.0
        print(f"\r [監控中] {match_data['title']} | 最佳 2-Way 成本: {c2:.4f} | 最佳 3-Way 成本: {c3:.4f}     ", end="", flush=True)

async def main():
    print(" 啟動三大平台 (SX/POLY/LIMITLESS) 雙核心套利引擎...")
    tasks = []
    
    for match_id, match_data in MATCH_MAPPING.items():
        # --- SX Bet ---
        if "SX_BET" in match_data:
            for outcome, m_hash in match_data["SX_BET"].items():
                tasks.append(SXBetConnector(SX_API_KEY, m_hash, arbitrage_callback).start())
            
        # --- Polymarket ---
        if "POLY" in match_data:
            for outcome, token_id in match_data["POLY"].items():
                tasks.append(PolyConnector(token_id, arbitrage_callback).start())
                
        # --- Limitless ---  新增啟動邏輯
        if "LIMITLESS" in match_data:
            for outcome, slug in match_data["LIMITLESS"].items():
                tasks.append(LimitlessConnector(slug, arbitrage_callback).start())
            
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n 已手動停止程式")