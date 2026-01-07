import pandas as pd
from src.data_loader import DataLoader
import datetime

# 1. Data Loading (2023 for context, 2024-2026 for Test)
try:
    # Use Refactored Codebase
    asset_conf = {"ticker": "BTC-USD", "cftc_name": "BITCOIN", "multiplier": 5}
    combined = DataLoader.load_all_data(2023, 2026, asset_conf)

    if combined.empty:
        print("Data load failed. Combined DF is empty.")
        exit()

    # 2. Simulation Loop (From 2024-01-01)
    print(f"Total Data Points: {len(combined)}")
    print("\n[SIMULATION REPORT: Jan 2024 ~ Present]")
    print(f"{'Date':<12} | {'Pattern':<15} | {'OI(%)':<7} | {'Price(%)':<7} | {'Next 4W':<8} | {'Result'}")
    print("-" * 80)

    wins = 0
    losses = 0

    bear_raid_wins = 0
    bear_raid_count = 0

    accum_wins = 0
    accum_count = 0

    for i in range(1, len(combined) - 4): # -4 to have Next 4 Weeks Data
        curr = combined.iloc[i]
        prev = combined.iloc[i-1]
        next_week = combined.iloc[i+4] # T+4 Weeks Result (Approx 1 Month)
        
        date_str = pd.to_datetime(curr['Date']).strftime('%Y-%m-%d')
        if date_str < "2024-01-01":
            continue
            
        # Data Setup
        c_oi = curr['Lev_Money_Positions_Short_All']
        p_oi = prev['Lev_Money_Positions_Short_All']
        c_price = curr['Close']
        p_price = prev['Close']
        
        # Deltas
        if p_oi == 0 or p_price == 0: continue
        
        w_oi_pct = ((c_oi - p_oi) / p_oi) * 100
        w_price_pct = ((c_price - p_price) / p_price) * 100
        
        # Outcome (Next 4 Weeks Return)
        next_return = ((next_week['Close'] - c_price) / c_price) * 100
        
        # --- ALGORITHM LOGIC (From app.py) ---
        signal = "NEUTRAL"
        pattern = "NONE"
        
        # 1. Bear Raid (Prioritized)
        if w_price_pct < -3.0 and w_oi_pct > 5.0:
            signal = "SELL" # Expect Down
            pattern = "Bear Raid 🩸"
        
        # 2. Dip Buying (Accumulation)
        elif w_price_pct < -1.0 and w_oi_pct > 1.0:
            signal = "BUY" # Expect Rebound
            pattern = "Dip Buy 🐜"
            
        # 3. Strong Accumulation
        elif w_price_pct > 1.0 and w_oi_pct > 5.0:
            signal = "BUY" # Trend Following
            pattern = "Strong Buy 🔥"
            
        # 4. Squeeze / Profit Taking
        elif w_oi_pct < -5.0:
            if w_price_pct > 1.0:
                signal = "SELL" # Short Squeeze (Usually temporary)
                pattern = "Squeeze 💥"
            else:
                signal = "NEUTRAL"
        
        else:
            signal = "NEUTRAL"
            
        # --- Evaluation ---
        is_win = False
        
        if signal == "BUY":
            accum_count += 1
            if next_return > 0:
                is_win = True
                wins += 1
                accum_wins += 1
            else:
                losses += 1
                
        elif signal == "SELL":
            if "Bear Raid" in pattern:
                bear_raid_count += 1
                
            if next_return < 0: # Predicted Drop
                is_win = True
                wins += 1
                if "Bear Raid" in pattern: bear_raid_wins += 1
            else:
                losses += 1
        
        # Log Significant Events
        if signal != "NEUTRAL":
            res_icon = "✅ Win" if is_win else "❌ Fail"
            print(f"{date_str} | {pattern:<15} | {w_oi_pct:+.1f}%  | {w_price_pct:+.1f}%  | {next_return:+.1f}%   | {res_icon}")

    print("-" * 80)
    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    print(f"SUMMARY (4 Week Forecast)")
    print(f"Total Signals: {total_trades}")
    print(f"Overall Accuracy: {win_rate:.1f}%")

    if bear_raid_count > 0:
        print(f"Bear Raid Acc : {bear_raid_wins}/{bear_raid_count} ({(bear_raid_wins/bear_raid_count*100):.1f}%)")
    if accum_count > 0:
        print(f"Accumulation Acc: {accum_wins}/{accum_count} ({(accum_wins/accum_count*100):.1f}%)")

except Exception as e:
    print(f"Simulation Error: {e}")
