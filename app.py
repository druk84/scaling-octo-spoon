import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta

st.set_page_config(page_title="SMA 매매 시그널 분석기", layout="wide")

st.title("📈 이동평균선(SMA) + 거래량 매수/매도 시그널 분석기")
st.caption("한국/미국 주식 종목 코드를 입력하면 SMA 골든크로스/데드크로스와 거래량을 함께 분석합니다.")

# ---------- 사이드바 입력 ----------
with st.sidebar:
    st.header("설정")
    st.markdown("**종목 코드 예시**")
    st.markdown("- 한국: `005930` (삼성전자), `035720` (카카오)")
    st.markdown("- 미국: `AAPL`, `TSLA`, `NVDA`")

    ticker = st.text_input("종목 코드 입력", value="005930")

    period_years = st.slider("조회 기간(년)", 1, 5, 2)

    short_window = st.number_input("단기 이동평균 (일)", min_value=2, max_value=60, value=5)
    mid_window = st.number_input("중기 이동평균 (일)", min_value=5, max_value=120, value=20)
    long_window = st.number_input("장기 이동평균 (일)", min_value=10, max_value=250, value=60)

    volume_multiplier = st.slider("거래량 급증 기준 (평균 대비 배수)", 1.0, 5.0, 2.0, 0.1)

    run = st.button("분석 시작", type="primary")


def load_data(ticker: str, years: int) -> pd.DataFrame:
    start = datetime.now() - timedelta(days=365 * years)
    df = fdr.DataReader(ticker, start)
    return df


def add_indicators(df: pd.DataFrame, s: int, m: int, l: int, vol_mult: float) -> pd.DataFrame:
    df = df.copy()
    df["SMA_short"] = df["Close"].rolling(s).mean()
    df["SMA_mid"] = df["Close"].rolling(m).mean()
    df["SMA_long"] = df["Close"].rolling(l).mean()

    # 거래량 평균 대비 급증 여부 (20일 평균 기준)
    df["Vol_MA20"] = df["Volume"].rolling(20).mean()
    df["Vol_Spike"] = df["Volume"] > (df["Vol_MA20"] * vol_mult)

    # 골든크로스 / 데드크로스 (단기가 중기를 상향/하향 돌파)
    df["Cross"] = df["SMA_short"] - df["SMA_mid"]
    df["Prev_Cross"] = df["Cross"].shift(1)

    df["Golden_Cross"] = (df["Prev_Cross"] < 0) & (df["Cross"] >= 0)
    df["Dead_Cross"] = (df["Prev_Cross"] > 0) & (df["Cross"] <= 0)

    # 거래량 급증이 동반된 신호만 별도 표시 (신뢰도 높은 신호)
    df["Golden_Cross_Strong"] = df["Golden_Cross"] & df["Vol_Spike"]
    df["Dead_Cross_Strong"] = df["Dead_Cross"] & df["Vol_Spike"]

    return df


if run:
    try:
        with st.spinner("데이터 불러오는 중..."):
            df = load_data(ticker, period_years)

        if df.empty:
            st.error("데이터를 찾을 수 없습니다. 종목 코드를 확인해주세요.")
        else:
            df = add_indicators(df, short_window, mid_window, long_window, volume_multiplier)

            # ---------- 차트 ----------
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=True,
                row_heights=[0.7, 0.3], vertical_spacing=0.03,
                subplot_titles=("주가 & 이동평균선", "거래량")
            )

            fig.add_trace(go.Candlestick(
                x=df.index, open=df["Open"], high=df["High"],
                low=df["Low"], close=df["Close"], name="캔들"
            ), row=1, col=1)

            fig.add_trace(go.Scatter(x=df.index, y=df["SMA_short"], name=f"SMA{short_window}", line=dict(width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA_mid"], name=f"SMA{mid_window}", line=dict(width=1)), row=1, col=1)
            fig.add_trace(go.Scatter(x=df.index, y=df["SMA_long"], name=f"SMA{long_window}", line=dict(width=1)), row=1, col=1)

            golden = df[df["Golden_Cross_Strong"]]
            dead = df[df["Dead_Cross_Strong"]]

            fig.add_trace(go.Scatter(
                x=golden.index, y=golden["Close"], mode="markers",
                marker=dict(symbol="triangle-up", size=14, color="red"),
                name="매수 시그널(거래량 급증)"
            ), row=1, col=1)

            fig.add_trace(go.Scatter(
                x=dead.index, y=dead["Close"], mode="markers",
                marker=dict(symbol="triangle-down", size=14, color="blue"),
                name="매도 시그널(거래량 급증)"
            ), row=1, col=1)

            colors = ["red" if v else "gray" for v in df["Vol_Spike"]]
            fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=colors, name="거래량"), row=2, col=1)

            fig.update_layout(height=800, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True)

            # ---------- 최근 신호 테이블 ----------
            st.subheader("최근 매수/매도 시그널")
            signals = df[df["Golden_Cross"] | df["Dead_Cross"]].copy()
            signals["신호"] = signals.apply(
                lambda r: "매수(골든크로스)" if r["Golden_Cross"] else "매도(데드크로스)", axis=1
            )
            signals["거래량 급증 동반"] = signals["Vol_Spike"].map({True: "O", False: "X"})
            st.dataframe(
                signals[["Close", "신호", "거래량 급증 동반"]].sort_index(ascending=False).head(20),
                use_container_width=True
            )

            st.info("⚠️ 이 도구는 교육/참고용이며 투자 조언이 아닙니다. 실제 투자 결정은 본인 책임입니다.")

    except Exception as e:
        st.error(f"오류가 발생했습니다: {e}")
else:
    st.info("왼쪽에서 종목 코드와 설정을 입력한 뒤 '분석 시작' 버튼을 눌러주세요.")
