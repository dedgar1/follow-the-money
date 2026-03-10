# ADR 001 — DonorRepRelationship as Aggregate Root

**Status**: Accepted
**Date**: 2026-03-09

## Context

The platform's core insight is not individual transactions but the *ongoing relationship*
between a donor and a representative. Individual contributions, while important,
are only meaningful in the context of the relationship over time.

## Decision

`DonorRepRelationship` is the aggregate root of the Finance bounded context.
All finance operations operate on the relationship, not on individual contributions.

## Consequences

- Contributions are always accessed through their relationship
- Total amounts, cycles, and date ranges are maintained on the relationship aggregate
- Neo4j graph stores `(Donor)-[:FUNDED]->(Rep)` edges at the relationship level
- The `add_contribution()` method on `DonorRepRelationship` maintains invariants
