# ADR 003 — Correlation Statistics: Fisher's Exact Test

**Status**: Accepted
**Date**: 2026-03-09

## Context

We need a statistically defensible method to detect meaningful shifts in
voting alignment before/after donation events. Results will be shown to
the public so the methodology must be rigorous and transparent.

## Decision

Use Fisher's exact test (not chi-squared, which requires large samples) with:
- Minimum 5 votes in each window (`evidence_count >= 5`)
- Minimum 0.15 absolute shift (`|shift| >= 0.15`)
- p-value < 0.05 significance threshold
- 24-month windows on each side of the event

## Consequences

- Small sample sizes are filtered out (many rep-industry pairs won't qualify)
- Results shown are more defensible but fewer in number
- Every score links to `methodology_url` — the public methodology page
- "Correlation ≠ causation" disclaimer required in all UI
