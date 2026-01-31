from typing import Dict, List
from dataclasses import dataclass


@dataclass
class PortfolioSignal:
    category: str
    signal: str
    description: str           # engine explanation / description
    percentile: float


def _compute_percentiles(scores: Dict[str, float]) -> Dict[str, float]:
    """
    Compute percentile rank for each dimension within a category.
    If all scores are equal, return an empty dict (no signal).
    """
    values = list(scores.values())

    if len(values) <= 1:
        return {}

    if max(values) == min(values):
        return {}  # no variance → no strengths or gaps

    sorted_items = sorted(scores.items(), key=lambda x: x[1])
    n = len(sorted_items)

    percentiles: Dict[str, float] = {}
    for rank, (dimension, _) in enumerate(sorted_items):
        percentiles[dimension] = rank / (n - 1)

    return percentiles


def analyse_portfolio(profile) -> Dict[str, List[Dict]]:
    """
    Derive strengths and gaps using percentile-based normalisation,
    with absolute thresholds and global caps.
    """

    # Relative thresholds
    STRENGTH_PERCENTILE = 0.80
    GAP_PERCENTILE = 0.20

    # Absolute thresholds (semantic honesty)
    ABSOLUTE_STRENGTH_FLOOR = 0.65
    ABSOLUTE_GAP_CEILING = 0.45

    # Output caps (portfolio-friendly)
    MAX_STRENGTHS = 5
    MAX_GAPS = 5

    strengths: List[PortfolioSignal] = []
    gaps: List[PortfolioSignal] = []

    data = profile.to_dict()

    for category, dimensions in data.items():
        if not isinstance(dimensions, dict):
            continue  # skip confidence or non-score fields

        percentiles = _compute_percentiles(dimensions)

        for name, pct in percentiles.items():
            raw_score = dimensions[name]

            if (
                pct >= STRENGTH_PERCENTILE
                and raw_score >= ABSOLUTE_STRENGTH_FLOOR
            ):
                strengths.append(
                    PortfolioSignal(
                        category=category,
                        signal=name,
                        description="Strong relative signal compared to other dimensions",
                        percentile=round(pct, 2),
                    )
                )

            elif (
                pct <= GAP_PERCENTILE
                and raw_score <= ABSOLUTE_GAP_CEILING
            ):
                gaps.append(
                    PortfolioSignal(
                        category=category,
                        signal=name,
                        description="Weaker relative signal compared to other dimensions",
                        percentile=round(pct, 2),
                    )
                )

    # Global sorting
    strengths.sort(key=lambda x: x.percentile, reverse=True)
    gaps.sort(key=lambda x: x.percentile)

    # Global caps
    strengths = strengths[:MAX_STRENGTHS]
    gaps = gaps[:MAX_GAPS]

    return {
        "strengths": [s.__dict__ for s in strengths],
        "gaps": [g.__dict__ for g in gaps],
    }
