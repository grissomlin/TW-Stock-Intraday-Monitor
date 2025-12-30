# -*- coding: utf-8 -*-
"""
🚀 Alpha-Refinery 漲停戰情室 2.0 - 主頁面
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import urllib.parse

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

# ========== 密碼保護機制 ==========
if 'gemini_authorized' not in st.session_state:
    st.session_state.gemini_authorized = False

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
            # 修改這裡：移除 supabase 參數
            df_limit = fetch_today_data("individual_stock_analysis", today)
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
    # 修改這裡：移除 supabase 參數
    summary_df = fetch_today_data("daily_market_summary", today)
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
    # 修改這裡：移除 supabase 參數
    df_limit_ups = fetch_today_data("individual_stock_analysis", today)
    
    if not df_limit_ups.empty:
        # ========== 主表格功能（你要的功能） ==========
        st.subheader("📊 漲停股票列表")
        
        # 添加連結欄位
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
        
        # ========== 強勢股一鍵分析（增強版） ==========
        st.divider()
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
                        ai_response = call_ai_safely(enhanced_prompt, gemini_model)
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

        # === Gemini 報告獨立顯示 ===
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
        
        # ========== 🎯 個股深度分析（新增功能） ==========
        st.divider()
        st.subheader("🎯 個股深度分析")
        
        # 建立股票選擇下拉選單
        stock_options = []
        for _, row in df_limit_ups.iterrows():
            display_text = f"{row['symbol']} {row['stock_name']}"
            if 'consecutive_days' in row and row['consecutive_days'] > 0:
                display_text += f" ({row['consecutive_days']}連板)"
            stock_options.append((display_text, row))
        
        # 下拉選單
        selected_display = st.selectbox(
            "請選擇要分析的漲停股：",
            options=[so[0] for so in stock_options],
            key="stock_selector"
        )
        
        # 找到選擇的股票
        selected_stock = None
        for display, stock in stock_options:
            if display == selected_display:
                selected_stock = stock
                break
        
        if selected_stock is not None:
            # 顯示股票詳細資訊
            col_info1, col_info2, col_info3, col_info4 = st.columns(4)
            
            with col_info1:
                st.metric("今日狀態", f"{selected_stock.get('consecutive_days', 1)} 連板")
            
            with col_info2:
                # 這裡可以加入更多統計數據，例如歷史漲停次數等
                # 目前先顯示今日漲幅
                return_rate = selected_stock.get('return_rate', 0)
                st.metric("今日漲幅", f"{return_rate:.2%}" if return_rate else "N/A")
            
            with col_info3:
                # 這裡可以加入更多統計數據
                # 目前先顯示價格
                price = selected_stock.get('price', 0)
                st.metric("當前價格", f"{price:.2f}" if price else "N/A")
            
            with col_info4:
                # 這裡可以加入隔日溢價等統計數據
                # 目前先顯示產業
                st.metric("所屬產業", selected_stock.get('sector', 'N/A'))
            
            # ========== 同產業聯動參考 ==========
            current_sector = selected_stock.get('sector', '')
            if current_sector:
                # 找出同產業的其他股票
                same_sector_stocks = df_limit_ups[df_limit_ups['sector'] == current_sector].copy()
                same_sector_stocks = same_sector_stocks[same_sector_stocks['symbol'] != selected_stock['symbol']]
                
                if not same_sector_stocks.empty:
                    st.write(f"🌿 **同產業聯動參考 ({current_sector})：**")
                    
                    # 建立連結列表
                    related_links = []
                    for _, r in same_sector_stocks.iterrows():
                        link_url = get_wantgoo_url(r['symbol'])
                        status_icon = "🔥" if r.get('consecutive_days', 0) > 0 else "➡️"
                        seq_info = f" ({r.get('consecutive_days', 0)}板)" if r.get('consecutive_days', 0) > 0 else ""
                        related_links.append(f"[{r['symbol']}{seq_info} {status_icon}]({link_url})")
                    
                    # 顯示產業聯動分析
                    st.markdown(" ".join(related_links))
                    
                    # 自動生成同產業分析提示詞
                    if len(same_sector_stocks) > 0:
                        industry_stocks = same_sector_stocks.copy()
                        industry_table = industry_stocks[['symbol', 'stock_name', 'consecutive_days']].to_markdown(index=False)
                        
                        industry_prompt = f"""分析台灣股市{current_sector}產業的連動效應：

核心個股：{selected_stock['symbol']} {selected_stock['stock_name']} (連板{selected_stock.get('consecutive_days', 1)}天)
同產業漲停夥伴：{len(industry_stocks)}家

## 同產業漲停清單
{industry_table}

## 分析問題
1. **產業聯動強度**：從漲停家數看，{current_sector}是否形成板塊效應？
2. **龍頭辨識**：{selected_stock['symbol']}是否是產業龍頭？從連板天數判斷。
3. **擴散效應**：產業內漲停是否從龍頭擴散到其他個股？
4. **風險評估**：產業集體漲停後，歷史回調風險如何？
5. **操作策略**：在產業聯動效應下，最佳進出場時機為何？

請提供具體的交易策略建議。"""
                        
                        encoded_industry_prompt = urllib.parse.quote(industry_prompt)
                        st.link_button(
                            f"🤝 分析{current_sector}產業聯動效應 (ChatGPT)",
                            f"https://chatgpt.com/?q={encoded_industry_prompt}",
                            use_container_width=True
                        )
                else:
                    st.caption("暫無同產業其他公司數據")
            
            # ========== 🤖 AI 專家診斷 ==========
            st.divider()
            st.subheader(f"🤖 AI 專家診斷：{selected_stock['stock_name']}")
            
            # 自動生成個股AI提示詞
            expert_prompt = f"""你是專業短線交易員。請深度分析股票 {selected_stock['symbol']} {selected_stock['stock_name']}：

