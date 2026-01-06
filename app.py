
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import datetime
import cftc_loader

st.set_page_config(layout="wide", page_title="BTC Price vs Hedge Fund Short OI")

st.title("BTC Price & Hedge Fund Short Position Analysis")
st.markdown("""
이 대시보드는 **CFTC(상품선물거래위원회)의 TFF(Traders in Financial Futures) 리포트**와 **비트코인 가격**을 오버레이하여 보여줍니다.
- **주황색 (좌축):** 비트코인 가격 (USD)
- **파란색 (우축):** 헤지펀드(Leveraged Funds) 숏 포지션 수량 (계약 수 or 추정 금액)
""")

# Sidebar
st.sidebar.header("설정 (Settings)")

# Date Range
current_year = datetime.datetime.now().year
start_year = st.sidebar.number_input("시작 연도", min_value=2018, max_value=current_year, value=2023)
end_year = st.sidebar.number_input("종료 연도", min_value=2018, max_value=current_year, value=current_year)

# Option to calculate $ value
# CME Bitcoin contract size is 5 BTC.
SHOW_DOLLAR_VALUE = st.sidebar.checkbox("금액($)으로 환산하여 보기", value=False)
# Smoothing Option
USE_MA = st.sidebar.checkbox("이동평균선(MA) 적용 (4주) - 추세 보기", value=True)

@st.cache_data(ttl=3600*24)
def load_data(start_y, end_y):
    # 1. Load CFTC Data
    cftc_df = cftc_loader.get_cftc_data(start_y, end_y)
    
    # 2. Load BTC Price
    # We need price daily to match with CFTC dates or to overlay
    start_date = f"{start_y}-01-01"
    end_date = f"{end_y}-12-31"
    
    btc_ticker = yf.Ticker("BTC-USD")
    btc_df = btc_ticker.history(start=start_date, end=end_date)
    
    return cftc_df, btc_df

if start_year > end_year:
    st.error("시작 연도가 종료 연도보다 큽니다.")
