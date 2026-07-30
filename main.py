import streamlit as st
import pandas as pd
import plotly.express as px
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

st.set_page_config(page_title="박스오피스 대시보드", layout="wide")
st.title("🎬 박스오피스 대시보드")

# 비밀 금고에서 인증키 꺼내기 (코드에는 키를 적지 않는다)
KOBIS_KEY = st.secrets["KOBIS_KEY"]

# 한국 시간 기준 '오늘'과 '어제' (배포 서버 시계는 외국 기준일 수 있다)
now_kst = datetime.now(ZoneInfo("Asia/Seoul"))
yesterday_date = (now_kst - timedelta(days=1)).date()

# 달력에서 날짜 고르기 (가장 늦은 날짜는 어제까지)
selected_date = st.date_input(
    "조회할 날짜를 선택하세요",
    value=yesterday_date,
    max_value=yesterday_date,
)
target_dt = selected_date.strftime("%Y%m%d")
st.caption(f"조회 기준일: {selected_date.strftime('%Y-%m-%d')}")

url = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
res = requests.get(url, params={"key": KOBIS_KEY, "targetDt": target_dt}, timeout=10)

if res.status_code != 200:
    st.error(f"요청이 실패했습니다 (상태코드: {res.status_code})")
    st.stop()

data = res.json()

# KOBIS는 키가 틀려도 상태코드 200을 준다. 대신 faultInfo 상자가 온다.
if "faultInfo" in data:
    st.error("인증키가 올바르지 않습니다. 금고(Secrets)의 KOBIS_KEY를 확인해 주세요.")
    st.stop()

box_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
if not box_list:
    st.warning("그날 자료가 없습니다. 다른 날짜를 골라 보세요.")
    st.stop()

df = pd.DataFrame(box_list)

# 글자로 온 숫자들을 진짜 숫자로 바꾸기
for col in ["rank", "audiCnt", "audiAcc", "scrnCnt", "showCnt"]:
    df[col] = pd.to_numeric(df[col])

# 누적관객 100만 이상이면 왕관 표시용 이름 만들기
CROWN_THRESHOLD = 1_000_000
df["display_name"] = df.apply(
    lambda r: f"👑 {r['movieNm']}" if r["audiAcc"] >= CROWN_THRESHOLD else r["movieNm"],
    axis=1,
)

# 1~3위 카드 (포스터 사진 대신 이모지 아이콘으로 정보 표현)
MEDALS = ["🥇", "🥈", "🥉"]
top3 = df.sort_values("rank").head(3)

st.subheader("🏅 오늘의 TOP 3")
cols = st.columns(3)
for col, (_, row) in zip(cols, top3.iterrows()):
    medal = MEDALS[int(row["rank"]) - 1] if 1 <= int(row["rank"]) <= 3 else "🎬"
    crown = "👑 " if row["audiAcc"] >= CROWN_THRESHOLD else ""
    with col:
        with st.container(border=True):
            st.markdown(
                f"<div style='text-align:center; font-size:52px; line-height:1.1'>{medal}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div style='text-align:center; font-size:18px; font-weight:700; margin-bottom:8px'>{crown}{row['movieNm']}</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"""
                <div style='font-size:15px; line-height:2.0'>
                🎟️ 하루 관객수 &nbsp; <b>{row['audiCnt']:,}명</b><br>
                📈 누적 관객수 &nbsp; <b>{row['audiAcc']:,}명</b><br>
                🖥️ 상영 스크린 &nbsp; <b>{row['scrnCnt']:,}개</b><br>
                📅 개봉일 &nbsp; <b>{row['openDt']}</b>
                </div>
                """,
                unsafe_allow_html=True,
            )

st.divider()

# 그래프용 데이터 (순위순 정렬, 화면에는 관객수 많은 순 = 순위순으로 위에서 아래로)
chart_df = df.sort_values("rank").head(10).copy()
chart_df = chart_df.iloc[::-1]  # plotly 가로 막대는 아래부터 그려지므로 뒤집어서 1위가 위로 오게 함

fig = px.bar(
    chart_df,
    x="audiCnt",
    y="display_name",
    orientation="h",
    text="audiCnt",
    color="audiAcc",
    color_continuous_scale="Sunset",
    labels={"audiCnt": "하루 관객수", "display_name": "", "audiAcc": "누적 관객"},
    title="📊 박스오피스 TOP 10 · 하루 관객수",
)
fig.update_traces(
    texttemplate="%{text:,}명",
    textposition="outside",
    marker_line_width=0,
)
fig.update_layout(
    height=520,
    coloraxis_colorbar_title="누적관객",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(size=14),
    margin=dict(l=10, r=40, t=60, b=10),
    xaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.3)"),
)
st.plotly_chart(fig, use_container_width=True)

# 누적 관객 비교 그래프
fig2 = px.bar(
    chart_df,
    x="audiAcc",
    y="display_name",
    orientation="h",
    text="audiAcc",
    color="audiAcc",
    color_continuous_scale="Sunset",
    labels={"audiAcc": "누적 관객", "display_name": ""},
    title="🏆 누적 관객수 비교 (👑 = 100만 명 이상)",
)
fig2.update_traces(
    texttemplate="%{text:,}명",
    textposition="outside",
    marker_line_width=0,
)
fig2.update_layout(
    height=520,
    showlegend=False,
    coloraxis_showscale=False,
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(size=14),
    margin=dict(l=10, r=40, t=60, b=10),
    xaxis=dict(showgrid=True, gridcolor="rgba(200,200,200,0.3)"),
)
st.plotly_chart(fig2, use_container_width=True)

# 오늘 극장가를 누가 차지했는지 보여주는 관객점유율 도넛 차트
share_df = chart_df.copy()
share_df["점유율"] = share_df["audiCnt"] / share_df["audiCnt"].sum() * 100

fig3 = px.pie(
    share_df,
    names="display_name",
    values="audiCnt",
    hole=0.55,
    color_discrete_sequence=px.colors.sequential.Sunset,
    title="🍩 오늘 극장가를 누가 차지했나 (TOP 10 관객점유율)",
)
fig3.update_traces(
    textposition="inside",
    insidetextorientation="horizontal",
    textinfo="percent",
    textfont=dict(size=13, color="white"),
    pull=[0.05 if n.startswith("👑") else 0 for n in share_df["display_name"]],
)
fig3.update_layout(
    height=560,
    showlegend=True,
    legend=dict(
        orientation="h",
        yanchor="top",
        y=-0.05,
        xanchor="center",
        x=0.5,
        font=dict(size=12),
    ),
    uniformtext_minsize=11,
    uniformtext_mode="hide",
    plot_bgcolor="rgba(0,0,0,0)",
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(size=13),
    margin=dict(l=20, r=20, t=60, b=100),
)
st.plotly_chart(fig3, use_container_width=True)


with st.expander("📋 원본 표로 보기"):
    table = df[["rank", "display_name", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
    table.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]
    table = table.sort_values("순위").reset_index(drop=True)
    st.dataframe(table, use_container_width=True)
