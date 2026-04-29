"""
Regime classification helpers for Olympus.

These utilities provide a lightweight market-state gate over the ranking engine.
They do not predict direction; they summarize whether the current cross-section
looks trend-friendly, mixed, or degraded.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.models import RankedUniverse


@dataclass(frozen=True)
class RegimeDecision:
    name: str
    allow_entries: bool
    position_scale: float
    long_enabled: bool
    short_enabled: bool
    dominant_side: str
    long_strength: float
    short_strength: float
    blended_strength: float
    scored_count: int
    error_count: int

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "allow_entries": self.allow_entries,
            "position_scale": self.position_scale,
            "long_enabled": self.long_enabled,
            "short_enabled": self.short_enabled,
            "dominant_side": self.dominant_side,
            "long_strength": round(self.long_strength, 2),
            "short_strength": round(self.short_strength, 2),
            "blended_strength": round(self.blended_strength, 2),
            "scored_count": self.scored_count,
            "error_count": self.error_count,
        }


def classify_regime(ranked: "RankedUniverse", settings) -> RegimeDecision:
    """
    Translate the latest ranking cycle into a simple execution regime.

    Long strength is the average of the top long scores.
    Short strength is expressed in the same "higher is stronger" space by
    converting low short scores into 100-score.
    """
    top_n = max(int(getattr(settings, "REGIME_TOP_N", 5)), 1)
    longs = ranked.longs[:top_n]
    shorts = ranked.shorts[:top_n]

    long_strength = (
        sum(float(rs.score) for rs in longs) / len(longs)
        if longs else 0.0
    )
    short_strength = (
        sum(100.0 - float(rs.score) for rs in shorts) / len(shorts)
        if shorts else 0.0
    )
    blended_strength = (long_strength + short_strength) / 2.0

    if long_strength > short_strength + 5.0:
        dominant_side = "long"
    elif short_strength > long_strength + 5.0:
        dominant_side = "short"
    else:
        dominant_side = "balanced"

    if (
        ranked.scored_count < settings.REGIME_MIN_SCORED_COUNT
        or ranked.error_count > settings.REGIME_MAX_ERROR_COUNT
    ):
        return RegimeDecision(
            name="degraded",
            allow_entries=False,
            position_scale=0.0,
            long_enabled=False,
            short_enabled=False,
            dominant_side=dominant_side,
            long_strength=long_strength,
            short_strength=short_strength,
            blended_strength=blended_strength,
            scored_count=ranked.scored_count,
            error_count=ranked.error_count,
        )

    if blended_strength >= settings.REGIME_TREND_STRENGTH_MIN:
        return RegimeDecision(
            name="trend",
            allow_entries=True,
            position_scale=1.0,
            long_enabled=dominant_side in {"long", "balanced"},
            short_enabled=dominant_side in {"short", "balanced"},
            dominant_side=dominant_side,
            long_strength=long_strength,
            short_strength=short_strength,
            blended_strength=blended_strength,
            scored_count=ranked.scored_count,
            error_count=ranked.error_count,
        )

    if blended_strength >= settings.REGIME_MIXED_STRENGTH_MIN:
        return RegimeDecision(
            name="mixed",
            allow_entries=True,
            position_scale=float(settings.REGIME_MIXED_POSITION_SCALE),
            long_enabled=True,
            short_enabled=True,
            dominant_side=dominant_side,
            long_strength=long_strength,
            short_strength=short_strength,
            blended_strength=blended_strength,
            scored_count=ranked.scored_count,
            error_count=ranked.error_count,
        )

    return RegimeDecision(
        name="degraded",
        allow_entries=False,
        position_scale=0.0,
        long_enabled=False,
        short_enabled=False,
        dominant_side=dominant_side,
        long_strength=long_strength,
        short_strength=short_strength,
        blended_strength=blended_strength,
        scored_count=ranked.scored_count,
        error_count=ranked.error_count,
    )
