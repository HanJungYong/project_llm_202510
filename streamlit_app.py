import io
import re
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from typing import Any, Dict, List
import openpyxl
from pypdf import PdfReader
from llm_schema import (
    recommend_services,
    extract_top_requirements_pure_llm
)

########################################
## 필요한 함수 정의
#########################################

# Cloude Services 를 엑셀 다운로드 함수
def cloudService_to_ExcelDownload(flat_rows: List[Dict[str, str]]) -> bytes | None:
    
    buf = io.BytesIO()
    df_all = pd.DataFrame(flat_rows)
    try:
        df_all = df_all.sort_values(["요구사항", "서비스 이름"]).reset_index(drop=True)
    except Exception:
        pass
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_all.to_excel(writer, sheet_name="All", index=False)
    buf.seek(0)
    return buf.getvalue()

# PDF 텍스트 요구사항 추출 함수
def pdfReqirement_extract_totext(file) -> str:
    if PdfReader is None:
        return ""
    try:
        reader = PdfReader(file)
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception:
        return ""

# 그리드 영역 데이터 조합
def make_grid_output(recommendations: dict, group_key: str) -> Dict[str, List[dict]]:
    groups: Dict[str, List[dict]] = {group_key: []}
    for rec in recommendations.get("recommendations", []):
        svc_name = rec.get("service_name", "")
        overview = rec.get("overview", "")
        feats = rec.get("feature_description", [])
        item = {
            "서비스 이름": svc_name,
            "서비스 설명": overview,
            "서비스 기능 리스트": feats if isinstance(feats, list) else [str(feats)],
        }
        groups[group_key].append(item)
    return groups



########################################
## Main 프로그램 시작 
#########################################

APP_TITLE = "Cloud Architecture Design Assistant"
sample = (
    "개인정보를 안전하게 저장하고 비공개로 접근제어가 되어야 한다.\n"
    "외부 파트너에게 API를 노출하되 트래픽 제어와 인증/인가가 필요하다.\n"
    "사내 문서 기반 검색형 챗봇 PoC를 만들고 싶다."
)

# Streamlit 앱 설정
st.set_page_config(page_title=APP_TITLE, page_icon="☁️", layout="wide")
st.title(APP_TITLE)
st.markdown("#### - 개요: User Requirement 에 따른 Cloud Architecture 설계를 위한 Azure Cloud Service 추천")

# 추천 모델 옵션 설정
top_n = 10
temperature = st.slider("정확한 서비스 추천: 0-0.2, 광범위한 서비스 추천: 0.4-0.6 (Model temperature)", 0.0, 1.0, 0.2, 0.1)

# 요구사항 입력(사용자 직접 입력 or pdf 파일)
if "req_text" not in st.session_state:
    st.session_state["req_text"] = sample

# textarea는 나중에 렌더하기 위해 placeholder만 생성 (세션 상태 갱신 후 그린다)
ta_ph = st.empty()
try:
    pdf_file = st.file_uploader("PDF 업로드(추후 기능 구현 예정)", type=["pdf"], accept_multiple_files=False)
except Exception:
    print("파일 업로더 오류")


# PDF 업로드시, 요구사항 자동 채우기 : 추후 기능 구현 예정
if pdf_file is not None:

    _stamp = f"{pdf_file.name}:{len(pdf_file.getvalue())}"
       
    if _stamp and st.session_state.get("_pdf_stamp") != _stamp:
        pdf_bytes = pdf_file.getvalue()
        pdf_text = pdfReqirement_extract_totext(io.BytesIO(pdf_bytes))

        if pdf_text.strip():
            with st.spinner("PDF에서 요구사항 추출 중..."):
                try:
                    extracted = extract_top_requirements_pure_llm(pdf_text, temperature=0.1)
                except Exception as e:
                    st.toast(f"PDF 요구사항 추출 실패: {e}", icon="⚠️")
            lines = []
            if isinstance(extracted, list):
                for x in extracted:
                    if isinstance(x, str) and x.strip():
                        lines.append(x.strip())
                    elif isinstance(x, dict) and x.get("text"):
                        t = str(x["text"]).strip()
                        if t:
                            lines.append(t)
            if lines:
                st.session_state["req_text"] = "\n".join(lines)
                st.session_state["_pdf_stamp"] = _stamp
                st.toast(f"PDF에서 요구사항 {len(lines)}개 자동 채움", icon="✅")
            else:
                st.toast("PDF에서 요구사항을 찾지 못했습니다.", icon="⚠️")

