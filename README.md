# 🔍 AI PR Reviewer

LangGraph + Claude API로 만든 GitHub PR 자동 코드 리뷰 에이전트입니다.

## 아키텍처

```
사용자 (Streamlit UI)
        ↓
  LangGraph Agent
        ↓
  ┌─────────────┐
  │  agent 노드  │ ← Claude가 툴 호출 여부 결정
  └─────┬───────┘
        ↓ (툴 호출 시)
  ┌─────────────┐
  │  tools 노드  │ ← GitHub API 실행
  └─────┬───────┘
        ↓ (결과 반환)
  ┌─────────────┐
  │  agent 노드  │ ← 결과 분석 후 최종 리뷰 작성
  └─────────────┘

Tools:
  - get_pr_info       : PR 기본 정보 수집
  - get_pr_diff       : 변경된 코드 diff 수집
  - post_review_comment: GitHub PR에 코멘트 등록
```

## 시작하기

### 1. 환경변수 설정
```bash
cp .env.example .env
# .env 파일에 API 키 입력
```

### 2. 도커로 실행
```bash
docker-compose up --build
```

### 3. 브라우저에서 접속
```
http://localhost:8501
```

## 환경변수

| 변수 | 설명 |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API 키 |
| `GITHUB_TOKEN` | GitHub Personal Access Token (repo 권한 필요) |

## 기술 스택

- **LangGraph** - 에이전트 워크플로우 관리
- **Claude claude-sonnet-4-6** - 코드 분석 LLM
- **PyGithub** - GitHub API 연동
- **Streamlit** - 웹 UI
- **Docker** - 컨테이너화
