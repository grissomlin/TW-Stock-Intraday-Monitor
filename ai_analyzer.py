# -*- coding: utf-8 -*-
"""
AI 分析核心模組 - 修正版（參考 Streamlit 成功版本）
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
    
    StockPrompts = SimplePrompts

class StockAIAnalyzer:
    """股票AI分析器"""
    
    def __init__(self, api_key: str, supabase_client=None):
        """初始化AI分析器 - 參考 Streamlit 的成功設定"""
        self.supabase = supabase_client
        self.analyzed_cache = {}
        
        # 檢查Gemini是否可用
        if not GEMINI_AVAILABLE:
            print("❌ google-generativeai 不可用，AI分析功能將禁用")
            self.model = None
            return
        
        if not api_key:
            print("❌ Gemini API Key 未提供")
            self.model = None
            return
        
        try:
            # 配置 API 金鑰
            genai.configure(api_key=api_key)
            
            # ========== 關鍵修正：使用 Streamlit 的成功方法 ==========
            # 列出所有可用模型
            available_models = []
            try:
                available_models = [m.name for m in genai.list_models() 
                                  if 'generateContent' in m.supported_generation_methods]
                print(f"✅ 可用模型: {len(available_models)} 個")
            except Exception as e:
                print(f"⚠️ 無法獲取模型列表: {e}")
            
            # 候選模型列表（按照優先順序）
            candidates = [
                'models/gemini-1.5-flash',  # Streamlit 中使用的格式
                'gemini-1.5-flash',         # 簡化格式
                'models/gemini-1.5-pro',    # Pro 版本
                'gemini-1.5-pro',
                'gemini-pro',               # 舊版
                'models/gemini-pro'
            ]
            
            # 選擇可用的模型
            target_model = None
            for candidate in candidates:
                if candidate in available_models:
                    target_model = candidate
                    break
            
            # 如果沒有匹配的候選模型，使用第一個可用模型
            if not target_model and available_models:
                target_model = available_models[0]
            
            if target_model:
                print(f"✅ 選擇模型: {target_model}")
                self.model = genai.GenerativeModel(target_model)
            else:
                print("❌ 沒有可用的模型")
                self.model = None
                
        except Exception as e:
            print(f"❌ AI分析器初始化失敗: {str(e)[:200]}")
            self.model = None
    
    def is_available(self):
        """檢查AI分析器是否可用"""
        return self.model is not None and GEMINI_AVAILABLE
    
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
            
            for record in response.data:
                return_rate = record.get('return_rate')
                is_rotc = record.get('is_rotc', False)
                threshold = 0.10 if is_rotc else 0.098
                
                # 檢查 return_rate 是否為 None
                if return_rate is None:
                    break
                
                try:
                    if float(return_rate) >= threshold:
                        consecutive_days += 1
                        recent_history.append({
                            'date': record['analysis_date'],
                            'return': return_rate
                        })
                    else:
                        break
                except (ValueError, TypeError):
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
        if not self.is_available():
            return None
            
        symbol = stock_info['symbol']
        
        # 檢查快取
        cache_key = f"individual_{symbol}"
        if cache_key in self.analyzed_cache:
            return self.analyzed_cache[cache_key]
        
        # 獲取連續漲停資訊（如果沒有提供）
        if 'consecutive_days' not in stock_info:
            consecutive_info = self.get_consecutive_limit_up_days(symbol)
            stock_info['consecutive_days'] = consecutive_info['consecutive_days']
        else:
            # 使用外部提供的連續天數
            consecutive_info = {
                'consecutive_days': stock_info['consecutive_days'],
                'recent_history': []
            }
        
        # 生成提示詞
        if PROMPTS_AVAILABLE:
            prompt = StockPrompts.get_individual_stock_prompt(
                stock_info, 
                consecutive_info['consecutive_days'],
                consecutive_info['recent_history']
            )
        else:
            # 預設提示詞
            prompt = f"""
            請分析以下漲停股票：
            股票名稱：{stock_info.get('name', 'N/A')}
            股票代碼：{stock_info.get('symbol', 'N/A')}
            產業：{stock_info.get('sector', '未分類')}
            價格：{stock_info.get('price', 'N/A')}
            漲幅：{stock_info.get('return', 0):.2%}
            連續漲停天數：{stock_info.get('consecutive_days', 1)}
            
            請提供技術面、基本面、風險評估和操作建議。
            """
        
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
            print(f"AI分析失敗 {symbol}: {str(e)[:100]}")
            return None
    
    def analyze_sector(self, sector_name: str, stocks_in_sector: List[Dict]) -> Optional[str]:
        """
        分析產業趨勢
        Returns: AI產業分析結果
        """
        if not self.is_available():
            return None
            
        if len(stocks_in_sector) <= 1:
            return None  # 只有一家漲停，略過產業分析
        
        # 檢查快取
        cache_key = f"sector_{sector_name}"
        if cache_key in self.analyzed_cache:
            return self.analyzed_cache[cache_key]
        
        # 獲取市場環境（簡化）
        market_context = "今日大盤..."
        
        # 生成提示詞
        if PROMPTS_AVAILABLE:
            prompt = StockPrompts.get_sector_analysis_prompt(
                sector_name, 
                stocks_in_sector,
                market_context
            )
        else:
            # 預設提示詞
            stocks_info = "\n".join([
                f"{i+1}. {stock['name']}({stock['symbol']}) - 漲幅:{stock.get('return',0):.2%}"
                for i, stock in enumerate(stocks_in_sector)
            ])
            prompt = f"""
            請分析以下產業的集體漲停現象：
            產業名稱：{sector_name}
            漲停家數：{len(stocks_in_sector)}家
            
            漲停股票明細：
            {stocks_info}
            
            請分析：
            1. 是否形成產業趨勢
            2. 可能的催化劑
            3. 投資建議
            """
        
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
            print(f"產業AI分析失敗 {sector_name}: {str(e)[:100]}")
            return None
    
    def analyze_market_summary(self, all_stocks: List[Dict]) -> Optional[str]:
        """
        分析整體市場
        Returns: AI市場總結
        """
        if not self.is_available():
            return None
            
        # 統計產業分布
        sector_distribution = {}
        for stock in all_stocks:
            sector = stock.get('sector', '其他')
            sector_distribution[sector] = sector_distribution.get(sector, 0) + 1
        
        # 市場指標（可擴充）
        market_indicators = {
            'temperature': '熱絡' if len(all_stocks) > 20 else '溫和',
            'volume': '一般'
        }
        
        # 生成提示詞
        if PROMPTS_AVAILABLE:
            prompt = StockPrompts.get_market_summary_prompt(
                all_stocks,
                sector_distribution,
                market_indicators
            )
        else:
            # 預設提示詞
            sector_text = "\n".join([
                f"- {sector}: {count}家" 
                for sector, count in sector_distribution.items()
            ])
            prompt = f"""
            請分析今日台股市場整體狀況：
            
            總漲停家數：{len(all_stocks)}
            產業分布：
            {sector_text}
            
            請分析市場情緒、資金流向、風險評估和明日展望。
            """
        
        # 呼叫AI
        try:
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            print(f"市場AI分析失敗: {str(e)[:100]}")
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
