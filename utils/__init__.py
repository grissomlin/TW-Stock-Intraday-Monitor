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

# 也可以導入 common.py 中的函數
from .common import (
    # 這裡可以列出 common.py 中你想要暴露的函數
)
