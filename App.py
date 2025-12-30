# -*- coding: utf-8 -*-
import streamlit as st
from supabase import create_client
import pandas as pd
from datetime import datetime, timedelta
import google.generativeai as genai
import urllib.parse
import sys

# ========== 檢查必要套件 ==========
try:
    import plotly.express as px
    import plotly.graph_objects as go
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    st.warning("⚠️ Plotly 套件未安裝，圖表功能將被禁用。請運行：pip install plotly")

# 設定頁面配置
st.set_page_config(page_title="Alpha-Refinery 漲停戰情室 2.0", layout="wide")

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

@st.cache_data(ttl=3600)
def fetch_all_metadata():
    try:
        res = supabase.table("stock_metadata").select("symbol, name, sector").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        st.error(f"載入元數據失敗: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_stock_info():
    try:
        res = supabase.table("stock_info").select("symbol, name, sector").execute()
        return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception as e:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_recent_limit_ups(days=5):
    try:
        recent_dates = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        all_data = []
        for date in recent_dates:
            res = supabase.table("individual_stock_analysis").select("*").eq("analysis_date", date).execute()
            if res.data:
                all_data.extend(res.data)
        return pd.DataFrame(all_data) if all_data else pd.DataFrame()
    except Exception as e:
        st.error(f"載入近期數據失敗: {e}")
        return pd.DataFrame()

# ========== 4. 數據載入 ==========
if supabase:
    df_limit_ups = fetch_today_data("individual_stock_analysis", today)
    df_stock_metadata = fetch_all_metadata()
    df_stock_info = fetch_stock_info()
    df_recent = fetch_recent_limit_ups(5)
   
    if not df_stock_metadata.empty:
        df_all_metadata = df_stock_metadata
    elif not df_stock_info.empty:
        df_all_metadata = df_stock_info
    else:
        df_all_metadata = df_limit_ups[['symbol', 'stock_name', 'sector']].copy()
        df_all_metadata.columns = ['symbol', 'name', 'sector']
else:
    df_limit_ups = pd.DataFrame()
    df_all_metadata = pd.DataFrame()
    df_recent = pd.DataFrame()

# ========== 5. 側邊欄設定 ==========
with st.sidebar:
    st.header("⚙️ 設定")
    st.subheader("🔧 系統狀態")
    status_col1, status_col2, status_col3 = st.columns(3)
    with status_col1:
        st.metric("Supabase", "✅" if supabase else "❌")
    with status_col2:
        st.metric("Gemini", "✅" if gemini_model else "❌")
    with status_col3:
        st.metric("漲停股票", f"{len(df_limit_ups)}" if not df_limit_ups.empty else "0")
   
    if not PLOTLY_AVAILABLE:
        st.error("Plotly 未安裝")
   
    st.subheader("🔐 AI 授權設定")
    if not st.session_state.gemini_authorized:
        with st.expander("Gemini API 授權", expanded=True):
            password_input = st.text_input("授權密碼：", type="password", key="sidebar_pw")
            if st.button("🔓 授權解鎖", use_container_width=True):
                if password_input == st.secrets.get("AI_ASK_PASSWORD", "default_password"):
                    st.session_state.gemini_authorized = True
                    st.success("✅ 授權成功！")
                    st.rerun()
                else:
                    st.error("❌ 密碼錯誤")
            st.caption("💡 授權後在同次會話中有效，關閉瀏覽器後需重新授權")
    else:
        st.success("✅ Gemini API 已授權")
        if st.button("🔒 撤銷授權", type="secondary", use_container_width=True):
            st.session_state.gemini_authorized = False
            st.rerun()
   
    st.divider()
    st.subheader("📊 分析選項")
    show_advanced = st.checkbox("顯示進階分析", value=True)
    show_history = st.checkbox("顯示歷史趨勢", value=True and PLOTLY_AVAILABLE)
    show_sector_analysis = st.checkbox("顯示產業分析", value=True and PLOTLY_AVAILABLE)
   
    st.divider()
    st.subheader("🔗 快速連結")
    st.page_link("https://chatgpt.com/", label="ChatGPT", icon="🤖")
    st.page_link("https://chat.deepseek.com/", label="DeepSeek", icon="🔍")
    st.page_link("https://claude.ai/", label="Claude", icon="📘")
   
    st.divider()
    if not PLOTLY_AVAILABLE:
        st.info("💡 請安裝 plotly 套件以啟用圖表功能：")
        st.code("pip install plotly")
   
    st.divider()
    st.subheader("🛠️ 除錯與維護工具")
    if st.button("🔄 強制清除所有快取並重新載入"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("所有快取已清除！正在重新載入最新資料...")
        st.rerun()

# ========== 6. 主介面呈現 ==========
st.title("🚀 Alpha-Refinery 漲停戰情室 2.0")
st.caption(f"📅 分析日期：{today} | 🕐 最後更新：{datetime.now().strftime('%H:%M:%S')}")

if not supabase:
    st.error("❌ 資料庫連線失敗，請檢查 Supabase 設定")
    st.stop()

# --- 區塊一：今日大盤總結 ---
with st.expander("📊 今日大盤總結", expanded=True):
    summary_df = fetch_today_data("daily_market_summary", today)
    if not summary_df.empty:
        summary_content = summary_df.iloc[0]['summary_content']
        st.info(summary_content)
    else:
        st.warning(f"📅 尚未找到 {today} 的大盤總結記錄。")
        st.info("💡 系統將於掃描完成後自動生成總結，請稍後刷新或點擊側邊欄「清除快取」按鈕。")

# --- 區塊二：強勢股偵測與AI分析 ---
st.divider()
st.header("🔥 今日強勢股偵測與AI分析")

if not df_limit_ups.empty:
    # 產業分佈視覺化（保持不變）
    if show_sector_analysis and PLOTLY_AVAILABLE and 'sector' in df_limit_ups.columns:
        sector_counts = df_limit_ups['sector'].value_counts().reset_index()
        sector_counts.columns = ['產業', '漲停家數']
        col_s1, col_s2 = st.columns([2, 1])
        with col_s1:
            fig = px.bar(sector_counts, x='漲停家數', y='產業', orientation='h',
                        color='漲停家數', color_continuous_scale='Reds',
                        title="今日漲停產業分佈")
            st.plotly_chart(fig, use_container_width=True)
        with col_s2:
            st.metric("總漲停家數", f"{len(df_limit_ups)}家")
            st.metric("涉及產業數", f"{len(sector_counts)}個")
    elif show_sector_analysis and 'sector' in df_limit_ups.columns:
        st.subheader("📊 產業分佈（文字版）")
        sector_counts = df_limit_ups['sector'].value_counts()
        for sector, count in sector_counts.items():
            st.write(f"- **{sector}**: {count}家")

    # 顯示主表（保持不變）
    df_limit_ups['玩股網K線'] = df_limit_ups['symbol'].apply(get_wantgoo_url)
    df_limit_ups['Goodinfo'] = df_limit_ups['symbol'].apply(get_goodinfo_url)
    df_limit_ups['鉅亨網'] = df_limit_ups['symbol'].apply(get_cnyes_url)

    display_df = df_limit_ups[['stock_name', 'symbol', 'sector', 'ai_comment',
                               '玩股網K線', 'Goodinfo', '鉅亨網']].copy()
    display_df.columns = ['股票名稱', '代碼', '產業別', 'AI點評',
                         '📈 K線圖', '📊 財報', '📰 新聞']

    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "📈 K線圖": st.column_config.LinkColumn("K線圖", display_text="玩股網"),
            "📊 財報": st.column_config.LinkColumn("財報", display_text="Goodinfo"),
            "📰 新聞": st.column_config.LinkColumn("新聞", display_text="鉅亨網")
        },
        height=400
    )

    # --- 強勢股一鍵分析（增強版） ---
    st.subheader("💡 強勢標的智能分析")

    # 準備提示詞
    all_limit_names = []
    for _, row in df_limit_ups.iterrows():
        stock_info = f"{row['stock_name']}({row['symbol']}) - 產業:{row['sector']}"
        if pd.notna(row.get('ai_comment')):
            stock_info += f" | AI點評:{row['ai_comment'][:50]}..."
        all_limit_names.append(stock_info)

    limit_up_details = "\n".join([f"{i+1}. {stock}" for i, stock in enumerate(all_limit_names)])

    sector_summary = ""
    if 'sector' in df_limit_ups.columns:
        sector_stats = df_limit_ups['sector'].value_counts()
        sector_summary = "\n產業分佈：\n" + "\n".join([f" - {sector}: {count}家" for sector, count in sector_stats.items()])

    enhanced_prompt = f"""請以專業短線交易員的角度，深度分析今日台股漲停股票：
## 今日漲停股票清單（共{len(df_limit_ups)}家）
{limit_up_details}
{sector_summary}
## 分析維度
### 1. 產業熱度分析
- 哪些產業是今日市場主流？背後的可能催化劑？
- 產業漲停家數分佈顯示什麼資金流向？
### 2. 龍頭辨識與連動
- 從代碼與產業分佈，判斷哪些可能是產業龍頭？
- 是否存在「龍頭帶動，小弟跟漲」的模式？
### 3. 技術面特徵
- 這些漲停股票是否有共同技術特徵？（突破、反轉、持續）
- 漲停時間分佈（如開盤漲停 vs 尾盤漲停）顯示什麼？
### 4. 籌碼面分析
- 哪些股票可能具有籌碼優勢？（可從代碼規模推斷）
- 散戶 vs 大戶的參與程度判斷？
### 5. 風險評估
- 當前漲停股票的風險等級分佈？
- 過熱跡象有哪些？回調風險最高的產業？
### 6. 操作策略建議
- 對於不同風險偏好的投資者，建議關注哪些股票？
- 進場時機建議：追價、回調買進、或觀望？
- 停利停損建議位置？
### 7. 明日關注焦點
- 哪些股票/產業有延續漲勢的潛力？
- 需要特別注意的風險事件或指標？
請提供具體、量化、可操作的投資建議。"""

    # 四個按鈕
    col_a1, col_a2, col_a3, col_a4 = st.columns(4)

    with col_a1:
        encoded_prompt = urllib.parse.quote(enhanced_prompt)
        st.link_button("🔥 ChatGPT 分析", f"https://chatgpt.com/?q={encoded_prompt}", use_container_width=True)

    with col_a2:
        st.link_button("🔍 DeepSeek 分析", "https://chat.deepseek.com/", use_container_width=True)

    with col_a3:
        st.link_button("📘 Claude 分析", "https://claude.ai/", use_container_width=True)

    with col_a4:
        if st.session_state.gemini_authorized:
            if st.button("🤖 Gemini 分析", use_container_width=True, type="primary"):
                with st.spinner("Gemini正在分析中..."):
                    ai_response = call_ai_safely(enhanced_prompt)
                    if ai_response:
                        st.session_state.gemini_strong_report = ai_response
                        st.rerun()
        else:
            st.markdown('<div class="password-protected">', unsafe_allow_html=True)
            st.info("🔒 Gemini 需要授權解鎖")
            auth_pw = st.text_input("授權密碼：", type="password", key="strong_stocks_pw")
            if st.button("解鎖 Gemini", key="strong_stocks_auth"):
                if auth_pw == st.secrets.get("AI_ASK_PASSWORD", "default_password"):
                    st.session_state.gemini_authorized = True
                    st.rerun()
                else:
                    st.error("密碼錯誤")
            st.markdown('</div>', unsafe_allow_html=True)

    # === Gemini 報告獨立顯示（在提示詞上方） ===
    if 'gemini_strong_report' in st.session_state:
        with st.expander("🤖 Gemini 強勢股分析報告", expanded=True):
            ai_response = st.session_state.gemini_strong_report
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
            report_text = f"# 今日強勢股分析報告\n\n日期：{today}\n\n{ai_response}"
            st.download_button(
                label="📥 下載分析報告 (.md)",
                data=report_text.encode('utf-8'),
                file_name=f"strong_stocks_analysis_{today}.md",
                mime="text/markdown",
                use_container_width=True
            )
            if st.button("🗑️ 清除此報告", type="secondary"):
                del st.session_state.gemini_strong_report
                st.rerun()

    # 提示詞放在最下方
    with st.expander("📋 查看完整分析提示詞", expanded=False):
        st.code(enhanced_prompt, language="text", height=300)

    # 後續區塊三、區塊四保持不變（你原本的程式碼）
    # （為了篇幅，這裡省略，但請保留你原本的產業補漲與歷史趨勢區塊）

else:
    st.info("📊 目前尚未偵測到今日強勢標的。")
    st.markdown("""
    ### 💡 可能原因：
    1. 今日市場無漲停股票
    2. 數據尚未更新
    3. 市場交易清淡
   
    ### 🔍 建議行動：
    - 檢查系統數據更新時間
    - 查看其他交易日的數據
    - 分析市場整體狀況
    """)

# ========== 7. 底部導覽列 ==========
st.divider()
st.markdown("### 🔗 快速資源與工具")
col_tool1, col_tool2, col_tool3, col_tool4 = st.columns(4)
with col_tool1:
    st.page_link("https://www.wantgoo.com/", label="玩股網", icon="📈")
with col_tool2:
    st.page_link("https://goodinfo.tw/", label="Goodinfo!", icon="📊")
with col_tool3:
    st.page_link("https://www.cnyes.com/", label="鉅亨網", icon="📰")
with col_tool4:
    st.page_link("https://tw.stock.yahoo.com/", label="Yahoo股市", icon="💹")
st.caption(f"Alpha-Refinery 漲停戰情室 2.0 | 版本：{datetime.now().strftime('%Y.%m.%d')} | 數據僅供參考，投資有風險")
