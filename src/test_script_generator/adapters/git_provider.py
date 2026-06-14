from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass(frozen=True)
class BranchPlan:
    base_branch: str
    work_branch: str
    remote_name: str


def build_branch_plan(prefix: str, source_ids: list[str], base_branch: str, remote: str) -> BranchPlan:
    suffix = "-".join(source_ids[:3]) if source_ids else "manual"
    safe_suffix = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in suffix)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    return BranchPlan(
        base_branch=base_branch,
        work_branch=f"{prefix}/{safe_suffix}-{timestamp}",
        remote_name=remote,
    )
