import json
import urllib.error
import urllib.request


GAPGPT_BASE_URL = "https://api.gapgpt.app/v1"
GAPGPT_CHAT_URL = GAPGPT_BASE_URL + "/chat/completions"


PROVIDERS = (
    {
        "name": "GapGPT",
        "kind": "gapgpt",
    },
)


def check_available_providers(gapgpt_key=""):
    configured = bool(str(gapgpt_key).strip())

    return [
        {
            "name": "GapGPT",
            "kind": "gapgpt",
            "status": 200 if configured else 0,
            "available": configured,
        }
    ]


def _extract_chat_completion(data):
    choices = data.get("choices", [])
    if not choices:
        return ""

    message = choices[0].get("message", {})
    return str(message.get("content", "")).strip()


def ask_provider(provider, question, api_key):
    if provider["kind"] != "gapgpt":
        raise RuntimeError("Unknown AI provider.")

    if not api_key:
        raise RuntimeError(
            "GapGPT API key is not configured."
        )

    payload = {
        "model": "gpt-4o",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are AVA, a friendly small robot. "
                    "Answer in English, plain text only, maximum 120 characters. "
                    "Do not use markdown."
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ],
    }

    request = urllib.request.Request(
        GAPGPT_CHAT_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        raise RuntimeError(
            f"GapGPT API HTTP {exc.code}: {body[:300]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"GapGPT API connection failed: {exc.reason}"
        ) from exc

    answer = _extract_chat_completion(data)

    if not answer:
        raise RuntimeError("GapGPT returned an empty answer.")

    return answer


def choose_provider(gapgpt_key=""):
    checks = check_available_providers(gapgpt_key=gapgpt_key)

    for item in checks:
        if item["available"]:
            return item, checks

    return None, checks
