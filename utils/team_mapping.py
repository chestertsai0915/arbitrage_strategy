import re
import unicodedata

class TeamNameMapper:
    """處理球隊名稱標準化：一律轉小寫並清理字串"""
    
    def get_standard_name(self, raw_name: str) -> str:
        if not raw_name:
            return "unknown"
            
        # 1. 轉小寫並去除前後空白
        clean = raw_name.lower().strip()
        
        # 2. 去除盤口數字後綴 (例如 +1.5, -0.5)
        clean = re.sub(r'\s*[+\-]\d+(\.\d+)?\s*$', '', clean)
        
        # 3. 消除重音符號 (例如將 atlético 轉為 atletico)
        clean = ''.join(c for c in unicodedata.normalize('NFD', clean)
                       if unicodedata.category(c) != 'Mn')
        
        # 4. 剔除足球常見的「噪音字眼」
        # 加入 \b 確保只替換獨立單字，不會誤殺 (例如不會把 defensor 裡的 de 刪掉)
        noise_words = [r'\bclub\b', r'\bde\b', r'\bfc\b', r'\bcf\b', r'\bafc\b', r'\bunited\b', r'\bcity\b']
        for noise in noise_words:
            clean = re.sub(noise, '', clean)
        
        # 5. 去除多餘的空白，並將空格或連字號轉為底線 (保持你原本的格式)
        clean = clean.strip()
        clean = re.sub(r'[\s\-]+', '_', clean)
        
        return clean if clean else "unknown"