from dataclasses import dataclass, field
import unicodedata

from app.schemas.agent import AgentRespondRequest


@dataclass(frozen=True)
class ContextRouteDecision:
    should_search_knowledge: bool
    reason: str
    tools: list[str] = field(default_factory=list)


def decide_context_tools(request: AgentRespondRequest) -> ContextRouteDecision:
    message = normalize(request.message)
    if not message:
        return ContextRouteDecision(False, "empty_message")

    if is_small_talk(message):
        return ContextRouteDecision(False, "small_talk")

    if not request.datasetIds:
        return ContextRouteDecision(False, "no_dataset_attached")

    if has_knowledge_intent(message):
        return ContextRouteDecision(True, "knowledge_intent", ["knowledge_search"])

    if is_complex_question(message):
        return ContextRouteDecision(True, "complex_question", ["knowledge_search"])

    return ContextRouteDecision(False, "direct_answer")


def normalize(value: str) -> str:
    value = value.replace("Đ", "D").replace("đ", "d")
    no_marks = "".join(
        char for char in unicodedata.normalize("NFD", value.lower())
        if unicodedata.category(char) != "Mn"
    )
    return " ".join(no_marks.strip().split())


def is_small_talk(message: str) -> bool:
    small_talk = {
        "hi",
        "hello",
        "hey",
        "chao",
        "xin chao",
        "alo",
        "ok",
        "oke",
        "okay",
        "cam on",
        "thanks",
        "thank you",
        "ban la ai",
        "m la ai",
        "tu gioi thieu",
    }
    if message in small_talk:
        return True

    words = message.split()
    greeting_tokens = ("chao", "hello", "hi", "thanks")
    return len(words) <= 3 and any(token in message for token in greeting_tokens)


def has_knowledge_intent(message: str) -> bool:
    retrieval_hints = (
        "noi dung",
        "tai lieu",
        "file",
        "pdf",
        "dataset",
        "chinh sach",
        "quy dinh",
        "huong dan",
        "bao hanh",
        "huy",
        "doi tra",
        "don hang",
        "san pham",
        "gia",
        "so sanh",
        "phan tich",
        "tom tat",
        "kiem tra",
        "tra cuu",
    )
    return any(hint in message for hint in retrieval_hints)


def is_complex_question(message: str) -> bool:
    words = message.split()
    question_markers = ("la gi", "nhu the nao", "vi sao", "tai sao", "co nen", "can gi")
    return len(words) > 8 or any(marker in message for marker in question_markers)
