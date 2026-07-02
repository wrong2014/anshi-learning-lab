"""
P01 理科学习卡点定位智能体 —— Web 服务

使用 ConversationAgent（LLM 驱动）代替旧的 DiagnosticEngine（问卷状态机）。
"""
from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

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


import dataclasses

def persist_event(session_id: str, event_type: str, payload) -> None:
    target = DATA_ROOT / f"{session_id}.jsonl"
    record = {"event_type": event_type, "payload": payload}
    with target.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")

def save_session_state(session: ConversationSession) -> None:
    target = DATA_ROOT / f"{session.session_id}_state.json"
    with target.open("w", encoding="utf-8") as file:
        # Convert Enum Subject to string for JSON serialization
        session_dict = dataclasses.asdict(session)
        session_dict["rule_subject"] = session_dict["rule_subject"].value
        file.write(json.dumps(session_dict, ensure_ascii=False, indent=2))

def load_all_sessions() -> None:
    from science_diagnostic_agent.models import Subject
    for state_file in DATA_ROOT.glob("*_state.json"):
        try:
            with state_file.open("r", encoding="utf-8") as file:
                data = json.load(file)
                # Convert string back to Subject Enum
                if "rule_subject" in data:
                    data["rule_subject"] = Subject(data["rule_subject"])
                session = ConversationSession(**data)
                sessions[session.session_id] = session
        except Exception as e:
            print(f"Failed to load session {state_file}: {e}")

# Load all sessions at module initialization
load_all_sessions()


class Handler(BaseHTTPRequestHandler):
    server_version = "P01DiagnosticAgent/2.0"

    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/start":
            session, turn_result = agent.start_session()
            sessions[session.session_id] = session
            save_session_state(session)

            persist_event(session.session_id, "session_started", {
                "session_id": session.session_id,
            })

            response = {
                "session_id": session.session_id,
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

                # 记录用户输入
                persist_event(session_id, "user_input", {
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

                save_session_state(session)

                response = {
                    "session_id": session_id,
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
    print(f"P01 Conversational Agent running at http://127.0.0.1:8765")
    print(f"  LLM mode: {llm_adapter.status().mode}")
    print(f"  DeepSeek ready: {llm_adapter.status().deepseek_ready}")
    server.serve_forever()


if __name__ == "__main__":
    main()
