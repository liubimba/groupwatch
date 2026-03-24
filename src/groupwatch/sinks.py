from __future__ import annotations

import csv
from pathlib import Path
from typing import Protocol

from .models import ERROR_COLUMNS, POST_COLUMNS, ErrorRecord, Post


class Sink(Protocol):
    def write_posts(self, posts: list[Post]) -> None: ...

    def write_error(self, error: ErrorRecord) -> None: ...


def _append(path: Path, header: list[str], rows: list[list[str]]) -> None:
    fresh = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if fresh:
            writer.writerow(header)
        writer.writerows(rows)


class CsvSink:
    def __init__(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        self.posts_path = directory / "posts.csv"
        self.errors_path = directory / "errors.csv"

    def write_posts(self, posts: list[Post]) -> None:
        if posts:
            _append(self.posts_path, POST_COLUMNS, [p.row() for p in posts])

    def write_error(self, error: ErrorRecord) -> None:
        _append(self.errors_path, ERROR_COLUMNS, [error.row()])


class GoogleSheetSink:
    def __init__(self, spreadsheet_key: str, credentials: Path) -> None:
        import gspread

        book = gspread.service_account(filename=str(credentials)).open_by_key(spreadsheet_key)
        self.posts = self._sheet(book, "posts", POST_COLUMNS)
        self.errors = self._sheet(book, "errors", ERROR_COLUMNS)

    @staticmethod
    def _sheet(book, title: str, header: list[str]):
        import gspread

        try:
            sheet = book.worksheet(title)
        except gspread.WorksheetNotFound:
            sheet = book.add_worksheet(title, rows=1000, cols=len(header))
        if not sheet.row_values(1):
            sheet.append_row(header)
        return sheet

    def write_posts(self, posts: list[Post]) -> None:
        if posts:
            self.posts.append_rows([p.row() for p in posts], value_input_option="RAW")

    def write_error(self, error: ErrorRecord) -> None:
        self.errors.append_row(error.row(), value_input_option="RAW")
