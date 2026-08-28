from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.conversation_import import redacted_messages
from app.conversation_providers import CodexConversationProvider


provider = CodexConversationProvider()
detection = provider.detect()
sessions = provider.list_sessions(limit=10)
healthy = next((item for item in sessions if not item.error and item.message_count), None)

print(f"provider=codex detected={detection['detected']} version={detection['version'] or 'unknown'}")
print(f"inspected_sessions={len(sessions)} isolated_errors={sum(bool(item.error) for item in sessions)}")
if healthy is None:
    print("native_read=UNAVAILABLE (no readable session with messages)")
    raise SystemExit(2)

messages = redacted_messages(provider.read_messages(healthy.session_id))
cursor_monotonic = all(
    previous["cursor"] < current["cursor"]
    for previous, current in zip(messages, messages[1:])
)
session_hash = hashlib.sha256(healthy.session_id.encode("ascii")).hexdigest()[:12]
print(
    "native_read=PASS "
    f"session_hash={session_hash} messages={len(messages)} "
    f"cursor_monotonic={cursor_monotonic}"
)
print("conversation_content_output=SUPPRESSED")
