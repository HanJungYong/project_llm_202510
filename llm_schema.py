import os, json, re
from dotenv import load_dotenv
from openai import AzureOpenAI
from typing import Any, Dict, List
from pydantic import BaseModel, Field


# =====================
# Azure 환경변수 로드
# =====================
load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")

AZURE_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT")
AZURE_SEARCH_KEY = os.getenv("AZURE_SEARCH_KEY")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX")
OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("OPENAI_EMBEDDING_DEPLOYMENT")

# =====================
# Recommend API 설정 영역
# =====================
SYSTEM_PROMPT = (
    "당신은 Microsoft Azure 클라우드 아키텍트이자 컨설턴트입니다.\n"
    "입력된 텍스트에서 '요구사항'만 해석하여, 이를 충족할 수 있는 **Azure 서비스**만 추천하세요.\n"
    "각 항목은 'service_name', 'overview', 'feature_description', 'matched_requirements' 키를 반드시 포함합니다.\n"
    "- overview: 서비스 핵심 역할을 1~2문장 요약\n"
    "- feature_description: 서비스가 가진 기능 리스트를 출력해줘\n"
)

USER_TEMPLATE = (
    "아래 입력을 줄바꿈/불릿/번호를 기준으로 분할하여 '요구사항 후보'를 만든 뒤, "
    "'요구사항 리스트'를 내부적으로 확정하고, 그 리스트를 기준으로, 각 요구사항과 직접적으로 부합하는 Azure 서비스들을 고려하여, 추천하세요.\n"
    "\n"
    "반드시 JSON 하나만 출력하고, 아래 스키마를 정확히 따르세요. 코드펜스(```` )는 사용하지 마세요.\n"
    "\n"
    "요구사항 원문:\n{requirements}\n"
)

SCHEMA = {
    "name": "ServiceRecommendationsV1",
    "schema": {
        "type": "object",
        "properties": {
            "recommendations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "service_name": {"type": "string"},
                        "overview": {"type": "string"},
                        "feature_description": {"type": "array", "items": {"type": "string"}},
                        "matched_requirements": {
                            "type": "array", "items": {"type": "string"}
                        }
                    },
                    "required": ["service_name", "overview", "feature_description", "matched_requirements"]
                }
            }
        },
        "required": ["recommendations"]
    }
}

# Azure OpenAI 클라이언트 초기화
client = AzureOpenAI(
    azure_endpoint=AZURE_OPENAI_ENDPOINT, 
    api_key=AZURE_OPENAI_API_KEY, 
    api_version=AZURE_OPENAI_API_VERSION,
    azure_deployment=AZURE_OPENAI_DEPLOYMENT
    )

# LLM 입력 파라미터 생성 함수
def make_LLM_InputParams(index_name: str | None = None, query_type: str = "vector", top_n_documents: int | None = None) -> dict:

    params = {
        "data_sources": [
            {
                "type": "azure_search",
                "parameters": {
                    "endpoint": AZURE_SEARCH_ENDPOINT,
                    "index_name": AZURE_SEARCH_INDEX,
                    "authentication": {
                        "type": "api_key",
                        "key": AZURE_SEARCH_KEY,
                    },
                    "query_type": query_type,
                    "embedding_dependency": {
                        "type": "deployment_name",
                        "deployment_name": OPENAI_EMBEDDING_DEPLOYMENT,
                    },
                },
            }
        ]
    }
    if top_n_documents is not None:
        try:
            params["data_sources"][0]["parameters"]["top_n_documents"] = int(top_n_documents)
        except Exception:
            pass
    return params


