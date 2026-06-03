from typing import Literal


def to_openai_role(role: str) -> Literal["user", "assistant", "system"]:
    if role == "assistant":
        return "assistant"
    if role == "system":
        return "system"
    return "user"
