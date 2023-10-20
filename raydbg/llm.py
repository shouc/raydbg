import hashlib
import os

import openai
import retry

ANYSCALE_ENDPOINT = "https://api.endpoints.anyscale.com/v1"


class LLM:
    def __init__(self, api_key, model="gpt-3.5-turbo", cache_path="/tmp/llm"):
        openai.api_key = api_key
        self.model = model
        if not os.path.exists(cache_path):
            os.makedirs(cache_path)
        self.cache_path = cache_path
        if "llama" in self.model:
            openai.api_base = ANYSCALE_ENDPOINT

    @retry.retry(tries=3, delay=0.1, backoff=0.5)
    def query(self, content):
        content_hash = hashlib.md5(content.encode()).hexdigest()
        if os.path.exists(f"{self.cache_path}/{content_hash}.txt"):
            with open(f"{self.cache_path}/{content_hash}.txt") as f:
                return f.read()
        response = openai.ChatCompletion.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": content
                }
            ],
            temperature=1,
            max_tokens=256,
            top_p=1,
            frequency_penalty=0,
            presence_penalty=0
        )
        try:
            result = response.choices[0]["message"]["content"]
        except:
            print("LLM provided invalid response", response)
            raise
        with open(f"{self.cache_path}/{content_hash}.txt", "w") as f:
            f.write(result)
        return result