## 基本資料
- 市場：TW | 產業：{selected_stock.get('sector', 'N/A')}
- 今日狀態：連板第 {selected_stock.get('consecutive_days', 1)} 天
- 今日漲幅：{selected_stock.get('return_rate', 0):.2%}

## 股票資訊
- 股票代碼：{selected_stock['symbol']}
- 股票名稱：{selected_stock['stock_name']}
- 產業類別：{selected_stock.get('sector', 'N/A')}
- 當前價格：{selected_stock.get('price', 'N/A')}
- AI點評：{selected_stock.get('ai_comment', 'N/A')}

## 技術分析維度
1. **連板天數解析**：當前{selected_stock.get('consecutive_days', 1)}連板在市場中處於什麼位置？
2. **漲停強度分析**：今日漲幅{selected_stock.get('return_rate', 0):.2%}顯示什麼市場情緒？
3. **產業地位**：在{selected_stock.get('sector', 'N/A')}產業中的領導地位？

## 市場心理維度
4. **市場情緒**：當前連板數反映的市場情緒溫度？
5. **資金流向**：為何資金選擇這檔股票？可能的催化劑是什麼？
6. **風險偏好**：適合何種風險偏好的投資者？

## 風險控制建議
7. **最大風險**：最可能導致虧損的情境？
8. **停損策略**：基於技術分析的最佳停損點位？
9. **資金配置**：建議的單筆投資比例？

## 具體操作建議
10. **進場時機**：明日開盤、盤中、還是等待回調？
11. **出場策略**：目標價位與持有時間建議？
12. **替代方案**：如果錯過此股，同產業其他選擇？

請提供量化、具體、可執行的交易計劃。"""

            # 顯示提示詞
            with st.expander("📋 查看完整AI分析提示詞", expanded=True):
                st.code(expert_prompt, language="text")
            
            # AI平台按鈕
            col_ai1, col_ai2, col_ai3, col_ai4 = st.columns(4)
            
            with col_ai1:
                # ChatGPT一鍵帶入
                encoded_prompt = urllib.parse.quote(expert_prompt)
                st.link_button(
                    "🔥 ChatGPT 分析",
                    f"https://chatgpt.com/?q={encoded_prompt}",
                    use_container_width=True,
                    help="自動在ChatGPT中打開此股票分析"
                )
            
            with col_ai2:
                st.link_button(
                    "🔍 DeepSeek 分析",
                    "https://chat.deepseek.com/",
                    use_container_width=True,
                    help="請複製上方提示詞貼到DeepSeek"
                )
            
            with col_ai3:
                st.link_button(
                    "📘 Claude 分析",
                    "https://claude.ai/",
                    use_container_width=True,
                    help="請複製上方提示詞貼到Claude"
                )
            
            with col_ai4:
                # Gemini內建診斷（密碼保護）
                if st.session_state.gemini_authorized:
                    if st.button("🤖 Gemini 分析", use_container_width=True, type="primary"):
                        with st.spinner("Gemini正在分析中..."):
                            ai_response = call_ai_safely(expert_prompt, gemini_model)
                            if ai_response:
                                st.session_state.gemini_stock_report = ai_response
                                st.rerun()
                else:
                    st.markdown('<div class="password-protected">', unsafe_allow_html=True)
                    st.info("🔒 Gemini 需要授權解鎖")
                    auth_pw = st.text_input("授權密碼：", type="password", key="stock_gemini_pw")
                    if st.button("解鎖 Gemini", key="stock_gemini_auth"):
                        if auth_pw == st.secrets.get("AI_ASK_PASSWORD", "default_password"):
                            st.session_state.gemini_authorized = True
                            st.rerun()
                        else:
                            st.error("密碼錯誤")
                    st.markdown('</div>', unsafe_allow_html=True)
            
            # === Gemini 個股報告獨立顯示 ===
            if 'gemini_stock_report' in st.session_state:
                st.divider()
                with st.expander(f"🤖 Gemini 個股分析報告：{selected_stock['stock_name']}", expanded=True):
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
    
    else:
        st.info("📊 目前尚未偵測到今日強勢標的。")
else:
    st.error("❌ 無法載入漲停板數據")

# --- 側邊欄設定 ---
with st.sidebar:
    st.header("⚙️ 設定")
    st.subheader("🔧 系統狀態")
    status_col1, status_col2, status_col3 = st.columns(3)
    with status_col1:
        st.metric("Supabase", "✅" if supabase else "❌")
    with status_col2:
        st.metric("Gemini", "✅" if gemini_model else "❌")
    with status_col3:
        if supabase:
            df_limit = fetch_today_data("individual_stock_analysis", today)
            limit_count = len(df_limit) if not df_limit.empty else 0
            st.metric("漲停股票", f"{limit_count}" if not df_limit.empty else "0")
        else:
            st.metric("漲停股票", "0")
    
    st.divider()
    
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
    
    st.subheader("🔗 快速連結")
    st.page_link("https://chatgpt.com/", label="ChatGPT", icon="🤖")
    st.page_link("https://chat.deepseek.com/", label="DeepSeek", icon="🔍")
    st.page_link("https://claude.ai/", label="Claude", icon="📘")
    
    st.divider()
    
    st.subheader("🛠️ 除錯與維護工具")
    if st.button("🔄 強制清除所有快取並重新載入"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.success("所有快取已清除！正在重新載入最新資料...")
        st.rerun()

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
