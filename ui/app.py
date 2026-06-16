import streamlit as st
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

from agent.reviewer import run_pr_review, run_batch_pr_review
from db.history import init_db, save_review, get_history, delete_review

# ── 페이지 설정 ────────────────────────────────────────────
st.set_page_config(
    page_title="AI PR Reviewer",
    page_icon="🔍",
    layout="wide",
)

init_db()

st.title("🔍 AI PR Reviewer")
st.caption("LangGraph + Claude로 만든 코드 리뷰 에이전트")

# ── 탭 레이아웃 ────────────────────────────────────────────
tab_single, tab_batch, tab_history = st.tabs(["단일 PR 리뷰", "배치 리뷰", "히스토리"])


# ──────────────────────────────────────────────────────────
# 탭 1: 단일 PR 리뷰
# ──────────────────────────────────────────────────────────
with tab_single:
    with st.form("review_form"):
        pr_url = st.text_input(
            "GitHub PR URL",
            placeholder="https://github.com/owner/repo/pull/42",
        )

        col1, col2 = st.columns(2)
        with col1:
            post_to_github = st.checkbox(
                "GitHub PR에 리뷰 코멘트 자동 등록",
                value=False,
                help="체크하면 리뷰 결과가 GitHub PR에 직접 코멘트로 달립니다.",
            )
        with col2:
            extensions = st.text_input(
                "파일 확장자 필터 (선택)",
                placeholder=".py,.ts,.js",
                help="쉼표로 구분. 비워두면 전체 파일을 리뷰합니다.",
            )

        submitted = st.form_submit_button("리뷰 시작", type="primary", use_container_width=True)

    if submitted:
        if not pr_url.strip():
            st.error("PR URL을 입력해주세요.")
        elif "github.com" not in pr_url or "/pull/" not in pr_url:
            st.error("올바른 GitHub PR URL을 입력해주세요. (예: https://github.com/owner/repo/pull/42)")
        else:
            with st.spinner("🤖 PR을 분석하고 있습니다..."):
                try:
                    result = run_pr_review(
                        pr_url.strip(),
                        post_to_github=post_to_github,
                        extensions=extensions.strip(),
                    )
                    save_review(pr_url.strip(), result, extensions.strip())

                    st.success("✅ 리뷰 완료!")
                    if post_to_github:
                        st.info("📝 GitHub PR에 코멘트가 등록되었습니다.")

                    st.divider()
                    st.markdown("## 리뷰 결과")
                    st.markdown(result)

                    # 다운로드 버튼
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    pr_id = pr_url.rstrip("/").split("/")[-1]
                    filename = f"review_pr{pr_id}_{timestamp}.md"
                    st.download_button(
                        label="📥 리뷰 결과 다운로드 (.md)",
                        data=f"# PR 리뷰 결과\n\n**PR URL:** {pr_url}\n**일시:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n---\n\n{result}",
                        file_name=filename,
                        mime="text/markdown",
                    )

                except Exception as e:
                    st.error(f"오류가 발생했습니다: {str(e)}")
                    st.exception(e)


