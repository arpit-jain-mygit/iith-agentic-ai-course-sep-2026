"""tracing.py - M7: LangFuse tracing, shared across the pipeline.

IN SHORT: one place to import @observe from, so every traced function uses
the same setup. Needs LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY (and
LANGFUSE_HOST if self-hosted) in .env. Without them, LangFuse logs one
warning and @observe becomes a no-op - tracing is observability, never a
hard dependency: a missing LangFuse key must never stop a triage running.
"""
from langfuse import observe

__all__ = ["observe"]
