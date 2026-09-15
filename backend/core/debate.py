"""Agreement between complete reviewer ballots; never confidence in factual truth."""

from itertools import combinations
from backend.core.types import Position, Review, RankingResult


class Debate:
    @staticmethod
    def rank_positions(
        positions: list[Position], reviews: list[Review]
    ) -> RankingResult:
        ids = {p.agent_id for p in positions}
        ballots = []
        seen = set()
        for review in reviews:
            rows = review.ranked_positions
            if (
                review.reviewer_id in seen
                or len(rows) != len(ids)
                or {r[0] for r in rows} != ids
                or {r[1] for r in rows} != set(range(1, len(ids) + 1))
            ):
                continue
            seen.add(review.reviewer_id)
            ballots.append({aid: rank for aid, rank, _ in rows})
        ranks = [
            (
                aid,
                sum(b[aid] for b in ballots) / len(ballots)
                if ballots
                else float(len(ids)),
                0.0,
            )
            for aid in sorted(ids)
        ]
        ranks.sort(key=lambda item: item[1])
        comparisons = []
        for a, b in combinations(ballots, 2):
            for x, y in combinations(sorted(ids), 2):
                comparisons.append((a[x] < a[y]) == (b[x] < b[y]))
        agreement = sum(comparisons) / len(comparisons) if comparisons else 0.0
        return RankingResult(
            aggregate_ranking=ranks,
            convergence_score=agreement,
            consensus_reached=len(ballots) >= 2 and len(ids) >= 2 and agreement >= 0.8,
        )
