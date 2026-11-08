"""slipguard weight audit (frozen from workstream F, 2026-11-05). audit-weights only; the repair candidates did not pass
the registered gate and are not part of this package."""
from .audit import audit_endpoint, position_metrics, sampler_from_top
from .report import summarize, compare, flag, TAU, SCHEMA
__all__ = ['audit_endpoint', 'position_metrics', 'sampler_from_top', 'summarize', 'compare', 'flag', 'TAU', 'SCHEMA']
__version__ = 'wsa-1.0'
