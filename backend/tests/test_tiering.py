from app.config import TierThresholds
from app.models.schemas import Tier
from app.services.matching.tiering import assign_tier

THRESHOLDS = TierThresholds(accept_min=0.85, review_min=0.60)


def test_high_score_is_green():
    assert assign_tier(0.95, THRESHOLDS) is Tier.green


def test_accept_threshold_score_is_green():
    assert assign_tier(THRESHOLDS.accept_min, THRESHOLDS) is Tier.green


def test_mid_score_is_yellow():
    assert assign_tier(0.70, THRESHOLDS) is Tier.yellow


def test_low_score_is_red():
    assert assign_tier(0.30, THRESHOLDS) is Tier.red
