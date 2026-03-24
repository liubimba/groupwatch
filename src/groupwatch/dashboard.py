from __future__ import annotations

from datetime import datetime

from rich.console import Group as Stack
from rich.panel import Panel
from rich.progress_bar import ProgressBar
from rich.table import Table
from rich.text import Text

from .accounts import AccountPool
from .runner import RoundStats


def pass_hours(groups: int, accounts: int, gap: float, visit: float, hourly_limit: int) -> float:
    per_account = min(hourly_limit, 3600 / (gap + visit))
    return groups / (per_account * accounts)


def render(stats: RoundStats, pool: AccountPool) -> Stack:
    finished = stats.done + stats.failed
    elapsed = max((datetime.now() - stats.started).total_seconds(), 0.001)

    head = Table.grid(padding=(0, 3))
    head.add_row(
        Text(f"groups {finished}/{stats.total}", style="bold"),
        Text(f"new posts {stats.new}", style="bold green"),
        Text(f"duplicates skipped {stats.seen - stats.new}", style="dim"),
        Text(f"retries {stats.retries}", style="yellow"),
        Text(f"failed {stats.failed}", style="red"),
        Text(f"{finished / elapsed:.1f} groups/s", style="cyan"),
    )
    bar = ProgressBar(total=max(stats.total, 1), completed=finished, width=100)

    accounts = Table(title="Sessions", expand=True, title_justify="left")
    accounts.add_column("account")
    accounts.add_column("requests", justify="right")
    accounts.add_column("state")
    for a in pool.accounts.values():
        state = Text(f"paused: {a.blocked}", style="red") if a.blocked else (
            Text("fetching", style="green") if a.busy else Text("waiting gap", style="dim")
        )
        accounts.add_row(a.name, str(a.requests), state)

    errors = Table(title="Error journal", expand=True, title_justify="left")
    errors.add_column("kind")
    errors.add_column("count", justify="right")
    for kind, count in stats.errors.most_common():
        errors.add_row(kind, str(count))

    latest = Table(title="Latest new posts", expand=True, title_justify="left")
    latest.add_column("group", no_wrap=True)
    latest.add_column("author", no_wrap=True)
    latest.add_column("text", overflow="ellipsis", no_wrap=True)
    latest.add_column("post id", no_wrap=True, style="dim")
    for p in reversed(stats.latest):
        latest.add_row(p.group_name, p.author, p.text, p.post_id)

    side = Table.grid(expand=True)
    side.add_column(ratio=1)
    side.add_column(ratio=1)
    side.add_row(accounts, errors)
    return Stack(Panel(Stack(head, bar), title="groupwatch"), side, latest)
