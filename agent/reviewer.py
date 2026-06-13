import os
from typing import Annotated
from typing_extensions import TypedDict

from langchain_anthropic import ChatAnthropic
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from tools.github_tools import get_pr_diff, get_pr_info, post_review_comment


# ── 상태 정의 ──────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    pr_url: str
    post_to_github: bool


# ── 도구 및 모델 설정 ───────────────────────────────────────
TOOLS = [get_pr_info, get_pr_diff, post_review_comment]

model = ChatAnthropic(
    model="claude-sonnet-4-6",
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_tokens=4096,
).bind_tools(TOOLS)

tool_node = ToolNode(TOOLS)

SYSTEM_PROMPT = """당신은 시니어 소프트웨어 엔지니어입니다. GitHub PR의 코드를 리뷰하는 역할을 맡고 있습니다.

리뷰 시 다음 세 가지 관점에서 분석하세요:

1. 🐛 **버그 / 논리 오류**
   - Null/None 처리 누락
   - 엣지 케이스 미처리
   - 잘못된 로직

2. 🔧 **코드 품질 / 개선 제안**
   - 가독성 개선
   - 중복 코드
   - 더 나은 패턴 제안

3. 🔒 **보안 취약점**
   - 하드코딩된 시크릿
   - SQL 인젝션 가능성
   - 입력값 검증 누락

리뷰는 구체적이고 친절하게, 개선 방법도 함께 제시하세요.
post_to_github가 True인 경우 리뷰 완료 후 반드시 post_review_comment 툴로 GitHub에 등록하세요."""


# ── 노드 정의 ──────────────────────────────────────────────
def agent_node(state: AgentState):
    messages = state["messages"]

    # 시스템 프롬프트가 없으면 추가
    if not any(isinstance(m, SystemMessage) for m in messages):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    response = model.invoke(messages)
    return {"messages": [response]}


def should_continue(state: AgentState) -> str:
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return END


# ── 그래프 구성 ────────────────────────────────────────────
def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)

    graph.set_entry_point("agent")
    graph.add_conditional_edges("agent", should_continue)
    graph.add_edge("tools", "agent")

    return graph.compile()


# ── 실행 함수 ──────────────────────────────────────────────
def run_pr_review(pr_url: str, post_to_github: bool = False) -> str:
    app = build_graph()

    post_instruction = "리뷰 완료 후 post_review_comment 툴로 GitHub에 코멘트를 등록해주세요." if post_to_github else ""

    initial_state = {
        "messages": [
            HumanMessage(
                content=f"다음 PR을 리뷰해주세요: {pr_url}\n\n"
                        f"먼저 get_pr_info로 PR 정보를 확인하고, "
                        f"get_pr_diff로 변경된 코드를 가져온 뒤 상세히 리뷰해주세요.\n"
                        f"{post_instruction}"
            )
        ],
        "pr_url": pr_url,
        "post_to_github": post_to_github,
    }

    final_state = app.invoke(initial_state)

    # 마지막 AI 메시지 반환
    for message in reversed(final_state["messages"]):
        if hasattr(message, "content") and not hasattr(message, "tool_calls"):
            if isinstance(message.content, str):
                return message.content
            elif isinstance(message.content, list):
                texts = [b["text"] for b in message.content if b.get("type") == "text"]
                return "\n".join(texts)

    return "리뷰 결과를 가져오지 못했습니다."
