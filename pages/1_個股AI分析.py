# -*- coding: utf-8 -*-
"""
📈 個股AI分析頁面 - 一檔一檔股票詢問AI
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import urllib.parse

# 設定頁面配置
st.set_page_config(
    page_title="個股AI分析 | Alpha-Refinery",
    layout="wide",
    page_icon="📈"
)

# 添加自訂CSS
st.markdown("""
    <style>
    .stock-selector { border: 2px solid #4CAF50; border-radius: 10px; padding: 20px; margin-bottom: 20px; }
    .ai-response-box { 
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 25px;
        border-radius: 15px;
        border-left: 8px solid #4CAF50;
        margin: 20px 0;
    }
    </style>
""", unsafe_allow_html=True)

# ========== 導入共享功能 ==========
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
try:
    from utils.common import (
        init_connections, fetch_today_data, get_stock_links,
        call_ai_safely, create_individual_stock_prompt
    )
    
    # 初始化連線
    supabase, gemini_model = init_connections()
    today = datetime.now().strftime("%Y-%m-%d")
    
except Exception as e:
    st.error(f"初始化失敗: {e}")
    supabase = None
    gemini_model = None
    today = datetime.now().strftime("%Y-%m-%d")

# ========== 頁面標題 ==========
st.title("📈 個股AI分析")
st.caption("選擇今日漲停股票，進行深度AI分析")

# 檢查連線
if not supabase:
    st.error("❌ 資料庫連線失敗，請檢查設定")
    st.stop()

# ========== 載入今日漲停股票數據 ==========
df_limit_ups = fetch_today_data("individual_stock_analysis", today)

if df_limit_ups.empty:
    st.info("📊 今日尚未有漲停股票數據，請稍後再試。")
    
    # 顯示最近可用的日期
    try:
        res = supabase.table("individual_stock_analysis")\
            .select("analysis_date")\
            .order("analysis_date", desc=True)\
            .limit(1)\
            .execute()
        
        if res.data:
            last_date = res.data[0]['analysis_date']
            st.info(f"最近可用的分析日期：{last_date}")
            if st.button("載入最近日期的數據"):
                df_limit_ups = fetch_today_data("individual_stock_analysis", last_date)
    except:
        pass
    
    st.stop()

# ========== 股票選擇器 ==========
st.markdown('<div class="stock-selector">', unsafe_allow_html=True)
st.subheader("🔍 選擇分析標的")

# 創建選擇列表
stock_options = []
for _, row in df_limit_ups.iterrows():
    display_text = f"{row['stock_name']} ({row['symbol']}) - {row['sector']}"
    
    # 添加連板天數資訊
    days = row.get('consecutive_days', 1)
    if days > 1:
        display_text += f" 🔥 {days}連板"
    
    stock_options.append({
        'display': display_text,
        'symbol': row['symbol'],
        'name': row['stock_name'],
        'data': row.to_dict()
    })

# 下拉選擇器
selected_display = st.selectbox(
    "選擇股票：",
    options=[s['display'] for s in stock_options],
    help="選擇您要分析的漲停板股票"
)

# 獲取選擇的股票數據
selected_stock = None
for stock in stock_options:
    if stock['display'] == selected_display:
        selected_stock = stock
        break

if selected_stock:
    st.success(f"✅ 已選擇：{selected_stock['name']} ({selected_stock['symbol']})")
st.markdown('</div>', unsafe_allow_html=True)

# ========== 顯示股票詳細資訊 ==========
if selected_stock:
    stock_data = selected_stock['data']
    
    col_info1, col_info2, col_info3, col_info4 = st.columns(4)
    
    with col_info1:
        st.metric("股票代碼", selected_stock['symbol'])
    
    with col_info2:
        return_rate = stock_data.get('return_rate', 0)
        st.metric("今日漲幅", f"{return_rate:.2%}" if return_rate else "N/A")
    
    with col_info3:
        price = stock_data.get('price', 0)
        st.metric("當前價格", f"{price:.2f}" if price else "N/A")
    
    with col_info4:
        consecutive_days = stock_data.get('consecutive_days', 1)
        st.metric("連續漲停", f"{consecutive_days}天")
    
    # 產業資訊
    st.write(f"**產業類別：** {stock_data.get('sector', '未分類')}")
    st.write(f"**市場類別：** {'興櫃' if stock_data.get('is_rotc') else '上市/上櫃'}")
    
    # 顯示連結
    st.subheader("🔗 相關資源")
    links = get_stock_links(selected_stock['symbol'])
    
    link_cols = st.columns(5)
    with link_cols[0]:
        st.link_button("📈 玩股網K線", links['玩股網'])
    with link_cols[1]:
        st.link_button("📊 Goodinfo財報", links['Goodinfo'])
    with link_cols[2]:
        st.link_button("📰 鉅亨網新聞", links['鉅亨網'])
    with link_cols[3]:
        st.link_button("💹 Yahoo股市", links['Yahoo股市'])
    with link_cols[4]:
        st.link_button("📋 財報狗分析", links['財報狗'])

# ========== AI 分析區域 ==========
st.divider()
st.header("🤖 AI深度分析")

if selected_stock and gemini_model:
    # 檢查是否有AI密碼保護
    if 'gemini_authorized' not in st.session_state:
        st.session_state.gemini_authorized = False
    
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
        prompt = create_individual_stock_prompt(stock_data)
        
        # 顯示提示詞
        with st.expander("📋 查看分析提示詞", expanded=False):
            st.code(prompt, language="text", height=300)
        
        # 分析按鈕
        col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
        
        with col_btn1:
            encoded_prompt = urllib.parse.quote(prompt)
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
                        key="analyze_stock"):
                
                with st.spinner("🤖 AI正在深度分析中..."):
                    ai_response = call_ai_safely(prompt, gemini_model)
                    
                    if ai_response:
                        # 儲存到 session state
                        st.session_state[f"ai_response_{selected_stock['symbol']}"] = ai_response
                        st.rerun()
        
        # 顯示AI回應
        response_key = f"ai_response_{selected_stock['symbol']}"
        if response_key in st.session_state:
            st.markdown('<div class="ai-response-box">', unsafe_allow_html=True)
            st.subheader(f"🤖 {selected_stock['name']} AI分析報告")
            
            ai_response = st.session_state[response_key]
            st.markdown(ai_response)
            
            # 下載按鈕
            report_text = f"# {selected_stock['name']}({selected_stock['symbol']}) AI分析報告\n\n日期：{today}\n\n{ai_response}"
            
            col_dl1, col_dl2 = st.columns([3, 1])
            with col_dl1:
                st.download_button(
                    label="📥 下載分析報告 (.md)",
                    data=report_text.encode('utf-8'),
                    file_name=f"{selected_stock['symbol']}_analysis_{today}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            with col_dl2:
                if st.button("🗑️ 清除報告", type="secondary", use_container_width=True):
                    del st.session_state[response_key]
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # 授權撤銷按鈕
        st.divider()
        if st.button("🔒 撤銷 AI 授權", type="secondary"):
            st.session_state.gemini_authorized = False
            st.rerun()

else:
    if not gemini_model:
        st.error("❌ AI模型未初始化，無法進行分析")
    elif not selected_stock:
        st.info("ℹ️ 請先選擇要分析的股票")

# ========== 頁面底部 ==========
st.divider()
st.markdown("### 🔄 其他選項")

if st.button("🔄 重新載入數據", type="secondary"):
    st.cache_data.clear()
    st.rerun()

st.caption(f"個股AI分析頁面 | 更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
