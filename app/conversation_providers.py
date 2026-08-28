from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SESSION_ID_PATTERN = re.compile(
    r"(?P<id>[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12})"
)


@dataclass(frozen=True)
class ConversationMessage:
    cursor: int
    role: str
    content: str
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ConversationSession:
    provider: str
    session_id: str
    title: str
    started_at: str
    updated_at: str
    message_count: int
    end_cursor: int
    source_version: str
    archived: bool = False
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ConversationProvider(ABC):
    """Read-only boundary around one native conversation store."""

    provider_name: str

    @abstractmethod
    def detect(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def list_sessions(self, *, limit: int = 100) -> list[ConversationSession]:
        raise NotImplementedError

    @abstractmethod
    def get_session_metadata(self, session_id: str) -> ConversationSession:
        raise NotImplementedError

    @abstractmethod
    def read_messages(self, session_id: str) -> list[ConversationMessage]:
        raise NotImplementedError

    def read_since(self, session_id: str, cursor: int) -> list[ConversationMessage]:
        return [message for message in self.read_messages(session_id) if message.cursor > cursor]


class CodexConversationProvider(ConversationProvider):
    """Parse locally observed Codex rollout JSONL without modifying Codex state.

    Codex 0.150.1 stores active rollouts below
    ``$CODEX_HOME/sessions/YYYY/MM/DD``. The parser is intentionally contained in
    this adapter because rollout details may change between Codex versions.
    """

    provider_name = "codex"

    def __init__(self, codex_home: Path | str | None = None, executable: str | None = None):
        configured_home = (
            codex_home
            or os.getenv("PROJECT_OS_CODEX_HOME")
            or os.getenv("CODEX_HOME")
            or (Path.home() / ".codex")
        )
        self.codex_home = Path(configured_home).expanduser().resolve()
        self.executable = executable if executable is not None else self._find_executable()

    @staticmethod
    def _find_executable() -> str:
        candidates = ["codex"]
        if os.name == "nt":
            candidates = ["codex.cmd", "codex.exe", "codex"]
        for candidate in candidates:
            found = shutil.which(candidate)
            if found:
                return found
        return ""

    def detect(self) -> dict[str, Any]:
        sessions_dir = self.codex_home / "sessions"
        archived_dir = self.codex_home / "archived_sessions"
        store_found = sessions_dir.is_dir() or archived_dir.is_dir()
        installed = bool(self.executable and Path(self.executable).exists())
        detected = installed or store_found
        version = self._stored_version()
        if installed:
            version = self._cli_version() or version
        if not detected:
            message = "Codex not detected"
        elif store_found and not installed:
            message = "Codex session store detected; CLI executable not detected"
        elif installed and not store_found:
            message = "Codex detected; no local sessions found"
        else:
            message = "Codex detected"
        return {
            "provider": self.provider_name,
            "detected": detected,
            "installed": installed,
            "store_found": store_found,
            "version": version,
            "message": message,
        }

    def _cli_version(self) -> str:
        if not self.executable:
            return ""
        command: list[str] | str = [self.executable, "--version"]
        if os.name == "nt" and Path(self.executable).suffix.lower() in {".cmd", ".bat"}:
            command = subprocess.list2cmdline([self.executable, "--version"])
        try:
            completed = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=5,
                shell=isinstance(command, str),
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        if completed.returncode != 0:
            return ""
        return (completed.stdout or completed.stderr).strip().splitlines()[0]

    def _stored_version(self) -> str:
        version_path = self.codex_home / "version.json"
        try:
            data = json.loads(version_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        for key in ("latest_version", "version", "current_version"):
            if data.get(key):
                return str(data[key])[:80]
        return ""

    def _title_index(self) -> dict[str, str]:
        path = self.codex_home / "session_index.jsonl"
        titles: dict[str, str] = {}
        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line in handle:
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    session_id = str(item.get("id") or "")
                    title = str(item.get("thread_name") or "").strip()
                    if SESSION_ID_PATTERN.fullmatch(session_id) and title:
                        titles[session_id.lower()] = title[:160]
        except OSError:
            pass
        return titles

    def _session_files(self) -> list[tuple[Path, bool]]:
        files: list[tuple[Path, bool]] = []
        for directory, archived in (
            (self.codex_home / "sessions", False),
            (self.codex_home / "archived_sessions", True),
        ):
            if not directory.is_dir():
                continue
            try:
                root = directory.resolve()
                for path in directory.rglob("*.jsonl"):
                    if not path.is_file():
                        continue
                    try:
                        path.resolve(strict=True).relative_to(root)
                    except (OSError, ValueError):
                        # A symlink must not turn a browser-selected session ID into
                        # an arbitrary local-file read outside the Codex store.
                        continue
                    files.append((path, archived))
            except OSError:
                continue
        files.sort(key=lambda item: self._safe_mtime(item[0]), reverse=True)
        return files

    @staticmethod
    def _safe_mtime(path: Path) -> float:
        try:
            return path.stat().st_mtime
        except OSError:
            return 0.0

    @staticmethod
    def _id_from_filename(path: Path) -> str:
        match = SESSION_ID_PATTERN.search(path.name)
        return match.group("id").lower() if match else ""

    def _path_for_session(self, session_id: str) -> tuple[Path, bool]:
        normalized = str(session_id or "").strip().lower()
        if not SESSION_ID_PATTERN.fullmatch(normalized):
            raise ValueError("Invalid Codex session ID")
        for path, archived in self._session_files():
            if self._id_from_filename(path) == normalized:
                return path, archived
        raise FileNotFoundError("Codex session not found")

    @staticmethod
    def _message_text(payload: dict[str, Any]) -> str:
        parts: list[str] = []
        content = payload.get("content")
        if isinstance(content, str):
            return content.strip()
        if not isinstance(content, list):
            return ""
        for item in content:
            if not isinstance(item, dict):
                continue
            kind = str(item.get("type") or "")
            if kind in {"input_text", "output_text", "text"}:
                text = str(item.get("text") or "").strip()
                if text:
                    parts.append(text)
            elif kind in {"input_image", "image", "image_url"}:
                parts.append("[image omitted]")
        return "\n".join(parts).strip()

    @staticmethod
    def _useful_title_candidate(text: str) -> str:
        candidate = re.sub(r"\s+", " ", str(text or "")).strip()
        technical_prefixes = (
            "<recommended_plugins>",
            "<environment_context>",
            "# agents.md instructions",
            "<instructions>",
            "<skills_instructions>",
        )
        if candidate.lower().startswith(technical_prefixes):
            return ""
        return candidate[:80]

    def _parse_rollout(
        self,
        path: Path,
        *,
        archived: bool,
        include_messages: bool,
        indexed_title: str = "",
    ) -> tuple[ConversationSession, list[ConversationMessage]]:
        session_id = self._id_from_filename(path)
        source_version = ""
        started_at = ""
        updated_at = ""
        end_cursor = -1
        message_count = 0
        parse_errors = 0
        messages: list[ConversationMessage] = []
        first_user_text = ""

        try:
            with path.open("r", encoding="utf-8", errors="replace") as handle:
                for line_number, line in enumerate(handle):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        parse_errors += 1
                        continue
                    timestamp = str(record.get("timestamp") or "")[:80]
                    if timestamp:
                        started_at = started_at or timestamp
                        updated_at = timestamp
                    ordinal = record.get("ordinal")
                    cursor = ordinal if isinstance(ordinal, int) else line_number
                    end_cursor = max(end_cursor, cursor)
                    payload = record.get("payload") if isinstance(record.get("payload"), dict) else {}
                    if record.get("type") == "session_meta":
                        candidate_id = str(payload.get("session_id") or payload.get("id") or "").lower()
                        if SESSION_ID_PATTERN.fullmatch(candidate_id):
                            session_id = candidate_id
                        source_version = str(payload.get("cli_version") or "")[:80]
                        started_at = str(payload.get("timestamp") or started_at)[:80]
                        continue
                    if record.get("type") != "response_item" or payload.get("type") != "message":
                        continue
                    role = str(payload.get("role") or "").lower()
                    if role not in {"user", "assistant"}:
                        continue
                    text = self._message_text(payload)
                    if not text:
                        continue
                    message_count += 1
                    if role == "user" and not first_user_text:
                        first_user_text = text
                    if include_messages:
                        messages.append(ConversationMessage(cursor, role, text, timestamp))
        except OSError as exc:
            error = f"Unreadable Codex session: {type(exc).__name__}"
            return (
                ConversationSession(
                    self.provider_name,
                    session_id,
                    "Unavailable session",
                    "",
                    self._mtime_iso(path),
                    0,
                    -1,
                    "",
                    archived,
                    error,
                ),
                [],
            )

        title = indexed_title.strip()[:160]
        if not title and first_user_text:
            title = self._useful_title_candidate(first_user_text)
        if not title:
            title = f"Codex session {session_id[:8] or 'unknown'}"
        error = ""
        if parse_errors:
            error = f"Skipped {parse_errors} malformed or partial record(s)"
        if not updated_at:
            updated_at = self._mtime_iso(path)
        return (
            ConversationSession(
                self.provider_name,
                session_id,
                title,
                started_at,
                updated_at,
                message_count,
                end_cursor,
                source_version,
                archived,
                error,
            ),
            messages,
        )

    @staticmethod
    def _mtime_iso(path: Path) -> str:
        try:
            return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()
        except OSError:
            return ""

    def list_sessions(self, *, limit: int = 100) -> list[ConversationSession]:
        titles = self._title_index()
        sessions: list[ConversationSession] = []
        for path, archived in self._session_files()[: max(1, min(limit, 500))]:
            session_id = self._id_from_filename(path)
            session, _messages = self._parse_rollout(
                path,
                archived=archived,
                include_messages=False,
                indexed_title=titles.get(session_id, ""),
            )
            sessions.append(session)
        return sessions

    def get_session_metadata(self, session_id: str) -> ConversationSession:
        path, archived = self._path_for_session(session_id)
        titles = self._title_index()
        session, _messages = self._parse_rollout(
            path,
            archived=archived,
            include_messages=False,
            indexed_title=titles.get(session_id.lower(), ""),
        )
        return session

    def read_messages(self, session_id: str) -> list[ConversationMessage]:
        path, archived = self._path_for_session(session_id)
        titles = self._title_index()
        session, messages = self._parse_rollout(
            path,
            archived=archived,
            include_messages=True,
            indexed_title=titles.get(session_id.lower(), ""),
        )
        if session.error and not messages:
            raise ValueError(session.error)
        return messages
