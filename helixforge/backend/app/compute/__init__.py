"""HelixForge compute layer (Phase 8).

CPU-first scientific compute plus an optional, provider-neutral, safety-gated
external-GPU gateway. The application is fully usable with CPU only; GPU is an
optional accelerator, never a hard dependency. An LLM never executes shell on a
worker — GPU work is expressed as an allowlisted, validated job specification
that requires a budget check and explicit human approval before submission.
"""
