import json
import urllib.request
import urllib.error


PROVIDERS = (
    {
        "name": "GapGPT",
        "health_url": "https://gapgpt.app/chat",
        "kind": "gapgpt",
    },
    {
        "name": "ZIGAP",
        "health_url": "https://zigap.ir/",
        "kind": "zigap",
    },
)


def _http_status(url, headers=None, timeout=8):
    request = urllib.request.Request(
        url,
        headers=headers or {"User-Agent": "AVA-PET"},
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return int(response.getcode())
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:
        return 0


def check_available_providers(gapgpt_key=""):
    result = []

    for provider in PROVIDERS:
        headers = {"User-Agent": "AVA-PET"}

        status = _http_status(
            provider["health_url"],
            headers=headers,
        )

        result.append(
            {
                "name": provider["name"],
                "kind": provider["kind"],
                "status": status,
                "available": status == 200,
            }
        )

    return result


def _extract_chat_completion(data):
    choices = data.get("choices", [])
    if not choices:
        return ""

    message = choices[0].get("message", {})
    return str(message.get("content", "")).strip()


def ask_provider(provider, question, api_key):
    kind = provider["kind"]

    if kind == "gapgpt":
        if not api_key:
            raise RuntimeError(
                "GapGPT is available, but its API key is not configured."
            )

        payload = {
            "model": "gpt-4o-mini",
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
            "https://api.gapgpt.app/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer " + api_key,
            },
            method="POST",
        )

        with urllib.request.urlopen(request, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))

        answer = _extract_chat_completion(data)

        if not answer:
            raise RuntimeError("GapGPT returned an empty answer.")

        return answer

    if kind == "zigap":
        raise RuntimeError(
            "ZIGAP is reachable, but no public chat API endpoint "
            "was found for direct app integration."
        )

    raise RuntimeError("Unknown AI provider.")


def choose_provider(gapgpt_key=""):
    checks = check_available_providers(
        gapgpt_key=gapgpt_key,
    )

    for item in checks:
        if not item["available"]:
            continue

        if item["kind"] == "gapgpt" and gapgpt_key:
            return item, checks

        if item["kind"] == "zigap":
            return item, checks

    return None, checks
