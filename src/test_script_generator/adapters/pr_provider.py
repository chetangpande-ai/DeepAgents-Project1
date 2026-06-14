from dataclasses import dataclass


@dataclass(frozen=True)
class PullRequestPlan:
    title: str
    body_path: str
    enabled: bool


def build_pr_plan(title_prefix: str, source_ids: list[str], report_path: str, enabled: bool) -> PullRequestPlan:
    joined = ", ".join(source_ids) if source_ids else "manual test cases"
    return PullRequestPlan(
        title=f"{title_prefix} {joined}",
        body_path=report_path,
        enabled=enabled,
    )
