# -*- coding: utf-8 -*-
"""
🌐 市場總覽AI分析頁面 - 整體市場全面解析
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import urllib.parse
import plotly.express as px

# 設定頁面配置
st.set_page_config(
    page_title="市場總覽AI分析 | Alpha-Refinery",
    layout="wide",
    page_icon="🌐"
)

# 添加自訂CSS
st.markdown("""
    <style>
    .market-header {
        background: linear-gradient(135deg, #9C27B0 0%, #673AB7 100%);
        color: white;
        padding: 25px;
        border-radius: 15px;
        margin-bottom: 25px;
    }
    .stat-card {
        background: white;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
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
    <div class="market-header">
        <h1 style="margin: 0;">🌐 市場總覽AI分析</h1>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">整體市場全面解析 | 產業分佈 | 資金流向 | 風險評估</p>
    </div>
""", unsafe_allow_html=True)

# 檢查連線
if not supabase:
    st.error("❌ 資料庫連線失敗，請檢查設定")
    st.stop()

# ========== 載入今日數據 ==========
df_limit_ups = fetch_today_data("individual_stock_analysis", today)
df_market_summary = fetch_today_data("daily_market_summary", today)

if df_limit_ups.empty:
    st.info("📊 今日尚未有漲停股票數據，請稍後再試。")
    st.stop()

# ========== 市場統計區塊 ==========
st.subheader("📊 今日市場統計")

# 計算統計數據
total_stocks = len(df_limit_ups)
rotc_count = len(df_limit_ups[df_limit_ups['is_rotc'] == True])
main_count = total_stocks - rotc_count
avg_consecutive = df_limit_ups['consecutive_days'].mean() if 'consecutive_days' in df_limit_ups.columns else 1
avg_return = df_limit_ups['return_rate'].mean() if 'return_rate' in df_limit_ups.columns else 0

# 產業分佈
sector_counts = df_limit_ups['sector'].value_counts().reset_index()
sector_counts.columns = ['產業', '漲停家數']

# 顯示統計卡片
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    st.metric("總漲停家數", f"{total_stocks}家")
    st.markdown('</div>', unsafe_allow_html=True)

with col2:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    st.metric("上市櫃/興櫃", f"{main_count}/{rotc_count}")
    st.markdown('</div>', unsafe_allow_html=True)

with col3:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    st.metric("平均連板天數", f"{avg_consecutive:.1f}天")
    st.markdown('</div>', unsafe_allow_html=True)

with col4:
    st.markdown('<div class="stat-card">', unsafe_allow_html=True)
    st.metric("平均漲幅", f"{avg_return:.2%}")
    st.markdown('</div>', unsafe_allow_html=True)

# ========== 產業分佈視覺化 ==========
st.divider()
st.subheader("🏭 產業分佈視覺化")

if not sector_counts.empty:
    col_chart1, col_chart2 = st.columns([2, 1])
    
    with col_chart1:
        # 長條圖
        fig = px.bar(
            sector_counts,
            x='漲停家數',
            y='產業',
            orientation='h',
            color='漲停家數',
            color_continuous_scale='Reds',
            title="今日漲停產業分佈"
        )
        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)
    
    with col_chart2:
        # 圓餅圖
        fig2 = px.pie(
            sector_counts,
            values='漲停家數',
            names='產業',
            title="產業佔比",
            hole=0.3
        )
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)

# ========== 今日漲停股票列表 ==========
st.divider()
st.subheader("📋 今日漲停股票列表")

if not df_limit_ups.empty:
    # 創建顯示表格
    display_cols = ['stock_name', 'symbol', 'sector', 'return_rate', 'price', 'consecutive_days', 'is_rotc']
    display_df = df_limit_ups[display_cols].copy()
    display_df.columns = ['股票名稱', '代碼', '產業', '漲幅', '價格', '連板天數', '是否興櫃']
    
    # 格式化
    display_df['漲幅'] = display_df['漲幅'].apply(lambda x: f"{x:.2%}" if x else "N/A")
    display_df['價格'] = display_df['價格'].apply(lambda x: f"{x:.2f}" if x else "N/A")
    display_df['是否興櫃'] = display_df['是否興櫃'].apply(lambda x: "✓" if x else "✗")
    
    # 排序
    display_df = display_df.sort_values(['連板天數', '漲幅'], ascending=False)
    
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        height=500
    )

# ========== AI 分析區域 ==========
st.divider()
st.header("🤖 市場總覽AI分析")

if gemini_model:
    # 檢查授權
    if 'gemini_authorized' not in st.session_state:
        st.session_state.gemini_authorized = False
    
    if not st.session_state.gemini_authorized:
        st.markdown('<div class="password-protected">', unsafe_allow_html=True)
        st.warning("🔒 AI分析需要授權解鎖")
        
        auth_col1, auth_col2 = st.columns([3, 1])
        with auth_col1:
            password_input = st.text_input("授權密碼：", type="password", key="market_analysis_pw")
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
        
        # 創建市場分析提示詞
        # 統計連板情況
        consecutive_stats = {}
        for _, row in df_limit_ups.iterrows():
            days = row.get('consecutive_days', 1)
            consecutive_stats[days] = consecutive_stats.get(days, 0) + 1
        
        stats_text = "\n".join([
            f"- {days}連板：{count}家" 
            for days, count in sorted(consecutive_stats.items())
        ])
        
        # 產業分布文字
        sector_text = "\n".join([
            f"- {sector}: {count}家" 
            for sector, count in sector_counts.head(10).itertuples(index=False)
        ])
        
        # 最強股票
        strongest_stocks = display_df.nlargest(3, '連板天數')
        strongest_text = "\n".join([
            f"{i+1}. {row['股票名稱']}({row['代碼']}): {row['連板天數']}連板"
            for i, (_, row) in enumerate(strongest_stocks.iterrows())
        ])
        
        market_prompt = f"""
        請以台灣股市首席分析師身份，分析今日市場整體狀況：

        ## 市場整體數據
        - 總漲停家數：{total_stocks}家
        - 市場溫度：{'熱絡' if total_stocks > 20 else '溫和'}
        - 上市櫃股票：{main_count}家
        - 興櫃股票：{rotc_count}家
        - 平均連板天數：{avg_consecutive:.1f}天
        - 平均漲幅：{avg_return:.2%}
        
        ## 連板統計：
        {stats_text}
        
        ## 產業分布（前10名）：
        {sector_text}
        
        ## 最強勢股票（連板數最多）：
        {strongest_text}

        ## 請分析今日市場特徵：

        ### 1. 市場情緒評估
        - 投機氣氛濃淡
        - 散戶參與程度
        - 主力動向分析

        ### 2. 資金結構分析
        - 資金集中度
        - 類股輪動狀況
        - 外資/內資比重

        ### 3. 技術面信號
        - 大盤位置與漲停家數關係
        - 強勢股與弱勢股對比
        - 關鍵技術位突破情況

        ### 4. 風險控管提示
        - 系統性風險評估
        - 過熱警示信號
        - 流動性風險

        ### 5. 明日操作策略
        - 大盤方向預判
        - 重點關注產業
        - 風險控管建議

        ### 6. 關鍵觀察指標
        - 明日開盤強度
        - 連板股續航力
        - 成交量變化

        ### 7. 給不同類型投資者的建議
        - 長線投資者：
        - 短線交易者：
        - 當沖客：

        請先給出今日市場核心結論（多空、強弱、風險），再詳細分析。
        用數據支持觀點，避免主觀臆測。
        """
        
        # 顯示提示詞
        with st.expander("📋 查看分析提示詞", expanded=False):
            st.code(market_prompt, language="text", height=400)
        
        # 分析按鈕
        col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
        
        with col_btn1:
            encoded_prompt = urllib.parse.quote(market_prompt)
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
                        key="analyze_market"):
                
                with st.spinner("🤖 AI正在分析市場趨勢中..."):
                    ai_response = call_ai_safely(market_prompt, gemini_model)
                    
                    if ai_response:
                        st.session_state["ai_response_market"] = ai_response
                        st.rerun()
        
        # 顯示AI回應
        if "ai_response_market" in st.session_state:
            st.markdown('<div class="ai-response-box">', unsafe_allow_html=True)
            st.subheader("🤖 市場總覽AI分析報告")
            
            ai_response = st.session_state["ai_response_market"]
            st.markdown(ai_response)
            
            # 下載按鈕
            report_text = f"# 市場總覽AI分析報告\n\n日期：{today}\n\n{ai_response}"
            
            col_dl1, col_dl2 = st.columns([3, 1])
            with col_dl1:
                st.download_button(
                    label="📥 下載分析報告 (.md)",
                    data=report_text.encode('utf-8'),
                    file_name=f"market_analysis_{today}.md",
                    mime="text/markdown",
                    use_container_width=True
                )
            with col_dl2:
                if st.button("🗑️ 清除報告", type="secondary", use_container_width=True):
                    del st.session_state["ai_response_market"]
                    st.rerun()
            
            st.markdown('</div>', unsafe_allow_html=True)
        
        # 授權撤銷按鈕
        st.divider()
        if st.button("🔒 撤銷 AI 授權", type="secondary"):
            st.session_state.gemini_authorized = False
            st.rerun()

else:
    st.error("❌ AI模型未初始化，無法進行分析")

# ========== 頁面底部 ==========
st.divider()
st.markdown("### 📈 市場相關資源")

res_col1, res_col2, res_col3, res_col4 = st.columns(4)
with res_col1:
    st.page_link("https://www.twse.com.tw/zh/", label="證交所", icon="🏢")
with res_col2:
    st.page_link("https://www.tpex.org.tw/web/", label="櫃買中心", icon="🏛️")
with res_col3:
    st.page_link("https://www.moneydj.com/", label="MoneyDJ", icon="💰")
with res_col4:
    st.page_link("https://www.wantgoo.com/", label="玩股網總覽", icon="📊")

st.caption(f"市場總覽AI分析頁面 | 更新時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
