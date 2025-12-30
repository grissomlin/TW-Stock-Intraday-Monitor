# utils/__init__.py
from .utils import (
    init_supabase,
    init_gemini,
    init_connections,
    fetch_today_data,
    get_wantgoo_url,
    get_goodinfo_url,
    get_cnyes_url,
    get_stock_links,
    call_ai_safely
)

# 注意：common.py 是一個完整的 Streamlit 頁面，不應該從中導入函數
# 它應該被直接運行或通過頁面路由訪問

def get_ai_prompt_template(prompt_name):
    """
    從 Streamlit secrets 中獲取 AI 提示詞模板
    
    Args:
        prompt_name: 提示詞名稱，如 'market_analysis', 'sector_analysis' 等
    
    Returns:
        提示詞模板字符串，如果找不到則返回 None
    """
    try:
        # 從 secrets 中讀取提示詞模板
        prompts = st.secrets.get("AI_PROMPT_TEMPLATES", {})
        return prompts.get(prompt_name)
    except Exception:
        return None
