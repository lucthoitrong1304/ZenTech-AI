import json

from app.config import settings
from app.prompts.admin_activity_timeline_prompt import SYSTEM_PROMPT_ACTIVITY_TIMELINE
from app.schemas.admin_activity_timeline import ActivityTimelineSummaryRequest
from app.services.openai_client import build_client


def summarize_activity_timeline(request: ActivityTimelineSummaryRequest) -> list[str]:
    payload = request.model_dump(by_alias=True)
    payload["logs"] = [log.model_dump() for log in request.logs]
    formatted_payload = json.dumps(payload, ensure_ascii=False, indent=2)

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_ACTIVITY_TIMELINE},
        {
            "role": "user",
            "content": (
                "Du lieu activity timeline can tom tat duoi dang JSON:\n\n"
                f"{formatted_payload}"
            ),
        },
    ]

    client = build_client()
    if hasattr(client, "chat"):
        response = client.chat.completions.create(
            model=settings.azure_openai_model_name,
            messages=messages,
            temperature=0.2,
        )
        content = response.choices[0].message.content.strip()
    else:
        response = client.responses.create(
            model=settings.azure_openai_model_name,
            input=messages,
        )
        content = response.output_text.strip()

    return split_summary_lines(content)


def split_summary_lines(content: str | None) -> list[str]:
    if not content or not content.strip():
        return []

    return [
        line.lstrip("-*0123456789. )").strip()
        for line in content.splitlines()
        if line.strip()
    ][:6]
