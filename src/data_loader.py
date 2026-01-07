
import os
import io
import datetime
import zipfile
import requests
import pandas as pd
import yfinance as yf
import streamlit as st
from src.config import ASSET_CONFIG, CFTC_URL_TEMPLATE, COLS_WE_NEED, CACHE_DIR

class DataLoader:
    @staticmethod
    def ensure_cache_dir():
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR)

    @staticmethod
    def download_and_read_cftc_year(year, asset_name="BITCOIN"):
        """Downloads zip for a year, extracts txt, and returns DataFrame."""
        DataLoader.ensure_cache_dir()
        
        # Check cache
        cache_file = os.path.join(CACHE_DIR, f"fin_fut_txt_{year}.txt")
        current_year = datetime.datetime.now().year
        
        df = None
        
        # Load from cache if possible (skip re-download for past years)
        if os.path.exists(cache_file) and year < current_year:
            try:
                df = pd.read_csv(cache_file, low_memory=False)
            except Exception as e:
                print(f"Error reading cache for {year}: {e}")

        # Download if needed
        if df is None:
            print(f"Downloading data for {year}...")
            url = CFTC_URL_TEMPLATE.format(year=year)
            try:
                r = requests.get(url)
                r.raise_for_status()
                
                with zipfile.ZipFile(io.BytesIO(r.content)) as z:
                    file_names = z.namelist()
                    txt_file = [f for f in file_names if f.endswith('.txt')][0]
                    
                    with z.open(txt_file) as f:
                        df = pd.read_csv(f, low_memory=False)
                        df.to_csv(cache_file, index=False)
                        
            except Exception as e:
                print(f"Failed to download or parse {year}: {e}")
                return pd.DataFrame()

        # Preprocessing
        df.columns = df.columns.str.strip()
        
        # Find Market Column
        market_col = [c for c in df.columns if 'Market' in c and 'Exchange' in c]
        if not market_col:
            return pd.DataFrame()
        market_col = market_col[0]

        # Filter by Asset Name
        target_df = df[df[market_col].str.contains(asset_name, na=False)].copy()
        
        if target_df.empty:
            return pd.DataFrame()

        # Find Date Column
        date_col = [c for c in df.columns if 'Report_Date' in c]
        if not date_col:
            return pd.DataFrame()
        date_col = date_col[0]
        
        # Parse Date
        target_df['Date'] = pd.to_datetime(target_df[date_col])
        
        return target_df

    @staticmethod
    def get_cftc_data(start_year, end_year, asset_name):
        all_dfs = []
        for y in range(start_year, end_year + 1):
            df = DataLoader.download_and_read_cftc_year(y, asset_name)
            if not df.empty:
                all_dfs.append(df)
                
        if not all_dfs:
            return pd.DataFrame()
            
        final_df = pd.concat(all_dfs)
        final_df = final_df.sort_values('Date').drop_duplicates(subset=['Date'], keep='last')
        return final_df

    @staticmethod
    def get_price_data(ticker, start_year, end_year):
        start_date = f"{start_year}-01-01"
        end_date = f"{end_year}-12-31"
        
        ticker_obj = yf.Ticker(ticker)
        price_df = ticker_obj.history(start=start_date, end=end_date)
        
        if not price_df.empty:
             # Remove timezone info for compatibility
            price_df.index = pd.to_datetime(price_df.index).tz_localize(None)
            
        return price_df

    @staticmethod
    @st.cache_data(ttl=3600*12) # Cache for 12 hours
    def load_all_data(start_year, end_year, asset_conf):
        """Loads and merges CFTC and Price data."""
        
        # 1. Load CFTC
        cftc_df = DataLoader.get_cftc_data(start_year, end_year, asset_conf['cftc_name'])
        
        # 2. Load Price
        price_df = DataLoader.get_price_data(asset_conf['ticker'], start_year, end_year)
        
        if cftc_df.empty or price_df.empty:
            return pd.DataFrame() # Return empty if fail

        # 3. Merge (AsOf Merge for Weekly CFTC + Daily Price)
        cftc_df = cftc_df.sort_values('Date')
        
        # Use 'Close' price
        combined = pd.merge_asof(
            cftc_df, 
            price_df['Close'], 
            left_on='Date', 
            right_index=True, 
            direction='nearest'
        )
        
        return combined
