from dotenv import load_dotenv
load_dotenv()

from app.core.llm import LLMClient

c = LLMClient()
print("LLM available:", c.available())
if c.available():
    resp = c.chat([
        {"role":"system","content":"You are a concise assistant."},
        {"role":"user","content":"Say hello in Indonesian."}
    ])
    print("Model reply:", resp)
