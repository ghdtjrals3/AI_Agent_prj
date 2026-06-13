import os
from github import Github
from langchain_core.tools import tool


def get_github_client() -> Github:
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise ValueError("GITHUB_TOKEN 환경변수가 설정되지 않았습니다.")
    return Github(token)


def parse_pr_url(pr_url: str) -> tuple[str, int]:
    """
    https://github.com/owner/repo/pull/42
    → ("owner/repo", 42)
    """
    parts = pr_url.rstrip("/").split("/")
    pr_number = int(parts[-1])
    repo_name = f"{parts[-4]}/{parts[-3]}"
    return repo_name, pr_number


@tool
def get_pr_diff(pr_url: str) -> str:
    """
    GitHub PR URL을 받아서 변경된 파일들의 diff를 반환합니다.
    """
    try:
        g = get_github_client()
        repo_name, pr_number = parse_pr_url(pr_url)
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(pr_number)

        result = []
        result.append(f"PR 제목: {pr.title}")
        result.append(f"작성자: {pr.user.login}")
        result.append(f"변경된 파일 수: {pr.changed_files}\n")

        files = pr.get_files()
        for file in files:
            result.append(f"=== 파일: {file.filename} ===")
            result.append(f"상태: {file.status} (+{file.additions} / -{file.deletions})")
            if file.patch:
                result.append(file.patch)
            else:
                result.append("(바이너리 파일 또는 diff 없음)")
            result.append("")

        return "\n".join(result)

    except Exception as e:
        return f"PR diff 가져오기 실패: {str(e)}"


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

        pr.create_issue_comment(review_body)
        return f"✅ 리뷰 코멘트가 PR #{pr_number}에 등록되었습니다."

    except Exception as e:
        return f"코멘트 등록 실패: {str(e)}"


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

        info = {
            "제목": pr.title,
            "작성자": pr.user.login,
            "상태": pr.state,
            "설명": pr.body or "(없음)",
            "base 브랜치": pr.base.ref,
            "head 브랜치": pr.head.ref,
            "변경 파일 수": pr.changed_files,
            "추가된 줄": pr.additions,
            "삭제된 줄": pr.deletions,
        }

        return "\n".join([f"{k}: {v}" for k, v in info.items()])

    except Exception as e:
        return f"PR 정보 가져오기 실패: {str(e)}"
