import base64

from app.prompts.chat_prompt import build_model_input
from app.schemas.chat import ChatAttachment, ChatRespondRequest


def make_request(message: str, attachments: list[ChatAttachment] | None = None) -> ChatRespondRequest:
    return ChatRespondRequest(
        conversationId="conversation-1",
        messageId="message-1",
        message=message,
        attachments=attachments or [],
    )


def test_text_only_input_stays_plain_text() -> None:
    messages = build_model_input(make_request("Shop co giao hang khong?"))

    assert messages[-1]["role"] == "user"
    assert messages[-1]["content"] == "Shop co giao hang khong?"


def test_image_attachment_builds_multimodal_input() -> None:
    messages = build_model_input(
        make_request(
            "Xem giup minh anh nay",
            [
                ChatAttachment(
                    fileName="layout.png",
                    contentType="image/png",
                    attachmentType="IMAGE",
                    mediaUrl="https://cdn.example.com/layout.png",
                )
            ],
        )
    )

    content = messages[-1]["content"]
    assert isinstance(content, list)
    assert content[0] == {"type": "input_text", "text": "Xem giup minh anh nay"}
    assert content[1] == {
        "type": "input_image",
        "image_url": "https://cdn.example.com/layout.png",
    }


def test_text_file_attachment_is_extracted_into_user_context() -> None:
    raw = "Chinh sach bao hanh: san pham duoc ho tro 12 thang."
    encoded = base64.b64encode(raw.encode("utf-8")).decode("ascii")
    messages = build_model_input(
        make_request(
            "Tom tat file nay",
            [
                ChatAttachment(
                    fileName="policy.txt",
                    contentType="text/plain",
                    attachmentType="FILE",
                    contentBase64=encoded,
                )
            ],
        )
    )

    content = messages[-1]["content"]
    assert isinstance(content, str)
    assert "Tom tat file nay" in content
    assert "policy.txt" in content
    assert "Chinh sach bao hanh" in content


def test_empty_file_attachment_fails_gracefully() -> None:
    encoded = base64.b64encode("   ".encode("utf-8")).decode("ascii")
    messages = build_model_input(
        make_request(
            "Doc file nay",
            [
                ChatAttachment(
                    fileName="empty.txt",
                    contentType="text/plain",
                    attachmentType="FILE",
                    contentBase64=encoded,
                )
            ],
        )
    )

    assert "File khong co noi dung van ban doc duoc" in messages[-1]["content"]
