from __future__ import annotations

import json
import os
import traceback
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .client import NovaCoreClient


class NovaWindow(QMainWindow):
    def __init__(self, client: NovaCoreClient) -> None:
        super().__init__()
        self.client = client
        self.last_intent: dict[str, Any] | None = None
        self.last_steps: list[dict[str, Any]] = []
        self.last_task_id: str | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Nova Command Center")
        self.resize(1380, 900)
        self.setStyleSheet(self._stylesheet())

        root = QWidget()
        self.setCentralWidget(root)
        layout = QVBoxLayout(root)

        title = QLabel("NOVA // DEV SECOND MIND")
        title.setObjectName("Title")
        layout.addWidget(title)

        subtitle = QLabel("Planner + Executor + Safe Approval Gate + Audit Timeline")
        subtitle.setObjectName("Subtitle")
        layout.addWidget(subtitle)

        prompt_layout = QHBoxLayout()
        self.prompt_input = QLineEdit()
        self.prompt_input.setPlaceholderText(
            "Describe a coding task, bootstrap brief, or autonomous workflow..."
        )
        prompt_layout.addWidget(self.prompt_input, 1)

        self.plan_button = QPushButton("Plan")
        self.plan_button.clicked.connect(self.on_plan_clicked)
        prompt_layout.addWidget(self.plan_button)

        self.ask_ai_button = QPushButton("Ask AI")
        self.ask_ai_button.clicked.connect(self.on_ask_ai_clicked)
        prompt_layout.addWidget(self.ask_ai_button)

        self.queue_dry_button = QPushButton("Queue Agent (Dry)")
        self.queue_dry_button.clicked.connect(self.on_queue_agent_dry_clicked)
        prompt_layout.addWidget(self.queue_dry_button)

        self.queue_exec_button = QPushButton("Queue Agent (Execute)")
        self.queue_exec_button.clicked.connect(self.on_queue_agent_execute_clicked)
        prompt_layout.addWidget(self.queue_exec_button)

        self.ptt_button = QPushButton("PTT Fallback")
        self.ptt_button.clicked.connect(self.on_push_to_talk_clicked)
        prompt_layout.addWidget(self.ptt_button)

        layout.addLayout(prompt_layout)

        content = QGridLayout()
        layout.addLayout(content, 1)

        content.addWidget(QLabel("Response"), 0, 0)
        content.addWidget(QLabel("Execution Gate"), 0, 1)
        content.addWidget(QLabel("Task Queue"), 0, 2)

        self.response_box = QTextEdit()
        self.response_box.setReadOnly(True)
        content.addWidget(self.response_box, 1, 0)

        safety_panel = QWidget()
        safety_layout = QVBoxLayout(safety_panel)
        self.approve_writes = QCheckBox("Approve write/bootstrap/memory mutations")
        self.approve_system = QCheckBox("Approve system/install/git/network actions")
        self.execute_approved = QPushButton("Execute Current Plan (Approved Only)")
        self.execute_approved.clicked.connect(self.on_execute_approved_clicked)
        self.dry_run_button = QPushButton("Execute Current Plan (Dry Run)")
        self.dry_run_button.clicked.connect(self.on_execute_dry_run_clicked)
        self.capabilities_button = QPushButton("Capabilities + Tools")
        self.capabilities_button.clicked.connect(self.on_capabilities_clicked)
        self.bootstrap_button = QPushButton("Bootstrap Dry Run")
        self.bootstrap_button.clicked.connect(self.on_bootstrap_dry_run_clicked)
        self.voice_status = QLabel("Voice idle.")

        safety_layout.addWidget(self.approve_writes)
        safety_layout.addWidget(self.approve_system)
        safety_layout.addWidget(self.execute_approved)
        safety_layout.addWidget(self.dry_run_button)
        safety_layout.addWidget(self.capabilities_button)
        safety_layout.addWidget(self.bootstrap_button)
        safety_layout.addWidget(self.voice_status)
        safety_layout.addStretch(1)
        content.addWidget(safety_panel, 1, 1)

        task_panel = QWidget()
        task_layout = QVBoxLayout(task_panel)
        task_controls = QHBoxLayout()
        self.refresh_tasks_button = QPushButton("Refresh Tasks")
        self.refresh_tasks_button.clicked.connect(self.on_refresh_tasks_clicked)
        task_controls.addWidget(self.refresh_tasks_button)
        self.view_task_button = QPushButton("View Task")
        self.view_task_button.clicked.connect(self.on_view_task_clicked)
        task_controls.addWidget(self.view_task_button)
        task_layout.addLayout(task_controls)

        self.task_id_input = QLineEdit()
        self.task_id_input.setPlaceholderText("Task ID for view/approve/cancel")
        task_layout.addWidget(self.task_id_input)

        task_action_controls = QHBoxLayout()
        self.approve_task_button = QPushButton("Approve Blocked Task")
        self.approve_task_button.clicked.connect(self.on_approve_task_clicked)
        task_action_controls.addWidget(self.approve_task_button)
        self.cancel_task_button = QPushButton("Cancel Task")
        self.cancel_task_button.clicked.connect(self.on_cancel_task_clicked)
        task_action_controls.addWidget(self.cancel_task_button)
        task_layout.addLayout(task_action_controls)

        self.tasks_box = QTextEdit()
        self.tasks_box.setReadOnly(True)
        task_layout.addWidget(self.tasks_box, 1)
        content.addWidget(task_panel, 1, 2)

        audit_header = QHBoxLayout()
        audit_header.addWidget(QLabel("Audit Timeline"))
        audit_header.addStretch(1)
        self.refresh_audit_button = QPushButton("Refresh Audit")
        self.refresh_audit_button.clicked.connect(self.on_refresh_audit_clicked)
        audit_header.addWidget(self.refresh_audit_button)
        layout.addLayout(audit_header)

        self.audit_box = QTextEdit()
        self.audit_box.setReadOnly(True)
        self.audit_box.setMinimumHeight(220)
        layout.addWidget(self.audit_box)

        self.response_box.setPlainText(
            "Nova is ready. Use Queue Agent for autonomous planning/execution."
        )
        self.run_safe(self._check_connection)

    def on_plan_clicked(self) -> None:
        self.run_safe(self._on_plan_clicked_impl)

    def _on_plan_clicked_impl(self) -> None:
        prompt = self.require_prompt()
        response = self.client.post("/actions/plan", {"input": prompt, "channel": "text"})
        self.last_intent = response.get("intent")
        self.last_steps = response.get("steps", [])
        self.response_box.setPlainText(json.dumps(response, indent=2))

    def on_execute_dry_run_clicked(self) -> None:
        self.run_safe(self._on_execute_dry_run_clicked_impl)

    def _on_execute_dry_run_clicked_impl(self) -> None:
        self.ensure_plan_ready()
        response = self.client.post(
            "/actions/execute",
            {
                "mode": "dry-run",
                "intent": self.last_intent,
                "steps": self.last_steps,
                "approvals": self.build_approvals(allow_write=False, allow_system=False),
            },
        )
        self.response_box.setPlainText(json.dumps(response, indent=2))

    def on_execute_approved_clicked(self) -> None:
        self.run_safe(self._on_execute_approved_clicked_impl)

    def _on_execute_approved_clicked_impl(self) -> None:
        self.ensure_plan_ready()
        response = self.client.post(
            "/actions/execute",
            {
                "mode": "execute",
                "intent": self.last_intent,
                "steps": self.last_steps,
                "approvals": self.build_approvals(
                    allow_write=self.approve_writes.isChecked(),
                    allow_system=self.approve_system.isChecked(),
                ),
            },
        )
        self.response_box.setPlainText(json.dumps(response, indent=2))
        self.on_refresh_audit_clicked()

    def on_bootstrap_dry_run_clicked(self) -> None:
        self.run_safe(self._on_bootstrap_dry_run_clicked_impl)

    def _on_bootstrap_dry_run_clicked_impl(self) -> None:
        prompt = self.require_prompt()
        target = os.getenv("NOVA_BOOTSTRAP_TARGET", os.path.expanduser("~/Desktop"))
        response = self.client.post(
            "/bootstrap/create",
            {"brief": prompt, "targetDirectory": target, "mode": "dry-run"},
        )
        self.response_box.setPlainText(json.dumps(response, indent=2))

    def on_queue_agent_dry_clicked(self) -> None:
        self.run_safe(lambda: self._queue_agent(mode="dry-run"))

    def on_queue_agent_execute_clicked(self) -> None:
        self.run_safe(lambda: self._queue_agent(mode="execute"))

    def _queue_agent(self, *, mode: str) -> None:
        prompt = self.require_prompt()
        approvals = self.build_approvals(
            allow_write=self.approve_writes.isChecked(),
            allow_system=self.approve_system.isChecked(),
        )
        response = self.client.post(
            "/agent/task",
            {
                "prompt": prompt,
                "channel": "text",
                "mode": mode,
                "priority": "high" if mode == "execute" else "normal",
                "approvals": approvals,
                "maxSteps": 8,
                "allowReplan": True,
            },
        )
        task = response.get("task", {})
        self.last_task_id = task.get("id")
        if self.last_task_id:
            self.task_id_input.setText(self.last_task_id)
        self.response_box.setPlainText(json.dumps(response, indent=2))
        self.on_refresh_tasks_clicked()

    def on_refresh_tasks_clicked(self) -> None:
        self.run_safe(self._on_refresh_tasks_clicked_impl)

    def _on_refresh_tasks_clicked_impl(self) -> None:
        tasks = self.client.get("/agent/tasks?limit=20")
        self.tasks_box.setPlainText(json.dumps(tasks, indent=2))

    def on_view_task_clicked(self) -> None:
        self.run_safe(self._on_view_task_clicked_impl)

    def _on_view_task_clicked_impl(self) -> None:
        task_id = self.require_task_id()
        response = self.client.get(f"/agent/task/{task_id}")
        self.response_box.setPlainText(json.dumps(response, indent=2))
        self.last_task_id = task_id

    def on_approve_task_clicked(self) -> None:
        self.run_safe(self._on_approve_task_clicked_impl)

    def _on_approve_task_clicked_impl(self) -> None:
        task_id = self.require_task_id()
        task_response = self.client.get(f"/agent/task/{task_id}")
        task = task_response.get("task", {})
        approvals = self.build_task_approvals(task)
        response = self.client.post(
            f"/agent/task/{task_id}/approve",
            {"approvals": approvals, "mode": "execute"},
        )
        self.response_box.setPlainText(json.dumps(response, indent=2))
        self.on_refresh_tasks_clicked()

    def on_cancel_task_clicked(self) -> None:
        self.run_safe(self._on_cancel_task_clicked_impl)

    def _on_cancel_task_clicked_impl(self) -> None:
        task_id = self.require_task_id()
        response = self.client.post(f"/agent/task/{task_id}/cancel", {})
        self.response_box.setPlainText(json.dumps(response, indent=2))
        self.on_refresh_tasks_clicked()

    def on_push_to_talk_clicked(self) -> None:
        text, ok = QInputDialog.getText(
            self,
            "Push-To-Talk (text fallback)",
            "Voice stack not wired yet. Type what you said:",
        )
        if ok and text.strip():
            self.prompt_input.setText(text.strip())
            self.voice_status.setText("Captured input via text fallback.")

    def on_ask_ai_clicked(self) -> None:
        self.run_safe(self._on_ask_ai_clicked_impl)

    def _on_ask_ai_clicked_impl(self) -> None:
        prompt = self.require_prompt()
        response = self.client.post(
            "/assistant/respond",
            {"input": prompt, "channel": "text", "includePlan": True},
        )
        self.last_intent = response.get("intent")
        self.last_steps = response.get("steps", [])
        self.response_box.setPlainText(json.dumps(response, indent=2))

    def on_capabilities_clicked(self) -> None:
        self.run_safe(self._on_capabilities_clicked_impl)

    def _on_capabilities_clicked_impl(self) -> None:
        response = self.client.get("/actions/catalog")
        self.response_box.setPlainText(json.dumps(response, indent=2))

    def on_refresh_audit_clicked(self) -> None:
        self.run_safe(self._on_refresh_audit_clicked_impl)

    def _on_refresh_audit_clicked_impl(self) -> None:
        response = self.client.get("/audit/timeline?limit=20")
        self.audit_box.setPlainText(json.dumps(response, indent=2))

    def run_safe(self, callback: Any) -> None:
        try:
            callback()
        except Exception as error:  # noqa: BLE001
            details = "".join(traceback.format_exception_only(type(error), error)).strip()
            self.response_box.setPlainText(f"Nova action failed.\n{details}")
            QMessageBox.critical(self, "Nova Error", f"{error}")

    def _check_connection(self) -> None:
        health = self.client.get("/health")
        model_meta = self.client.get("/meta/model")
        self.voice_status.setText(
            "Core online at "
            f"{health.get('baseUrl', 'unknown')} | "
            f"Model: {model_meta.get('provider')}:{model_meta.get('model')}"
        )
        self.on_refresh_tasks_clicked()
        self.on_refresh_audit_clicked()

    def require_prompt(self) -> str:
        text = self.prompt_input.text().strip()
        if not text:
            raise ValueError("Prompt is empty.")
        return text

    def require_task_id(self) -> str:
        task_id = self.task_id_input.text().strip() or (self.last_task_id or "")
        if not task_id:
            raise ValueError("Task ID is required.")
        return task_id

    def ensure_plan_ready(self) -> None:
        if self.last_intent and self.last_steps:
            return
        prompt = self.require_prompt()
        response = self.client.post("/actions/plan", {"input": prompt, "channel": "text"})
        self.last_intent = response.get("intent")
        self.last_steps = response.get("steps", [])

    def build_approvals(self, allow_write: bool, allow_system: bool) -> list[dict[str, Any]]:
        approvals: list[dict[str, Any]] = []
        for step in self.last_steps:
            if not step.get("requiresApproval"):
                continue
            kind = step.get("kind")
            approved = False
            if kind in {"write", "bootstrap", "memory"}:
                approved = allow_write
            elif kind in {"system", "install", "git", "network"}:
                approved = allow_system
            approvals.append(
                {
                    "actionId": step.get("id"),
                    "approved": approved,
                    "approver": "desktop-user",
                    "decidedAt": "",
                }
            )
        return approvals

    def build_task_approvals(self, task: dict[str, Any]) -> list[dict[str, Any]]:
        approval_requests = task.get("approvalRequests", [])
        steps = {item.get("id"): item for item in task.get("steps", [])}
        approvals: list[dict[str, Any]] = []
        allow_write = self.approve_writes.isChecked()
        allow_system = self.approve_system.isChecked()

        for request in approval_requests:
            action_id = request.get("actionId")
            step = steps.get(action_id, {})
            kind = step.get("kind")
            approved = False
            if kind in {"write", "bootstrap", "memory"}:
                approved = allow_write
            elif kind in {"system", "install", "git", "network"}:
                approved = allow_system
            approvals.append(
                {
                    "actionId": action_id,
                    "approved": approved,
                    "approver": "desktop-user",
                    "decidedAt": "",
                }
            )
        return approvals

    def _stylesheet(self) -> str:
        return """
        QWidget {
            background-color: #0a0f1e;
            color: #dbe9ff;
            font-family: "Consolas";
            font-size: 13px;
        }
        QLabel#Title {
            color: #74f0ff;
            font-size: 28px;
            font-weight: 700;
        }
        QLabel#Subtitle {
            color: #90a8d8;
            font-size: 13px;
            margin-bottom: 8px;
        }
        QLineEdit, QTextEdit {
            background-color: #0f162b;
            border: 1px solid #1f2b49;
            border-radius: 6px;
            padding: 8px;
            selection-background-color: #2656ff;
        }
        QPushButton {
            background-color: #12203f;
            border: 1px solid #2d4b9c;
            border-radius: 6px;
            padding: 8px 12px;
            color: #dff1ff;
            font-weight: 600;
        }
        QPushButton:hover {
            background-color: #173062;
            border-color: #4f7cff;
        }
        QPushButton:pressed {
            background-color: #0d1b38;
        }
        QCheckBox {
            spacing: 8px;
        }
        """


def run() -> int:
    auth_token = os.getenv("NOVA_AUTH_TOKEN", "")
    if not auth_token:
        print("NOVA_AUTH_TOKEN is required.")
        return 1

    host = os.getenv("NOVA_HOST", "127.0.0.1")
    port = os.getenv("NOVA_PORT", "8765")
    base_url = os.getenv("NOVA_BASE_URL", f"http://{host}:{port}")

    app = QApplication([])
    app.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeMenuBar, True)
    window = NovaWindow(NovaCoreClient(base_url=base_url, auth_token=auth_token))
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(run())
