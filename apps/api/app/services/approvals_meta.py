"""Needs-you metadata for approvals (Orca M1 concept)."""

from __future__ import annotations

from typing import Any


def waiting_on_for(action_tag: str, payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    explicit = payload.get("waiting_on")
    if explicit in ("founder", "ci", "external"):
        return str(explicit)
    if action_tag in ("deploy", "destructive", "payment"):
        return "founder"
    if action_tag == "ci" or payload.get("ci"):
        return "ci"
    if action_tag == "external":
        return "external"
    return "founder"


def suggested_actions_for(action_tag: str, waiting_on: str) -> list[dict[str, str]]:
    if waiting_on == "ci":
        return [
            {"id": "wait_ci", "label": "Wait for CI", "decision": "rejected"},
            {"id": "force_approve", "label": "Override & approve", "decision": "approved"},
        ]
    if action_tag == "deploy":
        return [
            {"id": "approve_deploy", "label": "Approve deploy", "decision": "approved"},
            {"id": "reject_deploy", "label": "Block deploy", "decision": "rejected"},
            {"id": "ask_more", "label": "Need more info", "decision": "rejected"},
        ]
    if action_tag == "external":
        return [
            {"id": "send", "label": "Approve send", "decision": "approved"},
            {"id": "keep_draft", "label": "Keep as draft", "decision": "rejected"},
        ]
    if action_tag == "payment":
        return [
            {"id": "pay", "label": "Approve payment", "decision": "approved"},
            {"id": "deny_pay", "label": "Deny payment", "decision": "rejected"},
        ]
    return [
        {"id": "approve", "label": "Approve", "decision": "approved"},
        {"id": "reject", "label": "Reject", "decision": "rejected"},
    ]