else:
    with st.spinner("데이터를 가져오는 중입니다... (CFTC 리포트 다운로드 및 파싱)"):
        cftc_data, btc_data = load_data(start_year, end_year)

    if cftc_data.empty:
        st.error(f"CFTC 데이터를 찾을 수 없습니다. ({start_year}~{end_year})")
    elif btc_data.empty:
        st.error("비트코인 가격 데이터를 가져올 수 없습니다.")
    else:
        # Data Processing
        # Merge Price into CFTC data to calculate $ volume if needed
        # CFTC data is weekly (Tuesday). We'll merge the closing price of that Tuesday.
        
        # Sort both
        cftc_data = cftc_data.sort_values('Date')
        btc_data.index = pd.to_datetime(btc_data.index).tz_localize(None) # Remove timezone for merge
        
        # Merge on Date (exact match might fail if holiday, use asof or reindex. 
        # But CFTC date is "As of Tuesday of that week".
        # Let's simple merge.
        combined = pd.merge_asof(cftc_data, btc_data['Close'], left_on='Date', right_index=True, direction='nearest')
        
        # Prepare Data Series
        x_cftc = combined['Date']
        hf_shorts_raw = combined['Lev_Money_Positions_Short_All']
        asset_mgr_shorts_raw = combined.get('Asset_Mgr_Positions_Short_All', pd.Series([0]*len(combined)))
        btc_price_raw = combined['Close']

        # Value Calculation ($ or Contracts)
        if SHOW_DOLLAR_VALUE:
            # CME BTC Future = 5 BTC
            y_hf = hf_shorts_raw * btc_price_raw * 5
            y_am = asset_mgr_shorts_raw * btc_price_raw * 5
            y_axis_title = "Short Interest (USD Value)"
        else:
            y_hf = hf_shorts_raw
            y_am = asset_mgr_shorts_raw
            y_axis_title = "Short Interest (Contract Count)"

        # Apply Smoothing (Moving Average) if requested
        if USE_MA:
            y_hf = y_hf.rolling(window=4).mean() # 4 Weeks MA
            y_am = y_am.rolling(window=4).mean()
        
        # Plotting
        x_btc = btc_data.index
        y_btc = btc_data['Close']

        # --- DRAW CHART ---
        fig = make_subplots(specs=[[{"secondary_y": True}]])

        # 1. BTC Price (Left - Orange)
        # Note: In the user's reference image, BTC was Orange Line.
        # But commonly Technical Analysis uses Candlesticks or Line.
        # User requested exact reproduction of idea.
        fig.add_trace(
            go.Scatter(x=x_btc, y=y_btc, name="BTC Price", line=dict(color='orange', width=2)),
            secondary_y=False,
        )

        # 2. Hedge Fund Shorts (Right - Blue)
        name_hf = "Hedge Funds Short (4W MA)" if USE_MA else "Hedge Funds Short"
        fig.add_trace(
            go.Scatter(x=x_cftc, y=y_hf, name=name_hf, line=dict(color='blue', width=2)),
            secondary_y=True,
        )
        
        # 3. Asset Manager Shorts (Right - Red)
        fig.add_trace(
            go.Scatter(x=x_cftc, y=y_am, name="Asset Managers Short", line=dict(color='red', width=1, dash='dot')),
            secondary_y=True,
        )

        # Layout
        fig.update_layout(
            title_text=f"Bitcoin Price vs CME Futures Short Interest ({start_year}-{end_year})",
            height=600,
            xaxis_title="Date",
            legend=dict(orientation="h", y=1.1, x=0),
            hovermode="x unified"
        )

        fig.update_yaxes(title_text="BTC Price (USD)", secondary_y=False)
        fig.update_yaxes(title_text=y_axis_title, secondary_y=True)

        st.plotly_chart(fig, use_container_width=True)
        
        # --- SMART MONEY ANALYSIS ENGINE (ENHANCED) ---
        st.subheader("🤖 Smart Money Analysis & Forecast")
        
        # 1. Calculation Engine
        analysis_df = combined.copy()
        
        # Calculate Rolling 4W for trend analysis to reduce noise
        analysis_df['MA_Shorts'] = analysis_df['Lev_Money_Positions_Short_All'].rolling(window=4).mean()
        analysis_df['MA_Price'] = analysis_df['Close'].rolling(window=4).mean()
        
        recent_window = 4
        
        if len(analysis_df) > 5:
            # Current (latest) vs 4 weeks ago
            curr = analysis_df.iloc[-1]
            prev = analysis_df.iloc[-5] 
            
            # Use MA for robust trend detection? Or raw? 
            # User complained about volatility, so MA is safer for "trend detection".
            oi_curr = curr['MA_Shorts'] if pd.notna(curr['MA_Shorts']) else curr['Lev_Money_Positions_Short_All']
            oi_prev = prev['MA_Shorts'] if pd.notna(prev['MA_Shorts']) else prev['Lev_Money_Positions_Short_All']
            
            price_curr = curr['Close']
            price_prev = prev['Close']
            
            # Avoid division by zero
            if oi_prev == 0 or pd.isna(oi_prev):
                oi_delta_pct = 0
            else:
                oi_delta_pct = ((oi_curr - oi_prev) / oi_prev) * 100
            
            if price_prev == 0 or pd.isna(price_prev):
                price_delta_pct = 0
            else:
                price_delta_pct = ((price_curr - price_prev) / price_prev) * 100
            
            # Correlation (Last 12 weeks - Quarterly)
            recent_segment = analysis_df.iloc[-12:]
            if len(recent_segment) > 2:
                correlation = recent_segment['Close'].corr(recent_segment['Lev_Money_Positions_Short_All'])
            else:
                correlation = 0
                
        else:
            oi_delta_pct = 0
            price_delta_pct = 0
            correlation = 0
            
        # Handle NaN correlation
        if pd.isna(correlation):
            correlation = 0

        # 2. Logic & Evidence Engine
        phase_title = "분석 대기"
        evidence_txt = "데이터 부족"
        forecast_txt = "충분한 데이터가 없습니다."
        color = "gray"
        
        # Thresholds (%) - Tuned for Sensitivity
        # Hedge funds manage billions; a 2% shift is massive. Lowering threshold.
        SIGNIFICANT_CHANGE = 1.5 
        
        # Macro Trend Context (Last 6 Months / 24 Weeks)
        # To bridge the gap between "Micro Neutral" and "Macro Bullish"
        macro_trend = ""
        if len(analysis_df) > 24:
            macro_start = analysis_df.iloc[-24]['MA_Shorts']
            macro_end = analysis_df.iloc[-1]['MA_Shorts']
            if macro_start > 0:
                macro_change = ((macro_end - macro_start) / macro_start) * 100
                if macro_change > 10: macro_trend = "(장기 추세: 매집 중 ↗️)"
                elif macro_change < -10: macro_trend = "(장기 추세: 청산 중 ↘️)"
                else: macro_trend = "(장기 추세: 횡보 ➡️)"

        if oi_delta_pct > SIGNIFICANT_CHANGE: # OI UP
            if price_delta_pct > SIGNIFICANT_CHANGE:
                phase_title = f"🚀 상승 가속 (Fueling) {macro_trend}"
                color = "green"
                forecast_txt = "단기 상승 모멘텀이 매우 강합니다. OI가 꺾이기 전까지는 추세 추종(Trend Following) 전략이 유효합니다."
                evidence_txt = f"최근 4주간 비트코인이 **{price_delta_pct:.1f}% 상승**했고, 숏 OI도 **{oi_delta_pct:.1f}% 증가**했습니다. 상승장을 즐기며 포지션을 늘리는 전형적인 불장 패턴입니다."
            elif -SIGNIFICANT_CHANGE <= price_delta_pct <= SIGNIFICANT_CHANGE:
                phase_title = f"🔒 폭등 전조/매집 (Accumulation) {macro_trend}"
                color = "blue"
                forecast_txt = "**가장 주목해야 할 구간입니다.** 가격은 멈췄지만 고래들은 물량을 쓸어 담고 있습니다. 곧 강력한 시세 분출이 예상됩니다."
                evidence_txt = f"가격은 **{price_delta_pct:.1f}%로 제자리**인데, 숏 OI(스마트 머니)만 **{oi_delta_pct:.1f}% 급증**했습니다. 에너지가 응축되고 있습니다."
            else:
                phase_title = f"📉 헷징/방어 (Hedging) {macro_trend}"
                color = "orange"
                forecast_txt = "하락장에 대비한 방어적 포지션 구축 단계입니다. 무리한 진입을 자제하세요."
                evidence_txt = f"가격이 **{price_delta_pct:.1f}% 하락**하는데 숏 OI가 **{oi_delta_pct:.1f}% 증가**했습니다. 추가 하락을 염두에 둔 헷징 물량입니다."
                
        elif oi_delta_pct < -SIGNIFICANT_CHANGE: # OI DOWN
            if price_delta_pct < -SIGNIFICANT_CHANGE:
                phase_title = f"🌊 대규모 청산 (Unwinding) {macro_trend}"
                color = "red"
                forecast_txt = "**'떨어지는 칼날'**입니다. 이 청산 사이클이 끝나고 지표가 안정을 찾을 때(횡보)까지 롱 포지션 진입을 미루세요."
                evidence_txt = f"비트코인 **{price_delta_pct:.1f}% 하락** + 숏 OI **{oi_delta_pct:.1f}% 급감**. 차익거래 매물이 시장가로 쏟아지며 시세를 무너뜨리고 있습니다."
            elif price_delta_pct > SIGNIFICANT_CHANGE:
                phase_title = "🎁 설거지 (Distribution)"
                color = "orange"
                forecast_txt = "강력한 매도 신호입니다. 지금이 고점일 수 있습니다."
                evidence_txt = f"가격은 **{price_delta_pct:.1f}% 올랐지만**, 스마트 머니는 숏을 **{oi_delta_pct:.1f}% 줄이며** 탈출 중입니다. 개미에게 물량을 넘기는 중입니다."
            else:
                phase_title = "💤 관심 이탈"
                color = "gray"
                forecast_txt = "관망하세요."
                evidence_txt = "가격과 OI 모두 뚜렷한 감소세를 보이며 시장 관심이 식고 있습니다."
        else:
            phase_title = "⚖️ 균형 (Equilibrium)"
            color = "green" if price_delta_pct > -5 else "gray"
            forecast_txt = "매도세가 진정되었습니다. 저점 매수를 고려해 볼 만합니다."
            evidence_txt = f"최근 1달간 숏 OI 변화가 **{oi_delta_pct:.1f}%**로 안정적입니다. 거대 자본의 이탈이 멈췄습니다."

        # 3. Render UI
        with st.container():
            st.markdown(f"### 📢 분석 결과: :{color}[{phase_title}]")
            
            c1, c2 = st.columns(2)
            with c1:
                st.info(f"**📊 판단 근거 (Evidence):**\n\n{evidence_txt}")
            
            with c2:
                if color == "red":
                    st.error(f"**🔮 향후 전망 (Forecast):**\n\n{forecast_txt}")
                elif color == "green":
                    st.success(f"**🔮 향후 전망 (Forecast):**\n\n{forecast_txt}")
                elif color == "blue":
                    st.info(f"**🔮 향후 전망 (Forecast):**\n\n{forecast_txt}")
                else:
                    st.warning(f"**🔮 향후 전망 (Forecast):**\n\n{forecast_txt}")

            st.markdown(f"""
            <small>
            * 분석 기준: 최근 {recent_window}주 데이터 변화율 (Price: {price_delta_pct:.1f}%, Short OI: {oi_delta_pct:.1f}%) <br>
            * 상관계수(Correlation, 12W): {correlation:.2f} ({'동조화' if correlation > 0.5 else '역상관' if correlation < -0.5 else '비상관'})
            </small>
            """, unsafe_allow_html=True)

        # --- RAW DATA ---
        with st.expander("원본 데이터 보기"):
            st.dataframe(combined[['Date', 'Lev_Money_Positions_Short_All', 'Close']].style.format({'Close': '{:.2f}'}))

