from app.services.analyzer import calculate_risk_score


def test_baseline_neutral_score():
    signals = []
    claims = []
    score, label = calculate_risk_score(signals, "Unknown", claims)
    # Neutral baseline: 50, with Unknown source clamped min 35
    assert score == 50
    assert label == "Needs Verification"


def test_positive_signals_lower_risk_when_supported():
    signals = [
        {"name": "Attribution", "status": "positive"},
        {"name": "Language", "status": "positive"},
        {"name": "Claims", "status": "positive"},
    ]
    claims = [
        {
            "id": 1,
            "text": "Tested claim",
            "verificationStatus": "SUPPORTED",
        }
    ]
    # 50 - 30 (positive signals) - 10 (supported) - 10 (high reliability) = 0
    score, label = calculate_risk_score(signals, "High", claims)
    assert score < 30
    assert label == "Low Risk"


def test_unverified_claims_cannot_receive_low_risk_certainty():
    signals = [
        {"name": "Attribution", "status": "positive"},
        {"name": "Language", "status": "positive"},
        {"name": "Claims", "status": "positive"},
    ]
    claims = [
        {
            "id": 1,
            "text": "NASA confirmed water ice on the Moon.",
            "verificationStatus": "UNVERIFIED",
        }
    ]
    # Positive signals want to reduce to 20, but claims are UNVERIFIED and source is Unknown
    # Guardrail clamps minimum score to 40 so it stays in Needs Verification!
    score, label = calculate_risk_score(signals, "Unknown", claims)
    assert score >= 40
    assert label == "Needs Verification"


def test_contradicted_claims_trigger_high_risk():
    signals = [
        {"name": "Language", "status": "positive"},
    ]
    claims = [
        {
            "id": 1,
            "text": "Fictitious event that never occurred",
            "verificationStatus": "CONTRADICTED",
        }
    ]
    score, label = calculate_risk_score(signals, "Moderate", claims)
    # Any confirmed contradiction clamps to at least 70 (High Risk)
    assert score >= 70
    assert label == "High Risk"


def test_mixed_evidence_increases_risk_and_uncertainty():
    signals = []
    claims = [
        {
            "id": 1,
            "text": "Disputed event",
            "verificationStatus": "MIXED_EVIDENCE",
        }
    ]
    score, label = calculate_risk_score(signals, "Moderate", claims)
    # 50 - 5 (moderate source) + 10 (mixed) = 55
    assert 50 <= score < 70
    assert label == "Needs Verification"


def test_low_source_reliability_increases_risk():
    signals = []
    claims = []
    score_low, _ = calculate_risk_score(signals, "Low", claims)
    score_high, _ = calculate_risk_score(signals, "High", claims)
    assert score_low > score_high


def test_score_boundaries_and_clamping():
    # Extreme warning signals and low reliability
    signals_warning = [{"name": f"W{i}", "status": "warning"} for i in range(10)]
    claims_contradicted = [
        {"id": i, "verificationStatus": "CONTRADICTED"} for i in range(5)
    ]
    score_max, label_max = calculate_risk_score(signals_warning, "Low", claims_contradicted)
    assert score_max == 100
    assert label_max == "High Risk"

    # Extreme positive signals and high reliability
    signals_positive = [{"name": f"P{i}", "status": "positive"} for i in range(10)]
    claims_supported = [
        {"id": i, "verificationStatus": "SUPPORTED"} for i in range(5)
    ]
    score_min, label_min = calculate_risk_score(signals_positive, "High", claims_supported)
    assert score_min == 0
    assert label_min == "Low Risk"


def test_lack_of_evidence_not_automatically_misinformation():
    # If a claim has no evidence, it shouldn't jump to High Risk solely for lack of evidence
    signals = []
    claims = [
        {
            "id": 1,
            "text": "A new claim",
            "verificationStatus": "UNVERIFIED",
        }
    ]
    score, label = calculate_risk_score(signals, "Unknown", claims)
    assert score < 70
    assert label == "Needs Verification"


def test_unresolved_claims_keep_positive_signals_in_needs_verification_range():
    signals = [
        {"name": "Attribution", "status": "positive"},
        {"name": "Language", "status": "positive"},
        {"name": "Claims", "status": "positive"},
    ]
    claims = [
        {
            "id": index,
            "verificationStatus": "INSUFFICIENT_EVIDENCE",
        }
        for index in range(1, 6)
    ]

    score, label = calculate_risk_score(signals, "High", claims)

    # 50 - 30 (positive signals) - 10 (high reliability), then the
    # unresolved-claim guardrail raises the result to 40.
    assert (score, label) == (40, "Needs Verification")


def test_duplicate_signals_are_counted_once():
    duplicate_signals = [
        {"name": "Sensational Language", "status": "warning"},
        {"name": " sensational   language ", "status": "warning"},
    ]

    score, label = calculate_risk_score(duplicate_signals, "Unknown", [])

    assert score == 65
    assert label == "Needs Verification"


def test_legacy_and_invalid_claim_statuses_are_conservative():
    legacy_score, legacy_label = calculate_risk_score(
        [],
        "Unknown",
        [{"verificationStatus": "UNVERIFIED"}],
    )
    invalid_score, invalid_label = calculate_risk_score(
        [],
        "Unknown",
        [{"verificationStatus": "not-a-status"}],
    )

    assert (legacy_score, legacy_label) == (50, "Needs Verification")
    assert (invalid_score, invalid_label) == (50, "Needs Verification")
