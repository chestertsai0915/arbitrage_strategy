import os
import json
import time
import asyncio
import aiohttp
from datetime import datetime

class PaperTrader:
    def __init__(self, initial_balance=2000000.0, max_bet_per_trade=400.0):
        self.state_file = "paper_trading_state.json"
        self.intercept_dir = "intercepted_logs" # 🌟 新增：攔截日誌專用資料夾
        self.initial_balance = initial_balance
        self.max_bet_per_trade = max_bet_per_trade 
        
        # 確保攔截日誌資料夾存在
        os.makedirs(self.intercept_dir, exist_ok=True)
        
        # 帳戶狀態
        self.balance = initial_balance
        self.locked_funds = 0.0
        self.active_trades = {}
        self.trade_history = []
        
        self._load_state()

    def _load_state(self):
        """從本地讀取虛擬帳戶狀態，確保重啟程式資金不會重置"""
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.balance = data.get("balance", self.initial_balance)
                    self.locked_funds = data.get("locked_funds", 0.0)
                    self.active_trades = data.get("active_trades", {})
                    self.trade_history = data.get("trade_history", [])
                print(f"💼 [模擬交易] 載入帳戶狀態成功 | 可用餘額: {self.balance:.2f} U | 鎖倉: {self.locked_funds:.2f} U")
            except Exception as e:
                print(f"⚠️ [模擬交易] 讀取狀態失敗: {e}，建立新帳戶。")

    def _save_state(self):
        """儲存帳戶狀態到本地"""
        data = {
            "balance": self.balance,
            "locked_funds": self.locked_funds,
            "active_trades": self.active_trades,
            "trade_history": self.trade_history,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(self.state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)

    def _save_intercepted_signal(self, arb_data, reason, real_roi=None):
        """🌟 新增：將被攔截的假訊號存檔，供後續復盤"""
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:19] # 精確到毫秒避免檔名重複
        match_title = arb_data.get("match_title", "Unknown").replace(" ", "_").replace("/", "_")
        
        log_data = {
            "intercept_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "reason": reason,
            "original_estimated_roi": arb_data.get("roi_percent"),
            "real_roi_after_rest": real_roi,
            "arb_data": arb_data
        }
        
        if not os.path.exists(self.intercept_dir):
            # 確保目錄本身存在 (避免 FileNotFoundError)
            os.makedirs(self.intercept_dir, exist_ok=True)

        file_path = os.path.join(self.intercept_dir, f"intercept_{match_title}_{timestamp_str}.json")
        
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(log_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f" ⚠️ [日誌錯誤] 無法儲存攔截紀錄: {e}")

    def execute_virtual_trade(self, arb_data):
        """接收套利引擎的訊號，發起非同步背景任務去進行 REST API 雙重驗證"""
        arb_key = arb_data.get("arb_key")
        current_roi = arb_data.get("roi_percent", 0)
        match_title = arb_data.get("match_title")
        
        # 1. 檢查是否已經在這個套利機會上車了
        if arb_key in self.active_trades:
            old_trade = self.active_trades[arb_key]
            old_roi = old_trade.get("roi_percent", 0)
            
            # 🌟 升級邏輯：如果新的 ROI 比舊的高出 0.5% (門檻可自訂)，就允許「加碼」！
            if current_roi >= old_roi + 0.5:
                print(f" 📈 [觸發加碼] {match_title} ROI 顯著提升 ({old_roi:.2f}% ➡️ {current_roi:.2f}%)，準備驗證加碼！")
                
                # 給這張單一個新的專屬 Key (加上時間戳)，避免覆蓋掉原本的舊訂單紀錄
                arb_key = f"{arb_key}_addon_{int(time.time())}"
                arb_data["arb_key"] = arb_key # 更新封包裡的 key
            else:
                # ROI 沒有顯著提升，靜默跳過
                return False 

        max_size = arb_data.get("max_size", 0)
        invest_amount = min(self.balance, self.max_bet_per_trade, max_size)

        if invest_amount < 10.0:
            print(f" ⚠️ [模擬攔截] 資金不足或深度太淺 ({invest_amount:.2f} U)，放棄驗證。")
            
            return False

        # 丟給背景去驗證並執行，不阻塞主程式
        asyncio.create_task(self._async_verify_and_execute(arb_data, invest_amount))
        return True

        

    async def _async_verify_and_execute(self, arb_data, invest_amount):
        """透過 REST API 重新拉取快照，確認報價是否真實存在"""
        arb_key = arb_data.get("arb_key")
        match_title = arb_data.get("match_title")
        original_roi = arb_data.get("roi_percent")
        
        print(f" 🔍 [雙重驗證中] 正在透過 REST API 檢查 {match_title} 的真實報價...")

        # 呼叫驗證模組
        is_valid, real_roi = await self.verify_prices_via_rest(arb_data)

        if not is_valid:
            reason = f"REST API 雙重驗證失敗 (原 Websocket 預估 ROI: {original_roi:.2f}%, 真實 ROI: {real_roi:.2f}%)"
            print(f" 🚫 [攔截假訊號] {match_title} 報價已消失或為幽靈殘影！(原預估 ROI: {original_roi:.2f}%)")
            self._save_intercepted_signal(arb_data, reason, real_roi)
            return

        # ==========================================
        # 驗證通過，正式執行扣款與建立訂單
        # ==========================================
        if self.balance < invest_amount:
            print(" ⚠️ [餘額不足] 驗證通過，但可用資金已被其他訂單佔用。")
            self._save_intercepted_signal(arb_data, "驗證通過，但執行當下帳戶餘額不足", real_roi)
            return

        self.balance -= invest_amount
        self.locked_funds += invest_amount
        
        expected_profit = invest_amount * (real_roi / 100)
        expected_revenue = invest_amount + expected_profit

        trade_id = f"TRADE_{int(time.time() * 1000)}"
        trade_record = {
            "trade_id": trade_id,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "arb_key": arb_key,
            "match_title": match_title,
            "strategy": arb_data.get("strategy"),
            "invested_amount": invest_amount,
            "expected_revenue": expected_revenue,
            "expected_profit": expected_profit,
            "roi_percent": real_roi, # 使用驗證後的真實 ROI
            "legs": arb_data.get("legs", {}),
            "status": "OPEN"
        }

        self.active_trades[arb_key] = trade_record
        self._save_state()

        # 印出精美的下單報告
        print("\n" + "="*60)
        print(f" ✅ [驗證通過 & 下單成功] 訂單號: {trade_id}")
        print(f" 🏆 賽事: {match_title}")
        print(f" 💰 投入本金: {invest_amount:.2f} U | 預期淨利: +{expected_profit:.2f} U (真實 ROI: {real_roi:.2f}%)")
        print(f" 💼 帳戶剩餘可用: {self.balance:.2f} U | 鎖倉: {self.locked_funds:.2f} U")
        print("="*60 + "\n")


    async def verify_prices_via_rest(self, arb_data):
        """
        透過 aiohttp 直接呼叫三大平台的 REST API 進行雙重驗證。
        不再依賴外部模組，獨立運作。
        """
        legs = arb_data.get("legs", {})
        total_real_cost = 0.0
        
        async with aiohttp.ClientSession() as session:
            for outcome, leg_info in legs.items():
                platform = leg_info.get("platform")
                market_hash = leg_info.get("market_hash")
                side = leg_info.get("side", "yes") # "yes" 或是 "no"
                
                real_price = None
                real_size = 0.0

                if not market_hash:
                    print(f" ⚠️ [驗證失敗] 缺少 {platform} 的 market_hash")
                    leg_info["real_price_after_rest"] = "Missing Hash"
                    return False, 0.0

                try:
                    # ==========================================
                    # 1. 驗證 Polymarket 報價
                    # ==========================================
                    if platform == "POLY":
                        url = "https://clob.polymarket.com/book"
                        params = {"token_id": market_hash}
                        async with session.get(url, params=params, timeout=5) as res:
                            if res.status == 200:
                                data = await res.json()
                                
                                if side == "yes":
                                    asks = data.get("asks", [])
                                    if asks:
                                        best_ask = min(asks, key=lambda x: float(x["price"]))
                                        real_price = float(best_ask["price"])
                                        real_size = float(best_ask["size"])
                                elif side == "no":
                                    bids = data.get("bids", [])
                                    if bids:
                                        best_bid = max(bids, key=lambda x: float(x["price"]))
                                        real_price = round(1.0 - float(best_bid["price"]), 6)
                                        real_size = float(best_bid["size"])

                    # ==========================================
                    # 2. 驗證 Limitless 報價
                    # ==========================================
                    elif platform == "LIMITLESS":
                        url = f"https://api.limitless.exchange/markets/{market_hash}/orderbook"
                        async with session.get(url, timeout=5) as res:
                            if res.status == 200:
                                data = await res.json()
                                
                                def get_lim_fee(p: float) -> float:
                                    if p <= 0.5:
                                        return 0.03
                                    progress = (p - 0.5) / 0.5
                                    return 0.03 - (0.0297 * progress)

                                if side == "yes":
                                    asks = data.get("asks", [])
                                    if asks:
                                        # 直接使用字典鍵值，乾淨俐落！
                                        best_ask = min(asks, key=lambda x: float(x["price"]))
                                        raw_price = float(best_ask["price"])
                                        real_price = raw_price * (1 + get_lim_fee(raw_price))
                                        real_size = float(best_ask["size"]) / 1000000.0
                                        
                                elif side == "no":
                                    bids = data.get("bids", [])
                                    if bids:
                                        # 直接使用字典鍵值，乾淨俐落！
                                        best_bid = max(bids, key=lambda x: float(x["price"]))
                                        raw_price = round(1.0 - float(best_bid["price"]), 6)
                                        real_price = raw_price * (1 + get_lim_fee(raw_price))
                                        real_size = float(best_bid["size"]) / 1000000.0
                    # ==========================================
                    # 3. 驗證 SX Bet 報價
                    # ==========================================
                    elif platform == "SX_BET":
                        url = "https://api.sx.bet/orders"
                        params = {"marketHashes": market_hash, "status": "ACTIVE"} 
                        async with session.get(url, params=params, timeout=5) as res:
                            if res.status == 200:
                                data = await res.json()
                                orders = data.get("data", [])
                                best_cost = float('inf')
                                best_size = 0.0
                                
                                for order in orders:
                                    total_bet = float(order.get("totalBetSize", 0))
                                    filled = float(order.get("fillAmount", 0))
                                    remaining_raw = total_bet - filled
                                    if remaining_raw <= 0: continue
                                    
                                    maker_prob = float(order.get("percentageOdds", 0)) / (10 ** 20)
                                    if maker_prob <= 0 or maker_prob >= 1: continue
                                    taker_prob = 1.0 - maker_prob
                                    
                                    taker_size = (remaining_raw / 10**6) * (taker_prob / maker_prob)
                                    is_maker_o1 = order.get("isMakerBettingOutcomeOne", False)
                                    
                                    if side == "yes" and not is_maker_o1:
                                        if taker_prob < best_cost: 
                                            best_cost = taker_prob
                                            best_size = taker_size
                                    elif side == "no" and is_maker_o1:
                                        if taker_prob < best_cost: 
                                            best_cost = taker_prob
                                            best_size = taker_size

                                if best_cost != float('inf'):
                                    real_price = best_cost
                                    real_size = best_size

                except asyncio.TimeoutError:
                    print(f" ⚠️ {platform} REST API 請求超時")
                    leg_info["error"] = "Timeout"
                    return False, 0.0
                except Exception as e:
                    print(f" ⚠️ {platform} REST API 請求錯誤: {e}")
                    leg_info["error"] = str(e)
                    return False, 0.0

                # ==========================================================
                # 🌟 關鍵新增：把 REST API 查到的真實數據寫回 leg_info 中！
                # 這樣 `_save_intercepted_signal` 存 JSON 時就會自動帶上這些資料
                # ==========================================================
                leg_info["real_price_after_rest"] = real_price
                leg_info["real_size_after_rest"] = real_size

                # --- 核心防線：檢查價格與深度 ---
                if real_price is None:
                    return False, 0.0 # 報價不存在
                
                if real_size < 10.0:
                    return False, 0.0 # 雖然報價還在，但剩下的肉太少(深度不足)，不值得下單
                    
                total_real_cost += real_price

        # --- 計算真實的套利結果 ---
        if total_real_cost >= 1.0:
            print(f" ⚠️ [驗證失敗] 扣除滑價後套利空間已消失 (總成本: {total_real_cost:.4f})")
            return False, 0.0 # 滑價後套利空間已消失
            
        real_roi = ((1.0 / total_real_cost) - 1.0) * 100
        
        # 扣除滑價後，如果真實利潤小於 0.2%，直接放棄
        if real_roi < 0.2:
            print(f" ⚠️ [驗證失敗] 扣除滑價後套利空間不足 (ROI: {real_roi:.2f}%)")
            return False, real_roi 
            
        print(f" ✅ [驗證成功] 扣除滑價後套利空間存在 (ROI: {real_roi:.2f}%)")
        return True, real_roi