# BusinessIntelligence.ai
# KPI Intelligence Engine V3

The KPI Intelligence Engine is an AI-powered business intelligence dashboard designed to synthesize quantitative metrics and qualitative narratives. It combines deterministic statistical analysis (like Z-score anomaly detection) with Generative AI (Mistral Large) to provide deep, actionable insights on business performance.

## 🚀 Features

- **Dynamic Role-Based Access:** Automatically filters KPIs and context based on the logged-in persona (e.g., CMO vs. Regional Manager).
- **Scenario Simulation:** Run data against multiple generated scenarios including normal operations, anomaly drops, delayed data, and sparse histories.
- **Custom Data Upload:** Upload your own CSV data directly into the dashboard to instantly analyze real-world metrics.
- **AI Narrative Synthesis:** Uses LLMs to generate a human-readable synthesis of what happened, why it happened, and what to do next.
- **Conversational Queries:** Ask follow-up questions directly to the AI about the specific KPI context.
- **Data Lineage & Structured Evidence:** Transparently displays where the data came from, its freshness, and the statistical method used to evaluate it.

## 🏗 Solution Architecture

The application is built using a modern, decoupled architecture:
1. **Frontend (Vanilla JS/HTML/CSS):** A lightweight, responsive dashboard that fetches data dynamically. It uses custom CSS for styling and `marked.js` to render Markdown from the AI.
2. **Backend Engine (FastAPI):** A high-performance asynchronous Python API that serves the frontend and handles data processing.
3. **Deterministic Data Layer (Pandas):** Processes synthetic scenarios or uploaded CSV files. It calculates Z-scores, percent changes, and contribution logic to provide a firm factual grounding.
4. **Generative AI Layer (Mistral Large):** Ingests the deterministic context (never raw data, ensuring privacy and speed) and returns a human-readable synthesis, driver explanations, and recommended actions.

## 🧠 Implementation Approach

Our approach focused on **"Determinism First, Generative Second."** 
Instead of sending raw tables of data to an LLM (which is slow, costly, and prone to hallucinations), we built a deterministic engine using `pandas` to calculate exact mathematical changes, Z-score anomalies, and data lineage. We then package this highly structured, factual context into a prompt for Mistral Large. This approach ensures the AI acts as an analytical synthesizer rather than a calculator, resulting in 100% factual accuracy with the UX benefits of a conversational AI.

## 🛠 Prerequisites

Make sure you have Python 3.9+ installed.

You will also need an API Key from Mistral AI to power the narrative synthesis.

## 📦 Installation

1. **Clone the repository:**
   ```bash
   git clone <https://github.com/akhilpavanpabolu/BusinessIntelligence.ai>
   ```

2. **Install the required Python dependencies:**
   ```bash
   pip install fastapi uvicorn pandas pydantic requests
   ```

3. **Set up your environment variables:**
   Create a `.env` file in the root directory and add your Mistral API key:
   ```env
   MISTRAL_API_KEY=your_api_key_here
   ```

## 🏃‍♂️ How to Run

Start the FastAPI development server by running:

```bash
python -m uvicorn main:app --reload
```

Then, open your web browser and navigate to: **http://localhost:8000**

## 📊 Using Custom Data

You can upload your own original data by selecting **"Upload Custom CSV"** in the sidebar. 

Your CSV must contain a `date` column and at least one of the following metric columns:
- `traffic`
- `conv_rate`
- `aov`
- `revenue`
- `enterprise_signups`

*Note: If your dataset is missing a specific column required for a KPI, the engine will gracefully degrade and mark the metric as "ambiguous/missing".*
