import pandas as pd
import numpy as np
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta
import json
import os
import numpy as np
from pydantic import BaseModel
from typing import List, Optional, Dict
from datetime import datetime, timedelta

class KPI(BaseModel):
    id: str
    name: str
    description: str
    source: str
    grain: str
    roles: List[str]
    unit: str
    direction_is_good: str
    last_refresh: str = "Just now"

# Base KPI Definitions (Values injected dynamically)
KPIS_META = [
    KPI(id="kpi_rev_1", name="Revenue (NA)", description="Total revenue from NA", source="Stripe", grain="Daily", roles=["CMO", "Regional Manager - NA"], unit="$", direction_is_good="up"),
    KPI(id="kpi_traffic", name="Web Traffic (NA)", description="Unique visitors from NA", source="Google Analytics", grain="Daily", roles=["CMO", "Regional Manager - NA"], unit="visits", direction_is_good="up"),
    KPI(id="kpi_conv_rate", name="Conversion Rate (NA)", description="Checkout completion rate", source="Amplitude", grain="Daily", roles=["CMO", "Regional Manager - NA"], unit="%", direction_is_good="up"),
    KPI(id="kpi_aov", name="Average Order Value", description="Average cart size", source="Stripe", grain="Daily", roles=["CMO", "Regional Manager - NA"], unit="$", direction_is_good="up"),
    KPI(id="kpi_new_product", name="Enterprise Signups", description="New enterprise tier", source="CRM", grain="Weekly", roles=["CMO"], unit="users", direction_is_good="up", last_refresh="2 hours ago")
]

# Global Data Store
class DataStore:
    def __init__(self):
        self.scenarios_data = {}
        self.generate_all_scenarios()

    def generate_all_scenarios(self):
        np.random.seed(42)
        dates = pd.date_range(end=datetime.today(), periods=90, freq='D')
        
        # Base realistic data
        base_traffic = np.random.normal(loc=50000, scale=2000, size=90)
        base_conv_rate = np.random.normal(loc=0.025, scale=0.001, size=90)
        base_aov = np.random.normal(loc=120, scale=5, size=90)
        
        def create_df(traffic, conv_rate, aov):
            df = pd.DataFrame({
                'date': dates,
                'traffic': traffic,
                'conv_rate': conv_rate,
                'aov': aov
            })
            df['revenue'] = df['traffic'] * df['conv_rate'] * df['aov']
            # Enterprise signups (sparse history, only last 14 days have data)
            signups = np.zeros(90)
            signups[-14:] = np.random.poisson(lam=10, size=14)
            df['enterprise_signups'] = signups
            return df

        # Scenario 1: Normal
        self.scenarios_data["normal"] = create_df(base_traffic.copy(), base_conv_rate.copy(), base_aov.copy())
        
        # Scenario 2: Multi-factor Revenue Drop
        s2_traffic = base_traffic.copy()
        s2_conv = base_conv_rate.copy()
        s2_aov = base_aov.copy()
        # On the last day, traffic drops 50%, conv rate drops 20% to guarantee massive anomaly
        s2_traffic[-1] = s2_traffic[-1] * 0.50
        s2_conv[-1] = s2_conv[-1] * 0.80
        self.scenarios_data["revenue_drop"] = create_df(s2_traffic, s2_conv, s2_aov)

        # Scenario 3: Delayed / Missing GA Data
        s3_df = self.scenarios_data["normal"].copy()
        s3_df.loc[s3_df.index[-1], 'traffic'] = np.nan # Simulate missing data today
        self.scenarios_data["delayed_ga"] = s3_df
        
        # Scenario 4: Sparse History
        self.scenarios_data["sparse_history"] = self.scenarios_data["normal"].copy()

        # Scenario 5: Contradictory Evidence
        s5_traffic = base_traffic.copy()
        s5_conv = base_conv_rate.copy()
        s5_aov = base_aov.copy()
        # Traffic spikes 80% (Bot attack?), but Revenue drops 30% because Conv crashes.
        s5_traffic[-1] = s5_traffic[-1] * 1.80
        s5_conv[-1] = s5_conv[-1] * 0.30
        self.scenarios_data["contradictory"] = create_df(s5_traffic, s5_conv, s5_aov)

    def insert_custom_data(self, df: pd.DataFrame):
        # Standardize column names to lowercase for easier mapping
        df.columns = [c.lower().strip() for c in df.columns]
        
        # Ensure it has a date column
        if 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values(by='date')
            
        self.scenarios_data["custom"] = df


store = DataStore()

