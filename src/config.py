
# 자산 설정 (Asset Configuration)
ASSET_CONFIG = {
    "Bitcoin (BTC)": {
        "ticker": "BTC-USD",
        "cftc_name": "BITCOIN",
        "multiplier": 5, # CME BTC Contract Multiplier
        "color": "orange"
    },
    "Ethereum (ETH)": {
        "ticker": "ETH-USD",
        "cftc_name": "ETHER",
        "multiplier": 50, # CME ETH Contract Multiplier
        "color": "purple"
    }
}

# CFTC 리포트 URL 템플릿
CFTC_URL_TEMPLATE = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"

# 추출할 컬럼 목록
COLS_WE_NEED = [
    "Report_Date_as_MM_DD_YYYY", 
    "Market_and_Exchange_Names", 
    "Lev_Money_Positions_Short_All",
    "Lev_Money_Positions_Long_All",
    "Asset_Mgr_Positions_Short_All",
    "Asset_Mgr_Positions_Long_All",
    "Other_Rept_Positions_Short_All",
    "Non-Rept_Positions_Short_All"
]

# 캐시 디렉토리
CACHE_DIR = "data_cache"
