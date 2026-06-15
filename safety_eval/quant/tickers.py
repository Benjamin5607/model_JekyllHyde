"""Ticker names and market universes (APAC + frontier)."""

TICKER_NAMES: dict[str, str] = {
    "VIC.VN": "Vingroup", "VHM.VN": "Vinhomes", "VCB.VN": "Vietcombank", "VNM.VN": "Vinamilk",
    "005930.KS": "Samsung Elec", "000660.KS": "SK Hynix", "035420.KS": "NAVER", "035720.KS": "Kakao",
    "AAPL": "Apple", "MSFT": "Microsoft", "GOOGL": "Alphabet", "AMZN": "Amazon", "NVDA": "NVIDIA",
    "META": "Meta", "TSLA": "Tesla", "AMD": "AMD",
    "APU.MN": "APU JSC", "GP.BD": "Grameenphone",
    "1299.HK": "AIA", "0700.HK": "Tencent", "9988.HK": "Alibaba HK",
    "PTT.BK": "PTT", "BBCA.JK": "BCA Indonesia", "2330.TW": "TSMC", "7203.T": "Toyota",
    "RELIANCE.NS": "Reliance", "TCS.NS": "TCS",
}

NAME_TO_TICKER: dict[str, str] = {
    "삼성전자": "005930.KS", "삼성": "005930.KS", "samsung": "005930.KS", "samsung electronics": "005930.KS",
    "sk하이닉스": "000660.KS", "sk hynix": "000660.KS", "hynix": "000660.KS", "하이닉스": "000660.KS",
    "apple": "AAPL", "nvidia": "NVDA", "테슬라": "TSLA", "tesla": "TSLA",
    "vinamilk": "VNM.VN", "vingroup": "VIC.VN", "tencent": "0700.HK", "tsmc": "2330.TW",
    "naver": "035420.KS", "kakao": "035720.KS", "reliance": "RELIANCE.NS",
}

MARKET_SAMPLES: dict[str, list[str]] = {
    "Vietnam": ["VIC.VN", "VHM.VN", "VRE.VN", "VNM.VN", "MSN.VN", "GAS.VN", "HPG.VN", "FPT.VN", "VCB.VN", "SSI.VN"],
    "USA": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "AMD", "INTC", "LLY"],
    "Korea": ["005930.KS", "000660.KS", "005380.KS", "000270.KS", "035420.KS", "035720.KS", "005490.KS"],
    "Mongolia": ["APU.MN", "TTL.MN", "GOV.MN"],
    "Bangladesh": ["GP.BD", "SQURPHARMA.BD", "BATBC.BD"],
    "Hong Kong": ["1299.HK", "0388.HK", "0005.HK", "0700.HK", "9988.HK"],
    "Thailand": ["PTT.BK", "AOT.BK", "CPALL.BK", "ADVANC.BK", "KBANK.BK"],
    "Indonesia": ["BBCA.JK", "BBRI.JK", "BMRI.JK", "TLKM.JK", "ASII.JK"],
    "Taiwan": ["2330.TW", "2317.TW", "2454.TW", "2881.TW"],
    "Japan": ["7203.T", "6758.T", "9984.T", "8035.T"],
    "India": ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS"],
}

MARKET_INDICES: dict[str, str] = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "KOSPI": "^KS11",
    "VN-INDEX": "^VNINDEX",
}
