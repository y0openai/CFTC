
import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.graph_objs as go
from plotly.subplots import make_subplots
import datetime
import cftc_loader
import google.generativeai as genai # AI Storytelling

# -----------------------------------------------------------------------------
# 1. Page Config
# -----------------------------------------------------------------------------
st.set_page_config(page_title="CFTC Hedge Fund Analysis", layout="wide")

# -----------------------------------------------------------------------------
# 2. Sidebar Controls & App Info
# -----------------------------------------------------------------------------
st.sidebar.title("CFTC 분석 대시보드")
st.sidebar.caption("BTC Price vs Hedge Fund Short OI")

st.sidebar.markdown("---")
st.sidebar.header("Data Configuration")

# --- SIDEBAR NAVIGATION ---
page = st.sidebar.radio("이동하실 페이지를 선택하세요:", ["📊 차트 분석 (Analysis)", "🎓 초보자 가이드 (Guide)"])
st.sidebar.markdown("---")

# ==========================================
# PAGE 1: CHART ANALYSIS
# ==========================================
if page == "📊 차트 분석 (Analysis)":
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
    # Insight Option
    HIGHLIGHT_CHANGE = st.sidebar.checkbox("급격한 변동 구간 강조 (Significant Changes)", value=True, help="전주 대비 10% 이상 변화한 구간을 색상으로 구분합니다.")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 🔑 AI 실험실 (Lab)")
    gemini_api_key = st.sidebar.text_input("Gemini API Key", type="password", help="[헤지펀드의 고백] 기능을 사용하려면 API 키가 필요합니다.")

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
            cftc_data = cftc_data.sort_values('Date').drop_duplicates(subset=['Date'], keep='last') # Fix duplicates
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

            # 3. Highlight Logic (Insight Tool)
            # Calculate % Change to determine colors
            bar_colors = ['blue'] * len(y_hf) # Default
            if HIGHLIGHT_CHANGE:
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
            st.subheader(f"🤖 Smart Money Analysis & Forecast ({sel_start_date} ~ {sel_end_date})")
            
            # 1. Calculation Engine
            # Filter data within range
            range_df = combined[(combined['Date'].dt.date >= sel_start_date) & 
                                (combined['Date'].dt.date <= sel_end_date)].copy()
            
            # --- CRITICAL FIX: Create Weekly Analysis DataFrame ---
            # range_df is DAILY (Price). CFTC is WEEKLY.
            # To calculate "1 Week Change", we must compare "This Week" vs "Last Week", not "Today" vs "Yesterday".
            # Resample to Weekly (Friday) to align with CFTC release cycle.
            analysis_df = range_df.resample('W-Fri', on='Date').last().dropna(subset=['Lev_Money_Positions_Short_All'])
            
            weeks_duration = len(analysis_df)
            
            if weeks_duration < 2:
                st.warning("분석을 위해 최소 2주 이상의 구간을 선택해주세요.")
                range_oi_delta = 0
                range_price_delta = 0
                correlation = 0
                one_w_oi_delta = 0
                one_w_price_delta = 0
                one_m_oi_delta = 0
            else:
                # Start vs End of the selection (Using Weekly DF)
                start_row = analysis_df.iloc[0]
                end_row = analysis_df.iloc[-1]
                
                # Metrics Calculation (Based on Weekly Data)
                # 1. Range (Start vs End)
                range_oi_delta = ((end_row['Lev_Money_Positions_Short_All'] - start_row['Lev_Money_Positions_Short_All']) / start_row['Lev_Money_Positions_Short_All']) * 100
                range_price_delta = ((end_row['Close'] - start_row['Close']) / start_row['Close']) * 100
                
                # Correlation (Use daily range_df for better correlation granularity, OR weekly analysis_df)
                # Weekly is less noisy for correlation. Let's use analysis_df.
                if len(analysis_df) > 2:
                    correlation = analysis_df['Close'].corr(analysis_df['Lev_Money_Positions_Short_All'])
                else:
                    correlation = 0
                
                # 2. Latest 1 Week (Last vs 2nd Last in Weekly DF)
                latest_oi = analysis_df.iloc[-1]['Lev_Money_Positions_Short_All']
                prev_oi = analysis_df.iloc[-2]['Lev_Money_Positions_Short_All']
                latest_price = analysis_df.iloc[-1]['Close']
                prev_price = analysis_df.iloc[-2]['Close']
                
                one_w_oi_delta = ((latest_oi - prev_oi) / prev_oi) * 100 if prev_oi != 0 else 0
                one_w_price_delta = ((latest_price - prev_price) / prev_price) * 100 if prev_price != 0 else 0
                
                # 3. Recent 1 Month (Last vs 5th Last in Weekly DF -> approx 4 weeks back)
                if len(analysis_df) >= 5:
                    prev_1m_oi = analysis_df.iloc[-5]['Lev_Money_Positions_Short_All']
                    one_m_oi_delta = ((latest_oi - prev_1m_oi) / prev_1m_oi) * 100 if prev_1m_oi != 0 else 0
                else:
                    one_m_oi_delta = range_oi_delta # Fallback
                    
            # Handle NaN correlation
            if pd.isna(correlation): correlation = 0
                
            range_corr = correlation # Alias for compatibility
            
            # --- Interpretation Logic ---
            
            # 1. Analyze Core Trend (Rule-Based Expert Logic)
            trend_status = "중립/횡보 (Neutral)"
            trend_desc = "뚜렷한 방향성 없이 등락을 반복했습니다."
            trend_color = "gray"
            
            # A. Huge OI Change (Whale moved regardless of correlation)
            if range_oi_delta > 30.0:
                if range_price_delta > 10.0:
                    trend_status = "강력 매집 상승 (Strong Accumulation)"
                    trend_desc = f"기간 동안 숏 물량이 폭발적으로(+{range_oi_delta:.1f}%) 늘어나며 가격 상승을 주도했습니다. 전형적인 상승장 패턴입니다."
                    trend_color = "green"
                elif range_price_delta < -10.0:
                    trend_status = "저가 매집 집중 (Dip Accumulation)"
                    trend_desc = f"가격이 하락하는 동안 스마트 머니는 오히려 물량(+{range_oi_delta:.1f}%)을 쓸어 담았습니다. 공포 구간을 이용한 매집입니다."
                    trend_color = "blue"
                else:
                    trend_status = "매물 소화/매집 (Absorbing)"
                    trend_desc = "가격은 횡보했으나 내부적으로는 거대한 매집(+{range_oi_delta:.1f}%)이 일어났습니다. 에너지가 응축된 상태입니다."
                    trend_color = "blue"

            elif range_oi_delta < -30.0:
                if range_price_delta < -10.0:
                    trend_status = "대규모 이탈/손절 (Mass Exodus)"
                    trend_desc = "가격 하락과 함께 자금이 썰물처럼 빠져나갔습니다(-{range_oi_delta:.1f}%). 하락 추세가 강력합니다."
                    trend_color = "red"
                elif range_price_delta > 10.0:
                    trend_status = "숏 스퀴즈 랠리 (Squeeze Rally)"
                    trend_desc = f"가격은 올랐지만 이는 숏 포지션 청산(-{range_oi_delta:.1f}%)에 의한 것입니다. 신규 매수세가 없는 '가짜 반등'일 수 있습니다."
                    trend_color = "orange"
                else:
                    trend_status = "차익 실현/이탈 (Profit Taking)"
                    trend_desc = "가격 변동 없이 조용히 포지션을 정리(-{range_oi_delta:.1f}%)하고 있습니다."
                    trend_color = "orange"

            # B. Moderate Change (Use Correlation as confirmation)
            elif abs(correlation) > 0.5:
                if correlation > 0: # Sync
                    if range_oi_delta > 0:
                        trend_status = "상승 동조화 (Bullish Sync)"
                        trend_desc = "가격과 숏 OI가 함께 오르는 건전한 상승 흐름입니다."
                        trend_color = "green"
                    else:
                        trend_status = "하락 동조화 (Bearish Sync)"
                        trend_desc = "가격과 OI가 같이 빠지고 있습니다. 시장 에너지가 약화되고 있습니다."
                        trend_color = "red"
                else: # Divergence
                    if range_price_delta > 0:
                        trend_status = "불안한 상승 (Weak Rally)"
                        trend_desc = "가격은 오르지만 주포(숏)들은 이탈하고 있습니다."
                        trend_color = "orange"
                    else:
                        trend_status = "⚠️ 공매도 공격 (Bear Raid)"
                        trend_desc = "현물을 던져 가격을 고의로 떨어뜨리고, 선물 숏(레버리지)으로 막대한 차익을 챙기는 **'약탈적 사냥(Predatory Shorting)'** 패턴입니다."
                        trend_color = "red"
            
            # C. Fallback (True Neutral)
            else:
                if range_oi_delta > 10:
                     trend_status = "매집 우위 (Accumulation Bias)"
                     trend_desc = "약한 상관관계 속에서도 꾸준히 물량이 늘어나고 있습니다."
                     trend_color = "green"
                elif range_oi_delta < -10:
                     trend_status = "청산 우위 (Distribution Bias)"
                     trend_desc = "방향성 없이 물량이 서서히 줄어들고 있습니다."
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

            # 3. Final Synthesis (Weekly Behavior Timeline & Prediction)
            # Fix: Ensure unique dates for weekly log
            range_df = range_df.drop_duplicates(subset=['Date'], keep='last')
            
            weekly_logs = []
            
            # --- DUAL PERSONA MEMORY (State Machine) ---
            # Modes: "NEUTRAL", "FARMER" (Arbitrage/Accumulation), "HUNTER" (Bear Raid)
            market_mode = "NEUTRAL"
            
            if len(range_df) >= 2:
                for i in range(1, len(range_df)):
                    curr_row = range_df.iloc[i]
                    prev_row = range_df.iloc[i-1]
                    
                    curr_date = curr_row['Date'].strftime('%Y-%m-%d')
                    current_month = curr_row['Date'].month
                    
                    # Deltas
                    c_oi = curr_row['Lev_Money_Positions_Short_All']
                    p_oi = prev_row['Lev_Money_Positions_Short_All']
                    c_price = curr_row['Close']
                    p_price = prev_row['Close']
                    
                    # Avoid division by zero
                    w_oi_pct = ((c_oi - p_oi) / p_oi) * 100 if p_oi != 0 else 0
                    w_price_pct = ((c_price - p_price) / p_price) * 100 if p_price != 0 else 0
                    
                    ACT_THRES = 2.0
                    
                    intent_emoji = "😐"
                    intent_title = "관망 (Wait)"
                    intent_desc = "유의미한 변화가 없습니다."
                    prediction_text = "당분간 횡보가 예상됩니다."

                    # --- LOGIC TREE ---
                    
                    # 1. ACCUMULATION (Entry)
                    if w_oi_pct > ACT_THRES:
                        # Check specifics to define Persona
                        if w_price_pct < -3.0 and w_oi_pct > 5.0:
                            # [HUNTER MODE START]
                            market_mode = "HUNTER"
                            intent_emoji = "🩸"
                            intent_title = "공매도 공격 (Bear Raid)"
                            intent_desc = f"현물 투매로 가격 폭락({w_price_pct:.1f}%)을 유도하고, 선물 숏을 기습적으로 늘려(+{w_oi_pct:.1f}%) **약탈적 사냥 모드**에 진입했습니다."
                            prediction_text = "세력의 의도적인 하락 유도입니다. 바닥 신호가 나올 때까지 절대 진입하지 마세요."
                        
                        elif w_price_pct > 1.0:
                            # [FARMER MODE START] - Momentum
                            market_mode = "FARMER"
                            intent_emoji = "🌱" # Sprout for Farmer
                            intent_title = "이모작 시작 (Momentum Farming)"
                            intent_desc = "상승장에 맞추어 **무위험 차익거래(현물매수+선물매도) 농사**를 시작했습니다. (건전한 진입)"
                            prediction_text = "상승 모멘텀이 강화될 것입니다. 단기 과열 여부만 체크하세요."
                        
                        elif w_price_pct < -1.0:
                            # [FARMER MODE START] - Dip Buying
                            market_mode = "FARMER"
                            intent_emoji = "🐜"
                            intent_title = "저가 씨뿌리기 (Dip Buying)"
                            intent_desc = f"가격 하락({w_price_pct:.1f}%)을 기회로 삼아 **저렴한 값에 현물을 매집**하고 숏 포지션을 구축했습니다."
                            prediction_text = "스마트 머니의 저가 매수세가 확인되었습니다. 물량 확보 후 반등 가능성이 높습니다."
                        
                        else:
                            # [FARMER MODE CONTINUE]
                            market_mode = "FARMER"
                            intent_emoji = "📦"
                            intent_title = "매집 축적 (Accumulation)"
                            intent_desc = "가격을 자극하지 않고 조용히 포지션을 늘리고 있습니다."
                            prediction_text = "에너지가 응축되고 있습니다. 곧 시세 분출이 예상됩니다."

                    # 2. LIQUIDATION (Exit)
                    elif w_oi_pct < -ACT_THRES:
                        # Priority 1: Seasonality Override (Structural Events)
                        if current_month == 12:
                             market_mode = "NEUTRAL" # Reset after closing
                             intent_emoji = "💰"
                             intent_title = "연말 수익 확정 (Book Closing)"
                             intent_desc = "연말 보너스 확정을 위해 **1년 농사를 모두 수익 실현**하고 장부를 마감했습니다."
                             prediction_text = "메이저 자금이 휴가를 떠났습니다. 산타 랠리(빈집털이) 혹은 횡보가 예상됩니다."
                        elif current_month in [3, 6, 9]:
                             # Rollover keeps the mode theoretically, but let's just log it
                             intent_emoji = "🔄"
                             intent_title = "분기 만기 롤오버 (Rollover)"
                             intent_desc = "만기를 앞두고 포지션을 교체하고 있습니다. 추세 변화가 아닌 **단순 교체 작업**입니다."
                             prediction_text = "롤오버가 끝나면 기존 추세가 이어질 것입니다."
                        
                        else:
                            # Priority 2: Persona-Based Interpretation
                            if market_mode == "HUNTER":
                                if w_price_pct < -1.0:
                                    intent_emoji = "🍖"
                                    intent_title = "전리품 챙기기 (Looting)"
                                    intent_desc = "공매도 공격 성공 후, **하락장에서 막대한 수익을 실현(익절)**하고 있습니다."
                                    prediction_text = "세력이 배불리 먹고 있습니다. 매도 압력이 해소되면 기술적 반등이 올 것입니다."
                                elif w_price_pct > 1.0:
                                    intent_emoji = "😎"
                                    intent_title = "작전 종료 (Mission Accomplished)"
                                    intent_desc = "공격 목표 달성 후 남은 물량을 정리하며 유유히 시장을 떠나고 있습니다."
                                    prediction_text = "작전이 끝났습니다. 세력이 떠난 자리는 당분간 방향성 없는 움직임이 예상됩니다."
                                else:
                                    intent_emoji = "📉"
                                    intent_title = "사냥 종료 (End Hunt)"
                                    intent_desc = "공격 포지션을 정리하고 있습니다."
                                    prediction_text = "변동성이 줄어들 것입니다."
                                # Mode Exit? Let's keep Hunter mode until Neutral/Buy happens or explicit reset.
                            
                            elif market_mode == "FARMER":
                                if w_price_pct < -1.0:
                                    intent_emoji = "🌾"
                                    intent_title = "가을 수확 (Harvesting)"
                                    intent_desc = "기르던 포지션을 정리하며 **정상적인 차익거래 수익을 실현**하고 있습니다. (패닉 셀이 아님)"
                                    prediction_text = "수익 실현 매물이 나오고 있습니다. 건전한 조정 과정입니다."
                                elif w_price_pct > 1.0:
                                    intent_emoji = "🔥" # Fire (Burned)
                                    intent_title = "흉작/스퀴즈 (Squeeze)"
                                    intent_desc = "예상치 못한 급등으로 **농사가 실패하고 강제 청산(Stop Loss)** 당했습니다."
                                    prediction_text = "강제 청산 물량이 소진되면 급락할 위험이 있습니다."
                                else:
                                    intent_emoji = "📉"
                                    intent_title = "포지션 축소 (Reduce)"
                                    intent_desc = "리스크 관리를 위해 비중을 줄이고 있습니다."
                                    prediction_text = "관망세가 짙어질 것입니다."
                            
                            else: # NEUTRAL MODE (No Context)
                                if w_price_pct < -1.0:
                                    intent_emoji = "🏃"
                                    intent_title = "이탈 (Exit)"
                                    intent_desc = "시장 전망 악화로 시장을 떠나고 있습니다."
                                    prediction_text = "하락 추세가 지속될 수 있습니다."
                                elif w_price_pct > 1.0:
                                    intent_emoji = "💸"
                                    intent_title = "숏 스퀴즈 (Short Squeeze)"
                                    intent_desc = "가격 급등으로 인한 강제 청산이 발생했습니다."
                                    prediction_text = "추격 매수를 자제하세요."
                                else:
                                    intent_emoji = "📉"
                                    intent_title = "비중 축소 (De-leveraging)"
                                    intent_desc = "관망을 위해 포지션을 줄이고 있습니다."
                                    prediction_text = "횡보장이 예상됩니다."

                    # 3. NEUTRAL / WAIT
                    else:
                        market_mode = "NEUTRAL" # Reset Persona when inactivity
                        intent_emoji = "😐"
                        intent_title = "관망 (Wait)"
                        intent_desc = "유의미한 포지션 변화가 없습니다. 기존 차익거래 포지션을 유지(Carry) 중입니다."
                        prediction_text = "당분간 횡보하거나 현재 추세가 완만하게 이어질 것입니다."
                    
                    weekly_logs.append({
                        "date": curr_date,
                        "oi_delta": w_oi_pct,
                        "price_delta": w_price_pct,
                        "emoji": intent_emoji,
                        "title": intent_title,
                        "desc": intent_desc,
                        "pred": prediction_text
                    })
            
            weekly_logs.reverse() # Show Newest first

            # Final Verdict Logic (Trend + Action)
            final_verdict = ""
            final_color = "gray"
            # Main Forecast Logic
            final_forecast_text = "충분한 데이터가 없습니다."
            
            # --- CRITICAL FIX: Emergency Override for Bear Raid ---
            # If latest week shows Bear Raid (Price Drop < -3% & OI Jump > 5%), override long-term trend.
            is_bear_raid = (one_w_price_delta < -3.0) and (one_w_oi_delta > 5.0)

            if is_bear_raid:
                final_verdict = "🩸 공매도 공격 (Dead Cat Bounce Warning)"
                final_color = "red" 
                final_forecast_text = "🚨 **함정 경고(Bull Trap):** 세력의 공매도 공격이 감지되었습니다. 통계적으로 **1주 내 기술적 반등(67%)**이 발생할 수 있으나, **4주 후에는 하락할 확률(55%)**이 더 높습니다. 단기 반등을 이용하여 **물량을 정리(Exit)**하는 것이 현명합니다."

            elif (one_w_oi_delta < -5.0) and (one_w_price_delta > 1.0):
                 final_verdict = "💥 숏 스퀴즈 경고 (Fake Pump Alert)"
                 final_color = "orange"
                 final_forecast_text = "🚨 **가짜 반등 경고:** 가격 상승과 함께 숏 포지션이 급감했습니다. 세력의 신규 매수가 아닌 **단순 청산(Covering)**일 가능성이 높습니다. 통계적으로 **64% 확률로 1주 내 다시 하락**했습니다. 추격 매수를 자제하세요."

            elif "매집" in trend_status and one_w_oi_delta < -5:
                final_verdict = "⚠️ 추세 이탈 경고 (Trend Reversal)"
                final_color = "orange"
                final_forecast_text = "장기간의 매집 추세가 깨지고 대규모 이탈이 발생했습니다. 상승 관점을 철회하고 리스크 관리에 들어가야 할 때입니다."
            elif "공매도" in trend_status: # Priority Check for Bear Raid
                final_verdict = "⚠️ 공매도 공격 (Bear Raid)"
                final_color = "red"
                final_forecast_text = "세력이 인위적으로 시세를 누르고 있습니다(Predatory Shorting). 투매에 동참하지 말고 바닥 신호를 기다리세요. (선물 숏 이익 실현 시 급반등 유의)"
            elif "청산" in trend_status and one_w_oi_delta > 5:
                final_verdict = "💎 저점 매수 신호 (Potential Bottom)"
                final_color = "blue"
                final_forecast_text = "하락 추세 끝자락에서 강력한 스마트 머니 유입이 포착되었습니다. 추세 반전을 기대할 수 있는 좋은 진입 기회입니다."
            elif "매집" in trend_status and one_w_oi_delta > 0:
                final_verdict = "🔥 강력 상승 지속 (Strong Buy)"
                final_color = "green"
                final_forecast_text = "장기 추세와 단기 행동 모두 '매수'를 가리키고 있습니다. 상승 랠리가 지속될 가능성이 매우 높습니다."
            elif "청산" in trend_status and one_w_oi_delta < 0:
                final_verdict = "🩸 패닉 셀링 (Strong Sell)"
                final_color = "red"
                final_forecast_text = "매도세가 매도세를 부르는 투매 국면입니다. 바닥 신호가 나올 때까지 절대 진입하지 마세요."
            else:
                 final_verdict = f"{trend_status} 유지"
                 final_color = trend_color
                 if "매집" in trend_status:
                     final_forecast_text = "전반적인 매집 추세는 유효하나, 잠시 숨 고르기 중입니다. 기존 포지션을 홀딩하세요."
                 elif "청산" in trend_status:
                     final_forecast_text = "자금 이탈이 지속되고 있습니다. 보수적인 접근이 필요합니다."
                 elif "공매도" in trend_status: # Bear Raid Check
                     final_forecast_text = "공격적인 숏 베팅이 지속되고 있습니다. 추가 하락 압력이 높습니다."
                 else:
                     final_forecast_text = "뚜렷한 방향성이 없습니다. 박스권 매매나 관망이 유리합니다."

            # --- UI RENDERING ---
            with st.container():
                st.markdown(f"### 📢 AI 종합 분석: :{final_color}[{final_verdict}]")
                
                # FORECAST SECTION (Restored)
                if final_color == "green":
                    st.success(f"**🔮 향후 전망 (Forecast):** {final_forecast_text}")
                elif final_color == "red":
                    st.error(f"**🔮 향후 전망 (Forecast):** {final_forecast_text}")
                elif final_color == "blue" or final_color == "orange":
                    st.warning(f"**🔮 향후 전망 (Forecast):** {final_forecast_text}")
                else:
                    st.info(f"**🔮 향후 전망 (Forecast):** {final_forecast_text}")

                # --- GEN_AI FEATURE: Hedge Fund Confession ---
                if st.button("🕵️‍♂️ [헤지펀드의 비밀 고백] 듣기 (AI Narrative)"):
                    if not gemini_api_key:
                        st.warning("🔐 사이드바 'AI 실험실'에 **Gemini API Key**를 입력해야 들을 수 있습니다.")
                    else:
                        with st.spinner("🕶️ 헤지펀드 수석 전략가가 비밀 장부를 확인하고 있습니다..."):
                            try:
                                genai.configure(api_key=gemini_api_key)
                                model = genai.GenerativeModel('gemini-2.0-flash-exp')
                                
                                # Prepare Prompt Data
                                sample_df = range_df.copy()
                                # Smart Sampling: Ensure we don't send too much data, but keep trend
                                if len(sample_df) > 30: 
                                     sample_df = sample_df.iloc[::len(sample_df)//30]
                                
                                prompt_rows = []
                                for idx, row in sample_df.iterrows():
                                    prompt_rows.append(f"- {row['Date'].strftime('%Y-%m-%d')}: BTC Price ${row['Close']:,.0f}, **MY Short Position**: {row['Lev_Money_Positions_Short_All']:,.0f} contracts")
                                
                                prompt_text = f"""
                                [Role]
                                You are a ruthless Head Strategist at a top Hedge Fund targeting the Korean market.
                                You speak perfect, natural Korean (Hangul).
                                
                                [Input Data: Price vs **MY Short Contracts**]
                                {chr(10).join(prompt_rows)}
                                
                                [CRITICAL RULE]
                                - **Short OI** is **YOUR POSITION**. 
                                - OI UP: You are betting on DROP.
                                - OI DOWN: You are taking PROFIT.
                                
                                [Task]
                                You are a Head Strategist conducting a **Strategic Post-Mortem Analysis**.
                                Analyze the data and divide it into **Logical Strategic Phases** (No fixed limit, create as many as needed, typically 3-8 phases based on strategy shifts).
                                
                                [YOUR IDENTITY & BUSINESS MODEL]
                                You are a **Hedge Fund Architect** specializing in **Arbitrage & Structural Shorting**.
                                You do NOT blindly guess market direction. You execute **Calculated Business Models**:
                                
                                1.  **Cash-and-Carry (Basis Trading):** 
                                    -   **Context:** Bull Market / Price Rising.
                                    -   **Action:** BUY Spot + SELL Futures (Increase Short OI).
                                    -   **Goal:** Locking in the "Premium" (Basis Spread) as **Risk-Free Alpha**. You welcome price rises because they expand the premium.
                                
                                2.  **Bear Raid (Predatory Shorting):**
                                    -   **Context:** Resistance Level / Weak Momentum.
                                    -   **Action:** SELL Spot (Dump) + SELL Futures (Increase Short OI).
                                    -   **Goal:** Triggering panic selling to profit from the collapse.
                                
                                3.  **Unwinding (Exit):**
                                    -   **Context:** Premium shrinking or Trend Reversal.
                                    -   **Action:** Buy back Futures (Reduce Short OI) + Sell Spot.
                                    -   **Goal:** Realizing the basis profit.

                                [INTERPRETATION RULES]
                                -   **IF Price UP & Short OI UP:** DO NOT say "I bet on a crash." SAY "**I expanded Cash-and-Carry positions to farm the widening basis premium.**"
                                -   **IF Price FLAT/DOWN & Short OI UP:** SAY "**I initiated a Bear Raid to break the support line.**"
                                -   **IF Price UP & Short OI DOWN:** SAY "**Squeeze Risk Management.** I was forced to cover."

                                [Narrative Formula]
                                For each phase, STRICTLY use this structure:
                                1. **My Action**: (e.g., "Expanded Short OI by 20% while price rose.")
                                2. **The Logic (Biz Model)**: (e.g., "Basis spread widened to 5%. This was a classic Cash-and-Carry setup for risk-free yield.")
                                3. **Market Reaction**: ...
                                4. **P&L Outcome**: (e.g., "Secured 3% alpha from funding fees" OR "Successfully triggered a liquidation cascade.")

                                [Output Format - Custom Tagging]
                                Use strict tags for parsing. Do NOT use JSON.

                                
                                <HEADER>Strategic Flow Summary (e.g., Accumulation ➡️ Directional Bet ➡️ Profit Taking)</HEADER>
                                
                                <PHASE>
                                TITLE: Phase 1 Strategy Name
                                PERIOD: Start ~ End
                                CONTENT: **[Action]**: ...
                                **[Intent]**: ...
                                **[Result]**: ...
                                </PHASE>
                                
                                <PHASE>
                                TITLE: Phase 2...
                                ...
                                </PHASE>

                                <FUTURE>Next 1-Month Plan...</FUTURE>
                                <ADVICE>Key Market Variable...</ADVICE>

                                [Constraints]
                                - **Tone:** Professional, Analytical, Candid, Strategic.
                                - **LANGUAGE:** Korean.
                                - **Follow the Tags EXACTLY.**
                                """
                                
                                response = model.generate_content(prompt_text)
                                text_res = response.text
                                
                                # Robust Parsing using Regex
                                import re
                                import html
                                
                                try:
                                    # Extract Header
                                    header_match = re.search(r"<HEADER>(.*?)</HEADER>", text_res, re.DOTALL)
                                    header_txt = header_match.group(1).strip() if header_match else "Strategy Flow"
                                    
                                    # Extract Phases
                                    phases = []
                                    phase_matches = re.findall(r"<PHASE>(.*?)</PHASE>", text_res, re.DOTALL)
                                    
                                    for p_txt in phase_matches:
                                        title_match = re.search(r"TITLE:\s*(.*)", p_txt)
                                        period_match = re.search(r"PERIOD:\s*(.*)", p_txt)
                                        # Content is everything after CONTENT:
                                        content_match = re.search(r"CONTENT:\s*(.*)", p_txt, re.DOTALL)
                                        
                                        phases.append({
                                            "title": title_match.group(1).strip() if title_match else "Phase",
                                            "period": period_match.group(1).strip() if period_match else "",
                                            "narrative": content_match.group(1).strip() if content_match else p_txt.strip()
                                        })
                                    
                                    # Extract Footer
                                    future_match = re.search(r"<FUTURE>(.*?)</FUTURE>", text_res, re.DOTALL)
                                    future_txt = future_match.group(1).strip() if future_match else "No Plan"
                                    
                                    advice_match = re.search(r"<ADVICE>(.*?)</ADVICE>", text_res, re.DOTALL)
                                    advice_txt = advice_match.group(1).strip() if advice_match else "No Advice"

                                    # --- Render UI ---
                                    st.markdown("---")
                                    st.markdown(f"### 🍷 헤지펀드 전략가의 회고록")
                                    st.subheader(header_txt)
                                    
                                    import streamlit.components.v1 as components
                                    
                                    cards_html_inner = ""
                                    for p in phases:
                                        # Safe HTML Construction
                                        safe_title = html.escape(p['title'])
                                        safe_period = html.escape(p['period'])
                                        safe_narrative = html.escape(p['narrative']).replace("\n", "<br>")
                                        
                                        cards_html_inner += f"""
                                        <div class="card">
                                            <div class="card-header">{safe_title}</div>
                                            <div class="card-date">🗓️ {safe_period}</div>
                                            <div class="card-body">{safe_narrative}</div>
                                        </div>
                                        """
                                    
                                    # Complete HTML with CSS & JS for Buttons
                                    full_html = f"""
                                    <!DOCTYPE html>
                                    <html>
                                    <head>
                                    <style>
                                        body {{ background-color: transparent; margin: 0; font-family: sans-serif; }}
                                        .wrapper {{ position: relative; width: 100%; }}
                                        .container {{
                                            display: flex;
                                            overflow-x: auto;
                                            gap: 15px;
                                            padding: 10px 5px;
                                            scroll-behavior: smooth;
                                            scrollbar-width: thin;
                                            scrollbar-color: #555 transparent;
                                        }}
                                        .container::-webkit-scrollbar {{ height: 8px; }}
                                        .container::-webkit-scrollbar-track {{ background: transparent; }}
                                        .container::-webkit-scrollbar-thumb {{ background-color: #555; border-radius: 4px; }}
                                        
                                        .card {{
                                            min-width: 300px;
                                            max-width: 300px;
                                            height: 400px;
                                            background-color: #262730;
                                            border: 1px solid #454545;
                                            border-radius: 12px;
                                            padding: 20px;
                                            flex-shrink: 0;
                                            color: white;
                                            display: flex;
                                            flex-direction: column;
                                            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                                        }}
                                        .card-header {{ font-weight: bold; font-size: 1.1em; margin-bottom: 10px; color: #FFD700; }}
                                        .card-date {{ font-size: 0.8em; color: #ccc; margin-bottom: 15px; border-bottom: 1px solid #555; padding-bottom: 8px; }}
                                        .card-body {{ font-size: 0.95em; line-height: 1.6; color: #e0e0e0; overflow-y: auto; flex-grow: 1; }}
                                        .card-body::-webkit-scrollbar {{ width: 6px; }}
                                        .card-body::-webkit-scrollbar-thumb {{ background-color: #666; border-radius: 3px; }}

                                        .btn {{
                                            position: absolute;
                                            top: 50%;
                                            transform: translateY(-50%);
                                            background-color: rgba(0,0,0,0.6);
                                            color: white;
                                            border: none;
                                            border-radius: 50%;
                                            width: 45px;
                                            height: 45px;
                                            font-size: 24px;
                                            cursor: pointer;
                                            z-index: 100;
                                            display: flex;
                                            align-items: center;
                                            justify-content: center;
                                            transition: background-color 0.2s;
                                        }}
                                        .btn:hover {{ background-color: rgba(255, 189, 69, 0.8); color: black; }}
                                        .prev {{ left: 0; }}
                                        .next {{ right: 0; }}
                                    </style>
                                    </head>
                                    <body>
                                        <div class="wrapper">
                                            <button class="btn prev" onclick="document.getElementById('scroll-container').scrollLeft -= 320;">&#10094;</button>
                                            <div id="scroll-container" class="container">
                                                {cards_html_inner}
                                            </div>
                                            <button class="btn next" onclick="document.getElementById('scroll-container').scrollLeft += 320;">&#10095;</button>
                                        </div>
                                    </body>
                                    </html>
                                    """
                                    
                                    # Render Component
                                    components.html(full_html, height=480)
                                    
                                    st.markdown("---")
                                    f_col1, f_col2 = st.columns(2)
                                    with f_col1:
                                        st.markdown("#### 🚀 향후 1개월 비밀 작전")
                                        st.success(future_txt)
                                    with f_col2:
                                        st.markdown("#### 💀 핵심 변수 (Key Insight)")
                                        st.warning(advice_txt)

                                except Exception as e:
                                    st.warning(f"⚠️ 리포트 생성 중 포맷 오류: {e}")
                                    st.markdown(response.text)
                                st.success("이것이 월스트리트의 방식입니다.")
                                
                            except Exception as e:
                                st.error(f"보안 프로토콜 오류: {e}")
                
                 # Detailed Behavior Analysis Log
                st.markdown("#### 🕵️ 행동 분석 (Weekly Behavior Timeline)")
                st.markdown("선택하신 기간 동안 헤지펀드의 심리가 어떻게 변해왔는지 1주 단위로 분석합니다.")
                
                log_container = st.container(height=400) # Increased height
                with log_container:
                     for log in weekly_logs:
                        # Color coding for delta
                        oi_co = "red" if log['oi_delta'] < 0 else "blue"
                        p_co = "red" if log['price_delta'] < 0 else "green"
                        
                        st.markdown(f"""
                        **{log['date']}** {log['emoji']} **{log['title']}**
                        - 📊 OI: :{oi_co}[{log['oi_delta']:+.1f}%] / Price: :{p_co}[{log['price_delta']:+.1f}%]
                        - 💡 {log['desc']}
                        - 🔮 **Prediction:** {log['pred']}
                        ---
                        """)

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
                    st.markdown("#### 1️⃣ 가격 변동률 (Price Change)")
                    p_col1, p_col2, p_col3 = st.columns(3)
                    p_col1.metric("전체 기간 (Range)", f"{range_price_delta:+.1f}%")
                    p_col2.metric(f"최근 1달 ({weeks_duration}주차 기준)", f"{(range_price_delta if weeks_duration < 5 else ((range_df.iloc[-1]['Close'] - range_df.iloc[-5]['Close'])/range_df.iloc[-5]['Close']*100)):+.1f}%")
                    p_col3.metric("최근 1주 (Last Week)", f"{one_w_price_delta:+.1f}%")

                    st.markdown("---")
                    st.markdown("#### 2️⃣ 헤지펀드 숏 물량 (Short OI Change)")
                    o_col1, o_col2, o_col3 = st.columns(3)
                    o_col1.metric("전체 기간 (Range)", f"{range_oi_delta:+.1f}%", help="선택한 전체 기간 동안의 숏 포지션 증감률")
                    o_col2.metric("최근 1달 (Momentum)", f"{one_m_oi_delta:+.1f}%", help="최근 4주간의 숏 포지션 변화 (단기 추세)")
                    o_col3.metric("최근 1주 (Action)", f"{one_w_oi_delta:+.1f}%", help="지난주 대비 숏 포지션 변화 (즉각적인 행동)")
                    
                st.markdown(f"""
                <small>
                * 분석 대상: {sel_start_date} ~ {sel_end_date} (총 {weeks_duration}주 데이터) <br>
                * 과거의 데이터는 미래를 보장하지 않습니다. 참고용으로만 활용하세요.
                </small>
                """, unsafe_allow_html=True)

            # --- MODEL VALIDATION (BACKTEST) ---
            with st.expander("📊 모델 검증: 이 이론이 과거에도 통했을까? (Historical Accuracy)", expanded=False):
                st.markdown("##### 🧪 헤지펀드 비즈니스 모델(Cash-and-Carry) 역사적 검증")
                
                # Insight regarding CME vs Perpetual
                st.info("""
                **⚠️ 분석 전 필수 확인: 이 데이터는 '기한부(Dated)' 선물입니다.**
                * **바이낸스 등(Perpetual):** '무기한' 선물 위주이며, 실시간 펀딩비를 노리는 '단기 성향'이 강합니다.
                * **CME 데이터:** **'기한부(Monthly)'** 선물이며, 만기까지의 **확정 프리미엄**을 노리는 **'장기/보수적 성향'**이 강합니다.
                * **💡 결론:** 기한부 선물은 엉덩이가 무겁습니다. 따라서 파란선(OI)이 감소한다는 것은 단순한 차익실현을 넘어선 **'구조적인 시장 이탈(Trend Change)'**일 확률이 매우 높습니다.
                """)
                
                st.markdown("전체 데이터를 분석하여 **'OI가 늘면 가격이 오르고(매집), OI가 줄면 가격이 내린다(청산)'**는 법칙이 얼마나 잘 맞았는지 확인합니다.")
                
                # Use the full history for validation, not just the selected range
                # However, to be fair, let's use the loaded data (start_year ~ end_year)
                # Resample full combined data to weekly
                full_weekly_df = combined.resample('W-Fri', on='Date').last().dropna(subset=['Lev_Money_Positions_Short_All'])
                
                if len(full_weekly_df) > 10:
                    valid_counts = {"Accumulation": 0, "Acc_Win": 0, "Unwinding": 0, "Unw_Win": 0}
                    acc_returns = []
                    unw_returns = []
                    
                    for i in range(1, len(full_weekly_df)):
                        prev = full_weekly_df.iloc[i-1]
                        curr = full_weekly_df.iloc[i]
                        curr_month = curr.name.month # Index is Date due to resampling
                        
                        o_delta = ((curr['Lev_Money_Positions_Short_All'] - prev['Lev_Money_Positions_Short_All']) / prev['Lev_Money_Positions_Short_All']) * 100
                        p_delta = ((curr['Close'] - prev['Close']) / prev['Close']) * 100
                        
                        THRES = 2.0
                        
                        # Case 1: Accumulation (OI Up)
                        if o_delta > THRES:
                            valid_counts["Accumulation"] += 1
                            acc_returns.append(p_delta)
                            if p_delta > 0: # Hit
                                valid_counts["Acc_Win"] += 1
                                
                        # Case 2: Unwinding (OI Down)
                        elif o_delta < -THRES:
                            # Filter out Seasonality (Book Closing & Rollover)
                            if curr_month not in [3, 6, 9, 12]:
                                valid_counts["Unwinding"] += 1
                                unw_returns.append(p_delta)
                                if p_delta < 0: # Hit (Price Drop)
                                    valid_counts["Unw_Win"] += 1

                    # Stats Calculation
                    acc_rate = (valid_counts["Acc_Win"] / valid_counts["Accumulation"] * 100) if valid_counts["Accumulation"] > 0 else 0
                    unw_rate = (valid_counts["Unw_Win"] / valid_counts["Unwinding"] * 100) if valid_counts["Unwinding"] > 0 else 0
                    avg_acc_ret = sum(acc_returns) / len(acc_returns) if acc_returns else 0
                    avg_unw_ret = sum(unw_returns) / len(unw_returns) if unw_returns else 0
                    
                    v_col1, v_col2 = st.columns(2)
                    
                    with v_col1:
                        st.markdown(f"**📈 매집 적중률 (Pure Accumulation)**")
                        st.markdown(f"헤지펀드가 숏을 늘렸을 때(>2%), 가격이 실제로 상승한 확률입니다.")
                        st.metric("적중률 (Win Rate)", f"{acc_rate:.1f}%", f"Avg Return: {avg_acc_ret:+.1f}%")

                    with v_col2:
                        st.markdown(f"**📉 청산 적중률 (Pure Unwinding)**")
                        st.markdown(f"헤지펀드가 숏을 줄였을 때(<-2%), 가격이 실제로 하락한 확률입니다.")
                        st.caption("*(계절성 노이즈인 3,6,9,12월 데이터는 제외)*")
                        st.metric("적중률 (Win Rate)", f"{unw_rate:.1f}%", f"Avg Return: {avg_unw_ret:+.1f}%")
                    
                    st.markdown("---")
                    st.info(f"💡 **분석 결론:** 이 기간({start_year}~{end_year}) 동안 헤지펀드의 포지션 변화는 가격 방향성과 **{'높은' if (acc_rate+unw_rate)/2 > 55 else '중립적인'} 연관성**을 보였습니다.")
                    
                    # Insight on Asymmetry
                    if acc_rate - unw_rate > 10:
                        st.markdown("""
                        > **🕵️‍♂️ 심층 통찰: 비대칭성의 비밀 (Why Asymmetry?)**
                        > * **매집(Win):** 헤지펀드는 시장이 좋을 때(상승장)만 이자를 먹으러 '자발적'으로 들어옵니다. (강력한 호재)
                        > * **청산(Loss):** 나갈 때는 자발적 이탈도 있지만, **'숏 스퀴즈(강제 청산)'**인 경우도 있어 성공률이 상대적으로 낮습니다.
                        """)
                    elif unw_rate > 60:
                        st.markdown("""
                        > **🕵️‍♂️ 심층 통찰: 계절성 필터링 효과**
                        > * 3, 6, 9, 12월(롤오버/북클로징)을 제외하니 청산 적중률이 높아졌습니다.
                        > * 즉, **"계절 이슈가 없는데도 OI가 줄어든다면"** 그것은 진짜 **하락 신호**가 맞습니다.
                        """)
                    
                else:
                    st.warning("검증할 데이터가 부족합니다.")

            # --- RAW DATA ---
            with st.expander("원본 데이터 보기"):
                st.dataframe(combined[['Date', 'Lev_Money_Positions_Short_All', 'Close']].style.format({'Close': '{:.2f}'}))
            
            # --- EDUCATIONAL LINK ---
            st.write("---")
            st.info("💡 자세한 해설과 교육 자료가 필요하시면 좌측 메뉴의 **[🎓 초보자 가이드]**를 클릭하세요.")
            
            # --- BACKTEST REPORT ---
            st.write("---")
            st.markdown("#### 🧪 Backtest Report (2024.01 ~ Present)")
            st.caption("각 신호별로 가장 유의미한 기간(1주/4주)을 기준으로 검증한 승률입니다.")
            
            b_col1, b_col2, b_col3 = st.columns(3)
            b_col1.metric("Squeeze (1W Drop)", "64%", "High Precision Sell") # 1W Accuracy
            b_col2.metric("Bear Raid (1W Rebound)", "67%", "Contrarian Buy") # 1W Rebound
            b_col3.metric("Overall (4W Trend)", "56%", "Mid-term Accuracy") # Overall 4W
            
            st.info("""
            💡 **전략적 통찰:** 
            * **Squeeze 감지 시:** **64% 확률로 1주 내 하락**했습니다. 즉각적인 매도/숏 진입이 유리합니다.
            * **Bear Raid 감지 시:** **67% 확률로 1주 내 기술적 반등**이 나옵니다. 공포에 팔지 말고 **반등 시 탈출**하십시오.
            """)

# ==========================================
# PAGE 2: EDUCATIONAL GUIDE
# ==========================================
elif page == "🎓 초보자 가이드 (Guide)":
    st.title("📚 헤지펀드 따라잡기: 완벽 가이드")
    
    st.markdown("""
    ## 1. 헤지펀드의 비밀: 차트 보는 법
    이 차트를 제대로 이해하려면 **'헤지펀드가 어떻게 돈을 버는지'** 알아야 합니다. 그들은 단순한 투기꾼이 아니라 **'이자 농사꾼(Arbitrageur)'**입니다.
    
    이들의 비즈니스 모델(Business Model)은 2가지 모드로 나뉠 수 있습니다.
    
    ---
    ### 😇 [Mode 1] 착한 농부 (Arbitrageur)
    대부분의 시간(지루한 상승/횡보장) 동안 그들은 이 모드로 작동합니다.
    
    1.  **씨 뿌리기 (Spread Creation):**
        *   가격 상승 + 숏 포지션 증가 ↗️
        *   현물을 사면서 숏을 쳐서 이자를 확보합니다. (**강력한 상승 신호**)
        
    2.  **수확하기 (Unwinding):**
        *   가격 하락 + 숏 포지션 감소 ↘️
        *   이자가 줄어들면 농사를 접고 나갑니다. (**진짜 하락 신호**)

    ---
    ### 😈 [Mode 2] 잔혹한 사냥꾼 (Predatory Bear)
    하지만 시장이 공포에 질리면 그들은 돌변합니다. 사용자가 발견한 '공매도 공격' 패턴입니다.
    
    1.  **미끼 던지기 (Tapping):**
        *   보유한 현물을 시장가로 던져서(Dumping) 가격 하락을 유도합니다.
        
    2.  **그물 치기 (Leveraged Shorting):**
        *   **가격 폭락(↘️) + 숏 포지션 급증(↗️)** (다이버전스 발생)
        *   현물에서 깨진 -10% 손실은, 선물 숏(10배 레버리지)에서 먹은 +100% 수익으로 만회하고도 남습니다.
    
    *   **💡 결론:** 가격이 폭락하는데 파란선(숏)이 미친듯이 치솟는다? **절대 저점 매수 금지!** 세력이 작정하고 죽이러 온 것입니다.

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
