
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import datetime
import cftc_loader

st.set_page_config(layout="wide", page_title="Crypto Price vs Hedge Fund Short OI")

st.title("Crypto Price & Hedge Fund Short Position Analysis")
st.markdown("""
이 대시보드는 **CFTC(상품선물거래위원회)의 TFF(Traders in Financial Futures) 리포트**와 **코인 가격**을 오버레이하여 보여줍니다.
- **주황색/보라색 (좌축):** 코인 가격 (USD)
- **파란색 (우축):** 헤지펀드(Leveraged Funds) 숏 포지션 수량 (계약 수 or 추정 금액)
""")

# Sidebar
st.sidebar.header("설정 (Settings)")

# Asset Selection
ASSET_CONFIG = {
    "Bitcoin (BTC)": {
        "ticker": "BTC-USD",
        "cftc_name": "BITCOIN",
        "multiplier": 5,
        "color": "orange"
    },
    "Ethereum (ETH)": {
        "ticker": "ETH-USD",
        "cftc_name": "ETHER",
        "multiplier": 50,
        "color": "purple" # Ethereum brand color
    }
}
selected_asset_name = st.sidebar.selectbox("분석 대상 코인", list(ASSET_CONFIG.keys()))
asset_conf = ASSET_CONFIG[selected_asset_name]

# Date Range
current_year = datetime.datetime.now().year
start_year = st.sidebar.number_input("시작 연도", min_value=2018, max_value=current_year, value=2023)
end_year = st.sidebar.number_input("종료 연도", min_value=2018, max_value=current_year, value=current_year)

# Option to calculate $ value
SHOW_DOLLAR_VALUE = st.sidebar.checkbox(f"금액($)으로 환산하여 보기 (Contract * Price * {asset_conf['multiplier']})", value=False)
# Smoothing Option
USE_MA = st.sidebar.checkbox("이동평균선(MA) 적용 (4주) - 추세 보기", value=True)

# Educational Content
st.sidebar.markdown("---")
with st.sidebar.expander("🎓 초보 트레이더를 위한 가르침"):
    st.markdown("""
    ### 1. 왜 헤지펀드는 '숏(Short)'을 칠까요?
    초보자는 **'숏 = 하락 배팅'**이라고 생각하기 쉽습니다. 하지만 이 차트에서 헤지펀드의 숏은 전혀 다른 의미입니다.
    
    그들은 가격을 맞추는 도박을 하지 않습니다. 대신 **'무위험 차익거래(Arbitrage)'**를 합니다. 이를 **캐시 앤 캐리(Cash-and-Carry)** 전략이라고 부릅니다.
    
    ### 2. 역설: 숏이 늘어나면 왜 가격이 오르나요?
    선물 가격은 보통 현물보다 비쌉니다(수수료/기대감 등). 헤지펀드는 이 '가격 차이(Premium)' 따먹기를 합니다.
    
    1.  **현물을 산다 (Buy Spot) 📈** → 가격 상승 유발
    2.  동시에 **선물을 판다 (Short Future) 📉** → 헤지펀드 숏 OI 증가
    
    즉, 차트의 **파란선(숏 물량)이 치솟는다는 것**은, 뒤에서 기관들이 **비트코인 현물을 미친듯이 사모으고 있다는 강력한 증거**입니다.
    
    ### 3. 왜 2024년부터 중요한가요?
    비트코인 ETF 승인 이후, 월가(Wall St.)의 거대 자본이 시장에 들어왔습니다. 이들은 코인의 미래를 믿어서라기보다, **안정적인 10~15%의 연수익(이자)**을 노리고 들어온 자금입니다.
    
    따라서 2024년 이후의 비트코인 가격은 이 **'이자 농사꾼(헤지펀드)'들이 돈을 넣느냐(현물 매수), 돈을 빼느냐(현물 매도)**에 따라 움직이는 경향이 매우 강해졌습니다.
    
    **💡 요약:** 파란선(숏) 급등을 두려워 마세요. 그것은 로켓의 연료(현물 매수)가 채워지고 있다는 뜻입니다.

    ### 4. 심화: 같이 가느냐, 따로 가느냐 (Correlation)
    항상 같이 오르는 것은 아닙니다. 두 선의 **'방향 관계'**를 해석하는 것이 고수의 영역입니다.

    *   **✅ 동조화 (Sync ↗️↗️):** 가격 상승 + 숏 증가
        *   **해석:** "찐반(진짜 반등)". 현물을 사모으면서 헷징을 하는 건전한 상승장입니다. 상승 추세가 길게 지속될 가능성이 높습니다.
    
    *   **❌ 역상관 A (Divergence ↗️↘️):** 가격 상승 + 숏 감소
        *   **해석:** **"숏 스퀴즈(Short Squeeze)"**. 현물 매수세가 아니라, 공매도친 세력이 손해를 보며 도망치느라 가격이 급등하는 것입니다. 단기 급등 후 폭락할 위험이 큽니다.
        
    *   **⚠️ 역상관 B (Divergence ↘️↗️):** 가격 하락 + 숏 증가
        *   **해석:** **"하락 배팅"**. 이 경우의 숏은 차익거래가 아니라, 진짜로 가격이 떨어질 것에 돈을 거는 '투기적 공매도'일 수 있습니다. 추가 하락을 조심해야 합니다.
    """)

