"""
P01 理科学习卡点定位智能体 —— Web 服务

使用 ConversationAgent（LLM 驱动）代替旧的 DiagnosticEngine（问卷状态机）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
ENGINE_ROOT = ROOT / "agent_engine"
sys.path.insert(0, str(ENGINE_ROOT))

from science_diagnostic_agent import (  # noqa: E402
    ConversationAgent,
    ConversationSession,
    LLMAdapter,
    load_provider_registry,
)


registry = load_provider_registry(ENGINE_ROOT / ".env")
llm_adapter = LLMAdapter(registry)
agent = ConversationAgent(llm_adapter)

# 存储活跃的对话会话
sessions: dict[str, ConversationSession] = {}

DATA_ROOT = Path(__file__).resolve().parent / "data" / "sessions"
DATA_ROOT.mkdir(parents=True, exist_ok=True)


def persist_event(session_id: str, event_type: str, payload) -> None:
    target = DATA_ROOT / f"{session_id}.jsonl"
    record = {"event_type": event_type, "payload": payload}
    with target.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_session_events(session_id: str) -> list[dict]:
    if not session_id or "/" in session_id or "\\" in session_id:
        raise FileNotFoundError(session_id)
    target = DATA_ROOT / f"{session_id}.jsonl"
    if not target.exists():
        raise FileNotFoundError(session_id)

    events: list[dict] = []
    with target.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return events


def display_time(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).isoformat(timespec="seconds")


def user_payload_text(payload: dict) -> str:
    free_text = payload.get("free_text")
    if free_text:
        return str(free_text)
    labels = payload.get("selected_labels") or []
    if labels:
        return "、".join(str(item) for item in labels)
    option_ids = payload.get("selected_option_ids") or []
    if option_ids:
        return "、".join(str(item) for item in option_ids)
    return "先跳过"


def summarize_session_file(path: Path) -> dict:
    events = read_session_events(path.stem)
    first_user = ""
    last_text = ""
    user_turns = 0
    is_complete = False

    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload") or {}
        if event_type == "user_input":
            text = user_payload_text(payload)
            user_turns += 1
            if not first_user and text != "先跳过":
                first_user = text
            last_text = text
        elif event_type == "agent_response":
            messages = payload.get("messages") or []
            if messages:
                last_text = str(messages[-1].get("text") or last_text)
            if payload.get("should_conclude"):
                is_complete = True
        elif event_type == "result_generated":
            is_complete = True

    stat = path.stat()
    title = first_user[:32] if first_user else "新对话"
    return {
        "session_id": path.stem,
        "title": title,
        "preview": last_text[:80] if last_text else "尚未输入内容",
        "turn_count": user_turns,
        "is_complete": is_complete,
        "created_at": display_time(stat.st_ctime),
        "updated_at": display_time(stat.st_mtime),
    }


def reconstruct_session_messages(events: list[dict]) -> tuple[list[dict], bool]:
    messages: list[dict] = []
    last_agent_index: int | None = None
    is_complete = False

    for event in events:
        event_type = event.get("event_type")
        payload = event.get("payload") or {}

        if event_type == "user_input":
            messages.append({
                "role": "user",
                "content": user_payload_text(payload),
            })
            continue

        if event_type == "agent_response":
            for agent_message in payload.get("messages") or []:
                messages.append({
                    "role": "agent",
                    "content": agent_message.get("text") or "",
                    "uiBlock": agent_message.get("ui_block"),
                })
                last_agent_index = len(messages) - 1
            if payload.get("should_conclude"):
                is_complete = True
            continue

        if event_type == "result_generated":
            result = payload
            is_complete = True
            if last_agent_index is not None:
                messages[last_agent_index]["result"] = result
            else:
                messages.append({
                    "role": "agent",
                    "content": "我先把这次卡点整理成一个可执行的判断。",
                    "result": result,
                })

    return messages, is_complete


class Handler(BaseHTTPRequestHandler):
    server_version = "MathScreeningAgent/2.0"

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/start":
            session, turn_result = agent.start_session()
            sessions[session.session_id] = session

            persist_event(session.session_id, "session_started", {
                "session_id": session.session_id,
            })

            response = {
                "session_id": session.session_id,
                "active_ui_block_id": session.pending_ui_block_id,
                "agent_messages": [
                    {
                        "text": msg.text,
                        "ui_block": msg.ui_block,
                    }
                    for msg in turn_result.messages
                ],
                "is_complete": turn_result.should_conclude,
                "result": turn_result.result,
            }
            self.send_json(response)
            return

        if parsed.path == "/api/sessions":
            session_files = sorted(
                DATA_ROOT.glob("*.jsonl"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            )
            summaries = [summarize_session_file(path) for path in session_files]
            self.send_json({
                "sessions": [
                    summary
                    for summary in summaries
                    if summary["turn_count"] > 0
                ]
            })
            return

        if parsed.path.startswith("/api/sessions/"):
            session_id = unquote(parsed.path.rsplit("/", 1)[-1])
            try:
                events = read_session_events(session_id)
            except FileNotFoundError:
                self.send_json({"error": "Session not found"}, status=404)
                return

            messages, is_complete = reconstruct_session_messages(events)
            target = DATA_ROOT / f"{session_id}.jsonl"
            summary = summarize_session_file(target)
            self.send_json({
                **summary,
                "messages": messages,
                "is_complete": is_complete,
            })
            return

        if parsed.path == "/api/status":
            status = llm_adapter.status()
            self.send_json(status.model_dump(mode="json"))
            return

        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/answer":
            try:
                payload = self.read_json()
                session_id = payload["session_id"]
                session = sessions.get(session_id)

                if not session:
                    self.send_json({"error": "Session not found"}, status=404)
                    return

                if session.is_complete:
                    self.send_json({"error": "Session already completed"}, status=400)
                    return

                free_text = payload.get("free_text") or None
                selected_option_ids = payload.get("selected_option_ids") or []
                selected_labels = payload.get("selected_labels") or []
                ui_block_id = payload.get("ui_block_id") or None

                # 记录用户输入
                persist_event(session_id, "user_input", {
                    "ui_block_id": ui_block_id,
                    "pending_ui_block_id": session.pending_ui_block_id,
                    "free_text": free_text,
                    "selected_option_ids": selected_option_ids,
                    "selected_labels": selected_labels,
                    "turn": session.turn_count,
                })

                # 调用对话智能体
                turn_result = agent.process_user_input(
                    session=session,
                    text=free_text,
                    selected_option_ids=selected_option_ids,
                    selected_labels=selected_labels,
                    ui_block_id=ui_block_id,
                )

                # 记录智能体回复
                persist_event(session_id, "agent_response", {
                    "messages": [{"text": m.text, "ui_block": m.ui_block} for m in turn_result.messages],
                    "should_conclude": turn_result.should_conclude,
                    "thinking": turn_result.thinking,
                    "turn": session.turn_count,
                })

                if turn_result.result:
                    persist_event(session_id, "result_generated", turn_result.result)

                response = {
                    "session_id": session_id,
                    "active_ui_block_id": session.pending_ui_block_id,
                    "agent_messages": [
                        {
                            "text": msg.text,
                            "ui_block": msg.ui_block,
                        }
                        for msg in turn_result.messages
                    ],
                    "is_complete": turn_result.should_conclude,
                    "result": turn_result.result,
                }
                self.send_json(response)

            except Exception as exc:
                import traceback
                traceback.print_exc()
                self.send_json({"error": str(exc)}, status=400)
            return

        self.send_error(404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def read_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format, *args):
        print("%s - %s" % (self.address_string(), format % args))


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print(f"Math Screening Agent V2 running at http://127.0.0.1:8765")
    print(f"  LLM mode: {llm_adapter.status().mode}")
    print(f"  DeepSeek ready: {llm_adapter.status().deepseek_ready}")
    server.serve_forever()


if __name__ == "__main__":
    main()
