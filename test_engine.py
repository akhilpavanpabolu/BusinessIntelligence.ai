import pytest
from data import analyze_kpi, store
import pandas as pd
import numpy as np

def test_z_score_calculation():
    # Test normal scenario
    res_normal = analyze_kpi("kpi_traffic", "normal")
    assert res_normal["status"] == "normal"
    assert -2.0 <= res_normal["z_score"] <= 2.0
    
def test_anomaly_detection():
    # Test anomaly scenario where we intentionally drop traffic
    res_drop = analyze_kpi("kpi_rev_1", "revenue_drop")
    assert res_drop["status"] == "anomaly"
    assert res_drop["z_score"] < -2.0
    assert len(res_drop["drivers"]) > 0

def test_sparse_history_logic():
    # Sparse history (Signups) should fall back to Business Rule
    res_sparse = analyze_kpi("kpi_new_product", "normal")
    assert res_sparse["status"] == "new_launch"
    assert "Business Rule" in res_sparse["method"]
    assert res_sparse["z_score"] is None

def test_missing_data_abstention():
    # Delayed GA should return low confidence and abstain
    res_delayed = analyze_kpi("kpi_traffic", "delayed_ga")
    assert res_delayed["status"] == "ambiguous"
    assert isinstance(res_delayed["confidence"], (int, float))
    assert res_delayed["confidence"] < 70
    assert "Delayed" in res_delayed["freshness"]
    
def test_contribution_math():
    # If revenue dropped in scenario 2, traffic should be a negative driver
    res_drop = analyze_kpi("kpi_rev_1", "revenue_drop")
    traffic_driver = next((d for d in res_drop["drivers"] if "Traffic" in d["factor"]), None)
    assert traffic_driver is not None
    assert traffic_driver["contribution"] < 0

def test_contradictory_evidence():
    # Test scenario 5
    res_contra = analyze_kpi("kpi_rev_1", "contradictory")
    assert res_contra["status"] == "contradictory"
    assert "Divergence" in res_contra["method"]
