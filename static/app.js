document.addEventListener("DOMContentLoaded", () => {
    const personaSelect = document.getElementById("persona");
    const scenarioSelect = document.getElementById("scenario");
    const kpiListContainer = document.getElementById("kpi-list");
    const emptyState = document.getElementById("empty-state");
    const analysisState = document.getElementById("analysis-state");
    
    // Telemetry
    const latencyBadge = document.getElementById("latency-badge");
    const llmBadge = document.getElementById("llm-badge");
    const tokenBadge = document.getElementById("token-badge");
    const costBadge = document.getElementById("cost-badge");

    let currentPersona = personaSelect.value;
    let currentScenario = scenarioSelect.value;
    let currentKpis = [];
    let activeKpiId = null;
    let activeAnalysis = null;

    // Fetch KPIs based on persona & scenario
    const loadKpis = async () => {
        try {
            const res = await fetch("/api/kpis", {
                headers: { "persona": currentPersona, "scenario": currentScenario }
            });
            const data = await res.json();
            currentKpis = data.kpis;
            renderKpiNav();
        } catch (e) {
            console.error("Failed to load KPIs", e);
        }
    };

    const renderKpiNav = () => {
        kpiListContainer.innerHTML = "";
        currentKpis.forEach(kpi => {
            const li = document.createElement("li");
            li.className = "kpi-item";
            li.textContent = kpi.name;
            if (kpi.id === activeKpiId) li.classList.add("active");
            li.onclick = () => selectKpi(kpi.id, li);
            kpiListContainer.appendChild(li);
        });
        
        if (!activeKpiId) {
            analysisState.classList.add("hidden");
            emptyState.classList.remove("hidden");
        } else {
            // Auto reload the active KPI if scenario/persona changed
            const activeLi = Array.from(kpiListContainer.children).find(el => el.textContent === currentKpis.find(k => k.id === activeKpiId)?.name);
            if (activeLi) selectKpi(activeKpiId, activeLi);
        }
    };

    const selectKpi = async (kpiId, listItemElement) => {
        activeKpiId = kpiId;
        document.querySelectorAll(".kpi-item").forEach(el => el.classList.remove("active"));
        listItemElement.classList.add("active");

        emptyState.classList.add("hidden");
        analysisState.classList.remove("hidden");
        analysisState.classList.add("loading");

        try {
            const res = await fetch(`/api/kpi/${kpiId}/analysis`, {
                headers: { "persona": currentPersona, "scenario": currentScenario }
            });
            if (!res.ok) throw new Error("API Error");
            const data = await res.json();
            activeAnalysis = data;
            
            renderAnalysis(data);
        } catch (e) {
            console.error("Analysis failed", e);
            document.getElementById("narrative-text").textContent = "Failed to load analysis. Check console.";
        } finally {
            analysisState.classList.remove("loading");
        }
    };

    const renderAnalysis = (data) => {
        const kpi = data.kpi;
        const det = data.deterministic_data;
        const ai = data.intelligence;

        // Header Metrics
        document.getElementById("kpi-name").textContent = kpi.name;
        document.getElementById("kpi-current").textContent = formatValue(det.current_value, kpi.unit);
        document.getElementById("kpi-previous").textContent = formatValue(det.previous_value, kpi.unit);
        
        const changeEl = document.getElementById("kpi-change");
        if (det.percent_change !== null) {
            changeEl.textContent = `${det.percent_change > 0 ? '+' : ''}${det.percent_change}%`;
            changeEl.className = `metric-value ${det.percent_change < 0 ? 'change-negative' : 'change-positive'}`;
        } else {
            changeEl.textContent = "N/A";
            changeEl.className = "metric-value";
        }

        const statusEl = document.getElementById("kpi-status");
        statusEl.textContent = det.status.replace("_", " ");
        statusEl.className = `status-badge status-${det.status}`;

        // Intelligence & Telemetry
        document.getElementById("narrative-text").textContent = ai.narrative;
        
        if (ai.telemetry) {
            llmBadge.textContent = `Engine: ${ai.telemetry.llm_used}`;
            tokenBadge.textContent = `Tokens: ${ai.telemetry.total_tokens || 0}`;
            costBadge.textContent = `Cost: $${ai.telemetry.cost_usd || 0}`;
            
            // Render detailed latency
            const a_lat = ai.telemetry.analytics_latency_ms || 0;
            const l_lat = ai.telemetry.llm_latency_ms || 0;
            latencyBadge.textContent = `Latency: ${a_lat}ms (Math) + ${l_lat}ms (AI)`;
        }

        const actionsContainer = document.getElementById("actions-container");
        actionsContainer.innerHTML = "";
        ai.action_recommendations.forEach(action => {
            actionsContainer.innerHTML += `
                <div class="action-card">
                    <div class="action-header">
                        <span class="action-driver">Lever: ${action.lever}</span>
                        <span class="action-confidence">Confidence: ${action.confidence}</span>
                    </div>
                    <div class="action-body">
                        <p><strong>Action:</strong> ${action.action}</p>
                    </div>
                    <div class="action-meta">
                        <span>👤 Owner: ${action.owner}</span>
                        <span>📈 Impact: ${action.expected_impact}</span>
                    </div>
                </div>
            `;
        });

        // Structured Evidence
        if (det.evidence) {
            document.getElementById("ev-source").textContent = det.evidence.source;
            document.getElementById("ev-obs").textContent = det.evidence.observation;
            document.getElementById("ev-freshness").textContent = det.evidence.freshness;
            document.getElementById("ev-method").textContent = det.evidence.method;
            const confEl = document.getElementById("ev-confidence");
            confEl.textContent = `${det.evidence.confidence_score}%`;
            confEl.className = det.evidence.confidence_score > 80 ? "confidence-high" : (det.evidence.confidence_score > 50 ? "confidence-medium" : "confidence-low");
        }
        
        // Lineage
        const lineageContainer = document.getElementById("lineage-container");
        lineageContainer.innerHTML = "";
        if (det.lineage && det.lineage.length > 0) {
            det.lineage.forEach((step, i) => {
                const isLast = i === det.lineage.length - 1;
                lineageContainer.innerHTML += `
                    <div style="display:flex; align-items:center; gap:8px;">
                        <span style="color:var(--accent-color); font-weight:bold;">${i+1}.</span>
                        <span>${step}</span>
                        ${!isLast ? '<div style="margin-left:8px; border-left:1px solid #3f3f46; height:16px;"></div>' : ''}
                    </div>
                `;
            });
        }

        // Drivers
        const driversList = document.getElementById("drivers-list");
        driversList.innerHTML = "";
        if (det.drivers.length === 0) {
            driversList.innerHTML = "<li class='driver-item' style='color: #a1a1aa;'>No drivers identified</li>";
        } else {
            det.drivers.forEach(driver => {
                const isNeg = driver.contribution < 0;
                driversList.innerHTML += `
                    <li class="driver-item">
                        <div class="driver-item-name">
                            <span>${driver.factor}</span>
                            <span class="driver-item-metric">${driver.metric}</span>
                        </div>
                        <span class="driver-impact ${isNeg ? 'driver-negative' : 'driver-positive'}">
                            ${isNeg ? '' : '+'}${driver.contribution}%
                        </span>
                    </li>
                `;
            });
        }
        
        // Reset feedback and chat
        document.getElementById("feedback-comment").value = "";
        document.getElementById("chat-input").value = "";
        document.getElementById("chat-response").style.display = "none";
    };

    const formatValue = (val, unit) => {
        if (unit === "$") return `$${Math.round(val).toLocaleString()}`;
        if (unit === "%") return `${val.toFixed(2)}%`;
        return `${Math.round(val).toLocaleString()} ${unit}`;
    };

    // Feedback Logic (Global so it can be called from onclick)
    window.submitFeedback = async (isUpvote) => {
        if (!activeKpiId) return;
        const comment = document.getElementById("feedback-comment").value;
        const btn = event.target;
        btn.style.background = "#10b981"; // success green temp
        
        try {
            await fetch("/api/feedback", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    kpi_id: activeKpiId,
                    scenario: currentScenario,
                    thumbs_up: isUpvote,
                    comment: comment
                })
            });
        } catch (e) { console.error("Feedback failed", e); }
        
        setTimeout(() => { btn.style.background = "var(--bg-hover)"; }, 1000);
    };

    // Chat Logic
    window.submitChat = async () => {
        const input = document.getElementById("chat-input");
        const query = input.value.trim();
        if (!query || !activeAnalysis) return;
        
        const responseBox = document.getElementById("chat-response");
        responseBox.style.display = "block";
        responseBox.textContent = "Thinking...";
        
        try {
            const res = await fetch("/api/query", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    query: query,
                    kpi_context: activeAnalysis.deterministic_data
                })
            });
            const data = await res.json();
            responseBox.innerHTML = marked.parse(data.response);
        } catch (e) {
            responseBox.textContent = "Error communicating with intelligence engine.";
        }
    };

    // Custom Data Upload Logic
    const uploadBtnUI = document.getElementById("btn-upload-ui");
    const fileInput = document.getElementById("csv-upload");
    
    uploadBtnUI.addEventListener("click", () => {
        fileInput.click();
    });

    fileInput.addEventListener("change", (e) => {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = async (event) => {
            const csvText = event.target.result;
            const originalText = uploadBtnUI.textContent;
            uploadBtnUI.textContent = "Uploading...";
            
            try {
                const res = await fetch("/api/upload", {
                    method: "POST",
                    headers: { "Content-Type": "text/csv" },
                    body: csvText
                });
                
                if (!res.ok) throw new Error("Upload failed");
                
                // Switch scenario to custom
                scenarioSelect.value = "custom";
                currentScenario = "custom";
                loadKpis();
                
                uploadBtnUI.textContent = "Upload Success!";
                uploadBtnUI.style.background = "#10b981";
                setTimeout(() => {
                    uploadBtnUI.textContent = "Upload Custom CSV";
                    uploadBtnUI.style.background = "var(--accent-color)";
                }, 2000);
                
            } catch (err) {
                console.error(err);
                uploadBtnUI.textContent = "Upload Failed";
                uploadBtnUI.style.background = "#ef4444";
                setTimeout(() => {
                    uploadBtnUI.textContent = "Upload Custom CSV";
                    uploadBtnUI.style.background = "var(--accent-color)";
                }, 3000);
            }
            
            // Reset input
            fileInput.value = "";
        };
        reader.readAsText(file);
    });

    // Listeners
    personaSelect.addEventListener("change", (e) => {
        currentPersona = e.target.value;
        loadKpis();
    });
    
    scenarioSelect.addEventListener("change", (e) => {
        currentScenario = e.target.value;
        loadKpis();
    });

    // Init
    loadKpis();
});
