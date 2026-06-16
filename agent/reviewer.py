import os
from typing import Annotated
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from tools.github_tools import get_pr_diff, get_pr_info, post_review_comment


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    pr_url: str
    post_to_github: bool


TOOLS = [get_pr_info, get_pr_diff, post_review_comment]

model = ChatAnthropic(
    model="claude-sonnet-4-6",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=8096,
).bind_tools(TOOLS)

tool_node = ToolNode(TOOLS)

SYSTEM_PROMPT = """당신은 10년 경력의 시니어 소프트웨어 엔지니어입니다. GitHub PR 코드를 꼼꼼하게 리뷰하는 역할을 맡고 있습니다.

## 리뷰 원칙
- 코드를 작성한 개발자를 존중하되, 문제점은 명확하게 짚어주세요.
- 단순 스타일 지적보다 실질적인 버그/보안/성능 이슈에 집중하세요.
- 개선 제안 시 **구체적인 코드 예시**를 함께 제공하세요.

## 리뷰 구조 (반드시 이 순서로 작성)

### 📋 PR 요약
PR이 무엇을 하는지 2~3문장으로 설명.

### ✅ 잘된 점
코드에서 긍정적인 부분 (최소 1개).

### 🐛 버그 / 논리 오류
- 파일명과 줄 번호 명시: `파일명:줄번호`
- Null/None 처리 누락, 엣지 케이스, 잘못된 로직
- **없으면 "발견되지 않음"으로 표기**

### 🔧 코드 품질 / 개선 제안
- 가독성, 중복 코드, 더 나은 패턴
- 각 항목에 수정 코드 예시 포함
- **없으면 "발견되지 않음"으로 표기**

### 🔒 보안 취약점
- 하드코딩된 시크릿, SQL 인젝션, 입력값 검증 누락
- 심각도: [높음/중간/낮음]으로 표기
- **없으면 "발견되지 않음"으로 표기**

### 🚀 성능 고려사항
- N+1 쿼리, 불필요한 반복, 메모리 낭비 등
- **없으면 "발견되지 않음"으로 표기**

### 💬 총평
전반적인 코드 품질 평가 (한 문단). Approve / Request Changes / Needs Discussion 중 하나 권고.

---
post_to_github가 True인 경우 리뷰 완료 후 반드시 post_review_comment 툴로 GitHub에 등록하세요."""


def agent_node(state: AgentState):
    messages = state["messages"]

    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    response = model.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")

    return graph.compile()


def _extract_text(final_state: dict) -> str:
    for message in reversed(final_state["messages"]):
        if hasattr(message, "content") and not hasattr(message, "tool_calls"):
            if isinstance(message.content, str):
                return message.content
            elif isinstance(message.content, list):
                texts = [b["text"] for b in message.content if b.get("type") == "text"]
                return "\n".join(texts)
    return "리뷰 결과를 가져오지 못했습니다."


def run_pr_review(
    pr_url: str,
    post_to_github: bool = False,
    extensions: str = "",
) -> str:
    app = build_graph()

    ext_hint = f"\n\n리뷰 대상 파일 확장자: {extensions} (이 확장자 파일만 diff를 가져옵니다.)" if extensions else ""
    post_instruction = "\n\n리뷰 완료 후 post_review_comment 툴로 GitHub에 코멘트를 등록해주세요." if post_to_github else ""

    initial_state = {
        "messages": [
            HumanMessage(
                content=(
                    f"다음 PR을 리뷰해주세요: {pr_url}\n\n"
                    f"먼저 get_pr_info로 PR 정보를 확인하고, "
                    f"get_pr_diff로 변경된 코드를 가져온 뒤 상세히 리뷰해주세요."
                    f"{ext_hint}{post_instruction}"
                )
            )
        ],
        "pr_url": pr_url,
        "post_to_github": post_to_github,
    }

    final_state = app.invoke(initial_state)
    return _extract_text(final_state)


def run_batch_pr_review(
    pr_urls: list[str],
    post_to_github: bool = False,
    extensions: str = "",
) -> dict[str, str]:
    """여러 PR URL을 순차적으로 리뷰하고 {url: 리뷰결과} 딕셔너리를 반환합니다."""
    results = {}
    for url in pr_urls:
        url = url.strip()
        if not url:
            continue
        try:
            results[url] = run_pr_review(url, post_to_github=post_to_github, extensions=extensions)
        except Exception as e:
            results[url] = f"리뷰 실패: {type(e).__name__}: {str(e)}"
    return results
