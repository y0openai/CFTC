
import pandas as pd
import requests
import zipfile
import io
import os
import datetime

# CFTC TFF Report URL Format
# Correct URL: https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip
CFTC_URL_TEMPLATE = "https://www.cftc.gov/files/dea/history/fut_fin_txt_{year}.zip"

# Columns to extract
# We need:
# 1. Report_Date_as_MM_DD_YYYY: Date
# 2. Market_and_Exchange_Names: Filter for "BITCOIN - CHICAGO MERCANTILE EXCHANGE"
# 3. Lev_Money_Positions_Short_All: Hedge Fund Short
# 4. Lev_Money_Positions_Long_All: Hedge Fund Long (for context)
# 5. Asset_Mgr_Positions_Short_All: Asset Manager Short
# 6. Asset_Mgr_Positions_Long_All: Asset Manager Long
# 7. Other_Rept_Positions_Short_All: Other Short
# 8. Dealer_Positions_Short_All: Dealer Short (optional, but good to have)

COLS_WE_NEED = [
    "Report_Date_as_MM_DD_YYYY", 
    "Market_and_Exchange_Names", 
    "Lev_Money_Positions_Short_All",
    "Lev_Money_Positions_Long_All",
    "Asset_Mgr_Positions_Short_All",
    "Asset_Mgr_Positions_Long_All",
    "Other_Rept_Positions_Short_All",
    "Non-Rept_Positions_Short_All" # Sometimes useful
]

CACHE_DIR = "data_cache"

def ensure_cache_dir():
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

def download_and_read_year(year):
    """Downloads zip for a year, extracts txt, and returns DataFrame."""
    ensure_cache_dir()
    
    # Check if we already have the unzipped csv/txt
    cache_file = os.path.join(CACHE_DIR, f"fin_fut_txt_{year}.txt")
    
    # For current year, always re-download or check freshness
    # For past years, cache is fine.
    current_year = datetime.datetime.now().year
    
    df = None
    
    if os.path.exists(cache_file) and year < current_year:
        print(f"Loading cached data for {year}")
        try:
             df = pd.read_csv(cache_file, low_memory=False)
        except Exception as e:
            print(f"Error reading cache for {year}, re-downloading... {e}")

    if df is None:
        print(f"Downloading data for {year}...")
        url = CFTC_URL_TEMPLATE.format(year=year)
        try:
            r = requests.get(url)
            r.raise_for_status()
            
            with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                # The zip usually contains a file named 'fin_fut_txt_{year}.txt' or similar.
                # Let's find the txt file.
                file_names = z.namelist()
                txt_file = [f for f in file_names if f.endswith('.txt')][0]
                
                with z.open(txt_file) as f:
                    # Read directly into pandas
                    df = pd.read_csv(f, low_memory=False)
                    
                    # Save to cache
                    df.to_csv(cache_file, index=False)
                    
        except Exception as e:
            print(f"Failed to download or parse {year}: {e}")
            return pd.DataFrame() # Return empty on failure

    # Normalize columns
    # Strip whitespace from column names just in case
    df.columns = df.columns.str.strip()
    
    # DEBUG: Print columns to find the correct Date column name
    # print(f"Columns found for {year}: {df.columns.tolist()}")

    # Filter for Bitcoin
    # Search for "BITCOIN" in Market names
    # Column might be 'Market_and_Exchange_Names' or 'Market_and_Exchange_Names ' etc.
    # Let's find the market column dynamically
    market_col = [c for c in df.columns if 'Market' in c and 'Exchange' in c]
    if not market_col:
        print(f"Error: Could not find Market column. Available: {df.columns.tolist()}")
        return pd.DataFrame()
    market_col = market_col[0]

    btc_df = df[df[market_col].str.contains("BITCOIN", na=False)].copy()
    
    # Find Date column dynamically
    date_col = [c for c in df.columns if 'Report_Date' in c]
    if not date_col:
        print("Error: Date column not found.")
        return pd.DataFrame()
    date_col = date_col[0]
    
    # Other columns mapping
    # We need to map our expected generic names to actual names if they differ
    # For now, let's just rename the critical ones if found
    
    # Parse Date
    btc_df['Date'] = pd.to_datetime(btc_df[date_col])
    
    return btc_df

def get_cftc_data(start_year, end_year):
    all_dfs = []
    for y in range(start_year, end_year + 1):
        df = download_and_read_year(y)
        if not df.empty:
            all_dfs.append(df)
            
    if not all_dfs:
        return pd.DataFrame()
        
    final_df = pd.concat(all_dfs)
    final_df = final_df.sort_values('Date')
    return final_df

if __name__ == "__main__":
    # Test
    data = get_cftc_data(2023, 2026)
    print(data.head())
    print(data.tail())
