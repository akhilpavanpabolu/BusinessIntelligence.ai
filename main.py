from fastapi import FastAPI, HTTPException, Header, Body
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
import os
import requests
import json
import time
import io
import pandas as pd
from fastapi import Request
from data import KPIS_META, analyze_kpi, get_kpis, store

# Load .env manually if exists
if os.path.exists(".env"):
    with open(".env") as f:
        for line in f:
            if "=" in line:
                key, val = line.strip().split("=", 1)
                os.environ[key] = val

MISTRAL_API_KEY = os.environ.get("MISTRAL_API_KEY", "")

app = FastAPI(title="KPI Intelligence Engine V2")

# Serve static files for frontend
os.makedirs("static", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# In-memory feedback store
feedback_db = []

@app.get("/", response_class=HTMLResponse)
async def read_index():
    with open("static/index.html", "r") as f:
        return f.read()

@app.get("/api/kpis")
async def api_get_kpis(persona: str = Header(default="CMO"), scenario: str = Header(default="normal")):
    """Returns KPIs filtered by Role-Based Access Control (RBAC) and dynamically calculated for the scenario."""
    kpis = get_kpis(persona, scenario)
    return JSONResponse({"kpis": kpis})

@app.post("/api/upload")
async def api_upload_csv(request: Request):
    try:
        body = await request.body()
        csv_text = body.decode("utf-8")
        df = pd.read_csv(io.StringIO(csv_text))
        store.insert_custom_data(df)
        return JSONResponse({"status": "success", "message": "Custom data uploaded."})
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=400)


def estimate_tokens_and_cost(prompt: str, response: str) -> dict:
    """Estimates tokens (since Mistral API might not always return them identically) and cost."""
    # Rough estimation: 1 token ~= 4 chars
    prompt_tokens = len(prompt) // 4
    completion_tokens = len(response) // 4
    total_tokens = prompt_tokens + completion_tokens
    
    # Mistral Large pricing approx (e.g., $3 per 1M tokens input, $9 per 1M output)
    cost = (prompt_tokens / 1000000 * 3.0) + (completion_tokens / 1000000 * 9.0)
    
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "cost_usd": round(cost, 5)
    }

def mock_llm_response(analysis: dict, persona: str) -> dict:
    """Fallback narrative generation with STRICT decision rights."""
    status = analysis.get("status")
    
    # Decision Rights Logic
    action_lever = "Global Advertising Budget" if persona == "CMO" else "Local Sales Discounts"
    action_owner = "VP of Marketing" if persona == "CMO" else "Regional Sales Director"
    action_desc = "Reallocate 15% of budget to top performing channels." if persona == "CMO" else "Offer a 5% local discount to win back traffic."
    
    if status == "anomaly":
        return {
            "narrative": f"As {persona}, you should know Revenue dropped. This was primarily driven by drops in underlying factors.",
            "action_recommendations": [
                {
                    "driver": "Traffic Drop",
                    "lever": action_lever,
                    "action": action_desc,
                    "owner": action_owner,
                    "expected_impact": "Recover traffic within 3 days",
                    "confidence": "High"
                }
            ],
            "telemetry": {"llm_used": "Mocked", "cost_usd": 0.0, "total_tokens": 0}
        }
    elif status == "ambiguous":
         return {
            "narrative": f"As {persona}, I cannot provide a definitive explanation. The underlying data is currently delayed.",
            "action_recommendations": [
                {
                    "driver": "Data Sync",
                    "lever": "Data Engineering",
                    "action": "Investigate sync issues.",
                    "owner": "Data Platform Team",
                    "expected_impact": "Restore data visibility",
                    "confidence": "High"
                }
            ],
            "telemetry": {"llm_used": "Mocked", "cost_usd": 0.0, "total_tokens": 0}
        }
    elif status == "contradictory":
        return {
            "narrative": f"As {persona}, we detected a contradictory signal. Traffic spiked significantly, but Revenue crashed. This suggests either a bot attack or a severe checkout bug.",
            "action_recommendations": [
                {
                    "driver": "Traffic/Revenue Divergence",
                    "lever": "Engineering / Security",
                    "action": "Investigate WAF logs for bot activity and check Stripe for payment gateway errors.",
                    "owner": "VP of Engineering",
                    "expected_impact": "Resolve checkout blockade",
                    "confidence": "Medium"
                }
            ],
            "telemetry": {"llm_used": "Mocked", "cost_usd": 0.0, "total_tokens": 0}
        }
    elif status == "new_launch":
         return {
            "narrative": f"As {persona}, this is a new product launch with sparse history. Statistical baselines are not yet established.",
            "action_recommendations": [
                {
                    "driver": "Sparse History",
                    "lever": "Sales Enablement",
                    "action": "Continue qualitative tracking until n>30.",
                    "owner": "Head of Sales",
                    "expected_impact": "Establish baseline",
                    "confidence": "Medium"
                }
            ],
             "telemetry": {"llm_used": "Mocked", "cost_usd": 0.0, "total_tokens": 0}
        }
    
    return {
        "narrative": f"Metrics are stable and tracking according to baseline.",
        "action_recommendations": [],
        "telemetry": {"llm_used": "Mocked", "cost_usd": 0.0, "total_tokens": 0}
    }


