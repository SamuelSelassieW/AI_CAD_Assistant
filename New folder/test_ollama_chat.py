import ollama

resp = ollama.chat(
    model="llama3.2:3b",
    messages=[{"role": "user", "content": "Say 'Ollama chat OK'"}],
)

print(resp["message"]["content"])