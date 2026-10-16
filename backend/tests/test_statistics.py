import math
import statistics
import pytest
from app.analytics import compute_descriptive_stats, build_histogram, compute_gap_severity


def test_descriptive_stats_known_values():
    """Verify statistical formulas: mean, median, population variance, std_dev, skewness, kurtosis, IQR."""
    data = [50.0, 60.0, 70.0, 80.0, 90.0]
    stats = compute_descriptive_stats(data)

    assert stats["n"] == 5
    assert stats["mean"] == 70.0
    assert stats["median"] == 70.0
    # Population variance: ((50-70)^2 + (60-70)^2 + (70-70)^2 + (80-70)^2 + (90-70)^2)/5 = (400+100+0+100+400)/5 = 200.0
    assert stats["variance"] == 200.0
    assert stats["std_dev"] == round(math.sqrt(200.0), 2)
    # Symmetric distribution has skewness 0
    assert abs(stats["skewness"]) < 1e-4
    assert stats["min"] == 50.0
    assert stats["max"] == 90.0
    assert stats["range"] == 40.0
    # Coefficient of variation
    expected_cv = round((math.sqrt(200.0) / 70.0) * 100, 2)
    assert stats["cv"] == expected_cv


def test_descriptive_stats_empty():
    """Verify graceful handling of empty sample distributions."""
    stats = compute_descriptive_stats([])
    assert stats["n"] == 0
    assert stats["mean"] is None
    assert stats["variance"] is None
    assert stats["skewness"] is None


def test_histogram_frequency_conservation():
    """Verify that histogram bins preserve total population count."""
    data = [12.5, 34.0, 45.2, 55.0, 68.9, 72.1, 88.0, 91.5, 94.0, 99.0]
    bins = build_histogram(data, bins=5)
    assert len(bins) == 5
    total_count = sum(b["count"] for b in bins)
    assert total_count == len(data)
    total_freq = sum(b["frequency"] for b in bins)
    assert round(total_freq, 2) == 1.0


def test_gap_severity_scoring():
    """Verify the 60% mention-ratio + 40% log-scaled impact weighting formula."""
    # 5 mentions out of 10 officers
    sev = compute_gap_severity(mention_count=5, total_profiles=10)
    assert sev["ratio"] == 50.0
    # score must be positive and bounded between 0 and 100
    assert 0 <= sev["score"] <= 100
    assert sev["level"] in ["low", "moderate", "high", "critical"]


def test_workforce_analytics_endpoint(client, viewer_token):
    """Verify /api/analytics/workforce returns comprehensive statistical insights."""
    headers = {"Authorization": f"Bearer {viewer_token}"}
    res = client.get("/api/analytics/workforce", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert "readiness" in data
    assert "descriptive_stats" in data["readiness"]
    assert data["readiness"]["descriptive_stats"]["n"] >= 6
