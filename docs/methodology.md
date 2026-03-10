# Correlation Methodology

> This page is linked from every AlignmentScore shown on the platform.
> Correlation ≠ causation. All correlations are statistical observations only.

## What We Measure

We compute an **AlignmentScore** for each (representative, donor industry) pair.
The score represents how often a representative voted in alignment with the
positions typically favored by donors in that industry.

## Before/After Analysis

The key signal is **shift**: the change in alignment score before vs. after
a representative received a significant donation from a donor industry.

- **Before window**: 24 months prior to the major donation event
- **After window**: 24 months following the major donation event
- **Shift** = `after_score - before_score`

## Statistical Thresholds

A correlation is only surfaced to users when ALL of the following are true:

| Criterion | Threshold | Rationale |
|---|---|---|
| Minimum evidence | `evidence_count >= 5` | Avoid small-sample noise |
| Meaningful shift | `|shift| >= 0.15` | 15-point alignment change |
| Statistical significance | `p-value < 0.05` | Fisher's exact test |

## Important Limitations

1. **Correlation ≠ causation.** A shift in voting alignment after a donation
   does not prove the donation caused the shift. Many factors influence how
   representatives vote.

2. **Industry categorization is approximate.** Bills are tagged by NLP;
   classification errors are possible.

3. **Data completeness.** FEC data may not capture all contributions,
   particularly from dark money sources.

4. **Voting context.** Representatives may vote against industry interests
   for procedural reasons unrelated to donor relationships.

## Data Sources

- **Contributions**: FEC API (federal election filings)
- **Industry categories**: OpenSecrets taxonomy
- **Votes**: Congress.gov API v3 (House) · Senate.gov XML feeds (Senate)
- **Bill industry tagging**: spaCy NLP + keyword taxonomy

*Last updated: Sprint 8 (TBD)*