# 고객 요구사항 입력 에 대한 서비스 추천 함수
def recommend_services(requirements: str,temperature: float = 0.2,
    rag_context: str | None = None,index_name: str | None = None,
    query_type: str = "vector", top_n_documents: int | None = None,) -> Dict[str, Any]:
    
    ## 입력 텍스트 전체를 한 번에 보내 추천 목록을 생성합니다.
    user_msg = USER_TEMPLATE.format(requirements=requirements.strip())

    max_tokens = 5000
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]
    if rag_context and rag_context.strip():
        # RAG 컨텍스트를 시스템으로 주입 (모델이 컨텍스트를 우선 참고하도록)
        messages.append({
            "role": "system",
            "content": (
                "[RAG CONTEXT]\n"
                "아래 문단들은 사용자의 요구사항과 연관된 참고 문서 발췌입니다.\n"
                "가능하면 이 컨텍스트를 우선적으로 근거로 사용하세요.\n\n"
                f"{rag_context.strip()}"
            )
        })
    messages.append({"role": "user", "content": user_msg})
    
    kwargs={}
    kwargs["extra_body"] = make_LLM_InputParams(index_name=AZURE_SEARCH_INDEX, query_type=query_type, top_n_documents=top_n_documents)

    client_chat = client.chat.completions.create(
        model=AZURE_OPENAI_DEPLOYMENT,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
        max_tokens=max_tokens,
        **kwargs
    )

    try:
        data = json.loads(client_chat.choices[0].message.content or "{}")
        if isinstance(data, dict) and isinstance(data.get("recommendations"), list):
            return data
        return {"recommendations": []}
    except Exception:
        return {"recommendations": []}


# 문단 단위로 청크 - pdf 파일 텍스트 요약 추출용
def make_chunk_for_llm(text: str, max_chars: int = 6000) -> list[str]:
    if not text:
        return []
    paras = re.split(r"\n{2,}", text)
    chunks, cur = [], ""
    for p in paras:
        p = p.strip()
        if not p:
            continue
        if len(cur) + len(p) + 1 <= max_chars:
            cur = (cur + "\n" + p) if cur else p
        else:
            if cur:
                chunks.append(cur)
            cur = p if len(p) <= max_chars else p[:max_chars]
    if cur:
        chunks.append(cur)
    return chunks

# PDF Requirement 추출 하는 구간 - pdf 파일 텍스트 요약 추출용
def extract_top_requirements_pure_llm(pdf_text: str, temperature: float = 0.1) -> list[dict]:

    chunks = make_chunk_for_llm(pdf_text)
    if not chunks:
        return []

    sys_extract = (
        "입력 텍스트에서 구현되어야 하는 '요구사항'만 추출하세요.\n"
        "오직 JSON 객체 하나만 출력: {\"requirements\": [\"문장1\", \"문장2\"]}"
    )

    candidates: List[str] = []
    for ch in chunks:
        if not ch.strip():
            continue
        cc = client.chat.completions.create(
            model=AZURE_OPENAI_DEPLOYMENT,
            messages=[
                {"role": "system", "content": sys_extract},
                {"role": "user", "content": "원문:\n" + ch},
            ],
            temperature=temperature,
            response_format={"type": "json_object"},
            max_tokens=2000,
        )
        try:
            parsed = json.loads(cc.choices[0].message.content or "{}")
        except Exception:
            parsed = {}

        # 허용 형태 1) {"requirements": [ ... ]}
        if isinstance(parsed, dict) and isinstance(parsed.get("requirements"), list):
            for v in parsed["requirements"]:
                t = (v.get("text") if isinstance(v, dict) else v)
                if isinstance(t, str):
                    t = t.strip()
                    if t:
                        candidates.append(t)
            continue
        # 허용 형태 2) 리스트 바로 온 경우 ["...", "..."]
        if isinstance(parsed, list):
            for v in parsed:
                if isinstance(v, str) and v.strip():
                    candidates.append(v.strip())
            continue
        # 그 외 형태는 무시

    if not candidates:
        return []

    # 중복 제거(순서 보존)
    seen = set()
    uniq: List[str] = []
    for t in candidates:
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)

    return [{"id": f"REQ-{i:03d}", "text": t} for i, t in enumerate(uniq, start=1)]
