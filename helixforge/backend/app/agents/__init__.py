"""HelixForge agentic layer.

An explicit, observable multi-agent runtime layered on top of the real tool
adapters. Agents are deterministic (no external LLM key required to run); an
optional LLM adapter can be added later. Agents emit observable trace only —
plan, task, evidence-backed summary, decision rationale, validation checks,
assumptions, uncertainty, next action — never hidden chain-of-thought.
"""
