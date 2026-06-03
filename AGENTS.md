# ZenTech AI Agent Rules

## Project Shape

This folder is the ZenTech AI FastAPI service. It is called by the Java BE through:

```text
POST /chat/respond
```

The wire contract must stay stable unless the user explicitly asks to change BE integration:

```text
Request:  conversationId, messageId, message, history[]
Response: { "content": string }
```

## Architecture Rules

Keep responsibilities separated:

* `main.py`: create and expose the FastAPI `app`.
* `app/api/routes.py`: HTTP routes, response models, HTTP errors.
* `app/schemas/chat.py`: Pydantic request and response schemas.
* `app/services/chat_service.py`: AI reply orchestration.
* `app/services/openai_client.py`: Azure OpenAI client creation.
* `app/prompts/chat_prompt.py`: system prompt and model input assembly.
* `app/utils/chat_roles.py`: chat role mapping helpers.
* `app/config.py`: environment and runtime settings only.

Do not put prompt text, OpenAI client setup, or business logic inside routes. Do not add new dependencies unless they clearly reduce real complexity.

## Prompt Rules

ZenTech AI is a Vietnamese ecommerce customer-support assistant.

When editing prompts:

* Edit `app/prompts/chat_prompt.py`.
* Keep answers short, polite, and in Vietnamese.
* Stay focused on shopping, warranty, delivery, payment, returns, and contacting staff.
* Do not claim exact price, stock, order status, voucher status, or policy details unless that data is explicitly provided in context.
* If unsure, ask the customer to contact staff support.
* Preserve the current history behavior: use only the latest 10 history messages passed to the model.

## Integration Rules

Preserve these behaviors:

* `/chat/respond` returns HTTP `502` when model generation fails.
* Empty model output returns HTTP `502`.
* `customer` and `staff` history roles map to OpenAI `user`.
* `assistant` maps to OpenAI `assistant`.
* `system` maps to OpenAI `system`.
* No secrets from `.env` may be printed or committed.

## Verification Rules

After refactors, run:

```text
python -m compileall app main.py scripts
```

Run endpoint smoke tests only when service credentials and environment values are available:

* `GET /health` or `GET /`
* `POST /chat/respond` with a small valid payload

Never claim tests passed unless they were actually run.
