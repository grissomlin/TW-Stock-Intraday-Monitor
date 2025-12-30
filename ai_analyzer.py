# -*- coding: utf-8 -*-
"""
AI 分析核心模組
"""
import google.generativeai as genai
import os
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from supabase import create_client
import pandas as pd
from .prompts import StockPrompts

class StockAIAnalyzer:
    """股票AI分析器"""
    
    def __init__(self, api_key: str, supabase_client=None):
        """初始化AI分析器"""
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-flash')
        self.supabase = supabase_client
        
        # 快取機制，避免重複分析
        self.analyzed_cache = {}
        
    def get_consecutive_limit_up_days(self, symbol: str) -> Dict:
        """
        查詢連續漲停天數
        返回：{'consecutive_days': int, 'recent_history': List}
        """
        if not self.supabase:
            return {'consecutive_days': 1, 'recent_history': []}
        
        try:
            # 查詢最近5天的記錄
            today = datetime.now().strftime("%Y-%m-%d")
            five_days_ago = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
            
            response = self.supabase.table("individual_stock_analysis")\
                .select("*")\
                .eq("symbol", symbol)\
                .gte("analysis_date", five_days_ago)\
                .lte("analysis_date", today)\
                .order("analysis_date", desc=True)\
                .execute()
            
            if not response.data:
                return {'consecutive_days': 1, 'recent_history': []}
            
            # 找出連續漲停天數
            consecutive_days = 0
            recent_history = []
            
            for i, record in enumerate(response.data):
                if record.get('return_rate', 0) >= 0.098:  # 漲停閾值
                    consecutive_days += 1
                    recent_history.append({
                        'date': record['analysis_date'],
                        'return': record['return_rate']
                    })
                else:
                    break
            
            return {
                'consecutive_days': consecutive_days or 1,
                'recent_history': recent_history[:3]  # 最近3天
            }
            
        except Exception as e:
            print(f"查詢連續漲停失敗 {symbol}: {e}")
            return {'consecutive_days': 1, 'recent_history': []}
    
    def analyze_individual_stock(self, stock_info: Dict) -> Optional[str]:
        """
        分析單一漲停股票
        Returns: AI分析結果
        """
        symbol = stock_info['symbol']
        
        # 檢查快取
        cache_key = f"individual_{symbol}"
        if cache_key in self.analyzed_cache:
            return self.analyzed_cache[cache_key]
        
        # 獲取連續漲停資訊
        consecutive_info = self.get_consecutive_limit_up_days(symbol)
        stock_info['consecutive_days'] = consecutive_info['consecutive_days']
        
        # 生成提示詞
        prompt = StockPrompts.get_individual_stock_prompt(
            stock_info, 
            consecutive_info['consecutive_days'],
            consecutive_info['recent_history']
        )
        
        # 呼叫AI
        try:
            response = self.model.generate_content(prompt)
            analysis = response.text
            
            # 存入快取
            self.analyzed_cache[cache_key] = analysis
            
            # 更新資料庫
            self._update_stock_analysis(symbol, analysis)
            
            return analysis
            
        except Exception as e:
            print(f"AI分析失敗 {symbol}: {e}")
            return None
    
    def analyze_sector(self, sector_name: str, stocks_in_sector: List[Dict]) -> Optional[str]:
        """
        分析產業趨勢
        Returns: AI產業分析結果
        """
        if len(stocks_in_sector) <= 1:
            return None  # 只有一家漲停，略過產業分析
        
        # 檢查快取
        cache_key = f"sector_{sector_name}"
        if cache_key in self.analyzed_cache:
            return self.analyzed_cache[cache_key]
        
        # 獲取市場環境（簡化）
        market_context = "今日大盤上漲/下跌，成交量..."  # 可從外部傳入
        
        # 生成提示詞
        prompt = StockPrompts.get_sector_analysis_prompt(
            sector_name, 
            stocks_in_sector,
            market_context
        )
        
        # 呼叫AI
        try:
            response = self.model.generate_content(prompt)
            analysis = response.text
            
            # 存入快取
            self.analyzed_cache[cache_key] = analysis
            
            # 儲存產業分析
            self._save_sector_analysis(sector_name, analysis, stocks_in_sector)
            
            return analysis
            
        except Exception as e:
            print(f"產業AI分析失敗 {sector_name}: {e}")
            return None
    
    def analyze_market_summary(self, all_stocks: List[Dict]) -> Optional[str]:
        """
        分析整體市場
        Returns: AI市場總結
        """
        # 統計產業分布
        sector_distribution = {}
        for stock in all_stocks:
            sector = stock.get('sector', '其他')
            sector_distribution[sector] = sector_distribution.get(sector, 0) + 1
        
        # 市場指標（可擴充）
        market_indicators = {
            'temperature': '熱絡' if len(all_stocks) > 20 else '溫和',
            'volume': '放大'  # 實際可從外部獲取
        }
        
        # 生成提示詞
        prompt = StockPrompts.get_market_summary_prompt(
            all_stocks,
            sector_distribution,
            market_indicators
        )
        
        # 呼叫AI
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"市場AI分析失敗: {e}")
            return None
    
    def _update_stock_analysis(self, symbol: str, ai_comment: str):
        """更新股票的AI分析到資料庫"""
        if not self.supabase:
            return
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            
            self.supabase.table("individual_stock_analysis")\
                .update({"ai_comment": ai_comment})\
                .eq("analysis_date", today)\
                .eq("symbol", symbol)\
                .execute()
                
        except Exception as e:
            print(f"更新AI分析失敗 {symbol}: {e}")
    
    def _save_sector_analysis(self, sector: str, analysis: str, stocks: List[Dict]):
        """儲存產業分析到資料庫"""
        if not self.supabase:
            return
        
        try:
            today = datetime.now().strftime("%Y-%m-%d")
            stock_symbols = [s['symbol'] for s in stocks]
            
            data = {
                "analysis_date": today,
                "sector_name": sector,
                "stock_count": len(stocks),
                "stocks_included": json.dumps(stock_symbols),
                "ai_analysis": analysis,
                "created_at": datetime.now().isoformat()
            }
            
            self.supabase.table("sector_analysis").upsert(data).execute()
            
        except Exception as e:
            print(f"儲存產業分析失敗 {sector}: {e}")
