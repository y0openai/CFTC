
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

            # 2. Logic & Evidence Engine
            phase_title = "분석 대기"
            evidence_txt = "데이터 부족"
            forecast_txt = "충분한 데이터가 없습니다."
            color = "gray"
            
            # Thresholds (%)
            SIGNIFICANT_CHANGE = 1.5 
            
            if oi_delta_pct > SIGNIFICANT_CHANGE: # OI UP (Phase 1: Spread Creation)
                if price_delta_pct > SIGNIFICANT_CHANGE:
                    phase_title = f"🌱 1단계: 파종 (Spread Creation) {macro_trend}"
                    color = "green"
                    forecast_txt = "**[강력 매수 구간]** 헤지펀드가 차익거래(Arbitrage)를 위해 현물을 공격적으로 사들이고 있습니다. 프리미엄 따먹기 자금이 유입되는 동안 상승 추세는 지속될 것입니다."
                    evidence_txt = f"**{ticker_name}** 가격 상승(**+{price_delta_pct:.1f}%**)과 함께 숏 OI가 급증(**+{oi_delta_pct:.1f}%**)했습니다. 이는 하락 배팅이 아니라, 현물을 매수하고 선물을 파는 **'포지션 구축'** 활동입니다."
                elif -SIGNIFICANT_CHANGE <= price_delta_pct <= SIGNIFICANT_CHANGE:
                    phase_title = f"📦 매집/축적 (Accumulation) {macro_trend}"
                    color = "blue"
                    forecast_txt = "**[폭발 임박]** 가격은 묶어두고(횡보) 물량을 쓸어 담고 있습니다. 스프레드(가격차)가 벌어져 헤지펀드의 진입 유인이 극대화된 상태입니다."
                    evidence_txt = f"가격은 **{price_delta_pct:.1f}%로 제자리**인데, 숏 OI만 **{oi_delta_pct:.1f}% 급증**했습니다. 조용히 현물을 매집하며 차익거래 포지션을 쌓고 있습니다."
                else:
                    phase_title = f"🛡️ 방어적 헷징 (Defensive Hedging) {macro_trend}"
                    color = "orange"
                    forecast_txt = "하락장에 대비해 보유 현물의 가치를 지키려는 방어적 숏입니다. 추가 하락 가능성이 있습니다."
                    evidence_txt = f"가격이 하락(**{price_delta_pct:.1f}%**)하는데 숏 OI가 증가(**{oi_delta_pct:.1f}%**)합니다. 이것은 차익거래보다는 순수한 **'가격 하락 방어(Insurance)'** 목적의 진입으로 보입니다."
                    
            elif oi_delta_pct < -SIGNIFICANT_CHANGE: # OI DOWN (Phase 3: Unwinding)
                if price_delta_pct < -SIGNIFICANT_CHANGE:
                    phase_title = f"🚜 3단계: 수확 (Unwinding) {macro_trend}"
                    color = "red"
                    forecast_txt = "**[매도/관망 구간]** '이자 농사'가 끝나고 청산하는 단계입니다. 헤지펀드가 현물을 시장가로 던지면서(매도) 포지션을 정리하고 있습니다. 소나기는 피하세요."
                    evidence_txt = f"**{ticker_name}** 가격 급락(**{price_delta_pct:.1f}%**)과 숏 OI 급감(**{oi_delta_pct:.1f}%**)이 동반됩니다. 차익거래 기회가 사라져 자금이 이탈(Exit)하는 전형적인 **청산 사이클**입니다."
                elif price_delta_pct > SIGNIFICANT_CHANGE:
                    phase_title = "💸 숏 스퀴즈 (Short Squeeze)"
                    color = "orange"
                    forecast_txt = "비정상적인 가격 상승입니다. 숏 포지션이 손실을 못 이기고 강제 청산당하며 가격을 밀어 올리는 중입니다. 추격 매수는 위험합니다."
                    evidence_txt = f"가격은 오르는데(**+{price_delta_pct:.1f}%**) 숏 OI는 줄어들고(**{oi_delta_pct:.1f}%**) 있습니다. 자발적 수익 실현이 아니라, **'도망치는'** 상황입니다."
                else:
                    phase_title = "🍂 관심 저하 (Cooling Off)"
                    color = "gray"
                    forecast_txt = "시장의 관심이 식어가고 있습니다. 뚜렷한 주매수 주체가 없습니다."
                    evidence_txt = "가격과 OI 모두 감소세입니다. 자금이 빠져나가며 시장의 활력이 떨어지고 있습니다."
            else: # OI Stable (Phase 2: Carry)
                phase_title = f"⏳ 2단계: 보유/이자 수익 (Carry) {macro_trend}"
                color = "green" if price_delta_pct > -5 else "gray"
                forecast_txt = "**[보유 구간]** 헤지펀드가 구축한 포지션을 유지하며 펀딩비(이자) 수익을 즐기고 있습니다. 대규모 이탈 신호가 없다면 추세는 유지됩니다."
                evidence_txt = f"숏 OI 변화가 **{oi_delta_pct:.1f}%**로 안정적입니다. 거대 자본이 포지션을 굳건히 지키고(Holding) 있습니다."

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
    ## 3. 자주 묻는 질문 (FAQ)
    
    **Q. 2024년 이후 이 지표가 더 잘 맞는 이유는?**
    A. 비트코인 현물 ETF 승인 이후, 월가(Wall St.)의 거대 자본이 시장에 들어왔습니다. 이들은 '코인의 꿈'보다는 **'확실한 이자 수익(연 10~15%)'**을 노리고 들어왔습니다. 따라서 이 '이자 농사 지표(숏 OI)'가 곧 가격의 향방을 결정하는 가장 큰손이 되었습니다.
    
    **Q. 타임머신 분석은 어떻게 쓰나요?**
    A. '차트 분석' 페이지 아래에 있는 녹색 슬라이더를 움직여보세요. 과거의 **대상승장 초입(2020년 말, 2023년 초)**과 **대폭락장 직전(2021년 5월)**을 설정해 보면, 위에서 배운 '매집'과 '청산' 패턴이 정확하게 나타나는 것을 볼 수 있습니다.
    """)
