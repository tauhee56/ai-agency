from __future__ import annotations

from typing import Any

PLAYBOOKS: list[dict[str, Any]] = [
    {
        "id": "research_brief",
        "name": "Research brief",
        "department": "Research",
        "description": "Produce a cited research brief with findings and open questions.",
        "adapter": "crewai",
        "task_graph": [
            {"title": "Scope research questions", "role": "researcher"},
            {"title": "Gather sources and synthesize", "role": "researcher"},
            {"title": "Write executive brief", "role": "researcher"},
        ],
        "memory_kinds": ["fact", "decision"],
    },
    {
        "id": "content_draft",
        "name": "Content draft",
        "department": "Operations",
        "description": "Draft on-brand content with optional outreach notes (external gated).",
        "adapter": "crewai",
        "task_graph": [
            {"title": "Outline narrative", "role": "content"},
            {"title": "Draft body copy", "role": "content"},
            {"title": "Prepare outreach external notes", "role": "content", "tags": ["external"]},
        ],
        "memory_kinds": ["procedure"],
    },
    {
        "id": "ops_report",
        "name": "Ops KPI report",
        "department": "Operations",
        "description": "Summarize agent throughput and spend into an ops report.",
        "adapter": "crewai",
        "task_graph": [
            {"title": "Collect run metrics", "role": "ops"},
            {"title": "Draft ops report", "role": "ops"},
        ],
        "memory_kinds": ["fact"],
    },
    {
        "id": "sdlc_idea",
        "name": "Software from idea (MetaGPT optional)",
        "department": "Engineering",
        "description": "SOP SDLC pipeline — requires MetaGPT worker (disabled by default).",
        "adapter": "metagpt",
        "task_graph": [{"title": "Generate repo from idea", "role": "cto"}],
        "memory_kinds": ["procedure", "decision"],
        "requires_metagpt": True,
    },
]


def get_playbook(playbook_id: str) -> dict[str, Any] | None:
    return next((p for p in PLAYBOOKS if p["id"] == playbook_id), None)
