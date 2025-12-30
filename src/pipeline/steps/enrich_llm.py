from openai import OpenAI

from ...utils.retry import with_retry


def summarize_text(text: str, api_key: str, base_url: str, model: str) -> str:
    client = OpenAI(api_key=api_key, base_url=base_url)

    def _call() -> str:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a concise Chinese assistant."},
                {"role": "user", "content": f"请用一句话总结下面文案：\n{text}"},
            ],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()

    return with_retry(_call, retries=2, base_delay=1.0)
