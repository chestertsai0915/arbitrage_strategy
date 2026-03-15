import re

class TeamNameMapper:
    """處理球隊名稱標準化：一律轉小寫並清理字串"""
    
    def get_standard_name(self, raw_name: str) -> str:
        if not raw_name:
            return "unknown"
            
        clean = raw_name.lower().strip()
        clean = re.sub(r'\s*[+\-]\d+(\.\d+)?\s*$', '', clean)
        clean = re.sub(r'\b(fc|cf|afc|united)\b', '', clean).strip()
        clean = re.sub(r'[\s\-]+', '_', clean)
        
        return clean