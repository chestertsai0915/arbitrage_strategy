import requests

def check_geoblock():
    url = "https://polymarket.com/api/geoblock"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status() # 檢查是否有 HTTP 錯誤
        
        # Geoblock API 通常回傳字串或簡單的 JSON
        print("=== Geoblock 測試結果 ===")
        print(f"狀態碼: {response.status_code}")
        print(f"回傳內容: {response.text}")
        
    except requests.exceptions.RequestException as e:
        print(f"請求發生錯誤: {e}")

check_geoblock()