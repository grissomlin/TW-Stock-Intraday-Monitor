# -*- coding: utf-8 -*-
"""
AI 分析核心模組 - GitHub Actions 版本
"""
import os
import sys
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import pandas as pd

# 嘗試導入 google-generativeai
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ google-generativeai 未安裝: {e}")
    GEMINI_AVAILABLE = False
    genai = None

# 嘗試導入提示詞模組
try:
    from prompts import StockPrompts
    PROMPTS_AVAILABLE = True
except ImportError:
    print("⚠️ 無法導入 StockPrompts，將創建簡單替代")
    PROMPTS_AVAILABLE = False
    
    # 簡單的提示詞類替代
    class SimplePrompts:
        @staticmethod
        def get_individual_stock_prompt(stock_info, consecutive_days, recent_history=None):
            return f"分析股票: {stock_info.get('name')} ({stock_info.get('symbol')}), 連板{consecutive_days}天"
        
        @staticmethod
        def get_sector_analysis_prompt(sector_name, stocks_in_sector, market_context):
            return f"分析產業: {sector_name}, 共{len(stocks_in_sector)}檔股票漲停"
        
        @staticmethod
        def get_market_summary_prompt(all_stocks, sector_distribution, market_indicators):
            return f"分析市場總結: 共{len(all_stocks)}檔漲停"

class StockAIAnalyzer:
    """股票AI分析器"""
    
    def __init__(self, api_key: str, supabase_client=None):
        """初始化AI分析器"""
        self.supabase = supabase_client
        self.analyzed_cache = {}
        
        # 檢查Gemini是否可用
        if not GEMINI_AVAILABLE:
            print("❌ google-generativeai 不可用，AI分析功能將禁用")
            self.model = None
            return
        
        try:
            genai.configure(api_key=api_key)
            
            # 嘗試不同的模型名稱
            model_names = [
                'gemini-1.5-flash',
                'models/gemini-1.5-flash',
                'gemini-1.5-flash-latest',
                'gemini-pro'
            ]
            
            self.model = None
            for model_name in model_names:
                try:
                    self.model = genai.GenerativeModel(model_name)
                    print(f"✅ 使用模型: {model_name}")
                    break
                except Exception as e:
                    print(f"❌ 模型 {model_name} 不可用: {e}")
                    continue
            
            if self.model is None:
                print("❌ 所有模型都不可用")
            
        except Exception as e:
            print(f"❌ AI分析器初始化失敗: {e}")
            self.model = None
    
    def is_available(self):
        """檢查AI分析器是否可用"""
        return self.model is not None
    
    # ... 其餘的方法保持不變
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
