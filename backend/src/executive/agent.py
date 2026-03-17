from __future__ import annotations

from langchain.agents import create_agent

from src.executive.service import get_advisory_payload, get_status_payload
from src.executive.tools import (
    executive_confirm_action,
    executive_execute_action,
    executive_get_advisory,
    executive_get_audit,
    executive_get_component,
    executive_get_system_state,
    executive_list_actions,
    executive_list_approvals,
    executive_preview_action,
    executive_reject_action,
)
from src.models import create_chat_model
from src.observability import make_trace_id

EXECUTIVE_SYSTEM_PROMPT = """
You are MaestroFlow Executive, the system operator for MaestroFlow.

Rules:
- You are not a generic assistant. You are an operational advisor and control-plane agent.
- Base every operational claim on live Executive tools or explicit advisory output.
- If an action requires approval, preview it first and then explain that approval is required.
- Never claim shell-level authority beyond the supported Executive actions.
- If a user asks for an unsupported action, say so clearly and suggest the closest supported path.
- Prefer concise, operational answers: diagnosis, recommended action, risk, next step.
"""


async def run_executive_chat(messages: list[dict[str, str]]) -> dict:
    recommendations = await get_advisory_payload()
    status = await get_status_payload()

    try:
        agent = create_agent(
            model=create_chat_model(thinking_enabled=False, trace_id=make_trace_id(seed="executive-agent")),
            tools=[
                executive_get_system_state,
                executive_get_component,
                executive_list_actions,
                executive_preview_action,
                executive_execute_action,
                executive_list_approvals,
                executive_confirm_action,
                executive_reject_action,
                executive_get_audit,
                executive_get_advisory,
            ],
            system_prompt=EXECUTIVE_SYSTEM_PROMPT,
        )
        result = await agent.ainvoke(
            {
                "messages": [
                    {
                        "role": "system",
                        "content": f"Current system summary: {status['summary']}\nCurrent advisory count: {len(recommendations)}",
                    },
                    *messages,
                ]
            }
        )
        output_messages = result.get("messages", [])
        answer = ""
        for message in reversed(output_messages):
            if getattr(message, "type", None) == "ai":
                answer = message.text() if hasattr(message, "text") else str(message.content)
                break
        if not answer:
            answer = "Executive agent completed without a final response. Use the system state and advisory panels to continue."
        return {"answer": answer, "recommendations": recommendations}
    except Exception as exc:
        degraded = [item for item in recommendations if item.get("severity") in {"critical", "high"}]
        fallback = "Executive agent could not reach the model layer. Here is the current operational picture instead."
        if degraded:
            fallback += " High-priority issues: " + "; ".join(item["title"] for item in degraded[:3]) + "."
        return {"answer": fallback, "recommendations": recommendations}
