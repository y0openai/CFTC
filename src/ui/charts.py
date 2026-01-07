
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import pandas as pd

def plot_market_overview(combined_df, price_df, asset_conf, show_dollar_value=False, highlight_change=True, analysis_range=None):
    """
    Generates the dual-axis chart for Price vs Short OI.
    combined_df: Weekly merged data (CFTC + Price at that time).
    price_df: Daily price data (for smooth price line).
    """
    
    # Value Calculation ($ or Contracts)
    multiplier = asset_conf['multiplier']
    
    hf_shorts_raw = combined_df['Lev_Money_Positions_Short_All']
    asset_mgr_shorts_raw = combined_df.get('Asset_Mgr_Positions_Short_All', pd.Series([0]*len(combined_df)))
    btc_price_raw = combined_df['Close']
    x_cftc = combined_df['Date']
    
    if show_dollar_value:
        y_hf = hf_shorts_raw * btc_price_raw * multiplier
        y_am = asset_mgr_shorts_raw * btc_price_raw * multiplier
        y_axis_title = "Short Interest (USD Value)"
    else:
        y_hf = hf_shorts_raw
        y_am = asset_mgr_shorts_raw
        y_axis_title = "Short Interest (Contract Count)"

    # Highlight Logic (Insight Tool)
    bar_colors = ['blue'] * len(y_hf)
    if highlight_change:
        pct_change = y_hf.pct_change() * 100
        new_colors = []
        for chg in pct_change:
            if pd.isna(chg):
                    new_colors.append('blue')
            elif chg > 10.0:
                new_colors.append('red') # Sharp Increase (Bearish Signal)
            elif chg < -10.0:
                new_colors.append('green') # Sharp Decrease (Bullish Signal)
            else:
                new_colors.append('blue')
        bar_colors = new_colors

    # --- DRAW CHART ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    ticker_name = asset_conf['ticker'].split("-")[0] # BTC or ETH

    # 1. Price (Left - Asset Color) - Use Daily Data
    # price_df index is Date
    x_btc = price_df.index
    y_btc = price_df['Close']
    
    fig.add_trace(
        go.Scatter(x=x_btc, y=y_btc, name=f"{ticker_name} Price", line=dict(color=asset_conf['color'], width=2)),
        secondary_y=False,
    )

    # 2. Hedge Fund Shorts (Right - Bar)
    name_hf = "Hedge Funds Short"
    fig.add_trace(
        go.Bar(x=x_cftc, y=y_hf, name=name_hf, marker=dict(color=bar_colors, opacity=0.6)),
        secondary_y=True,
    )
    
    # 3. Asset Manager Shorts (Right - Red)
    fig.add_trace(
        go.Scatter(x=x_cftc, y=y_am, name="Asset Managers Short", line=dict(color='red', width=1, dash='dot')),
        secondary_y=True,
    )

    # Layout
    fig.update_layout(
        title_text=f"{ticker_name} Price vs CME Futures Short Interest",
        height=600,
        xaxis_title="Date",
        legend=dict(orientation="h", y=1.1, x=0),
        hovermode="x unified"
    )

    fig.update_yaxes(title_text=f"{ticker_name} Price (USD)", secondary_y=False)
    fig.update_yaxes(title_text=y_axis_title, secondary_y=True)

    # Analysis Range Highlight
    if analysis_range:
        sel_start_date, sel_end_date = analysis_range
        fig.add_vrect(
            x0=sel_start_date, x1=sel_end_date,
            fillcolor="green", opacity=0.1,
            layer="below", line_width=0,
            annotation_text="분석 구간", annotation_position="top left"
        )

    return fig
