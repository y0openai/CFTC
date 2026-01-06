# 💰 CFTC Bitcoin Hedge Fund Tracker

미국 CFTC(상품선물거래위원회)의 **Traders in Financial Futures (TFF)** 리포트 데이터를 실시간으로 분석하여, **헤지펀드(Smart Money)의 비트코인 숏 포지션** 추이를 시각화하는 대시보드입니다.

## 🚀 기능 (Features)
*   **실시간 데이터 동기화:** 2018년부터 현재까지의 CFTC 리포트 자동 다운로드 및 파싱
*   **스마트 분석 엔진:** 최근 4주간의 데이터를 기반으로 '매집', '청산', '가속' 등 6단계 시장 페이즈 자동 진단
*   **인터랙티브 차트:** Plotly 기반의 확대/축소 및 듀얼 축(가격 vs OI) 지원
*   **추세 분석:** 4주 이동평균선(MA) 스무딩 적용

## 🛠 실행 방법 (Local)

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 앱 실행
streamlit run app.py
```

## ☁️ 배포 방법 (Deployment)

이 프로젝트는 **Streamlit Community Cloud**에 최적화되어 있습니다.

1.  이 폴더를 본인의 GitHub 저장소(Repository)에 업로드(Push) 하세요.
2.  [share.streamlit.io](https://share.streamlit.io/)에 접속하여 가입/로그인하세요.
3.  `New app` 버튼을 누르고 GitHub 저장소를 선택하면 **1분 안에 배포가 완료**됩니다.

---
**Files**
*   `app.py`: 메인 애플리케이션
*   `cftc_loader.py`: 데이터 수집 크롤러
*   `Procfile`: Heroku/Render 배포 설정 파일
