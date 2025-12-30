# -*- coding: utf-8 -*-
"""
🏭 產業AI分析頁面 - 選擇產業族群進行分析
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import urllib.parse

# 設定頁面配置
st.set_page_config(
    page_title="產業AI分析 | Alpha-Refinery",
    layout="wide",
    page_icon="🏭"
)

# 添加自訂CSS
st.markdown("""
    <style>
    .sector-card {
        background: white;
        border-radius: 10px;
        padding: 20px;
        margin: 10px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .sector-header {
        background: linear-gradient(135deg, #2196F3 0%, #21CBF3 100%);
        color: white;
        padding: 20px;
        border-radius: 10px;
        margin-bottom: 20px;
    }
    </style>
""", unsafe_allow_html=True)

# ========== 導入共享功能 ==========
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
try:
    from utils.common import init_connections, fetch_today_data, call_ai_safely
    supabase, gemini_model = init_connections()
    today = datetime.now().strftime("%Y-%m-%d")
except Exception as e:
    st.error(f"初始化失敗: {e}")
    supabase = None
    gemini_model = None
    today = datetime.now().strftime("%Y-%m-%d")

# ========== 頁面標題 ==========
st.markdown("""
    <div class="sector-header">
        <h1 style="margin: 0;">🏭 產業AI分析</h1>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">選擇今日漲停產業，進行趨勢分析</p>
    </div>
""", unsafe_allow_html=True)

# 檢查連線
if not supabase:
    st.error("❌ 資料庫連線失敗，請檢查設定")
    st.stop()

# ========== 載入今日漲停股票數據 ==========
df_limit_ups = fetch_today_data("individual_stock_analysis", today)

if df_limit_ups.empty:
    st.info("📊 今日尚未有漲停股票數據，請稍後再試。")
    st.stop()

# ========== 計算產業分佈 ==========
if 'sector' not in df_limit_ups.columns:
    st.error("❌ 數據中缺少產業欄位")
    st.stop()

sector_counts = df_limit_ups['sector'].value_counts().reset_index()
sector_counts.columns = ['產業', '漲停家數']

# ========== 產業選擇器 ==========
st.subheader("🔍 選擇分析產業")

# 顯示產業統計
col_stats1, col_stats2, col_stats3 = st.columns(3)
with col_stats1:
    st.metric("總產業數", len(sector_counts))
with col_stats2:
    avg_stocks = sector_counts['漲停家數'].mean()
    st.metric("平均漲停家數", f"{avg_stocks:.1f}")
with col_stats3:
    max_sector = sector_counts.iloc[0] if not sector_counts.empty else None
    st.metric("最熱產業", f"{max_sector['產業']}" if max_sector else "N/A")

# 產業選擇下拉
selected_sector = st.selectbox(
    "選擇產業：",
    options=sector_counts['產業'].tolist(),
    help="選擇您要分析的產業"
)

# ========== 顯示選擇的產業資訊 ==========
if selected_sector:
    st.markdown(f'<div class="sector-card">', unsafe_allow_html=True)
    st.subheader(f"📊 {selected_sector} 產業概況")
    
    # 獲取該產業的股票
    sector_stocks = df_limit_ups[df_limit_ups['sector'] == selected_sector]
    stock_count = len(sector_stocks)
    
    col_info1, col_info2, col_info3 = st.columns(3)
    with col_info1:
        st.metric("漲停家數", f"{stock_count}家")
    with col_info2:
        avg_return = sector_stocks['return_rate'].mean() if 'return_rate' in sector_stocks.columns else 0
        st.metric("平均漲幅", f"{avg_return:.2%}" if avg_return else "N/A")
    with col_info3:
        avg_days = sector_stocks['consecutive_days'].mean() if 'consecutive_days' in sector_stocks.columns else 1
        st.metric("平均連板", f"{avg_days:.1f}天")
    
    # 顯示股票列表
    st.write(f"**漲停股票列表 ({stock_count}家)：**")
    
    if stock_count > 0:
        display_cols = ['stock_name', 'symbol', 'return_rate', 'price', 'consecutive_days']
        display_df = sector_stocks[display_cols].copy()
        display_df.columns = ['股票名稱', '代碼', '漲幅', '價格', '連板天數']
        
        # 格式化
        display_df['漲幅'] = display_df['漲幅'].apply(lambda x: f"{x:.2%}" if x else "N/A")
        display_df['價格'] = display_df['價格'].apply(lambda x: f"{x:.2f}" if x else "N/A")
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True,
            height=min(400, 100 + stock_count * 35)
        )
    
    st.markdown('</div>', unsafe_allow_html=True)

# ========== AI 分析區域 ==========
st.divider()
st.header("🤖 產業趨勢AI分析")

if selected_sector and gemini_model:
    # 檢查授權
    if 'gemini_authorized' not in st.session_state:
        st.session_state.gemini_authorized = False
    
    if not st.session_state.gemini_authorized:
        st.markdown('<div class="password-protected">', unsafe_allow_html=True)
        st.warning("🔒 AI分析需要授權解鎖")
        
        auth_col1, auth_col2 = st.columns([3, 1])
        with auth_col1:
            password_input = st.text_input("授權密碼：", type="password", key="sector_analysis_pw")
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
        
        # 創建產業分析提示詞
        stocks_info = "\n".join([
            f"{i+1}. {row['stock_name']}({row['symbol']}) - "
            f"漲幅:{row.get('return_rate',0):.2%} - "
            f"連板:{row.get('consecutive_days',1)}天 - "
            f"價格:{row.get('price','N/A')}"
            for i, (_, row) in enumerate(sector_stocks.iterrows())
        ])
        
        sector_prompt = f"""
        請以台灣股市產業分析師身份，分析以下產業的集體漲停現象：

        ## 產業概況
        - 產業名稱：{selected_sector}
        - 漲停家數：{stock_count}家
        - 市場佔比：佔今日總漲停的 {stock_count/len(df_limit_ups):.1%}

        ## 該產業漲停股票明細：
        {stocks_info}

        ## 請分析以下面向：

        ### 1. 產業趨勢判斷
        - 這是單一個股表現還是產業趨勢？
        - 漲停股票在產業中的代表性（龍頭/二線）
        - 可能的產業催化劑

        ### 2. 資金流向分析
        - 資金是否集中流入該產業
        - 產業鏈上下游聯動情況
        - 外資/投信/自營商動向

        ### 3. 時機分析
        - 產業循環位置
        - 政策面影響
        - 季節性因素

        ### 4. 強度評估
        - 漲停家數的意義
        - 連板股票的分布
        - 漲停時間點分析

        ### 5. 風險提示
        - 產業過熱風險
        - 補漲/輪動可能性
        - 潛在利空因素

        ### 6. 投資策略建議
        - 產業ETF選擇建議
        - 個股選擇優先順序
        - 進出場時機建議

        ### 7. 明日觀察重點
        - 關鍵指標股
        - 產業新聞追蹤
        - 資金流向變化

        請先給出核心結論（是否形成產業趨勢），再詳細分析。
        """
        
        # 顯示提示詞
        with st.expander("📋 查看分析提示詞", expanded=False):
            st.code(sector_prompt, language="text", height=300)
        
        # 分析按鈕
        col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
        
        with col_btn1:
            encoded_prompt = urllib.parse.quote(sector_prompt)
            st.link_button("🔥 ChatGPT 分析", 
                         f"https://chatgpt.com/?q={encoded_prompt}", 
                         use_container_width=True)
        
        with col_btn2:
            st.link_button("🔍 DeepSeek 分析", 
                         "https://chat.deepseek.com/", 
                         use_container_width=True)
        
        with col_btn3:
            st.link_button("📘 Claude 分析", 
                         "https://claude.ai/", 
                         use_container_width=True)
        
        with col_btn4:
            if st.button("🤖 Gemini 分析", 
                        use_container_width=True, 
                        type="primary",
                        key="analyze_sector"):
                
                with st.spinner("🤖 AI正在分析產業趨勢中..."):
                    ai_response = call_ai_safely(sector_prompt, gemini_model)
                    
                    if ai_response:
                        st.session_state[f"ai_response_sector_{selected_sector}"] = ai_response
                        st.rerun()
        
        # 顯示AI回應
        response_key = f"ai_response_sector_{selected_sector}"
        if response_key in st.session_state:
            st.markdown('<div class="ai-response-box">', unsafe_allow_html=True)
            st.subheader(f"🤖 {selected_sector} 產業AI分析報告")
            
            ai_response = st.session_state[response_key]
            st.markdown(ai_response)
            
            # 下載按鈕
            report_text = f"# {selected_sector} 產業AI分析報告\n\n日期：{today}\n\n{ai_response}"
            
            col_dl1, col_dl2 = st.columns([3, 1])
            with col_dl1:
                st.download_button(
                    label="📥 下載分析報告 (.md)",
                    data=report_text.encode('utf-8'),
                    file_name=f"{selected_sector}_analysis_{today}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            with col_dl2:
                if st.button("🗑️ 清除報告", type="secondary", use_container_width=True):
                    del st.session_state[response_key]
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)

# ========== 頁面底部 ==========
st.divider()
st.caption(f"產業AI分析頁面 | 更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
