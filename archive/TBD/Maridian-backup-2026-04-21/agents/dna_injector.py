# agents/dna_injector.py
import random
from utils.llm import llm_call
from utils.vault import canonicalize_domain

DNA_SYSTEM = """You are Meridian's DNA Injector. Force one domain into this belief note so the fusion feels INEVITABLE.

Rules:
- The injected domain must become structurally load-bearing, not decorative
- First person voice throughout — this is Ignacio's thinking
- Make the note stranger AND more coherent simultaneously
- Output ONLY the mutated section (2-3 paragraphs). No commentary."""

# Personal domain library — built from Ignacio's journal topics
DNA_LIBRARY = [
    "identity", "ambition", "relationships", "money-mindset",
    "earned-love", "compounding", "failure-processing", "discipline",
    "self-perception", "entrepreneurship", "cultural-identity",
    "friendship", "urgency", "legacy", "creativity", "learning-systems",
    "trust", "consistency", "risk-tolerance", "patience",
    "self-worth", "comparison", "momentum", "solitude",
    "gratitude", "fear", "growth-metaphors", "time-perception",
    # Extended — cross-domain fusions
    "systems-thinking", "game-theory", "compounding-relationships",
    "attention-economics", "identity-debt", "emotional-leverage",
    "signal-vs-noise", "optionality", "asymmetric-returns",
    "network-effects-in-trust", "activation-energy-personal",
    "mean-reversion-in-behavior", "narrative-vs-data",
    "deep-work-vs-shallow-presence", "skin-in-the-game",
    "first-principles-identity", "inversion-thinking",
    "black-swan-in-relationships", "antifragility-personal",
]


def inject(note_content: str, note_domains: list,
           force: bool = False, injection_count: int = 0) -> tuple:
    if injection_count >= 2:
        return None, None
    if not force and random.random() > 0.15:
        return None, None

    canonical_domains = [canonicalize_domain(d) for d in note_domains]
    available = [d for d in DNA_LIBRARY if d not in canonical_domains]
    if not available:
        return None, None

    domain = random.choice(available)
    print(f"  [DNA] Injecting: {domain}")

    try:
        mutation = llm_call(
            "llama3.2", DNA_SYSTEM,
            f"Note:\n{note_content[:2000]}\n\nInjected domain: {domain.replace('-', ' ')}",
            temperature=0.9
        )
        return mutation, domain
    except Exception as e:
        print(f"  [DNA] Failed: {e}")
        return None, None
