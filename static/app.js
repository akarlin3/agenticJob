document.addEventListener("DOMContentLoaded", () => {
    // 1. Upload Zone Drag and Drop Handlers
    const uploadZone = document.getElementById("upload-zone");
    const portfolioInput = document.getElementById("portfolio");
    const fileBadge = document.getElementById("file-badge");
    const fileNameSpan = document.getElementById("file-name");
    const removeFileBtn = document.getElementById("btn-remove-file");

    uploadZone.addEventListener("click", (e) => {
        if (e.target.closest("#btn-remove-file")) return;
        portfolioInput.click();
    });

    portfolioInput.addEventListener("change", () => {
        if (portfolioInput.files.length > 0) {
            handleFileSelect(portfolioInput.files[0]);
        }
    });

    uploadZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        uploadZone.classList.add("dragover");
    });

    uploadZone.addEventListener("dragleave", () => {
        uploadZone.classList.remove("dragover");
    });

    uploadZone.addEventListener("drop", (e) => {
        e.preventDefault();
        uploadZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            portfolioInput.files = e.dataTransfer.files;
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    function handleFileSelect(file) {
        fileNameSpan.textContent = file.name;
        fileBadge.style.display = "flex";
        addLogLine("system", `[System] File selected for upload: "${file.name}" (${(file.size/1024).toFixed(1)} KB)`);
    }

    removeFileBtn.addEventListener("click", (e) => {
        e.stopPropagation();
        portfolioInput.value = "";
        fileBadge.style.display = "none";
        addLogLine("system", `[System] Uploaded portfolio removed.`);
    });

    // 2. Logging and Terminal Utilities
    const consoleLogs = document.getElementById("console-logs");
    const statusIndicator = document.getElementById("status-indicator");
    const statusText = document.getElementById("status-text");

    function addLogLine(type, text) {
        const line = document.createElement("div");
        line.className = `log-line ${type}-line`;
        line.textContent = text;
        consoleLogs.appendChild(line);
        consoleLogs.scrollTop = consoleLogs.scrollHeight;
    }

    function setStatus(state, label) {
        statusIndicator.className = `status-indicator ${state}`;
        statusText.textContent = label;
    }

    // 3. Tab Navigation
    const tabBtns = document.querySelectorAll(".tab-btn");
    const tabContents = document.querySelectorAll(".tab-content");

    tabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const tabId = btn.getAttribute("data-tab");
            switchTab(tabId);
        });
    });

    function switchTab(tabId) {
        tabBtns.forEach(b => {
            if (b.getAttribute("data-tab") === tabId) {
                b.classList.add("active");
            } else {
                b.classList.remove("active");
            }
        });
        
        tabContents.forEach(c => {
            if (c.id === tabId) {
                c.classList.add("active");
            } else {
                c.classList.remove("active");
            }
        });
    }

    // 4. Form Submission & Agent Orchestration
    const form = document.getElementById("pipeline-form");
    const agentVisualizer = document.getElementById("agent-visualizer");
    const outputsWrapper = document.getElementById("outputs-wrapper");
    const btnSubmit = document.getElementById("btn-submit");

    // Visual nodes
    const nodeIngestion = document.getElementById("node-ingestion");
    const nodeEvaluator = document.getElementById("node-evaluator");
    const nodeTailor = document.getElementById("node-tailor");
    const nodeCoach = document.getElementById("node-coach");
    
    // Connectors
    const conn1 = document.getElementById("conn-1");
    const conn2 = document.getElementById("conn-2");
    const conn3 = document.getElementById("conn-3");

    // Tab buttons for visibility toggles
    const btnDiscovery = document.getElementById("tab-btn-discovery");
    const btnDashboard = document.getElementById("tab-btn-dashboard");
    const btnResume = document.getElementById("tab-btn-resume");
    const btnCoverLetter = document.getElementById("tab-btn-coverletter");
    const btnCoach = document.getElementById("tab-btn-coach");

    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        triggerPipeline();
    });

    const STAGE_NODES = {
        ingestion: nodeIngestion,
        evaluator: nodeEvaluator,
        tailor: nodeTailor,
        coach: nodeCoach,
    };
    const STAGE_CONNECTOR_AFTER = {
        ingestion: conn1,
        evaluator: conn2,
        tailor: conn3,
    };

    function finishRun() {
        btnSubmit.disabled = false;
        btnSubmit.innerHTML = `<i class="fa-solid fa-play"></i> Run Orchestration Pipeline`;
    }

    async function triggerPipeline() {
        agentVisualizer.style.display = "flex";
        resetVisualizer();

        btnSubmit.disabled = true;
        btnSubmit.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processing pipeline...`;

        setStatus("running", "Running");
        consoleLogs.innerHTML = "";
        addLogLine("system", "[Orchestrator] Starting end-to-end multi-agent orchestration...");

        const formData = new FormData();
        formData.append("job_description", document.getElementById("job_description").value);
        formData.append("mock", document.getElementById("mock").checked);
        if (portfolioInput.files.length > 0) {
            formData.append("portfolio", portfolioInput.files[0]);
        }

        // Accumulator that mirrors the legacy /api/run response shape so
        // populateDashboard can be reused unchanged.
        const accumulated = {
            job_analysis: null,
            fit_evaluation: null,
            tailored_resume: null,
            cover_letter: null,
            interview_prep: null,
            tailored_resume_pdf_available: false,
        };

        let response;
        try {
            response = await fetch("/api/run/stream", {
                method: "POST",
                body: formData,
            });
        } catch (error) {
            console.error(error);
            setStatus("error", "Error");
            addLogLine("error", `[Critical Error] ${error.message}`);
            setNodeError();
            finishRun();
            return;
        }

        if (!response.ok) {
            let detail = "Failed to execute orchestration pipeline.";
            try {
                const body = await response.json();
                detail = body.detail || body.message || detail;
            } catch (_) {}
            setStatus("error", "Error");
            addLogLine("error", `[Critical Error] ${detail}`);
            setNodeError();
            finishRun();
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let sawError = false;
        let terminated = false;
        let done = false;

        function handleEvent(eventName, payload) {
            switch (eventName) {
                case "log": {
                    const msg = payload.message || "";
                    let type = "system";
                    if (/Agent \d/.test(msg)) type = "agent";
                    else if (/successfully|Complete/i.test(msg)) type = "success";
                    addLogLine(type, msg);
                    break;
                }
                case "stage": {
                    const node = STAGE_NODES[payload.name];
                    if (!node) break;
                    if (payload.status === "active") {
                        setNodeActive(node);
                    } else if (payload.status === "completed") {
                        setNodeCompleted(node);
                        const conn = STAGE_CONNECTOR_AFTER[payload.name];
                        if (conn) setConnectorActive(conn);
                    } else if (payload.status === "error") {
                        node.className = "agent-node active error";
                    }
                    break;
                }
                case "result":
                    accumulated[payload.key] = payload.value;
                    break;
                case "terminated":
                    terminated = true;
                    break;
                case "error":
                    sawError = true;
                    addLogLine("error", `[Critical Error] ${payload.message}`);
                    setNodeError();
                    break;
                case "done":
                    done = true;
                    break;
            }
        }

        function drainBuffer() {
            let idx;
            while ((idx = buffer.indexOf("\n\n")) >= 0) {
                const raw = buffer.slice(0, idx);
                buffer = buffer.slice(idx + 2);
                if (!raw.trim()) continue;
                let eventName = "message";
                let dataLine = "";
                for (const line of raw.split("\n")) {
                    if (line.startsWith("event:")) {
                        eventName = line.slice(6).trim();
                    } else if (line.startsWith("data:")) {
                        dataLine += line.slice(5).trim();
                    }
                }
                let payload = {};
                if (dataLine) {
                    try { payload = JSON.parse(dataLine); } catch (_) {}
                }
                handleEvent(eventName, payload);
            }
        }

        try {
            while (true) {
                const { value, done: streamDone } = await reader.read();
                if (streamDone) break;
                buffer += decoder.decode(value, { stream: true });
                drainBuffer();
            }
            buffer += decoder.decode();
            drainBuffer();
        } catch (error) {
            console.error(error);
            setStatus("error", "Error");
            addLogLine("error", `[Critical Error] ${error.message}`);
            setNodeError();
            finishRun();
            return;
        }

        if (sawError) {
            setStatus("error", "Error");
            finishRun();
            return;
        }

        if (done || terminated) {
            setStatus("success", terminated ? "Terminated" : "Completed");
            populateDashboard(accumulated);
        }
        finishRun();
    }

    function resetVisualizer() {
        [nodeIngestion, nodeEvaluator, nodeTailor, nodeCoach].forEach(n => {
            n.className = "agent-node";
        });
        [conn1, conn2, conn3].forEach(c => {
            c.className = "node-connector";
        });
    }

    function setNodeActive(node) {
        node.className = "agent-node active";
    }

    function setNodeCompleted(node) {
        node.className = "agent-node completed";
    }

    function setConnectorActive(conn) {
        conn.className = "node-connector active";
    }

    function setNodeError() {
        const activeNode = document.querySelector(".agent-node.active");
        if (activeNode) {
            activeNode.className = "agent-node active error";
        }
    }

    // 5. Job Discovery search event handlers
    const jobSearchForm = document.getElementById("job-search-form");
    const btnSearch = document.getElementById("btn-search");
    const searchResultsSection = document.getElementById("search-results-section");
    const jobCardsGrid = document.getElementById("job-cards-grid");

    jobSearchForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        
        btnSearch.disabled = true;
        btnSearch.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Searching Boards...`;
        
        setStatus("running", "Searching");
        addLogLine("system", "[Search Agent] Initiating job boards secure search grounding...");

        // Collect inputs
        const query = document.getElementById("search_query").value;
        const location = document.getElementById("search_location").value;
        
        // Collect checked platforms
        const checkedPlatforms = [];
        document.querySelectorAll("input[name='search_platform']:checked").forEach(cb => {
            checkedPlatforms.push(cb.value);
        });
        
        const datePosted = document.getElementById("search_date_posted").value;
        const remoteOnly = document.getElementById("search_remote").checked;
        const isMock = document.getElementById("mock").checked;

        const formData = new FormData();
        formData.append("query", query);
        formData.append("location", location);
        formData.append("platforms", checkedPlatforms.join(","));
        formData.append("date_posted", datePosted);
        formData.append("remote", remoteOnly);
        formData.append("mock", isMock);

        try {
            const response = await fetch("/api/search", {
                method: "POST",
                body: formData
            });

            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.detail || "Failed to search job boards.");
            }

            renderDiscoveredJobs(data.jobs);
            setStatus("success", "Discovered");
            addLogLine("success", `[Search Agent] Sourcing Complete. Successfully discovered ${data.jobs.length} jobs.`);

        } catch (error) {
            console.error(error);
            setStatus("error", "Error");
            addLogLine("error", `[Search Agent Error] Sourcing failed: ${error.message}`);
            btnSearch.disabled = false;
            btnSearch.innerHTML = `<i class="fa-solid fa-search"></i> Search Target Boards`;
        }
    });

    function renderDiscoveredJobs(jobs) {
        jobCardsGrid.innerHTML = "";
        btnSearch.disabled = false;
        btnSearch.innerHTML = `<i class="fa-solid fa-search"></i> Search Target Boards`;

        if (!jobs || jobs.length === 0) {
            jobCardsGrid.innerHTML = `<p style="grid-column: 1/-1; text-align: center; color: var(--text-muted); padding: 30px;">No jobs discovered matching your keywords. Please try adjusting your search terms.</p>`;
            searchResultsSection.style.display = "block";
            return;
        }

        jobs.forEach(job => {
            const card = document.createElement("div");
            card.className = "job-card";
            
            // Build the card HTML
            card.innerHTML = `
                <div class="jc-header">
                    <span class="jc-title">${job.title}</span>
                    <span class="jc-source">${job.source}</span>
                </div>
                <div class="jc-meta">
                    <span><strong>Company:</strong> ${job.company}</span>
                    <span><strong>Location:</strong> ${job.location}</span>
                    ${job.posted ? `<span><strong>Posted:</strong> ${job.posted}</span>` : ""}
                </div>
                <div class="jc-snippet">${job.snippet}</div>
                <div class="jc-actions">
                    <a href="${job.url}" target="_blank" rel="noopener noreferrer"><i class="fa-solid fa-external-link"></i> View Sourced Post</a>
                    <button class="btn btn-sm btn-primary btn-analyze-job"><i class="fa-solid fa-wand-magic-sparkles"></i> Customize Application</button>
                </div>
            `;

            // Wire up the Customization trigger button
            const analyzeBtn = card.querySelector(".btn-analyze-job");
            analyzeBtn.addEventListener("click", () => {
                // Feed the FULL job description into the pipeline when available,
                // falling back to the short card snippet only if it's empty.
                const jobBody = (job.description && job.description.trim())
                    ? job.description
                    : job.snippet;
                const simulatedJobSpec = `Role: ${job.title} at ${job.company}
Location: ${job.location}

Summary & Requirements:
${jobBody}

Source Job Link:
${job.url}
`;
                // 1. Populate sidebar text area
                document.getElementById("job_description").value = simulatedJobSpec;
                
                // 2. Add orchestration logs
                addLogLine("system", `[System] Job selected from discovery: "${job.title}" at "${job.company}". Auto-populating pipeline configurations...`);
                
                // 3. Programmatically switch tab to visualizer and Dashboard
                btnDashboard.style.display = "flex";
                switchTab("tab-dashboard");
                
                // 4. Launch multi-agent pipeline
                triggerPipeline();
            });

            jobCardsGrid.appendChild(card);
        });

        searchResultsSection.style.display = "block";
        
        // Scroll results into view smoothly
        searchResultsSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    // 6. Populate Dashboard & Previews
    const fitScoreVal = document.getElementById("fit-score-val");
    const gaugeCircle = document.getElementById("gauge-circle");
    const decisionBadge = document.getElementById("decision-badge");
    const dashRoleTitle = document.getElementById("dash-role-title");
    const dashDomains = document.getElementById("dash-domains");
    const dashTechTags = document.getElementById("dash-tech-tags");
    const dashGapsList = document.getElementById("dash-gaps-list");
    
    const resumePre = document.querySelector("#resume-pre code");
    const btnDownloadResumePdf = document.getElementById("btn-download-resume-pdf");
    const coverLetterDiv = document.getElementById("coverletter-div");
    const coachQuestionsDiv = document.getElementById("coach-questions-div");

    function populateDashboard(data) {
        const job = data.job_analysis || {};
        const fit = data.fit_evaluation || {};
        
        // Populate Ingestion detail
        dashRoleTitle.textContent = job.role_title || "Unknown Title";
        dashDomains.textContent = (job.domain_expertise || []).join(", ") || "-";
        
        dashTechTags.innerHTML = "";
        (job.required_tech_stack || []).forEach(tech => {
            const tag = document.createElement("span");
            tag.className = "tag";
            tag.textContent = tech;
            dashTechTags.appendChild(tag);
        });

        // Set Gauge matching percentage
        const score = fit.fit_score_out_of_100 || 0;
        fitScoreVal.textContent = `${score}%`;
        
        const circleLength = 2 * Math.PI * 15.9155;
        const strokeVal = (score / 100) * circleLength;
        gaugeCircle.style.strokeDasharray = `${strokeVal}, ${circleLength}`;
        
        if (score >= 70) {
            gaugeCircle.style.stroke = "var(--status-success)";
        } else if (score >= 50) {
            gaugeCircle.style.stroke = "var(--status-warning)";
        } else {
            gaugeCircle.style.stroke = "var(--status-danger)";
        }

        // Decision Badge
        if (fit.go_no_go) {
            decisionBadge.textContent = "GO";
            decisionBadge.className = "badge-decision go";
            
            btnResume.style.display = "flex";
            btnCoverLetter.style.display = "flex";
            btnCoach.style.display = "flex";
        } else {
            decisionBadge.textContent = "NO-GO";
            decisionBadge.className = "badge-decision nogo";
            
            btnResume.style.display = "none";
            btnCoverLetter.style.display = "none";
            btnCoach.style.display = "none";
            
            addLogLine("system", "[Orchestrator] Gaps and Match Fit score fell below GO threshold. Document Customization skipped.");
        }

        // Technical Gaps
        dashGapsList.innerHTML = "";
        if (fit.technical_gaps && fit.technical_gaps.length > 0) {
            fit.technical_gaps.forEach(gap => {
                const li = document.createElement("li");
                li.textContent = gap;
                dashGapsList.appendChild(li);
            });
        } else {
            const li = document.createElement("li");
            li.textContent = "No critical gaps identified! Excellent portfolio fit.";
            li.style.color = "var(--status-success)";
            li.style.paddingLeft = "0";
            li.style.listStyle = "none";
            dashGapsList.appendChild(li);
        }

        // Text previews
        if (data.tailored_resume) {
            resumePre.textContent = data.tailored_resume;
        }

        if (btnDownloadResumePdf) {
            btnDownloadResumePdf.style.display =
                data.tailored_resume_pdf_available ? "inline-flex" : "none";
        }

        if (data.cover_letter) {
            coverLetterDiv.innerHTML = parseMarkdown(data.cover_letter);
        }

        coachQuestionsDiv.innerHTML = "";
        if (data.interview_prep && data.interview_prep.length > 0) {
            data.interview_prep.forEach((q, idx) => {
                const card = document.createElement("div");
                card.className = "q-card";
                card.innerHTML = `
                    <div class="q-header">
                        <span class="q-title">Question ${idx + 1}</span>
                        <span class="badge-q-type ${q.type.toLowerCase()}">${q.type}</span>
                    </div>
                    <div class="q-body">
                        <h4 style="margin-bottom:6px; font-weight:600;">"${q.question}"</h4>
                        <div class="q-rationale"><strong>Why Asked:</strong> ${q.rationale}</div>
                        <div class="q-strategy"><strong>Defense Strategy:</strong> ${q.suggested_strategy}</div>
                    </div>
                `;
                coachQuestionsDiv.appendChild(card);
            });
        }

        btnDashboard.style.display = "flex";
        switchTab("tab-dashboard");
    }

    function parseMarkdown(mdText) {
        if (!mdText) return "";
        let html = mdText;
        
        html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
        html = html.replace(/^\s*$/gim, '</p><p>');
        html = `<p>${html}</p>`;
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/<p><\/p>/g, '');
        
        return html;
    }
});

// Toast notification copy helper
function copyContent(elementId) {
    const element = document.getElementById(elementId);
    let text = "";
    if (element.tagName === "PRE") {
        text = element.textContent;
    } else {
        text = element.innerText;
    }
    
    navigator.clipboard.writeText(text).then(() => {
        const toast = document.getElementById("toast");
        toast.classList.add("show");
        setTimeout(() => {
            toast.classList.remove("show");
        }, 2500);
    });
}
