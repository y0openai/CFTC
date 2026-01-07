
import pandas as pd
import datetime

class MarketAnalyzer:
    @staticmethod
    def analyze(range_df: pd.DataFrame):
        """
        Analyzes the filtered DataFrame (Daily).
        Logic partially adapted from original app.py Smart Money Analysis Engine.
        """
        result = {
            "is_valid": False,
            "metrics": {},
            "trend": {},
            "weekly_logs": [],
            "verdict": {},
            "analysis_df": None # The weekly resampled DF
        }

        # 1. Weekly Resampling
        # range_df is DAILY (Price). CFTC is WEEKLY.
        # Resample to Weekly (Friday) to align with CFTC release cycle.
        analysis_df = range_df.resample('W-Fri', on='Date').last().dropna(subset=['Lev_Money_Positions_Short_All'])
        
        # Ensure we keep the Date column after resampling
        if 'Date' not in analysis_df.columns:
            analysis_df = analysis_df.reset_index()

        result['analysis_df'] = analysis_df
        weeks_duration = len(analysis_df)

        if weeks_duration < 2:
            result['error'] = "Not enough data (minimum 2 weeks needed)."
            return result

        result['is_valid'] = True

        # --- Metrics Calculation ---
        start_row = analysis_df.iloc[0]
        end_row = analysis_df.iloc[-1]
        
        # 1. Range (Start vs End)
        range_oi_delta = ((end_row['Lev_Money_Positions_Short_All'] - start_row['Lev_Money_Positions_Short_All']) / start_row['Lev_Money_Positions_Short_All']) * 100
        range_price_delta = ((end_row['Close'] - start_row['Close']) / start_row['Close']) * 100
        
        # Correlation
        correlation = 0
        if len(analysis_df) > 2:
            correlation = analysis_df['Close'].corr(analysis_df['Lev_Money_Positions_Short_All'])
        if pd.isna(correlation): correlation = 0

        # 2. Latest 1 Week (Last vs 2nd Last)
        latest_oi = analysis_df.iloc[-1]['Lev_Money_Positions_Short_All']
        prev_oi = analysis_df.iloc[-2]['Lev_Money_Positions_Short_All']
        latest_price = analysis_df.iloc[-1]['Close']
        prev_price = analysis_df.iloc[-2]['Close']
        
        one_w_oi_delta = ((latest_oi - prev_oi) / prev_oi) * 100 if prev_oi != 0 else 0
        one_w_price_delta = ((latest_price - prev_price) / prev_price) * 100 if prev_price != 0 else 0
        
        # 3. Recent 1 Month
        one_m_oi_delta = range_oi_delta # Fallback
        if len(analysis_df) >= 5:
            prev_1m_oi = analysis_df.iloc[-5]['Lev_Money_Positions_Short_All']
            one_m_oi_delta = ((latest_oi - prev_1m_oi) / prev_1m_oi) * 100 if prev_1m_oi != 0 else 0

        result['metrics'] = {
            "range_oi_delta": range_oi_delta,
            "range_price_delta": range_price_delta,
            "correlation": correlation,
            "one_w_oi_delta": one_w_oi_delta,
            "one_w_price_delta": one_w_price_delta,
            "one_m_oi_delta": one_m_oi_delta
        }

        # --- Trend Interpretation ---
        trend_status = "중립/횡보 (Neutral)"
        trend_desc = "뚜렷한 방향성 없이 등락을 반복했습니다."
        trend_color = "gray"

        # A. Huge OI Change
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
                trend_desc = f"가격은 횡보했으나 내부적으로는 거대한 매집(+{range_oi_delta:.1f}%)이 일어났습니다. 에너지가 응축된 상태입니다."
                trend_color = "blue"
        elif range_oi_delta < -30.0:
            if range_price_delta < -10.0:
                trend_status = "대규모 이탈/손절 (Mass Exodus)"
                trend_desc = f"가격 하락과 함께 자금이 썰물처럼 빠져나갔습니다({range_oi_delta:.1f}%). 하락 추세가 강력합니다."
                trend_color = "red"
            elif range_price_delta > 10.0:
                trend_status = "숏 스퀴즈 랠리 (Squeeze Rally)"
                trend_desc = f"가격은 올랐지만 이는 숏 포지션 청산({range_oi_delta:.1f}%)에 의한 것입니다. 신규 매수세가 없는 '가짜 반등'일 수 있습니다."
                trend_color = "orange"
            else:
                trend_status = "차익 실현/이탈 (Profit Taking)"
                trend_desc = f"가격 변동 없이 조용히 포지션을 정리({range_oi_delta:.1f}%)하고 있습니다."
                trend_color = "orange"
        # B. Moderate Change (Correlation)
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
        # C. Fallback
        else:
            if range_oi_delta > 10:
                trend_status = "매집 우위 (Accumulation Bias)"
                trend_desc = "약한 상관관계 속에서도 꾸준히 물량이 늘어나고 있습니다."
                trend_color = "green"
            elif range_oi_delta < -10:
                trend_status = "청산 우위 (Distribution Bias)"
                trend_desc = "방향성 없이 물량이 서서히 줄어들고 있습니다."
                trend_color = "red"

        result['trend'] = {
            "status": trend_status,
            "desc": trend_desc,
            "color": trend_color
        }

        # --- Weekly Logs (Log Logic) ---
        weekly_logs = []
        market_mode = "NEUTRAL"
        
        # Iterate excluding the first row (since we need prev row)
        # analysis_df is already strictly sorted by date/resampled
        temp_df = analysis_df.drop_duplicates(subset=['Date'], keep='last')
        
        if len(temp_df) >= 2:
            for i in range(1, len(temp_df)):
                curr_row = temp_df.iloc[i]
                prev_row = temp_df.iloc[i-1]
                
                curr_date = curr_row['Date'].strftime('%Y-%m-%d')
                current_month = curr_row['Date'].month
                
                c_oi = curr_row['Lev_Money_Positions_Short_All']
                p_oi = prev_row['Lev_Money_Positions_Short_All']
                c_price = curr_row['Close']
                p_price = prev_row['Close']
                
                w_oi_pct = ((c_oi - p_oi) / p_oi) * 100 if p_oi != 0 else 0
                w_price_pct = ((c_price - p_price) / p_price) * 100 if p_price != 0 else 0
                
                ACT_THRES = 2.0
                
                intent_emoji = "😐"
                intent_title = "관망 (Wait)"
                intent_desc = "유의미한 변화가 없습니다."
                prediction_text = "당분간 횡보가 예상됩니다."

                # Logic Tree (Same as app.py)
                if w_oi_pct > ACT_THRES:
                    if w_price_pct < -3.0 and w_oi_pct > 5.0:
                        market_mode = "HUNTER"
                        intent_emoji = "🩸"
                        intent_title = "공매도 공격 (Bear Raid)"
                        intent_desc = f"현물 투매로 가격 폭락({w_price_pct:.1f}%)을 유도하고, 선물 숏을 기습적으로 늘려(+{w_oi_pct:.1f}%) **약탈적 사냥 모드**에 진입했습니다."
                        prediction_text = "세력의 의도적인 하락 유도입니다. 바닥 신호가 나올 때까지 절대 진입하지 마세요."
                    elif w_price_pct > 1.0:
                        market_mode = "FARMER"
                        intent_emoji = "🌱"
                        intent_title = "이모작 시작 (Momentum Farming)"
                        intent_desc = "상승장에 맞추어 **무위험 차익거래(현물매수+선물매도) 농사**를 시작했습니다. (건전한 진입)"
                        prediction_text = "상승 모멘텀이 강화될 것입니다. 단기 과열 여부만 체크하세요."
                    elif w_price_pct < -1.0:
                        market_mode = "FARMER"
                        intent_emoji = "🐜"
                        intent_title = "저가 씨뿌리기 (Dip Buying)"
                        intent_desc = f"가격 하락({w_price_pct:.1f}%)을 기회로 삼아 **저렴한 값에 현물을 매집**하고 숏 포지션을 구축했습니다."
                        prediction_text = "스마트 머니의 저가 매수세가 확인되었습니다. 물량 확보 후 반등 가능성이 높습니다."
                    else:
                        market_mode = "FARMER"
                        intent_emoji = "📦"
                        intent_title = "매집 축적 (Accumulation)"
                        intent_desc = "가격을 자극하지 않고 조용히 포지션을 늘리고 있습니다."
                        prediction_text = "에너지가 응축되고 있습니다. 곧 시세 분출이 예상됩니다."

                elif w_oi_pct < -ACT_THRES:
                    if current_month == 12:
                         market_mode = "NEUTRAL"
                         intent_emoji = "💰"
                         intent_title = "연말 수익 확정 (Book Closing)"
                         intent_desc = "연말 보너스 확정을 위해 **1년 농사를 모두 수익 실현**하고 장부를 마감했습니다."
                         prediction_text = "메이저 자금이 휴가를 떠났습니다. 산타 랠리(빈집털이) 혹은 횡보가 예상됩니다."
                    elif current_month in [3, 6, 9]:
                         intent_emoji = "🔄"
                         intent_title = "분기 만기 롤오버 (Rollover)"
                         intent_desc = "만기를 앞두고 포지션을 교체하고 있습니다. 추세 변화가 아닌 **단순 교체 작업**입니다."
                         prediction_text = "롤오버가 끝나면 기존 추세가 이어질 것입니다."
                    else:
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
                        elif market_mode == "FARMER":
                            if w_price_pct < -1.0:
                                intent_emoji = "🌾"
                                intent_title = "가을 수확 (Harvesting)"
                                intent_desc = "기르던 포지션을 정리하며 **정상적인 차익거래 수익을 실현**하고 있습니다. (패닉 셀이 아님)"
                                prediction_text = "수익 실현 매물이 나오고 있습니다. 건전한 조정 과정입니다."
                            elif w_price_pct > 1.0:
                                intent_emoji = "🔥"
                                intent_title = "흉작/스퀴즈 (Squeeze)"
                                intent_desc = "예상치 못한 급등으로 **농사가 실패하고 강제 청산(Stop Loss)** 당했습니다."
                                prediction_text = "강제 청산 물량이 소진되면 급락할 위험이 있습니다."
                            else:
                                intent_emoji = "📉"
                                intent_title = "포지션 축소 (Reduce)"
                                intent_desc = "리스크 관리를 위해 비중을 줄이고 있습니다."
                                prediction_text = "관망세가 짙어질 것입니다."
                        else: # NEUTRAL
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
                else:
                    market_mode = "NEUTRAL"
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

        weekly_logs.reverse()
        result['weekly_logs'] = weekly_logs

        # --- Final Verdict ---
        final_verdict = ""
        final_color = "gray"
        final_forecast_text = "충분한 데이터가 없습니다."
        
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
        elif "공매도" in trend_status:
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
             elif "공매도" in trend_status:
                 final_forecast_text = "공격적인 숏 베팅이 지속되고 있습니다. 추가 하락 압력이 높습니다."
             else:
                 final_forecast_text = "뚜렷한 방향성이 없습니다. 박스권 매매나 관망이 유리합니다."

        result['verdict'] = {
            "title": final_verdict,
            "color": final_color,
            "forecast": final_forecast_text
        }
        
        return result
