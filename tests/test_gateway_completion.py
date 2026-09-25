import json

import httpx
import pytest

from backend.llm.gateway import Budget, Gateway, ProviderFailure


@pytest.mark.parametrize(
    "reason, message",
    [
        ("length", "output token limit"),
        ("content_filter", "filtered"),
        ("error", "provider reported an error"),
    ],
)
async def test_final_stream_chunk_preserved_with_specific_failure(
    provider_keys, reason, message
):
    calls = []

    def respond(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert payload["reasoning"] == {"exclude": True, "enabled": False}
        return httpx.Response(
            200,
            text="data: "
            + json.dumps(
                {
                    "choices": [
                        {
                            "delta": {"content": "Last answer words"},
                            "finish_reason": reason,
                        }
                    ],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 20},
                }
            )
            + "\n\ndata: [DONE]\n\n",
        )

    gateway = Gateway(httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    budget, chunks = Budget(), []

    async def emit(chunk):
        chunks.append(chunk)

    try:
        with pytest.raises(ProviderFailure, match=message):
            await gateway.ask(
                "nemotron_lightning", "Question", budget, stream=emit, fallback=True
            )
        assert chunks == ["Last answer words"]
        assert (
            len(calls) == 1
        )  # Never append another model's answer to a partial stream.
        assert budget.records[0]["finish_reason"] == reason
        assert budget.records[0]["total_tokens"] == 32
    finally:
        await gateway.close()


async def test_reasoning_fields_are_not_streamed_as_answer(provider_keys):
    def respond(request):
        frames = [
            {"choices": [{"delta": {"reasoning": "Internal planning"}}]},
            {
                "choices": [
                    {"delta": {"content": "The final answer."}, "finish_reason": "stop"}
                ]
            },
        ]
        return httpx.Response(
            200,
            text="".join("data: " + json.dumps(f) + "\n\n" for f in frames)
            + "data: [DONE]\n\n",
        )

    gateway = Gateway(httpx.AsyncClient(transport=httpx.MockTransport(respond)))
    chunks = []

    async def emit(chunk):
        chunks.append(chunk)

    try:
        response = await gateway.ask(
            "nemotron_lightning", "Question", Budget(), stream=emit
        )
        assert response.content == "The final answer."
        assert chunks == ["The final answer."]
    finally:
        await gateway.close()
