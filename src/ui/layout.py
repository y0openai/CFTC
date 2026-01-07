
import streamlit as st
import datetime
from src.config import ASSET_CONFIG

def render_page_config():
    st.set_page_config(page_title="CFTC Hedge Fund Analysis", layout="wide")

def render_sidebar():
    """
    Renders the sidebar and returns the user settings as a dictionary.
    """
    st.sidebar.title("CFTC 분석 대시보드")
    st.sidebar.caption("BTC Price vs Hedge Fund Short OI")
    st.sidebar.markdown("---")
    st.sidebar.header("Data Configuration")

    # Navigation
    page = st.sidebar.radio("이동하실 페이지를 선택하세요:", ["📊 차트 분석 (Analysis)", "🎓 초보자 가이드 (Guide)"])
    st.sidebar.markdown("---")
    
    settings = {
        "page": page,
        "asset_name": None,
        "start_year": None,
        "end_year": None,
        "show_dollar": False,
        "highlight": False,
        "api_key": None
    }

    if page == "📊 차트 분석 (Analysis)":
        st.sidebar.header("설정 (Settings)")
        
        # Asset
        selected_asset_name = st.sidebar.selectbox("분석 대상 코인", list(ASSET_CONFIG.keys()))
        settings["asset_name"] = selected_asset_name
        
        # Date
        current_year = datetime.datetime.now().year
        start_year = st.sidebar.number_input("시작 연도", min_value=2018, max_value=current_year, value=2023)
        end_year = st.sidebar.number_input("종료 연도", min_value=2018, max_value=current_year, value=current_year)
        settings["start_year"] = start_year
        settings["end_year"] = end_year
        
        asset_conf = ASSET_CONFIG[selected_asset_name]
        
        # Options
        settings["show_dollar"] = st.sidebar.checkbox(f"금액($)으로 환산하여 보기 (Contract * Price * {asset_conf['multiplier']})", value=False)
        settings["highlight"] = st.sidebar.checkbox("급격한 변동 구간 강조 (Significant Changes)", value=True, help="전주 대비 10% 이상 변화한 구간을 색상으로 구분합니다.")
        
        st.sidebar.markdown("---")
        st.sidebar.markdown("### 🔑 AI 실험실 (Lab)")
        settings["api_key"] = st.sidebar.text_input("Gemini API Key", type="password", help="[헤지펀드의 고백] 기능을 사용하려면 API 키가 필요합니다.")

    return settings