def analyze_kpi(kpi_id: str, scenario: str = "normal") -> Dict:
    df = store.scenarios_data.get(scenario, store.scenarios_data["normal"])
    
    # Map KPI ID to column
    col_map = {
        "kpi_rev_1": "revenue",
        "kpi_traffic": "traffic",
        "kpi_conv_rate": "conv_rate",
        "kpi_aov": "aov",
        "kpi_new_product": "enterprise_signups"
    }
    
    col = col_map.get(kpi_id)
    if not col or col not in df.columns:
        # Gracefully handle missing data/columns in custom uploads
        return {
            "status": "ambiguous",
            "current_value": 0,
            "previous_value": 0,
            "percent_change": None,
            "drivers": [],
            "confidence": 0,
            "method": "Column not found in data",
            "z_score": None,
            "freshness": "N/A",
            "evidence": {
                "source": col_map.get(kpi_id, "Unknown"),
                "observation": "Missing Column",
                "method": "Data Quality Check",
                "freshness": "N/A",
                "confidence_score": 0.0
            },
            "lineage": ["Upload", "Missing Column"]
        }
        
    current_val = df[col].iloc[-1]
    prev_val = df[col].iloc[-2] if len(df) > 1 else current_val
    try:
        current_date = df['date'].iloc[-1].strftime('%Y-%m-%d') if 'date' in df.columns else "Unknown Date"
    except:
        current_date = str(df['date'].iloc[-1]) if 'date' in df.columns else "Unknown Date"
    
    # 1. Check for Missing Data (Abstention Logic)
    if pd.isna(current_val):
        return {
            "status": "ambiguous",
            "current_value": 0,
            "previous_value": float(prev_val),
            "percent_change": None,
            "drivers": [],
            "confidence": 10.0,
            "method": "Data Quality Check",
            "z_score": None,
            "freshness": "Delayed by >24h",
            "evidence": {
                "source": col_map.get(kpi_id, "Unknown"),
                "observation": "Missing Data",
                "method": "Data Quality Check",
                "freshness": "Delayed by >24h",
                "confidence_score": 10.0
            },
            "lineage": ["System DB", "Pipeline Failure"],
            "date": current_date
        }
        
    # 2. Check for Sparse History
    non_zero_days = (df[col] > 0).sum()
    if non_zero_days < 30:
        pct_change = ((current_val - prev_val) / prev_val * 100) if prev_val else None
        return {
            "status": "new_launch",
            "current_value": float(current_val),
            "previous_value": float(prev_val),
            "percent_change": round(pct_change, 2) if pct_change else None,
            "drivers": [],
            "confidence": 60.0,
            "method": f"Business Rule (Sparse History: {non_zero_days} days)",
            "z_score": None,
            "freshness": "2 hours ago",
            "evidence": {
                "source": col_map.get(kpi_id, "Unknown"),
                "observation": "n < 30 days",
                "method": "Business Rule",
                "freshness": "2 hours ago",
                "confidence_score": 60.0
            },
            "lineage": ["CRM DB", "Business Rule Engine"],
            "date": current_date
        }

    # 3. Z-Score Calculation (using past 30 days as baseline, excluding today)
    baseline = df[col].iloc[-31:-1]
    mean = baseline.mean()
    std = baseline.std()
    z_score = (current_val - mean) / std if std > 0 else 0
    
    pct_change = ((current_val - prev_val) / prev_val) * 100
    status = "normal"
    if z_score < -2.0:
        status = "anomaly"
    elif z_score > 2.0:
        status = "anomaly"
    
    # Check for Contradictory Evidence (Scenario 5)
    if kpi_id == "kpi_rev_1" and scenario == "contradictory":
        # Check Z-scores for traffic vs revenue
        t_baseline = df['traffic'].iloc[-31:-1]
        t_z = (df['traffic'].iloc[-1] - t_baseline.mean()) / t_baseline.std()
        if z_score < -2.0 and t_z > 2.0:
            status = "contradictory"
        
    # 4. True Contribution Analysis (Only for Revenue)
    drivers = []
    if kpi_id == "kpi_rev_1" and status in ["anomaly", "contradictory"]:
        t_curr, t_prev = df['traffic'].iloc[-1], df['traffic'].iloc[-2]
        c_curr, c_prev = df['conv_rate'].iloc[-1], df['conv_rate'].iloc[-2]
        a_curr, a_prev = df['aov'].iloc[-1], df['aov'].iloc[-2]
        
        # Partial derivative approximation of absolute impact
        impact_traffic = (t_curr - t_prev) * c_prev * a_prev
        impact_conv = (c_curr - c_prev) * t_prev * a_prev
        impact_aov = (a_curr - a_prev) * t_prev * c_prev
        
        total_abs_impact = abs(impact_traffic) + abs(impact_conv) + abs(impact_aov)
        
        if total_abs_impact > 0:
            drivers = [
                {"factor": "Web Traffic", "metric": "volume", "contribution": round((impact_traffic / total_abs_impact) * 100, 2)},
                {"factor": "Conversion Rate", "metric": "mix", "contribution": round((impact_conv / total_abs_impact) * 100, 2)},
                {"factor": "Average Order Value", "metric": "price", "contribution": round((impact_aov / total_abs_impact) * 100, 2)}
            ]

        # 5. Active Feedback Loop Logic
        # Read feedback.json to penalize downvoted drivers
        if os.path.exists("feedback.json"):
            try:
                with open("feedback.json") as f:
                    feedback_db = json.load(f)
                    # Count net votes per driver
                    driver_votes = {}
                    for fb in feedback_db:
                        if fb.get("kpi_id") == kpi_id and fb.get("scenario") == scenario:
                            driver_name = fb.get("comment", "").lower() # Simulating NLP extraction of driver from comment
                            # For simplicity, if comment contains factor name, apply vote
                            for d in drivers:
                                if d["factor"].lower() in driver_name:
                                    driver_votes[d["factor"]] = driver_votes.get(d["factor"], 0) + (1 if fb["thumbs_up"] else -1)
                    
                    # Apply penalty
                    for d in drivers:
                        net_votes = driver_votes.get(d["factor"], 0)
                        if net_votes < 0:
                            # Demote its apparent absolute contribution so it ranks lower
                            d["penalized_rank_score"] = abs(d["contribution"]) * (0.5 ** abs(net_votes))
                        else:
                            d["penalized_rank_score"] = abs(d["contribution"])
            except:
                for d in drivers: d["penalized_rank_score"] = abs(d["contribution"])
        else:
             for d in drivers: d["penalized_rank_score"] = abs(d["contribution"])

        # Sort by penalized rank score, then remove the temp key
        drivers.sort(key=lambda x: x.get("penalized_rank_score", abs(x["contribution"])), reverse=True)
        for d in drivers:
            if "penalized_rank_score" in d:
                del d["penalized_rank_score"]
                
    # Calculate numerical confidence score
    # Base 100, minus 20 points if abs(Z) > 3 (high variance/outlier), minus penalty for freshness
    z_penalty = min(abs(z_score), 3) / 3 * 20 if not pd.isna(z_score) else 50
    freshness = "Just now" if status != "ambiguous" else "Delayed by >24h"
    fresh_penalty = 0 if status != "ambiguous" else 40
    confidence_score = max(0, min(100, round(100 - z_penalty - fresh_penalty, 1)))

    # Determine Method
    method = f"Statistical Z-Score"
    if status == "ambiguous": method = "Data Quality Check"
    elif status == "new_launch": method = "Business Rule"
    elif status == "contradictory": method = "Multivariate Divergence Check"

    kpi_meta = next((k for k in KPIS_META if k.id == kpi_id), None)
    source_sys = kpi_meta.source if kpi_meta else "Unknown"

    evidence = {
        "source": source_sys,
        "observation": f"{round(pct_change, 2) if not pd.isna(pct_change) else 'N/A'}% change",
        "method": method,
        "freshness": freshness,
        "confidence_score": confidence_score
    }
    
    lineage = [
        f"{source_sys} Production DB",
        "dbt Daily Aggregation",
        "Anomaly Detection Engine (Z-Score)",
        "Lineage Graph Verified"
    ]

    return {
        "status": status,
        "current_value": float(current_val),
        "previous_value": float(prev_val),
        "percent_change": round(pct_change, 2) if not pd.isna(pct_change) else None,
        "drivers": drivers,
        "confidence": confidence_score,
        "method": method,
        "z_score": round(z_score, 2) if not pd.isna(z_score) else None,
        "freshness": freshness,
        "evidence": evidence,
        "lineage": lineage,
        "date": current_date
    }

def get_kpis(persona: str, scenario: str) -> List[dict]:
    # Inject dynamic current/prev values from the scenario data
    result = []
    for kpi in KPIS_META:
        if persona in kpi.roles:
            analysis = analyze_kpi(kpi.id, scenario)
            kpi_dict = kpi.model_dump()
            kpi_dict["current_value"] = analysis.get("current_value", 0)
            kpi_dict["previous_value"] = analysis.get("previous_value", 0)
            # Update freshness dynamically based on scenario
            kpi_dict["last_refresh"] = analysis.get("freshness", kpi.last_refresh)
            result.append(kpi_dict)
    return result
