import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from agent.reviewer import run_pr_review

# ── 페이지 설정 ────────────────────────────────────────────
st.set_page_config(
    page_title="AI PR Reviewer",
    page_icon="🔍",
    layout="wide",
)

st.title("🔍 AI PR Reviewer")
st.caption("LangGraph + Claude로 만든 코드 리뷰 에이전트")

# ── 입력 폼 ────────────────────────────────────────────────
with st.form("review_form"):
    pr_url = st.text_input(
        "GitHub PR URL",
        placeholder="https://github.com/owner/repo/pull/42",
    )
    post_to_github = st.checkbox(
        "GitHub PR에 리뷰 코멘트 자동 등록",
        value=False,
        help="체크하면 리뷰 결과가 GitHub PR에 직접 코멘트로 달립니다.",
    )
    submitted = st.form_submit_button("리뷰 시작", type="primary", use_container_width=True)

# ── 리뷰 실행 ──────────────────────────────────────────────
if submitted:
    if not pr_url.strip():
        st.error("PR URL을 입력해주세요.")
    elif "github.com" not in pr_url or "/pull/" not in pr_url:
        st.error("올바른 GitHub PR URL을 입력해주세요. (예: https://github.com/owner/repo/pull/42)")
    else:
        with st.spinner("🤖 PR을 분석하고 있습니다..."):
            try:
                result = run_pr_review(pr_url.strip(), post_to_github=post_to_github)

                st.success("✅ 리뷰 완료!")

                if post_to_github:
                    st.info("📝 GitHub PR에 코멘트가 등록되었습니다.")

                st.divider()
                st.markdown("## 리뷰 결과")
                st.markdown(result)

            except Exception as e:
                st.error(f"오류가 발생했습니다: {str(e)}")
                st.exception(e)

# ── 사이드바 ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 사용 방법")
    st.markdown("""
1. GitHub PR URL을 입력하세요
2. GitHub에 자동 등록 여부를 선택하세요
3. **리뷰 시작** 버튼을 누르세요

---

## 리뷰 항목
- 🐛 버그 / 논리 오류
- 🔧 코드 품질 / 개선 제안
- 🔒 보안 취약점

---

## 주의사항
- GitHub Token에 `repo` 권한이 필요합니다
- Private 레포도 지원합니다
    """)
