# -*- coding: utf-8 -*-
"""
🚀 Alpha-Refinery 漲停戰情室 2.0 - 主頁面
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# 設定頁面配置
st.set_page_config(
    page_title="Alpha-Refinery 漲停戰情室 2.0",
    layout="wide",
    page_icon="🚀"
)

# 自訂CSS樣式
st.markdown("""
    <style>
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border: 1px solid #f0f2f6; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
    .ai-section { background-color: #fff3cd; padding: 15px; border-radius: 8px; border-left: 5px solid #ffc107; }
    .stock-card { border: 1px solid #e0e0e0; border-radius: 8px; padding: 12px; margin: 8px 0; background: linear-gradient(135deg, #f5f7fa 0%, #e4edf5 100%); }
    .password-protected { border: 2px solid #ff6b6b; border-radius: 8px; padding: 15px; background-color: #fff5f5; }
    .welcome-header { 
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 3rem 2rem;
        border-radius: 15px;
        color: white;
        margin-bottom: 2rem;
        text-align: center;
    }
    .feature-card {
        background: white;
        border-radius: 10px;
        padding: 1.5rem;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        transition: transform 0.3s;
        height: 100%;
    }
    .feature-card:hover {
        transform: translateY(-5px);
    }
    </style>
""", unsafe_allow_html=True)

# ========== 導入共享功能 ==========
import sys
import os

# 添加父目錄到路徑，讓 Python 能找到 utils 包
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # 專案根目錄

# 將專案根目錄添加到路徑
sys.path.insert(0, parent_dir)

try:
    # 從 utils 包導入
    from utils import (
        init_connections, 
        fetch_today_data, 
        get_stock_links,
        get_wantgoo_url,
        get_goodinfo_url,
        get_cnyes_url,
        call_ai_safely
    )
except ImportError as e:
    st.error(f"導入共享功能失敗: {e}")
    # 除錯訊息
    st.error(f"當前工作目錄: {os.getcwd()}")
    st.error(f"Python 路徑: {sys.path}")
    st.error(f"目錄內容: {os.listdir(parent_dir)}")
    st.stop()

# 初始化連線
supabase, gemini_model = init_connections()
today = datetime.now().strftime("%Y-%m-%d")

# ========== 主頁面內容 ==========
# 歡迎區塊
st.markdown(f"""
    <div class="welcome-header">
        <h1 style="font-size: 3rem; margin-bottom: 1rem;">🚀 Alpha-Refinery 漲停戰情室 2.0</h1>
        <p style="font-size: 1.2rem; opacity: 0.9;">智能漲停板分析系統 | 即時監控 | AI決策支援</p>
        <p style="font-size: 1rem; opacity: 0.8;">📅 分析日期：{today} | 🕐 最後更新：{datetime.now().strftime('%H:%M:%S')}</p>
    </div>
""", unsafe_allow_html=True)

# 系統狀態區塊
st.subheader("🔧 系統狀態")
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("資料庫連線", "✅" if supabase else "❌")

with col2:
    st.metric("AI 模型", "✅" if gemini_model else "❌")

with col3:
    if supabase:
        try:
            df_limit = fetch_today_data(supabase, "individual_stock_analysis", today)
            limit_count = len(df_limit) if not df_limit.empty else 0
            st.metric("今日漲停", f"{limit_count}檔")
        except Exception as e:
            st.metric("今日漲停", "載入中...")
    else:
        st.metric("今日漲停", "N/A")

with col4:
    st.metric("更新時間", datetime.now().strftime("%H:%M"))

# --- 今日大盤總結 ---
st.divider()
st.header("📊 今日大盤總結")

if supabase:
    summary_df = fetch_today_data(supabase, "daily_market_summary", today)
    if not summary_df.empty:
        summary_content = summary_df.iloc[0]['summary_content']
        st.info(summary_content)
    else:
        st.warning(f"📅 尚未找到 {today} 的大盤總結記錄。")
        st.info("💡 監控系統將於掃描完成後自動生成總結，請稍後刷新頁面。")
else:
    st.error("❌ 資料庫連線失敗，請檢查設定")

# --- 功能介紹區塊 ---
st.divider()
st.header("🎯 系統功能")

# 三個主要功能介紹
col_f1, col_f2, col_f3 = st.columns(3)

with col_f1:
    st.markdown("""
    <div class="feature-card">
        <h3>📈 個股AI分析</h3>
        <p><strong>一檔一檔深度分析</strong></p>
        <ul style="padding-left: 1.2rem;">
            <li>單一漲停股票技術分析</li>
            <li>連板天數判斷</li>
            <li>AI風險評估</li>
            <li>操作建議生成</li>
        </ul>
        <p style="margin-top: 1rem;">
            <a href="/1_個股AI分析" target="_self">
                <button style="background-color: #4CAF50; color: white; padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer;">
                    進入分析 →
                </button>
            </a>
        </p>
    </div>
    """, unsafe_allow_html=True)

with col_f2:
    st.markdown("""
    <div class="feature-card">
        <h3>🏭 產業AI分析</h3>
        <p><strong>產業趨勢深度解析</strong></p>
        <ul style="padding-left: 1.2rem;">
            <li>產業漲停家數分析</li>
            <li>資金流向判斷</li>
            <li>龍頭股辨識</li>
            <li>產業前景評估</li>
        </ul>
        <p style="margin-top: 1rem;">
            <a href="/2_產業AI分析" target="_self">
                <button style="background-color: #2196F3; color: white; padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer;">
                    進入分析 →
                </button>
            </a>
        </p>
    </div>
    """, unsafe_allow_html=True)

with col_f3:
    st.markdown("""
    <div class="feature-card">
        <h3>🌐 市場總覽AI分析</h3>
        <p><strong>整體市場全面解析</strong></p>
        <ul style="padding-left: 1.2rem;">
            <li>市場情緒分析</li>
            <li>資金結構判斷</li>
            <li>風險控管建議</li>
            <li>明日策略規劃</li>
        </ul>
        <p style="margin-top: 1rem;">
            <a href="/3_市場總覽AI分析" target="_self">
                <button style="background-color: #9C27B0; color: white; padding: 8px 16px; border: none; border-radius: 5px; cursor: pointer;">
                    進入分析 →
                </button>
            </a>
        </p>
    </div>
    """, unsafe_allow_html=True)

# --- 今日漲停板概覽 ---
st.divider()
st.header("🔥 今日漲停板概覽")

if supabase:
    df_limit_ups = fetch_today_data(supabase, "individual_stock_analysis", today)
    
    if not df_limit_ups.empty:
        # 顯示前10檔漲停股票
        display_cols = ['stock_name', 'symbol', 'sector', 'return_rate', 'price']
        if 'consecutive_days' in df_limit_ups.columns:
            display_cols.append('consecutive_days')
        
        display_df = df_limit_ups[display_cols].head(10).copy()
        
        # 重命名欄位
        column_mapping = {
            'stock_name': '股票名稱',
            'symbol': '代碼',
            'sector': '產業',
            'return_rate': '漲幅',
            'price': '價格',
            'consecutive_days': '連板天數'
        }
        display_df = display_df.rename(columns=column_mapping)
        
        # 格式化
        if '漲幅' in display_df.columns:
            display_df['漲幅'] = display_df['漲幅'].apply(lambda x: f"{x:.2%}" if isinstance(x, (int, float)) else "N/A")
        if '價格' in display_df.columns:
            display_df['價格'] = display_df['價格'].apply(lambda x: f"{x:.2f}" if isinstance(x, (int, float)) else "N/A")
        
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # 顯示統計
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("總漲停家數", f"{len(df_limit_ups)}家")
        with col_s2:
            if 'is_rotc' in df_limit_ups.columns:
                rotc_count = len(df_limit_ups[df_limit_ups['is_rotc'] == True])
                st.metric("興櫃漲停", f"{rotc_count}家")
            else:
                st.metric("興櫃漲停", "N/A")
        with col_s3:
            if 'consecutive_days' in df_limit_ups.columns:
                avg_days = df_limit_ups['consecutive_days'].mean() if not df_limit_ups.empty else 1
                st.metric("平均連板", f"{avg_days:.1f}天")
            else:
                st.metric("平均連板", "N/A")
    else:
        st.info("📊 目前尚未偵測到今日強勢標的。")
else:
    st.error("❌ 無法載入漲停板數據")

# --- 底部導覽列 ---
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

