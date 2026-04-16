import os
import json
import glob
from collections import defaultdict

def count_unreasonable_quotes(directory_path="arbitrage_opportunities2"):
    """
    掃描資料夾內的 JSON 紀錄，統計各平台出現不合理報價的總次數：
    1. 單一選項異常 (Yes+No < 1)
    2. 同一平台組合異常 (所有選項的 Yes 加總 < 1)
    """
    json_files = glob.glob(os.path.join(directory_path, "*.json"))
    
    if not json_files:
        print(f"找不到任何 JSON 檔案於資料夾: {directory_path}")
        return

    # 分別記錄兩種異常的出錯次數
    anomaly_2way_counts = defaultdict(int)       # 紀錄 Yes+No < 1
    anomaly_multiway_counts = defaultdict(int)   # 紀錄 所有選項Yes總和 < 1
    
    total_files_checked = 0
    files_with_anomalies = 0

    for file_path in json_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 條件 1：檢查是否有 roi_percent 且大於 3
            roi = data.get("roi_percent")
            if roi is None or roi <= 3:
                continue
                
            total_files_checked += 1
            price_memory = data.get("price_memory", {})
            file_has_anomaly = False
            
            # 抓取這場比賽總共有幾個結果選項 (例如: 3代表有 Home, Away, Draw)
            num_outcomes = len(price_memory.keys())
            
            # 用來收集每個平台的各個選項的 yes_price
            # 格式: {"LIMITLESS": {"Home": 0.43, "Away": 0.33, "Draw": 0.25}}
            platform_yes_prices = defaultdict(dict)

            # --- 遍歷掃描 ---
            for outcome, platforms in price_memory.items():
                for platform_name, prices in platforms.items():
                    yes_price = prices.get("yes_price")
                    no_price = prices.get("no_price")
                    
                    # 順手記錄 yes_price 給稍後的「組合審查」使用
                    if yes_price is not None:
                        platform_yes_prices[platform_name][outcome] = yes_price
                    
                    # [審查一] 單一選項的 Yes + No 檢查
                    if yes_price is not None and no_price is not None:
                        total_cost = yes_price + no_price
                        if total_cost < 1.0:
                            anomaly_2way_counts[platform_name] += 1
                            file_has_anomaly = True
            
            # [審查二] 同一平台所有選項 (如主、客、和) 的 Yes 總和檢查
            if num_outcomes > 1:
                for platform_name, outcome_prices in platform_yes_prices.items():
                    # 必須確認該平台有提供「全部選項」的報價，才計算總和
                    if len(outcome_prices) == num_outcomes:
                        total_multi_cost = sum(outcome_prices.values())
                        
                        # 篩查不合理的組合報價 (小於 1.0)
                        if total_multi_cost < 1.0:
                            anomaly_multiway_counts[platform_name] += 1
                            file_has_anomaly = True

            if file_has_anomaly:
                files_with_anomalies += 1
                
        except json.JSONDecodeError:
            pass  # 忽略解析錯誤的檔案
        except Exception:
            pass

    # ===== 印出最終統計報告 =====
    print("=" * 65)
    print(" 📊 平台異常報價與幽靈訂單 統計總表")
    print("=" * 65)
    print(f" 掃描檔案數 (ROI > 3%) : {total_files_checked} 份")
    print(f" 包含異常報價的檔案數  : {files_with_anomalies} 份\n")
    
    print(" 🔍 [異常類型一] 單一選項對沖異常 (Yes + No < 1)")
    if not anomaly_2way_counts:
        print(" ✅ 皆正常")
    else:
        for p, c in sorted(anomaly_2way_counts.items(), key=lambda x: x[1], reverse=True):
            print(f" 🚩 {p:<12} : {c} 次")
            
    print("\n 🔍 [異常類型二] 單一平台組合套利異常 (全部選項 Yes 總和 < 1)")
    if not anomaly_multiway_counts:
        print(" ✅ 皆正常")
    else:
        for p, c in sorted(anomaly_multiway_counts.items(), key=lambda x: x[1], reverse=True):
            print(f" 🚩 {p:<12} : {c} 次")
    print("=" * 65)

if __name__ == "__main__":
    # 將這裡的路徑替換成你實際存放 JSON 的資料夾名稱
    count_unreasonable_quotes("arbitrage_opportunities2")