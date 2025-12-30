# -*- coding: utf-8 -*-
"""
AI 提示詞管理模組
"""

class StockPrompts:
    """股票分析提示詞"""
    
    @staticmethod
    def get_individual_stock_prompt(stock_info, consecutive_days, recent_history=None):
        """
        單一股票分析提示詞
        Args:
            stock_info: 股票資訊 dict
            consecutive_days: 連續漲停天數
            recent_history: 近期價格歷史
        """
        
        # 根據連板天數設定不同的分析重點
        if consecutive_days == 1:
            stage = "第一根漲停板（啟動階段）"
            focus = """
            1. 分析這是否為突破性漲停（突破盤整、突破壓力位等）
            2. 昨日成交量與今日漲停成交量的比較
            3. 是否有消息面或基本面支撐
            4. 建議追蹤觀察，等待確認"""
        elif consecutive_days == 2:
            stage = "第二根漲停板（確認階段）"
            focus = """
            1. 分析是否形成有效突破
            2. 今日成交量是否較昨日放大（量價齊揚）
            3. 漲停板是否堅固（開板次數、委買張數）
            4. 建議可小量試單，設好停損"""
        elif consecutive_days >= 3:
            stage = f"第{consecutive_days}根漲停板（加速階段）"
            focus = """
            1. 注意是否出現過熱跡象
            2. 成交量變化（溫和放大為佳）
            3. 注意獲利了結壓力
            4. 高風險高報酬，嚴設停損點"""
        else:
            stage = "漲停板"
            focus = "一般漲停板分析"
        
        # 如果有近期歷史，加入分析
        history_analysis = ""
        if recent_history:
            history_analysis = f"""
            近期價格走勢：
            {recent_history}
            """
        
        prompt = f"""
        請以台灣股市專業分析師的身份，分析以下漲停板股票：

        ## 股票基本資訊
        - 股票名稱：{stock_info['name']}
        - 股票代碼：{stock_info['symbol']}
        - 所屬產業：{stock_info.get('sector', '未分類')}
        - 當前價格：${stock_info.get('price', 'N/A')}
        - 今日漲幅：{stock_info.get('return', 0):.2%}
        - 漲停階段：{stage}
        {history_analysis}
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
        
        return prompt
    
    @staticmethod
    def get_sector_analysis_prompt(sector_name, stocks_in_sector, market_context):
        """
        產業分析提示詞
        Args:
            sector_name: 產業名稱
            stocks_in_sector: 該產業漲停股票列表
            market_context: 市場整體狀況
        """
        
        stocks_info = "\n".join([
            f"{i+1}. {stock['name']}({stock['symbol']}) - "
            f"漲幅:{stock.get('return',0):.2%} - "
            f"連板:{stock.get('consecutive_days',1)}天"
            for i, stock in enumerate(stocks_in_sector)
        ])
        
        prompt = f"""
        請以台灣股市產業分析師身份，分析以下產業的集體漲停現象：

        ## 產業概況
        - 產業名稱：{sector_name}
        - 漲停家數：{len(stocks_in_sector)}家
        - 市場環境：{market_context}

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
        
        return prompt
    
    @staticmethod
    def get_market_summary_prompt(all_limit_up_stocks, sector_distribution, market_indicators):
        """
        整體市場分析提示詞
        Args:
            all_limit_up_stocks: 所有漲停股票
            sector_distribution: 產業分布
            market_indicators: 市場指標
        """
        
        # 統計連板情況
        consecutive_stats = {}
        for stock in all_limit_up_stocks:
            days = stock.get('consecutive_days', 1)
            consecutive_stats[days] = consecutive_stats.get(days, 0) + 1
        
        stats_text = "\n".join([
            f"- {days}連板：{count}家" 
            for days, count in sorted(consecutive_stats.items())
        ])
        
        # 產業分布文字
        sector_text = "\n".join([
            f"- {sector}: {count}家" 
            for sector, count in sector_distribution.items()
        ])
        
        prompt = f"""
        請以台灣股市首席分析師身份，分析今日市場整體狀況：

        ## 市場整體數據
        - 總漲停家數：{len(all_limit_up_stocks)}
        - 市場溫度：{market_indicators.get('temperature', 'N/A')}
        - 成交量能：{market_indicators.get('volume', 'N/A')}
        
        ## 連板統計：
        {stats_text}
        
        ## 產業分布：
        {sector_text}
        
        ## 今日市場特徵分析：

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
        
        return prompt
