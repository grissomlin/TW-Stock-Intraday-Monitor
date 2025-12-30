# -*- coding: utf-8 -*-
import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime, timedelta
import google.generativeai as genai
import urllib.parse

# 設定頁面配置
st.set_page_config(page_title="個股AI分析 | Alpha-Refinery", layout="wide")

# 自訂CSS樣式
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #f0f2f6; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .ai-section { background-color: #fff3cd; padding: 15px; border-radius: 8px; border-left: 5px solid #ffc107; }
    .stock-card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px; margin: 8px 0; background: linear-gradient(135deg, #f5f7fa 0%, #e4edf5 100%); }
    .password-protected { border: 2px solid #ff6b6b; border-radius: 8px; padding: 15px; background-color: #fff5f5; }
    </style>
""", unsafe_allow_html=True)

# ========== 1. 初始化連線 ==========
@st.cache_resource
def init_supabase():
    try:
        return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
    except Exception as e:
        st.error(f"Supabase 連線失敗: {e}")
        return None

@st.cache_resource
def init_gemini():
    """自動偵測可用模型，解決 404 與 429 錯誤處理"""
    try:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
        available_models = [m.name for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
        candidates = ['models/gemini-1.5-flash', 'gemini-1.5-flash', 'models/gemini-1.5-pro']
        target_model = next((c for c in candidates if c in available_models), available_models[0] if available_models else 'gemini-pro')
        return genai.GenerativeModel(target_model)
    except Exception as e:
        st.error(f"AI 初始化失敗: {e}")
        return None

supabase = init_supabase()
gemini_model = init_gemini()
today = datetime.now().strftime("%Y-%m-%d")
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

# ========== 2. 密碼保護機制 ==========
if 'gemini_authorized' not in st.session_state:
    st.session_state.gemini_authorized = False

# ========== 3. 輔助函式 ==========
def get_wantgoo_url(symbol):
    code = str(symbol).split('.')[0]
    return f"https://www.wantgoo.com/stock/{code}/technical-chart"

def get_goodinfo_url(symbol):
    code = str(symbol).split('.')[0]
    return f"https://goodinfo.tw/tw/StockBZPerformance.asp?STOCK_ID={code}"

def get_cnyes_url(symbol):
    code = str(symbol).split('.')[0]
    return f"https://www.cnyes.com/twstock/{code}/"

def call_ai_safely(prompt):
    if not gemini_model:
        st.error("AI 客戶端未啟動")
        return None

    try:
        with st.spinner("🤖 AI 正在深度思考中..."):
            res = gemini_model.generate_content(prompt)
            return res.text
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "ResourceExhausted" in err_msg:
            st.error("⚠️ AI 額度已耗盡。請稍候 1 分鐘再試，或複製 Prompt 手動貼至 ChatGPT。")
        else:
            st.error(f"❌ AI 呼叫失敗: {e}")
        return None

@st.cache_data(ttl=600)
def fetch_today_data(table_name, date_str):
    try:
        res = supabase.table(table_name).select("*").eq("analysis_date", date_str).execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"載入數據失敗: {e}")
        return pd.DataFrame()

# ========== 4. 數據載入 ==========
if supabase:
    df_limit_ups = fetch_today_data("individual_stock_analysis", today)
else:
    df_limit_ups = pd.DataFrame()

# ========== 5. 頁面標題 ==========
st.title("📈 個股AI分析")
st.caption(f"📅 分析日期：{today} | 🕐 最後更新：{datetime.now().strftime('%H:%M:%S')}")

if not supabase:
    st.error("❌ 資料庫連線失敗，請檢查 Supabase 設定")
    st.stop()

# ========== 6. 主介面呈現 ==========
if not df_limit_ups.empty:
    # 股票選擇器
    st.header("🔍 選擇分析標的")

    # 建立股票選項
    stock_options = []
    for _, row in df_limit_ups.iterrows():
        display_text = f"{row['stock_name']} ({row['symbol']}) - {row['sector']}"
        # 如果有連板天數，顯示
        if 'consecutive_days' in row and row['consecutive_days'] > 1:
            display_text += f" - {row['consecutive_days']}連板"
        stock_options.append((display_text, row))

    # 下拉選單
    selected_display = st.selectbox(
        "選擇股票：",
        options=[so[0] for so in stock_options],
        index=0,
        help="選擇您要分析的漲停板股票"
    )

    # 找到選擇的股票
    selected_stock = None
    for display, stock in stock_options:
        if display == selected_display:
            selected_stock = stock
            break

    if selected_stock is not None:
        st.markdown('<div class="stock-card">', unsafe_allow_html=True)
        st.subheader(f"{selected_stock['stock_name']} ({selected_stock['symbol']})")

        # 顯示股票資訊
        col_info1, col_info2, col_info3, col_info4 = st.columns(4)
        with col_info1:
            st.metric("產業別", selected_stock['sector'])
        with col_info2:
            return_rate = selected_stock.get('return_rate', 0)
            st.metric("今日漲幅", f"{return_rate:.2%}" if return_rate else "N/A")
        with col_info3:
            price = selected_stock.get('price', 0)
            st.metric("當前價格", f"{price:.2f}" if price else "N/A")
        with col_info4:
            consecutive_days = selected_stock.get('consecutive_days', 1)
            st.metric("連續漲停", f"{consecutive_days}天")

        # 顯示連結
        st.write("🔗 相關連結：")
        link_cols = st.columns(4)
        with link_cols[0]:
            st.link_button("玩股網K線", get_wantgoo_url(selected_stock['symbol']))
        with link_cols[1]:
            st.link_button("Goodinfo財報", get_goodinfo_url(selected_stock['symbol']))
        with link_cols[2]:
            st.link_button("鉅亨網新聞", get_cnyes_url(selected_stock['symbol']))
        with link_cols[3]:
            code = selected_stock['symbol'].split('.')[0]
            st.link_button("Yahoo股市", f"https://tw.stock.yahoo.com/quote/{code}.TW")

        st.markdown('</div>', unsafe_allow_html=True)

        # AI 分析區域
        st.divider()
        st.header("🤖 AI深度分析")

        # 密碼保護
        if not st.session_state.gemini_authorized:
            st.markdown('<div class="password-protected">', unsafe_allow_html=True)
            st.warning("🔒 AI分析需要授權解鎖")

            auth_col1, auth_col2 = st.columns([3, 1])
            with auth_col1:
                password_input = st.text_input("授權密碼：", type="password", key="stock_analysis_pw")
            with auth_col2:
                if st.button("解鎖 AI", use_container_width=True):
                    if password_input == st.secrets.get("AI_ASK_PASSWORD", "default_password"):
                        st.session_state.gemini_authorized = True
                        st.success("✅ 授權成功！")
                        st.rerun()
                    else:
                        st.error("❌ 密碼錯誤")
            st.markdown('</div>', unsafe_allow_html=True)
        else:
            st.success("✅ Gemini API 已授權")

            # 創建提示詞
            prompt = f"""
請以台灣股市專業分析師的身份，分析以下漲停板股票：

## 股票基本資訊
- 股票名稱：{selected_stock['stock_name']}
- 股票代碼：{selected_stock['symbol']}
- 所屬產業：{selected_stock['sector']}
- 當前價格：${selected_stock.get('price', 'N/A')}
- 今日漲幅：{selected_stock.get('return_rate', 0):.2%}
- 連續漲停天數：{selected_stock.get('consecutive_days', 1)}天

## 請分析以下面向：

### 1. 技術面分析
- 漲停板強度（開板次數、封單量）
- 量價關係是否健康
- K線型態與位置
- 壓力與支撐位分析

### 2. 基本面考量
- 所屬產業前景
- 近期公司動態（如有）
- 估值合理性

### 3. 市場心理分析
- 散戶與主力動向
- 市場關注度
- 後續追價意願評估

### 4. 風險評估
- 短期風險（過熱、獲利了結）
- 中期風險（產業循環、政策）
- 流動性風險

### 5. 操作建議（請分不同風險偏好）
- 保守型投資者：
- 積極型投資者：
- 短線交易者：

### 6. 後續觀察重點
- 明日開盤表現
- 關鍵價位
- 相關指標監控

請以條列式重點摘要開始，然後詳細分析。
分析請務實客觀，避免過度樂觀。
            """

            # 顯示提示詞
            with st.expander("📋 查看完整分析提示詞", expanded=False):
                st.code(prompt, language="text", height=300)

            # 四個按鈕
            col_a1, col_a2, col_a3, col_a4 = st.columns(4)

            with col_a1:
                encoded_prompt = urllib.parse.quote(prompt)
                st.link_button("🔥 ChatGPT 分析", f"https://chatgpt.com/?q={encoded_prompt}", use_container_width=True)

            with col_a2:
                st.link_button("🔍 DeepSeek 分析", "https://chat.deepseek.com/", use_container_width=True)

            with col_a3:
                st.link_button("📘 Claude 分析", "https://claude.ai/", use_container_width=True)

            with col_a4:
                if st.button("🤖 Gemini 分析", use_container_width=True, type="primary"):
                    with st.spinner("Gemini正在分析中..."):
                        ai_response = call_ai_safely(prompt)
                        if ai_response:
                            st.session_state.gemini_stock_report = ai_response
                            st.rerun()

            # 顯示AI回應
            if 'gemini_stock_report' in st.session_state:
                with st.expander("🤖 Gemini 個股分析報告", expanded=True):
                    ai_response = st.session_state.gemini_stock_report
                    st.markdown(
                        f"""
                        <div style="
                            background-color: #f8f9fa !important;
                            padding: 30px !important;
                            border-radius: 15px !important;
                            border-left: 8px solid #28a745 !important;
                            box-shadow: 0 6px 20px rgba(0,0,0,0.12) !important;
                            line-height: 2 !important;
                            font-size: 17px !important;
                            white-space: pre-wrap !important;
                            word-wrap: break-word !important;
                            max-width: 100% !important;
                            width: 100% !important;
                            box-sizing: border-box !important;
                            margin: 10px 0 !important;
                        ">
                        {ai_response.replace('\n', '<br>')}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )
                    report_text = f"# {selected_stock['stock_name']} AI分析報告\n\n日期：{today}\n\n{ai_response}"
                    st.download_button(
                        label="📥 下載分析報告 (.md)",
                        data=report_text.encode('utf-8'),
                        file_name=f"{selected_stock['symbol']}_analysis_{today}.md",
                        mime="text/markdown",
                        use_container_width=True
                    )
                    if st.button("🗑️ 清除此報告", type="secondary"):
                        del st.session_state.gemini_stock_report
                        st.rerun()

            # 撤銷授權按鈕
            st.divider()
            if st.button("🔒 撤銷 AI 授權", type="secondary"):
                st.session_state.gemini_authorized = False
                st.rerun()

else:
    st.info("📊 目前尚未偵測到今日強勢標的。")

# 返回主頁面
st.divider()
if st.button("🏠 返回主頁面"):
    st.switch_page("app.py")