@st.cache_data(ttl=3600*24)
def load_data(start_y, end_y, conf):
    # 1. Load CFTC Data
    cftc_df = cftc_loader.get_cftc_data(start_y, end_y, asset_name=conf['cftc_name'])
    
    # 2. Load Price
    start_date = f"{start_y}-01-01"
    end_date = f"{end_y}-12-31"
    
    ticker = yf.Ticker(conf['ticker'])
    price_df = ticker.history(start=start_date, end=end_date)
    
    return cftc_df, price_df

if start_year > end_year:
    st.error("시작 연도가 종료 연도보다 큽니다.")
else:
    with st.spinner(f"{selected_asset_name} 데이터를 가져오는 중입니다..."):
        cftc_data, btc_data = load_data(start_year, end_year, asset_conf)

    if cftc_data.empty:
        st.error(f"CFTC 데이터를 찾을 수 없습니다. ({start_year}~{end_year}) - {asset_conf['cftc_name']}")
    elif btc_data.empty:
        st.error(f"{asset_conf['ticker']} 가격 데이터를 가져올 수 없습니다.")
    else:
        # Data Processing
        cftc_data = cftc_data.sort_values('Date')
        btc_data.index = pd.to_datetime(btc_data.index).tz_localize(None) 
        
        combined = pd.merge_asof(cftc_data, btc_data['Close'], left_on='Date', right_index=True, direction='nearest')
        
        # Prepare Data Series
        x_cftc = combined['Date']
        hf_shorts_raw = combined['Lev_Money_Positions_Short_All']
        asset_mgr_shorts_raw = combined.get('Asset_Mgr_Positions_Short_All', pd.Series([0]*len(combined)))
        btc_price_raw = combined['Close']

        # Value Calculation ($ or Contracts)
        multiplier = asset_conf['multiplier']
        if SHOW_DOLLAR_VALUE:
            y_hf = hf_shorts_raw * btc_price_raw * multiplier
            y_am = asset_mgr_shorts_raw * btc_price_raw * multiplier
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
        
        ticker_name = asset_conf['ticker'].split("-")[0] # BTC or ETH

        # 1. Price (Left - Asset Color)
        fig.add_trace(
            go.Scatter(x=x_btc, y=y_btc, name=f"{ticker_name} Price", line=dict(color=asset_conf['color'], width=2)),
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
            title_text=f"{ticker_name} Price vs CME Futures Short Interest ({start_year}-{end_year})",
            height=600,
            xaxis_title="Date",
            legend=dict(orientation="h", y=1.1, x=0),
            hovermode="x unified"
        )

        fig.update_yaxes(title_text=f"{ticker_name} Price (USD)", secondary_y=False)
        fig.update_yaxes(title_text=y_axis_title, secondary_y=True)

        # --- ANALYSIS DATE SELECTOR (RANGE) ---
        st.write("---")
        st.markdown("### 🕰 타임머신 구간 분석 (Historical Range Analysis)")
        st.write("슬라이더의 양쪽 끝을 조절하여 **분석하고 싶은 구간(예: 상승장 초입)**을 지정하세요.")
        
        min_date = combined['Date'].min().date()
        max_date = combined['Date'].max().date()
        
        # Default: Last 12 weeks
        default_start = max_date - datetime.timedelta(weeks=12)
        
        analysis_range = st.slider(
            "분석 구간 설정",
            min_value=min_date,
            max_value=max_date,
            value=(default_start, max_date),
            format="YYYY-MM-DD"
        )
        
        sel_start_date, sel_end_date = analysis_range
        
        # Highlight Selected Range on Chart
        fig.add_vrect(
            x0=sel_start_date, x1=sel_end_date,
            fillcolor="green", opacity=0.1,
            layer="below", line_width=0,
            annotation_text="분석 구간", annotation_position="top left"
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # --- SMART MONEY ANALYSIS ENGINE (DYNAMIC RANGE) ---
        st.subheader(f"🤖 Smart Money Analysis & Forecast (구간: {sel_start_date} ~ {sel_end_date})")
        
        # 1. Calculation Engine
        # Filter data within range
        range_df = combined[(combined['Date'].dt.date >= sel_start_date) & 
                            (combined['Date'].dt.date <= sel_end_date)].copy()
        
        weeks_duration = len(range_df)
        
        if weeks_duration < 2:
            st.warning("분석을 위해 최소 2주 이상의 구간을 선택해주세요.")
            oi_delta_pct = 0
            price_delta_pct = 0
            correlation = 0
        else:
            # Start vs End of the selection
            # Use RAW data for Start and End points to capture exact change
            start_row = range_df.iloc[0]
            end_row = range_df.iloc[-1]
            
            oi_start = start_row['Lev_Money_Positions_Short_All']
            oi_end = end_row['Lev_Money_Positions_Short_All']
            
            price_start = start_row['Close']
            price_end = end_row['Close']
            
            # Change Calculation
            if oi_start == 0 or pd.isna(oi_start): oi_delta_pct = 0
            else: oi_delta_pct = ((oi_end - oi_start) / oi_start) * 100
                
            if price_start == 0 or pd.isna(price_start): price_delta_pct = 0
            else: price_delta_pct = ((price_end - price_start) / price_start) * 100
            
            # Correlation for the selected range
            if len(range_df) > 2:
                correlation = range_df['Close'].corr(range_df['Lev_Money_Positions_Short_All'])
            else:
                correlation = 0
                
        # Handle NaN correlation
        if pd.isna(correlation): correlation = 0
            
        # Macro Trend Context (Last 6 Months relative to SELECTION END)
        # We need the full combined df up to sel_end_date for macro context
        # Filter full history up to selection end
        history_df = combined[combined['Date'].dt.date <= sel_end_date].copy()
        history_df['MA_Shorts'] = history_df['Lev_Money_Positions_Short_All'].rolling(window=4).mean()
        
        macro_trend = ""
        if len(history_df) > 24:
            macro_start = history_df.iloc[-24]['MA_Shorts']
            macro_end = history_df.iloc[-1]['MA_Shorts']
            if macro_start > 0:
                macro_change = ((macro_end - macro_start) / macro_start) * 100
                if macro_change > 10: macro_trend = "(장기 추세: 매집 중 ↗️)"
                elif macro_change < -10: macro_trend = "(장기 추세: 청산 중 ↘️)"
                else: macro_trend = "(장기 추세: 횡보 ➡️)"

        # 2. Logic & Evidence Engine
        phase_title = "분석 대기"
        evidence_txt = "데이터 부족"
        forecast_txt = "충분한 데이터가 없습니다."
        color = "gray"
        
        # Thresholds (%) - Tuned for Sensitivity
        # Hedge funds manage billions; a 2% shift is massive. Lowering threshold.
        SIGNIFICANT_CHANGE = 1.5 
        
        if oi_delta_pct > SIGNIFICANT_CHANGE: # OI UP
            if price_delta_pct > SIGNIFICANT_CHANGE:
                phase_title = f"🚀 상승 가속 (Fueling) {macro_trend}"
                color = "green"
                forecast_txt = "상승 추세가 매우 견고합니다. OI가 꺾이기 전까지는 추세 추종(Trend Following) 전략이 유효합니다."
                evidence_txt = f"선택 구간 동안 **{ticker_name}** 가격이 **{price_delta_pct:.1f}% 상승**하는 동안, 헤지펀드도 숏 물량을 **{oi_delta_pct:.1f}%나 더 쌓았습니다**. 이것은 '상승 프리미엄'을 노린 동반 매수세입니다."
            elif -SIGNIFICANT_CHANGE <= price_delta_pct <= SIGNIFICANT_CHANGE:
                phase_title = f"🔒 폭등 전조/매집 (Accumulation) {macro_trend}"
                color = "blue"
                forecast_txt = "**가장 주목해야 할 구간입니다.** 가격은 멈췄지만 고래들은 물량을 쓸어 담고 있습니다. 강력한 시세 분출이 일어났던 구간일 확률이 높습니다."
                evidence_txt = f"가격은 **{price_delta_pct:.1f}%로 제자리**인데, 숏 OI(스마트 머니)만 **{oi_delta_pct:.1f}% 급증**했습니다. 에너지가 응축되었던 구간입니다."
            else:
                phase_title = f"📉 헷징/방어 (Hedging) {macro_trend}"
                color = "orange"
                forecast_txt = "하락장에 대비한 방어적 포지션 구축 단계입니다. 무리한 진입을 자제하세요."
                evidence_txt = f"가격이 **{price_delta_pct:.1f}% 하락**하는데 숏 OI가 **{oi_delta_pct:.1f}% 증가**했습니다. 추가 하락을 염두에 둔 헷징 물량입니다."
                
        elif oi_delta_pct < -SIGNIFICANT_CHANGE: # OI DOWN
            if price_delta_pct < -SIGNIFICANT_CHANGE:
                phase_title = f"🌊 대규모 청산 (Unwinding) {macro_trend}"
                color = "red"
                forecast_txt = "**'떨어지는 칼날'** 구간입니다. 이 청산 사이클이 끝나고 지표가 안정을 찾을 때(횡보)까지 롱 포지션 진입을 미루세요."
                evidence_txt = f"**{ticker_name}** **{price_delta_pct:.1f}% 하락** + 숏 OI **{oi_delta_pct:.1f}% 급감**. 차익거래 매물이 시장가로 쏟아지며 시세를 무너뜨린 구간입니다."
            elif price_delta_pct > SIGNIFICANT_CHANGE:
                phase_title = "🎁 설거지 (Distribution)"
                color = "orange"
                forecast_txt = "강력한 고점 신호입니다. 가격은 오르는데 세력은 이탈했습니다."
                evidence_txt = f"가격은 **{price_delta_pct:.1f}% 올랐지만**, 스마트 머니는 숏을 **{oi_delta_pct:.1f}% 줄이며** 오히려 탈출했습니다. 개미에게 물량을 넘긴 전형적인 설거지 구간입니다."
            else:
                phase_title = "💤 관심 이탈"
                color = "gray"
                forecast_txt = "관망 구간입니다."
                evidence_txt = "가격과 OI 모두 뚜렷한 감소세를 보이며 시장 관심이 식었습니다."
        else:
            phase_title = "⚖️ 균형 (Equilibrium)"
            color = "green" if price_delta_pct > -5 else "gray"
            forecast_txt = "매도세가 진정되었습니다. 저점 매수를 고려해 볼 만합니다."
            evidence_txt = f"선택 구간 동안 숏 OI 변화가 **{oi_delta_pct:.1f}%**로 안정적입니다. 거대 자본의 이탈이 멈췄습니다."

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
            * 분석 기준: 선택 구간 ({pd.Timestamp(sel_start_date).strftime('%Y-%m-%d')} ~ {pd.Timestamp(sel_end_date).strftime('%Y-%m-%d')}, {weeks_duration}주) <br>
            * 구간 수익률: Price **{price_delta_pct:.1f}%** / Short OI **{oi_delta_pct:.1f}%** <br>
            * 상관계수(Correlation): {correlation:.2f} ({'동조화' if correlation > 0.5 else '역상관' if correlation < -0.5 else '비상관'})
            </small>
            """, unsafe_allow_html=True)

        # --- RAW DATA ---
        with st.expander("원본 데이터 보기"):
            st.dataframe(combined[['Date', 'Lev_Money_Positions_Short_All', 'Close']].style.format({'Close': '{:.2f}'}))
