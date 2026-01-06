
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import datetime
import cftc_loader

st.set_page_config(layout="wide", page_title="Crypto Price vs Hedge Fund Short OI")

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("메뉴 (Menu)")
page = st.sidebar.radio("이동하실 페이지를 선택하세요:", ["📊 차트 분석 (Analysis)", "🎓 초보자 가이드 (Guide)"])
st.sidebar.markdown("---")

# ==========================================
# PAGE 1: CHART ANALYSIS
# ==========================================
if page == "📊 차트 분석 (Analysis)":
    st.title("Crypto Price & Hedge Fund Short Position Analysis")
    st.markdown("""
    이 대시보드는 **CFTC(상품선물거래위원회)의 TFF(Traders in Financial Futures) 리포트**와 **코인 가격**을 오버레이하여 보여줍니다.
    - **주황색/보라색 (좌축):** 코인 가격 (USD)
    - **파란색 (우축):** 헤지펀드(Leveraged Funds) 숏 포지션 수량 (계약 수 or 추정 금액)
    """)

    # Sidebar Settings (Only for Analysis Page)
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

            # 2. Logic & Evidence Engine (Multi-Timeframe Analysis)
            # A. Define Timeframes
            # (1) Range (Full Selection)
            # (2) Latest 1 Week (Immediate Action)
            # (3) Recent 1 Month (Short-term Trend)
            
            # --- Metrics Calculation ---
            # 1. Range (Start vs End)
            range_oi_delta = ((range_df.iloc[-1]['Lev_Money_Positions_Short_All'] - range_df.iloc[0]['Lev_Money_Positions_Short_All']) / range_df.iloc[0]['Lev_Money_Positions_Short_All']) * 100
            range_price_delta = ((range_df.iloc[-1]['Close'] - range_df.iloc[0]['Close']) / range_df.iloc[0]['Close']) * 100
            range_corr = correlation
            
            # 2. Latest 1 Week (Last vs 2nd Last)
            if len(range_df) >= 2:
                latest_oi = range_df.iloc[-1]['Lev_Money_Positions_Short_All']
                prev_oi = range_df.iloc[-2]['Lev_Money_Positions_Short_All']
                latest_price = range_df.iloc[-1]['Close']
                prev_price = range_df.iloc[-2]['Close']
                
                one_w_oi_delta = ((latest_oi - prev_oi) / prev_oi) * 100 if prev_oi != 0 else 0
                one_w_price_delta = ((latest_price - prev_price) / prev_price) * 100 if prev_price != 0 else 0
            else:
                one_w_oi_delta = 0
                one_w_price_delta = 0
                
            # 3. Recent 1 Month (Last vs 5th Last)
            if len(range_df) >= 5:
                prev_1m_oi = range_df.iloc[-5]['Lev_Money_Positions_Short_All']
                one_m_oi_delta = ((range_df.iloc[-1]['Lev_Money_Positions_Short_All'] - prev_1m_oi) / prev_1m_oi) * 100 if prev_1m_oi != 0 else 0
            else:
                one_m_oi_delta = range_oi_delta # Fallback
            
            # --- Interpretation Logic ---
            
            # 1. Analyze Core Trend (Based on Correlation & Range)
            trend_status = "중립/횡보"
            trend_desc = "뚜렷한 방향성 없이 등락을 반복했습니다."
            trend_color = "gray"
            
            if range_corr > 0.5:
                if range_oi_delta > 5: 
                    trend_status = "매집 우위 (Accumulation)"
                    trend_desc = "기간 동안 가격과 숏 OI가 동반 상승했습니다. 헤지펀드의 지속적인 매집세가 관찰됩니다."
                    trend_color = "green"
                elif range_oi_delta < -5:
                    trend_status = "청산 우위 (Distribution)"
                    trend_desc = "기간 동안 가격과 숏 OI가 동반 하락했습니다. 차익거래 포지션을 정리하는 추세였습니다."
                    trend_color = "red"
            elif range_corr < -0.5:
                if range_oi_delta < 0 and range_price_delta > 0:
                    trend_status = "숏 스퀴즈 (Squeeze)"
                    trend_desc = "가격은 올랐지만 숏 물량은 줄었습니다. 손절매성 청산이 상승을 주도했습니다."
                    trend_color = "orange"
                elif range_oi_delta > 0 and range_price_delta < 0:
                    trend_status = "하락 배팅 (Bearish Bet)"
                    trend_desc = "가격 하락에도 불구하고 숏 물량이 늘었습니다. 투기적 하락 배팅 추세입니다."
                    trend_color = "red"
            
            # 2. Analyze Latest Action (Change of Heart?)
            action_status = ""
            action_desc = ""
            
            if one_w_oi_delta > 2.0:
                action_status = "급격한 매집 📈"
                action_desc = f"마지막 주에 숏 OI가 **{one_w_oi_delta:.1f}% 급증**했습니다. 다시 포지션을 구축하고 있습니다."
            elif one_w_oi_delta < -2.0:
                action_status = "긴급 이탈/청산 📉"
                action_desc = f"마지막 주에 숏 OI가 **{one_w_oi_delta:.1f}% 급감**했습니다. 단기적인 자금 이탈이 발생했습니다."
            else:
                action_status = "관망/유지 ✊"
                action_desc = f"마지막 주 변동폭이 미미합니다({one_w_oi_delta:.1f}%). 기존 포지션을 유지하고 있습니다."

            # 3. Final Synthesis (Verdict)
            final_verdict = ""
            final_color = "gray"
            
            # Logic: Conflict Check
            if "매집" in trend_status and "이탈" in action_status:
                final_verdict = "⚠️ 추세 이탈 경고 (Reversal Warning)"
                final_synth = "전체적으로는 매집 구간이었으나, **가장 최근(1주) 헤지펀드가 갑자기 물량을 던지고 있습니다.** 상승 추세가 꺾일 위험이 있으니 주의가 필요합니다."
                final_color = "orange"
            elif "청산" in trend_status and "매집" in action_status:
                final_verdict = "💎 저점 매수 신호 (Re-Entry)"
                final_synth = "지루한 청산(하락) 추세였으나, **가장 최근(1주) 다시 자금이 유입되기 시작했습니다.** 추세 반전(상승)의 초입일 수 있습니다."
                final_color = "blue"
            elif "매집" in trend_status and "매집" in action_status:
                final_verdict = "🔥 강력 상승 지속 (Strong Buy)"
                final_synth = "장기적으로도 매집 중이고, **지금 당장도 더 강력하게 사고 있습니다.** 상승 모멘텀이 매우 강합니다."
                final_color = "green"
            elif "청산" in trend_status and "이탈" in action_status:
                final_verdict = "🩸 패닉 셀링 (Strong Sell)"
                final_synth = "물량이 계속 빠지고 있으며, **최근에는 더 빠른 속도로 도망치고 있습니다.** 절대 진입 금지 구간입니다."
                final_color = "red"
            else:
                 final_verdict = f"{trend_status} + {action_status}"
                 final_synth = f"전체적으로 {trend_status} 흐름을 보이고 있으며, 최근 행동 또한 {action_status} 상태로 일관적입니다. 큰 변곡점은 보이지 않습니다."
                 final_color = trend_color

            # --- UI RENDERING ---
            with st.container():
                st.markdown(f"### 📢 AI 종합 분석: :{final_color}[{final_verdict}]")
                st.info(f"**💡 핵심 요약:** {final_synth}")
                
                # Tab Structure for Detail
                tab1, tab2 = st.tabs(["📝 상세 분석 리포트", "🔢 기간별 수치 데이터"])
                
                with tab1:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("#### 1. 전체 흐름 (Trend)")
                        st.markdown(f"**상태:** :{trend_color}[{trend_status}]")
                        st.caption(trend_desc)
                        st.markdown(f"- **상관계수:** {range_corr:.2f}")
                        st.markdown(f"- **총 OI 변동:** {range_oi_delta:+.1f}%")
                        
                    with col2:
                        st.markdown("#### 2. 최근 행동 (Latest Action)")
                        st.markdown(f"**상태:** **{action_status}**")
                        st.caption(action_desc)
                        st.markdown(f"- **1주 변동:** {one_w_oi_delta:+.1f}%")
                        st.markdown(f"- **가격 변동:** {one_w_price_delta:+.1f}%")

                with tab2:
                    metric_cols = st.columns(3)
                    metric_cols[0].metric("전체 기간 (Range)", f"{range_oi_delta:+.1f}%", f"Price {range_price_delta:+.1f}%")
                    metric_cols[1].metric("최근 1달 (1M)", f"{one_m_oi_delta:+.1f}%", "Shorts Momentum")
                    metric_cols[2].metric("최근 1주 (1W)", f"{one_w_oi_delta:+.1f}%", f"Price {one_w_price_delta:+.1f}%")
                    
                st.markdown(f"""
                <small>
                * 분석 대상: {sel_start_date} ~ {sel_end_date} (총 {weeks_duration}주 데이터) <br>
                * 과거의 데이터는 미래를 보장하지 않습니다. 참고용으로만 활용하세요.
                </small>
                """, unsafe_allow_html=True)

            # --- RAW DATA ---
            with st.expander("원본 데이터 보기"):
                st.dataframe(combined[['Date', 'Lev_Money_Positions_Short_All', 'Close']].style.format({'Close': '{:.2f}'}))
            
            # --- EDUCATIONAL CONTENT (Main Area - Short Summary) ---
            st.write("---")
            st.info("💡 자세한 해설과 교육 자료가 필요하시면 좌측 메뉴의 **[🎓 초보자 가이드]**를 클릭하세요.")

