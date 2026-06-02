"""RAG observability metrics — lightweight in-memory counters."""

from __future__ import annotations

import logging
import threading
import time

logger = logging.getLogger("shuyu.rag")

_lock = threading.Lock()


class RagMetrics:
    """Thread-safe RAG metrics collector."""

    def __init__(self):
        self.total_queries = 0
        self.rag_enabled_queries = 0
        self.fallback_count = 0
        self.self_learn_count = 0
        self.latency_ms_sum = 0
        self.last_reset = time.time()

    def record_query(self, enabled: bool, tier_hit: str = "none", score: float = 0.0,
                     latency_ms: int = 0, tables_retrieved: int = 0):
        with _lock:
            self.total_queries += 1
            if enabled:
                self.rag_enabled_queries += 1
            if tier_hit == "fallback":
                self.fallback_count += 1
            self.latency_ms_sum += latency_ms

    def record_self_learn(self):
        with _lock:
            self.self_learn_count += 1

    def snapshot(self) -> dict:
        with _lock:
            return {
                "total_queries": self.total_queries,
                "rag_enabled_queries": self.rag_enabled_queries,
                "fallback_count": self.fallback_count,
                "self_learn_count": self.self_learn_count,
                "avg_latency_ms": round(self.latency_ms_sum / max(self.total_queries, 1)),
                "uptime_seconds": int(time.time() - self.last_reset),
            }


_metrics = RagMetrics()


def record_query(enabled: bool, tier_hit: str = "none", score: float = 0.0,
                 latency_ms: int = 0, tables_retrieved: int = 0):
    _metrics.record_query(enabled, tier_hit, score, latency_ms, tables_retrieved)


def record_self_learn():
    _metrics.record_self_learn()


def get_rag_metrics() -> dict:
    return _metrics.snapshot()