def call_mistral_api(prompt: str) -> dict:
    """Calls Mistral API using the requests library and extracts telemetry."""
    url = "https://api.mistral.ai/v1/chat/completions"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MISTRAL_API_KEY}"
    }
    data = {
        "model": "mistral-small-latest",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    response = requests.post(url, headers=headers, json=data)
    response.raise_for_status()
    resp_json = response.json()
    content = resp_json["choices"][0]["message"]["content"]
    
    # Try to get usage from API response, fallback to estimation
    usage = resp_json.get("usage", {})
    if usage:
         telemetry = {
             "prompt_tokens": usage.get("prompt_tokens", 0),
             "completion_tokens": usage.get("completion_tokens", 0),
             "total_tokens": usage.get("total_tokens", 0),
             "cost_usd": round((usage.get("prompt_tokens",0)/1e6*3) + (usage.get("completion_tokens",0)/1e6*9), 5)
         }
    else:
         telemetry = estimate_tokens_and_cost(prompt, content)
         
    telemetry["llm_used"] = "Mistral-Large"
    return {"content": content, "telemetry": telemetry}


@app.get("/api/kpi/{kpi_id}/analysis")
async def get_kpi_analysis(kpi_id: str, persona: str = Header(default="CMO"), scenario: str = Header(default="normal")):
    """
    1. Runs deterministic logic (Data Engine).
    2. Uses LLM to synthesize narrative (Intelligence Engine).
    """
    kpi_meta = next((k for k in KPIS_META if k.id == kpi_id), None)
    if not kpi_meta:
        raise HTTPException(status_code=404, detail="KPI not found")
        
    if persona not in kpi_meta.roles:
         raise HTTPException(status_code=403, detail="Not authorized to view this KPI")

    # Step 1: Deterministic Engine
    t0 = time.perf_counter()
    deterministic_analysis = analyze_kpi(kpi_id, scenario)
    t1 = time.perf_counter()
    deterministic_latency_ms = round((t1 - t0) * 1000)
    
    llm_payload = {}
    llm_latency_ms = 0
    
    # Step 2: Intelligence Engine (LLM)
    t2 = time.perf_counter()
    if not MISTRAL_API_KEY:
        llm_payload = mock_llm_response(deterministic_analysis, persona)
        llm_latency_ms = round((time.perf_counter() - t2) * 1000)
        llm_payload["telemetry"]["llm_latency_ms"] = llm_latency_ms
        llm_payload["telemetry"]["analytics_latency_ms"] = deterministic_latency_ms
    else:
        try:
            prompt = f"""
            You are an AI Business Intelligence Analyst. Your audience is the {persona}.
            You must synthesize a narrative and recommend actions based EXACTLY on the following deterministic data.
            Do NOT hallucinate new numbers. Do NOT act as the source of truth.
            
            If the persona is "CMO", focus on global marketing levers. 
            If the persona is "Regional Manager", focus ONLY on local sales levers.
            
            KPI: {kpi_meta.name} ({kpi_meta.description})
            Data: {json.dumps(deterministic_analysis)}
            
            Return a JSON object with this exact structure:
            {{
                "narrative": "A plain language explanation tailored for {persona}. If confidence is Low due to missing data, abstain from guessing and explicitly state why.",
                "action_recommendations": [
                    {{
                        "driver": "Name of the root driver",
                        "lever": "Controllable business lever",
                        "action": "Practical recommended action",
                        "owner": "Suggested owner role based on the persona context",
                        "expected_impact": "Expected outcome",
                        "confidence": "High/Medium/Low"
                    }}
                ]
            }}
            """
            
            mistral_res = call_mistral_api(prompt)
            llm_latency_ms = round((time.perf_counter() - t2) * 1000)
            
            response_text = mistral_res["content"]
            if response_text.startswith("```json"):
                response_text = response_text.strip("```json").strip("```")
                
            llm_payload = json.loads(response_text)
            llm_payload["telemetry"] = mistral_res["telemetry"]
            llm_payload["telemetry"]["llm_latency_ms"] = llm_latency_ms
            llm_payload["telemetry"]["analytics_latency_ms"] = deterministic_latency_ms
            
        except Exception as e:
            print(f"Mistral API failed: {e}")
            llm_payload = mock_llm_response(deterministic_analysis, persona)
            llm_payload["telemetry"]["llm_latency_ms"] = round((time.perf_counter() - t2) * 1000)
            llm_payload["telemetry"]["analytics_latency_ms"] = deterministic_latency_ms

    return JSONResponse({
        "kpi": kpi_meta.model_dump(),
        "deterministic_data": deterministic_analysis,
        "intelligence": llm_payload
    })

class FeedbackItem(BaseModel):
    kpi_id: str
    scenario: str
    thumbs_up: bool
    comment: str

@app.post("/api/feedback")
async def post_feedback(feedback: FeedbackItem):
    """Stores user feedback for learning loop simulation."""
    feedback_db.append(feedback.model_dump())
    # Save to a json file so it persists
    with open("feedback.json", "w") as f:
        json.dump(feedback_db, f)
    return {"status": "success", "total_feedback": len(feedback_db)}

class ChatQuery(BaseModel):
    query: str
    kpi_context: dict

@app.post("/api/query")
async def chat_query(query: ChatQuery):
    """Conversational API with Dynamic Fallback."""
    t0 = time.perf_counter()
    if not MISTRAL_API_KEY:
        # Dynamic fallback
        ctx = query.kpi_context
        drivers = [d["factor"] for d in ctx.get("drivers", [])]
        response = f"*(Mock Mode)* Based on the data, the status is {ctx.get('status')} and the current value is {ctx.get('current_value')}. The top drivers are: {', '.join(drivers) if drivers else 'None identified'}."
        
        return {
            "response": response, 
            "telemetry": {"llm_latency_ms": round((time.perf_counter() - t0) * 1000)}
        }
        
    prompt = f"Context: {json.dumps(query.kpi_context)}. User asks: {query.query}. Provide a short, direct answer."
    try:
        mistral_res = call_mistral_api(prompt)
        mistral_res["telemetry"]["llm_latency_ms"] = round((time.perf_counter() - t0) * 1000)
        return {"response": mistral_res["content"], "telemetry": mistral_res["telemetry"]}
    except Exception as e:
        print(f"Chat API failed: {e}")
        
        ctx = query.kpi_context
        drivers = [d["factor"] for d in ctx.get("drivers", [])]
        response = f"*(Mock Mode)* Based on the data, the status is {ctx.get('status')} and the current value is {ctx.get('current_value')}. The top drivers are: {', '.join(drivers) if drivers else 'None identified'}."
        
        return {
            "response": response,
            "telemetry": {"llm_used": "Mocked", "cost_usd": 0, "total_tokens": 0, "llm_latency_ms": round((time.perf_counter() - t0) * 1000)}
        }