# ==========================================
# PAGE 2: EDUCATIONAL GUIDE
# ==========================================
elif page == "🎓 초보자 가이드 (Guide)":
    st.title("📚 헤지펀드 따라잡기: 완벽 가이드")
    
    st.markdown("""
    ## 1. 헤지펀드의 비밀: 차트 보는 법
    이 차트를 제대로 이해하려면 **'헤지펀드가 어떻게 돈을 버는지'** 알아야 합니다. 그들은 단순한 투기꾼이 아니라 **'이자 농사꾼(Arbitrageur)'**입니다.
    
    이들의 비즈니스 모델(Business Model)은 3단계로 이루어집니다.
    
    ---
    ### 🔄 [1단계] 씨 뿌리기 (Spread Creation)
    *   **상황:** 선물 가격이 현물보다 비쌀 때 (프리미엄 발생 💰)
    *   **행동:** **현물 매수(Buy Spot) 📈 + 선물 매도(Short Future) 📉**
    *   **차트의 모습:** 
        *   가격(주황색)이 상승합니다 (현물 매수 때문)
        *   **파란선(Short OI)이 급등합니다** (선물 매도 포지션을 쌓았기 때문)
    *   **우리의 해석:** "아! 롱이 아니라 숏이 늘어나는 걸 보니, 헤지펀드가 현물을 엄청 사들이고 있구나! **찐반등(진짜 상승장)**이다!"
    
    ---
    ### ⏳ [2단계] 농작물 키우기 (Carry / Earning)
    *   **상황:** 만기일이나 수익실현 목표일까지 대기
    *   **행동:** **포지션 유지 (Hold) ✊**
    *   **차트의 모습:** 
        *   가격은 횡보하거나 천천히 오릅니다.
        *   **파란선(OI)이 높은 곳에서 평평하게 유지됩니다.**
    *   **우리의 해석:** "헤지펀드가 아직 안 나갔네? 그럼 아직 상승 추세가 살아있구나. 나도 좀 더 들고 가야지." (안정적인 이자/펀딩비 수익 구간)
    
    ---
    ### 🚜 [3단계] 수확하기 (Unwinding)
    *   **상황:** 프리미엄이 사라졌거나(이자 매력 감소), 만기가 됐을 때
    *   **행동:** **현물 매도(Sell Spot) 📉 + 선물 숏 청산(Cover Short) 📈**
    *   **차트의 모습:** 
        *   가격이 하락합니다 (현물 매도 폭탄)
        *   **파란선(Short OI)이 급감합니다** (포지션 정리)
    *   **우리의 해석:** "파란선이 꺾였네? 이제 헤지펀드가 농사 끝내고 집에 가는구나. **나도 얼른 팔고 도망가자!**"
    
    ---
    ## 2. 심화: 같이 가느냐, 따로 가느냐 (Correlation)
    항상 같이 오르는 것은 아닙니다. 두 선의 **'방향 관계'**를 해석하는 것이 고수의 영역입니다.

    *   **✅ 동조화 (Sync ↗️↗️):** 가격 상승 + 숏 증가
        *   **해석:** "찐반(진짜 반등)". 현물을 사모으면서 헷징을 하는 건전한 상승장입니다.
    
    *   **❌ 역상관 A (Divergence ↗️↘️): 숏 스퀴즈**
        *   가격은 오르는데 숏이 줄어든다? 이는 누군가 손해를 보고 **도망치느라(청산)** 가격이 오르는 것입니다. 오래 못 갑니다.
        
    *   **⚠️ 역상관 B (Divergence ↘️↗️): 하락 배팅**
        *   가격은 내리는데 숏이 늘어난다? 이때는 헷징용 숏이 아니라, 정말로 **가격 하락에 돈을 건(투기적) 공매도**일 수 있습니다. 조심해야 합니다.

    ---
    ## 3. 핵심 원리 복습: 왜 '숏'인데 호재인가?
    아직도 "헤지펀드가 숏을 치는데 왜 가격이 오르지?" 헷갈리시나요? 이 **'역설(Paradox)'**이 가장 중요합니다.

    ### 1) 헤지펀드는 겁쟁이입니다 (Risk Aversion)
    그들은 가격이 오를지 내릴지 맞추는 도박을 싫어합니다. 오직 **'100% 안전한 수익'**만 원합니다.
    
    ### 2) 그래서 '양방향' 배팅을 합니다 (Cash-and-Carry)
    *   **현물 매수 (+)**: 가격이 오르면 돈을 범 ↗️
    *   **선물 매도 (-)**: 가격이 내리면 돈을 범 ↘️
    
    이 두 개를 동시에 하면, 가격이 오르건 내리건 **'상관없는 상태(Neutral)'**가 됩니다. 대신, 선물과 현물의 **'가격 차이(Premium)'**만큼을 꼬박꼬박 이자로 챙기는 것입니다.

    ### 3) 결론: 파란선의 진짜 의미 🕵️
    차트에서 **파란선(숏 물량/OI)**이 하늘로 치솟고 있나요?
    그것은 헤지펀드가 **"나 지금 비트코인 현물을 미친듯이 사모으고 있어!"**라고 확성기에 대고 소리치는 것과 같습니다. 절대 겁먹지 마세요.

    ---
    ## 4. 자주 묻는 질문 (FAQ)
    
    **Q. 2024년 이후 이 지표가 더 잘 맞는 이유는?**
    A. 비트코인 현물 ETF 승인 이후, 월가(Wall St.)의 거대 자본이 시장에 들어왔습니다. 이들은 '코인의 꿈'보다는 **'확실한 이자 수익(연 10~15%)'**을 노리고 들어왔습니다. 따라서 이 '이자 농사 지표(숏 OI)'가 곧 가격의 향방을 결정하는 가장 큰손이 되었습니다.
    
    **Q. 타임머신 분석은 어떻게 쓰나요?**
    A. '차트 분석' 페이지 아래에 있는 녹색 슬라이더를 움직여보세요. 과거의 **대상승장 초입(2020년 말, 2023년 초)**과 **대폭락장 직전(2021년 5월)**을 설정해 보면, 위에서 배운 '매집'과 '청산' 패턴이 정확하게 나타나는 것을 볼 수 있습니다.
    """)
