
import google.generativeai as genai
import pandas as pd
import re

class AINarrator:
    @staticmethod
    def generate_narrative(range_df: pd.DataFrame, api_key: str):
        """
        Generates the 'Hedge Fund Confession' narrative using Gemini.
        Returns a dictionary with parsed sections.
        """
        if not api_key:
            return {"error": "API Key is missing."}
            
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-2.0-flash-exp')
            
            # Prepare Prompt Data
            sample_df = range_df.copy()
            # Smart Sampling
            if len(sample_df) > 30: 
                    sample_df = sample_df.iloc[::len(sample_df)//30]
            
            prompt_rows = []
            for idx, row in sample_df.iterrows():
                prompt_rows.append(f"- {row['Date'].strftime('%Y-%m-%d')}: BTC Price ${row['Close']:,.0f}, **MY Short Position**: {row['Lev_Money_Positions_Short_All']:,.0f} contracts")
            
            prompt_text = f"""
            [Role]
            You are a ruthless, cynical, yet intellectually superior **Head Strategist** at a top Wall Street Hedge Fund.
            You view retail investors ("Ants") not as people, but as **liquidity providers** who pay for your champagne.
            You speak **perfect, professional Korean (Hangul)** with a tone of cold, calculated confidence.

            [Input Data: Price vs **MY Short Contracts (OI)**]
            {chr(10).join(prompt_rows)}

            [YOUR CORE PHILOSOPHY: THE "HOUSE" ALWAYS WINS]
            You do not gamble. You run a casino. You exploit the **"Structural Long Bias"** of the market.
            *   **Retail Psychology:** They blindly believe "Number Go Up" (Bullish Sentiment).
            *   **Your Edge:** You feed their greed by selling them expensive Futures (Premium) and buying cheap Spot.
            *   **Gambler's Premium:** You profit from the leverage-addicted gamblers who pay premium & funding fees.

            [STRATEGIC PLAYBOOK: 4 SEASONS OF MONEY MAKING]
            Analyze the data by identifying which of these 4 modes you were in:

            1.  **😇 The Farmer (Arbitrageur) - [Market: Uptrend/Bull]**
                *   **Data:** Price ↗️ AND Short OI ↗️
                *   **Logic:** "The ants are excited. Premium is widening. I buy Spot and SELL Futures to lock in risk-free yield."
                *   **Narrative:** "Classic Cash-and-Carry. Planting seeds in their greed."

            2.  **😈 The Predatory Hunter (Bear Raid) - [Market: Weak/Resistance]**
                *   **Data:** Price ➡️/↘️ AND Short OI ↗️
                *   **Logic:** "Momentum is fading. I dump Spot to trigger panic and pile into Short Futures."
                *   **Narrative:** "They looked weak. I broke their support line to feed on their stop-losses."

            3.  **🌾 The Harvester (Unwinding) - [Market: Downtrend/Crash]**
                *   **Data:** Price ↘️ AND Short OI ↘️
                *   **Logic:** "Panic is everywhere. Premium is gone. I buy back my cheap Futures to close the position."
                *   **Narrative:** "Harvest season. While they cry over losses, I'm booking my guaranteed arbitrage profits."

            4.  **💰 The Landlord (Funding Farming) - [Market: Sideways]**
                *   **Data:** Price ➡️ AND Short OI ➡️
                *   **Logic:** "Boring market? Good. I just hold and collect Funding Fees every 8 hours."
                *   **Narrative:** "Collecting rent from the dreamers."

            [INTERPRETATION RULES]
            *   **NEVER** say "I lost money" because the market dropped. You hedged (Cash-and-Carry), so you profited from the *spread*, not the price.
            *   **IF** Price skyrocketed and you reduced shorts (Price ↗️, OI ↘️), admit a **"Short Squeeze"** (Operational Failure): "The ants overpowered us. Forced to cover."

            [Task]
            Conduct a **Strategic Post-Mortem**.
            Based on the data, reconstruct your psychological state and strategic moves for each phase.

            [Output Format - Custom Tagging]
            Use strict tags. No JSON.

            <HEADER>
            (One sentence summary of your masterful operation, e.g., "Milked the bull run and harvested the crash perfectly.")
            </HEADER>
            
            <PHASE>
            TITLE: (Creative Strategy Name, e.g., "Operation: Sheep Shearing")
            PERIOD: YYYY-MM-DD ~ YYYY-MM-DD
            CONTENT: 
            **[Scenario]**: (Market atmosphere)
            **[My Move]**: (Specific action: "Sold into strength", "Triggered cascade")
            **[The Alpha]**: (Why this made money: "Captured 15% basis spread", "Farmed funding rates")
            </PHASE>
            
            ... (Repeat for key phases) ...

            <FUTURE>
            (Your short-term outlook. Based on current Premium/Basis, what is your next move? 
            - IF Premium High: "I will accumulate more positions."
            - IF Premium Low/Negative: "I will unwind and leave.")
            </FUTURE>
            <ADVICE>
            (A cynical piece of advice to the retail investor. e.g., "Stop paying me premiums and looking at charts. Go to work.")
            </ADVICE>
            """
            
            response = model.generate_content(prompt_text)
            text_res = response.text
            
            return AINarrator.parse_response(text_res)

        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def parse_response(text_res):
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
            
            return {
                "header": header_txt,
                "phases": phases,
                "future": future_txt,
                "advice": advice_txt
            }
        except Exception as e:
             return {"error": f"Parsing Error: {str(e)}", "raw": text_res}
