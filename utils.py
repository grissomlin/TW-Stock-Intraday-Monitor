# -*- coding: utf-8 -*-

def clean_markdown(text: str) -> str:
    """
    清洗 AI 內容中的 Markdown 衝突字元，防止 Telegram 400 錯誤
    Telegram Markdown 最敏感符號：* _ [ ] ( ) `
    """
    if not text:
        return ""
    for ch in ["*", "_", "`", "[", "]", "(", ")"]:
        text = text.replace(ch, " ")
    return text.strip()

def get_stock_links(symbol: str) -> dict:
    code = str(symbol).split(".")[0]
    return {
        "玩股網": f"https://www.wantgoo.com/stock/{code}/technical-chart",
        "Goodinfo": f"https://goodinfo.tw/tw/StockBZPerformance.asp?STOCK_ID={code}",
        "鉅亨網": f"https://www.cnyes.com/twstock/{code}/",
        "Yahoo股市": f"https://tw.stock.yahoo.com/quote/{code}.TW",
        "財報狗": f"https://statementdog.com/analysis/{code}/",
        "CMoney": f"https://www.cmoney.tw/finance/f00025.aspx?s={code}",
    }