# ──────────────────────────────────────────────────────────
# 탭 2: 배치 PR 리뷰
# ──────────────────────────────────────────────────────────
with tab_batch:
    st.markdown("여러 PR URL을 한 번에 리뷰합니다. 한 줄에 하나씩 입력하세요.")

    with st.form("batch_form"):
        batch_urls = st.text_area(
            "PR URL 목록",
            placeholder="https://github.com/owner/repo/pull/1\nhttps://github.com/owner/repo/pull/2",
            height=150,
        )

        col1, col2 = st.columns(2)
        with col1:
            batch_post = st.checkbox("GitHub에 코멘트 자동 등록", value=False)
        with col2:
            batch_extensions = st.text_input("파일 확장자 필터", placeholder=".py,.ts")

        batch_submitted = st.form_submit_button("배치 리뷰 시작", type="primary", use_container_width=True)

    if batch_submitted:
        urls = [u.strip() for u in batch_urls.strip().splitlines() if u.strip()]
        if not urls:
            st.error("PR URL을 최소 하나 입력해주세요.")
        else:
            valid_urls = [u for u in urls if "github.com" in u and "/pull/" in u]
            invalid = [u for u in urls if u not in valid_urls]
            if invalid:
                st.warning(f"올바르지 않은 URL {len(invalid)}개는 건너뜁니다: {', '.join(invalid)}")

            if valid_urls:
                progress = st.progress(0, text="배치 리뷰 시작...")
                batch_results = {}

                for i, url in enumerate(valid_urls):
                    progress.progress((i) / len(valid_urls), text=f"리뷰 중... ({i+1}/{len(valid_urls)}) {url}")
                    try:
                        result = run_pr_review(url, post_to_github=batch_post, extensions=batch_extensions.strip())
                        batch_results[url] = result
                        save_review(url, result, batch_extensions.strip())
                    except Exception as e:
                        batch_results[url] = f"❌ 리뷰 실패: {type(e).__name__}: {str(e)}"

                progress.progress(1.0, text="완료!")
                st.success(f"✅ {len(valid_urls)}개 PR 리뷰 완료!")

                # 결과 표시 및 일괄 다운로드
                all_content = []
                for url, result in batch_results.items():
                    pr_id = url.rstrip("/").split("/")[-1]
                    all_content.append(f"# PR #{pr_id}\n\n**URL:** {url}\n\n{result}\n\n---\n")

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                st.download_button(
                    label=f"📥 전체 리뷰 다운로드 ({len(valid_urls)}개)",
                    data="\n".join(all_content),
                    file_name=f"batch_review_{timestamp}.md",
                    mime="text/markdown",
                )

                for url, result in batch_results.items():
                    pr_id = url.rstrip("/").split("/")[-1]
                    with st.expander(f"PR #{pr_id} — {url}", expanded=False):
                        st.markdown(result)


# ──────────────────────────────────────────────────────────
# 탭 3: 히스토리
# ──────────────────────────────────────────────────────────
with tab_history:
    st.markdown("저장된 리뷰 히스토리를 조회합니다.")

    history = get_history(limit=50)

    if not history:
        st.info("저장된 리뷰 히스토리가 없습니다. PR을 리뷰하면 자동으로 저장됩니다.")
    else:
        st.caption(f"총 {len(history)}개의 리뷰 기록")

        for row in history:
            row_id, pr_url, created_at, extensions, preview = row
            pr_id = pr_url.rstrip("/").split("/")[-1]
            repo_part = "/".join(pr_url.rstrip("/").split("/")[-4:-2])
            label = f"PR #{pr_id} — {repo_part}  |  {created_at[:16]}"
            if extensions:
                label += f"  |  필터: {extensions}"

            with st.expander(label, expanded=False):
                full = get_history(row_id=row_id)
                if full:
                    st.markdown(full[0][-1])
                col_dl, col_del = st.columns([3, 1])
                with col_dl:
                    if full:
                        st.download_button(
                            label="📥 다운로드",
                            data=full[0][-1],
                            file_name=f"review_pr{pr_id}_{created_at[:10]}.md",
                            mime="text/markdown",
                            key=f"dl_{row_id}",
                        )
                with col_del:
                    if st.button("🗑️ 삭제", key=f"del_{row_id}"):
                        delete_review(row_id)
                        st.rerun()


# ── 사이드바 ───────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 사용 방법")
    st.markdown("""
1. **단일 PR 리뷰**: PR URL 입력 후 리뷰 시작
2. **배치 리뷰**: 여러 URL을 한 줄씩 입력
3. **히스토리**: 과거 리뷰 조회 및 다운로드

---

## 리뷰 항목
- 📋 PR 요약
- ✅ 잘된 점
- 🐛 버그 / 논리 오류
- 🔧 코드 품질 / 개선 제안
- 🔒 보안 취약점
- 🚀 성능 고려사항
- 💬 총평

---

## 주의사항
- GitHub Token에 `repo` 권한이 필요합니다
- Private 레포도 지원합니다
- 대용량 PR은 자동으로 분할 처리됩니다
    """)
