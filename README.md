# Cloud Architecture Design Assistant
- KT DS 금융Cloud사업팀 한정용
- MS AI Study LLM 교육 7차
- 
# APP 기획 배경 
 ## 언제나 고객은 시간을 주지 않는다.
 ### R1. 내일까지 이 요구사항에 맞는 Cloud Service 주세요
 ### R2. 이번주말에 제안서 제춠해주세요~
 ### R3. 이 시스템 만들려고 하는 데 어떤 Cloud Service 가 필요하지요?
  
#  APP 개발 모토 : Save your Time, Enjoy your life !!!

 
## Cloud Architecture Design Assistant 설명

1. 개요: User Requirement 에 따른 Cloud Architecture 설계를 위한 Azure Cloud Service 추천
2. 목적: 프로젝트 제안이나 고객의 요청시, 쉽고 빠른 Cloud Architecture 설계 지원
3. 사용자 경험 (UX) : WEB UI (Streamlit UI)
	- 입력: User Requirement (System/Business)
	- 출력: Cloud Architecture 설계를 위한 추천 Azure Cloud Service lsit 결과 화면 
	- 출력 결과에 대한 Execl File download 지원 

## Process 별 기능 및 기술
![mcp image](./CloudArchitectureDesignAssistant.png)

  - Azure Cloud Service 기능 수집 및 저장 
    - 사용 서비스: Azure Storage account
    - 설명: Azure Cloud Service file 에서 Azure Storage 로 load 
  - User Requirement 에 맞는 Azure Cloud Service 검색 (RAG)
    - 사용 서비스: Azure AI Search
	- 사용 Model:  text-embedding-3-small
	- 설명: Azure AI Search 를 통한 검색 RAG 구현 
  - User Requirement 를 만족하는 Azure Cloud Service 추천
    - 사용 서비스: Azure AI Foundry - OpenAI
	- 사용 Model: gpt-4.1-mini
    - 설명: Azure AI Search RAG 결과 와 Prompt(User Requirement) 를 기반으로 서비스 추천 (추론)
  - Streamlit 을 통한 화면 출력 
    - 사용 서비스: Streamlit 
	- 설명:  추천 Azure Cloud Service lsit 결과 출력 및 Excel File download

## APP Service 실행
[실행 Site](https://hjy-webapp-serviceassistant-1030-fucwfpdcdkhuf2dq.eastus2-01.azurewebsites.net)

## MVP 이후 차후 기능 확장 방안 
	- AWS, GCP 등 타 CSP Cloud Service 추천으로 확장 
	- RFP file 분석 등 여러 Requirement 분석 기능 지원 
	- Requirement 별 구현 Cloud Architecture 구성 및 샘플 제공
