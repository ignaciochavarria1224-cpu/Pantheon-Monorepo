# utils/llm.py
import ollama

# Single model strategy for low-RAM machines (< 10 GB).
# phi3 and llama3.2 can't both stay loaded on 8 GB RAM.
# Route everything through llama3.2; keep_alive=0 unloads after each call.
MODEL_OVERRIDE = "llama3.2"


def llm_call(model: str, system: str, user: str,
             temperature: float = 0.7, timeout: int = 300) -> str:
    """Single LLM call via Ollama. Returns response text."""
    actual_model = MODEL_OVERRIDE  # override phi3 -> llama3.2
    response = ollama.chat(
        model=actual_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        options={"temperature": temperature},
        keep_alive=300,  # keep loaded 5 min between calls (single model, no OOM risk)
    )
    return response["message"]["content"].strip()
