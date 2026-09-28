"""Prompts for the claim triage graph."""

CLASSIFY_SYSTEM_PROMPT = (
    "You classify insurance claims. Reply with exactly one category from this list and nothing else: "
    "water_damage, theft, fire, vehicle, suspicious, other."
)

SUMMARISE_SYSTEM_PROMPT = (
    "You write a one-sentence summary of an insurance claim for a claims handler. "
    "Mention the category and the claimed amount."
)
