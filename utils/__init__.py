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
