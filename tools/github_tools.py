import os
from github import Github, GithubException, RateLimitExceededException
from langchain_core.tools import tool

MAX_DIFF_CHARS = 30_000  # Claude 컨텍스트 절약을 위한 diff 상한
MAX_FILES = 50           # 한 번에 처리할 최대 파일 수


def get_github_client() -> Github:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN 환경변수가 설정되지 않았습니다.")
    return Github(token)


def parse_pr_url(pr_url: str) -> tuple[str, int]:
    """
    https://github.com/owner/repo/pull/42
    -> ("owner/repo", 42)
    """
    parts = pr_url.rstrip("/").split("/")
    if len(parts) < 5 or parts[-2] != "pull":
        raise ValueError(f"올바르지 않은 PR URL 형식입니다: {pr_url}")
    try:
        pr_number = int(parts[-1])
    except ValueError:
        raise ValueError(f"PR 번호를 파싱할 수 없습니다: {parts[-1]}")
    repo_name = f"{parts[-4]}/{parts[-3]}"
    return repo_name, pr_number


def _truncate(text: str, max_chars: int, label: str = "") -> str:
    if len(text) <= max_chars:
        return text
    suffix = f"\n\n[{label}] diff가 너무 커서 {max_chars:,}자로 잘렸습니다. (원본: {len(text):,}자)"
    return text[:max_chars] + suffix


@tool
def get_pr_diff(pr_url: str, extensions: str = "") -> str:
    """
    GitHub PR URL을 받아서 변경된 파일들의 diff를 반환합니다.
    extensions: 쉼표로 구분된 확장자 필터 (예: ".py,.js"). 비어있으면 전체 파일.
    대용량 PR은 자동으로 잘립니다.
    """
    try:
        g = get_github_client()
        repo_name, pr_number = parse_pr_url(pr_url)
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        ext_filter = [e.strip() for e in extensions.split(",") if e.strip()] if extensions else []

        result = []
        result.append(f"PR 제목: {pr.title}")
        result.append(f"작성자: {pr.user.login}")
        result.append(f"변경된 파일 수: {pr.changed_files}\n")

        files = list(pr.get_files())
        if len(files) > MAX_FILES:
            result.append(f"파일이 {len(files)}개로 많아 상위 {MAX_FILES}개만 처리합니다.\n")
            files = files[:MAX_FILES]

        if ext_filter:
            files = [f for f in files if any(f.filename.endswith(e) for e in ext_filter)]
            if not files:
                return f"필터({', '.join(ext_filter)})에 해당하는 변경 파일이 없습니다."

        total_chars = 0
        for file in files:
            header = (
                f"=== 파일: {file.filename} ===\n"
                f"상태: {file.status} (+{file.additions} / -{file.deletions})\n"
            )
            patch = file.patch or "(바이너리 파일 또는 diff 없음)"

            if len(patch) > 10_000:
                patch = patch[:10_000] + f"\n... (이하 생략, 원본 {len(patch):,}자)"

            block = header + patch + "\n"
            total_chars += len(block)

            if total_chars > MAX_DIFF_CHARS:
                result.append(f"전체 diff 한도({MAX_DIFF_CHARS:,}자) 초과로 이후 파일은 생략합니다.")
                break

            result.append(block)

        return "\n".join(result)

    except RateLimitExceededException:
        return "GitHub API Rate Limit 초과입니다. 잠시 후 다시 시도해주세요."
    except GithubException as e:
        status = e.status if hasattr(e, "status") else "unknown"
        if status == 404:
            return f"PR을 찾을 수 없습니다. URL 또는 GITHUB_TOKEN 권한을 확인하세요. ({pr_url})"
        if status == 401:
            return "GITHUB_TOKEN이 유효하지 않거나 권한이 없습니다."
        return f"GitHub API 오류 ({status}): {e.data.get('message', str(e))}"
    except ValueError as e:
        return f"입력값 오류: {str(e)}"
    except Exception as e:
        return f"예상치 못한 오류: {type(e).__name__}: {str(e)}"


@tool
def post_review_comment(pr_url: str, review_body: str) -> str:
    """
    GitHub PR에 리뷰 코멘트를 등록합니다.
    """
    try:
        g = get_github_client()
        repo_name, pr_number = parse_pr_url(pr_url)
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        if not review_body or not review_body.strip():
            return "등록할 리뷰 내용이 비어있습니다."

        pr.create_issue_comment(review_body)
        return f"리뷰 코멘트가 PR #{pr_number}에 등록되었습니다."

    except RateLimitExceededException:
        return "GitHub API Rate Limit 초과입니다. 잠시 후 다시 시도해주세요."
    except GithubException as e:
        status = e.status if hasattr(e, "status") else "unknown"
        if status == 403:
            return "PR에 코멘트를 달 권한이 없습니다. GITHUB_TOKEN의 repo 권한을 확인하세요."
        if status == 404:
            return f"PR을 찾을 수 없습니다: {pr_url}"
        return f"GitHub API 오류 ({status}): {e.data.get('message', str(e))}"
    except ValueError as e:
        return f"입력값 오류: {str(e)}"
    except Exception as e:
        return f"예상치 못한 오류: {type(e).__name__}: {str(e)}"


@tool
def get_pr_info(pr_url: str) -> str:
    """
    PR의 기본 정보(제목, 설명, 라벨 등)를 가져옵니다.
    """
    try:
        g = get_github_client()
        repo_name, pr_number = parse_pr_url(pr_url)
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        labels = ", ".join(label.name for label in pr.labels) or "(없음)"
        reviewers = ", ".join(r.login for r in pr.requested_reviewers) or "(없음)"

        info = {
            "제목": pr.title,
            "작성자": pr.user.login,
            "상태": pr.state,
            "설명": (pr.body or "(없음)")[:500] + ("..." if pr.body and len(pr.body) > 500 else ""),
            "base 브랜치": pr.base.ref,
            "head 브랜치": pr.head.ref,
            "변경 파일 수": pr.changed_files,
            "추가된 줄": pr.additions,
            "삭제된 줄": pr.deletions,
            "라벨": labels,
            "리뷰 요청자": reviewers,
            "draft 여부": "예" if pr.draft else "아니오",
        }

        return "\n".join([f"{k}: {v}" for k, v in info.items()])

    except RateLimitExceededException:
        return "GitHub API Rate Limit 초과입니다. 잠시 후 다시 시도해주세요."
    except GithubException as e:
        status = e.status if hasattr(e, "status") else "unknown"
        if status == 404:
            return f"PR을 찾을 수 없습니다. URL 또는 GITHUB_TOKEN 권한을 확인하세요. ({pr_url})"
        if status == 401:
            return "GITHUB_TOKEN이 유효하지 않거나 권한이 없습니다."
        return f"GitHub API 오류 ({status}): {e.data.get('message', str(e))}"
    except ValueError as e:
        return f"입력값 오류: {str(e)}"
    except Exception as e:
        return f"예상치 못한 오류: {type(e).__name__}: {str(e)}"
