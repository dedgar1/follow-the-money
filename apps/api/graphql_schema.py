"""
Strawberry GraphQL schema.

Sprint 1: Minimal schema with health query.
Sprint 4+: Add Representative, Donor, Correlation types.
"""

from __future__ import annotations

import strawberry
from strawberry.fastapi import GraphQLRouter


@strawberry.type
class Query:
    @strawberry.field(description="API health check")
    def hello(self) -> str:
        return "Follow the Money GraphQL API — v0.1.0"

    # TODO Sprint 4: representative, topDonors, correlations
    # TODO Sprint 6: donorNetwork (multi-hop Neo4j traversal)


schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)