# 세션 상태가 갱신된 뒤 textarea를 렌더 (write-after-instantiation 오류 방지)
ta_ph.text_area("User Requirement (System/Business)", key="req_text", height=160)

if st.button("서비스 추천", type="primary"):
    
    # 1) 요구사항: textarea 전체를 하나의 요구사항으로 사용 (세션 값 사용)
    requirement_str = (st.session_state.get("req_text") or "").strip()

    if not requirement_str:
        st.error("요구사항이 없습니다. 텍스트를 입력해주세요.")
        st.stop()

    # 2) LLM: 서비스 추천 (textarea 전체 문자열 1건)
    with st.spinner("Cloud Service 추천 생성 중..."):
        try:
            data = recommend_services(
                requirements=requirement_str,
                temperature=temperature,
                top_n_documents=top_n,
            )
        except Exception as e:
            st.error(f"서비스 추천 호출 실패: {e}")
            st.stop()

    # 3) 표 렌더링 (요구사항별 그룹) + Excel 다운로드
    if not isinstance(data, dict) or not isinstance(data.get("recommendations"), list):
        st.error("LLM 응답이 올바르지 않습니다.")
        st.stop()

    groups = make_grid_output(data, group_key=requirement_str)
    if not groups:
        st.info("추천 Cloud Service 결과가 없습니다.")

    st.subheader("추천 Cloud Services")
    flat_rows: List[Dict[str, str]] = []
    for i, (req, items) in enumerate(groups.items(), start=1):
  
        lines = [ln for ln in req.splitlines() if ln.strip()]
        header_label = f"{i}. {"User Requirement (System/Business)"}"

        with st.expander(header_label, expanded=(i == 1)):
            # 불릿 목록으로 요구사항 출력
            md = "\n".join(f"- {ln}" for ln in lines)
            st.markdown(md)

            st.markdown("---")
            # 화면용: 표 렌더링 (기능 컬럼은 리스트 그대로 유지 → ListColumn으로 칩 표시)
            display_rows: List[Dict[str, str]] = []
            for it in items:
                service_list = it.get("서비스 기능 리스트", [])
                # 리스트가 아니면 리스트로 강제
                service_list_cell = service_list if isinstance(service_list, list) else [str(service_list)]
                display_rows.append({
                    "추천 서비스 이름": it.get("서비스 이름", ""),
                    "서비스 설명": it.get("서비스 설명", ""),
                    "서비스 기능 리스트": service_list_cell
                })
            ui_df = pd.DataFrame(display_rows).reset_index(drop=True)

            # 화면 그리드 출력: ListColumn으로 칩(tag) 렌더링
            st.data_editor(
                ui_df,
                width="stretch",
                hide_index=True,
                disabled=True,
                column_config={
                    "추천 서비스 이름": st.column_config.TextColumn("서비스 이름", width="medium"),
                    "서비스 설명": st.column_config.TextColumn("서비스 설명", width="large"),
                    "서비스 기능 리스트": st.column_config.ListColumn(
                        "서비스 기능 리스트",
                        help="리스트 항목을 칩 형태로 표시합니다.",
                        width="large",
                    ),
                },
                row_height=100,
            )

            # 엑셀용 flat row 적재 (기능은 줄바꿈으로 합치기)
            for it in items:
                service_list = it.get("서비스 기능 리스트", [])
                service_list_cell = "\n".join(map(str, service_list)) if isinstance(service_list, list) else str(service_list)
                flat_rows.append({
                    "요구사항": req,
                    "추천 서비스 이름": it.get("서비스 이름", ""),
                    "서비스 설명": it.get("서비스 설명", ""),
                    "서비스 기능 리스트": service_list_cell,
                })

    # Excel 다운로드
    xlsx_bytes = cloudService_to_ExcelDownload(flat_rows)
    if xlsx_bytes:
        st.download_button(
            label="⬇️ Excel 다운로드",
            data=xlsx_bytes,
            file_name="CloudService_Recommendations.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

