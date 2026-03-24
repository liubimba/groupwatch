from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime


class Checkpoint(Exception):
    pass


class GroupUnavailable(Exception):
    pass


class NoAccountAvailable(Exception):
    pass


_GROUP_ID = re.compile(r"/groups/([^/?#]+)")


def group_id_from_url(url: str) -> str:
    match = _GROUP_ID.search(url)
    return match.group(1) if match else url.rstrip("/").rsplit("/", 1)[-1]


@dataclass(frozen=True)
class Group:
    url: str
    name: str = ""
    members: frozenset[str] = field(default_factory=frozenset)

    @property
    def id(self) -> str:
        return group_id_from_url(self.url)

    @property
    def title(self) -> str:
        return self.name or self.id


@dataclass(frozen=True)
class Post:
    post_id: str
    group_id: str
    group_name: str
    author: str
    text: str
    url: str
    collected_at: datetime

    def row(self) -> list[str]:
        return [
            self.collected_at.isoformat(timespec="seconds"),
            self.group_name,
            self.author,
            self.text,
            self.url,
            self.post_id,
        ]


POST_COLUMNS = ["collected_at", "group", "author", "text", "url", "post_id"]


@dataclass(frozen=True)
class ErrorRecord:
    at: datetime
    group_id: str
    account: str
    kind: str
    detail: str

    def row(self) -> list[str]:
        return [self.at.isoformat(timespec="seconds"), self.group_id, self.account, self.kind, self.detail]


ERROR_COLUMNS = ["at", "group_id", "account", "kind", "detail"]
