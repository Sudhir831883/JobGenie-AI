const state = {
    selectedFile: null,
    latestAnalysis: null,
    latestRecommendations: [],
    jobChart: null,
    skillChart: null,
};

const PROCESSING_STEPS = [
    { label: "Uploading Resume...", percent: 18 },
    { label: "Extracting Text...", percent: 38 },
    { label: "Analyzing Skills...", percent: 58 },
    { label: "Matching Jobs...", percent: 78 },
    { label: "Generating Insights...", percent: 100 },
];

const CHAT_HISTORY_KEY = "jobgenie:chatHistory";

const qs = (selector) => document.querySelector(selector);
const qsa = (selector) => [...document.querySelectorAll(selector)];

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function debounce(callback, delay = 220) {
    let timerId;
    return (...args) => {
        window.clearTimeout(timerId);
        timerId = window.setTimeout(() => callback(...args), delay);
    };
}

function formatBytes(bytes) {
    if (!bytes) return "0 KB";
    const units = ["bytes", "KB", "MB"];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    return `${(bytes / Math.pow(1024, index)).toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function setStatus(message, type = "") {
    const status = qs("#uploadStatus");
    status.textContent = message;
    status.className = `status-message ${type}`.trim();
}

function setLoading(isLoading) {
    const button = qs("#analyzeButton");
    button.disabled = isLoading;
    button.classList.toggle("is-loading", isLoading);
    qs(".button-text").textContent = isLoading ? "Analyzing..." : "Analyze Resume";
}

function updateProcessingStep(index) {
    const panel = qs("#processingPanel");
    const text = qs("#processingText");
    const percent = qs("#processingPercent");
    const fill = qs("#processingFill");
    const step = PROCESSING_STEPS[index];

    if (!panel || !step) return;

    panel.hidden = false;
    text.textContent = step.label;
    percent.textContent = `${step.percent}%`;
    fill.style.width = `${step.percent}%`;

    qsa("#processingSteps li").forEach((item, itemIndex) => {
        item.classList.toggle("done", itemIndex < index);
        item.classList.toggle("active", itemIndex === index);
    });
    console.log("AI processing step:", step);
}

async function runProcessingStep(index, task) {
    updateProcessingStep(index);
    const delay = 1050 + (index * 120);
    const taskPromise = typeof task === "function" ? task() : Promise.resolve();
    const [result] = await Promise.all([taskPromise, sleep(delay)]);
    return result;
}

function finishProcessingFlow() {
    qsa("#processingSteps li").forEach((item) => {
        item.classList.remove("active");
        item.classList.add("done");
    });
    qs("#processingText").textContent = "Insights ready";
    qs("#processingPercent").textContent = "100%";
    qs("#processingFill").style.width = "100%";
}

function resetProcessingFlow() {
    const panel = qs("#processingPanel");
    if (!panel) return;
    panel.hidden = true;
    qs("#processingFill").style.width = "0%";
    qs("#processingPercent").textContent = "0%";
    qsa("#processingSteps li").forEach((item) => item.classList.remove("active", "done"));
}

function showFile(file) {
    console.log("Selected file:", file);
    state.selectedFile = file;
    qs("#fileName").textContent = file.name;
    qs("#fileMeta").textContent = `${formatBytes(file.size)} - ${file.type || "application/pdf"}`;
    qs("#filePreview").hidden = false;
    setStatus("PDF ready for analysis.", "success");
}

function clearFile() {
    state.selectedFile = null;
    qs("#resumeInput").value = "";
    qs("#filePreview").hidden = true;
    setStatus("");
}

function validatePdf(file) {
    if (!file) {
        return "Please select a PDF resume first.";
    }
    if (!file.name.toLowerCase().endsWith(".pdf") || (file.type && file.type !== "application/pdf")) {
        return "Only PDF files are supported.";
    }
    if (file.size <= 0) {
        return "The selected PDF is empty.";
    }
    if (file.size > 8 * 1024 * 1024) {
        return "Please upload a PDF smaller than 8 MB.";
    }
    return "";
}

async function parseJsonResponse(response) {
    const text = await response.text();
    console.log("Raw response:", text);
    try {
        return text ? JSON.parse(text) : {};
    } catch (error) {
        console.error("JSON parse failed:", error);
        throw new Error("Server returned an invalid response.");
    }
}

async function uploadResume(file) {
    const formData = new FormData();
    formData.append("resume", file);
    console.log("Uploading resume via /upload:", file.name);

    const response = await fetch("/upload", {
        method: "POST",
        body: formData,
    });
    const data = await parseJsonResponse(response);
    console.log("/upload JSON:", data);

    if (!response.ok) {
        throw new Error(data.error || "Resume upload failed.");
    }
    return data;
}

async function predictJobs(extractedText) {
    console.log("Sending extracted text to /predict. Characters:", extractedText.length);
    const response = await fetch("/predict", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ text: extractedText }),
    });
    const data = await parseJsonResponse(response);
    console.log("/predict JSON:", data);

    if (!response.ok) {
        throw new Error(data.error || "Job prediction failed.");
    }
    return data;
}

async function searchJobs(query) {
    console.log("Searching jobs:", query);
    const response = await fetch(`/search?q=${encodeURIComponent(query)}`);
    const data = await parseJsonResponse(response);
    console.log("/search JSON:", data);

    if (!response.ok) {
        throw new Error(data.error || "Search failed.");
    }
    return data;
}

async function fetchSearchSuggestions(query) {
    console.log("Fetching search suggestions:", query);
    const response = await fetch(`/search_suggestions?q=${encodeURIComponent(query)}`);
    const data = await parseJsonResponse(response);
    console.log("/search_suggestions JSON:", data);

    if (!response.ok) {
        throw new Error(data.error || "Could not load search suggestions.");
    }
    return data.suggestions || [];
}

function renderSearchResults(data) {
    const panel = qs("#searchResults");
    const grid = qs("#searchResultGrid");
    const title = qs("#searchTitle");
    const results = data.results || [];

    title.textContent = results.length
        ? `Matches for "${data.query}"`
        : `No matches for "${data.query}"`;
    grid.innerHTML = "";

    if (!results.length) {
        grid.innerHTML = `<article class="search-result-card glass-card"><h3>No roles found</h3><p>Try a broader skill like python, sql, react, cloud, or analytics.</p></article>`;
    }

    results.forEach((job) => {
        const card = document.createElement("article");
        card.className = "search-result-card glass-card";
        card.innerHTML = `
            <h3>${job.job_title}</h3>
            <div class="job-meta">
                <span>${job.category}</span>
                <span>${job.location}</span>
            </div>
            <p>${job.job_description}</p>
            <div class="chip-row">${(job.skills || []).slice(0, 5).map((skill) => `<span class="skill-chip">${skill}</span>`).join("")}</div>
        `;
        grid.appendChild(card);
    });

    panel.hidden = false;
    panel.classList.add("is-visible");
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
}

function hideSearchSuggestions() {
    const dropdown = qs("#searchSuggestions");
    const panel = qs(".search-panel");
    if (!dropdown) return;
    dropdown.hidden = true;
    dropdown.innerHTML = "";
    panel?.classList.remove("is-suggesting");
}

function renderSearchSuggestions(suggestions) {
    const dropdown = qs("#searchSuggestions");
    if (!dropdown) return;

    dropdown.innerHTML = "";
    if (!suggestions.length) {
        hideSearchSuggestions();
        return;
    }

    suggestions.forEach((suggestion) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "suggestion-item";
        button.dataset.value = suggestion.label;
        button.innerHTML = `
            <span>${suggestion.label}</span>
            <span class="suggestion-type">${suggestion.type}</span>
        `;
        dropdown.appendChild(button);
    });

    dropdown.hidden = false;
    qs(".search-panel")?.classList.add("is-suggesting");
}

function renderSummary(data) {
    const summaryGrid = qs("#summaryGrid");
    const summary = data.summary || {};
    const skills = data.resume_skills || [];
    summaryGrid.innerHTML = `
        <article class="summary-card glass-card">
            <span>Top Match</span>
            <strong>${summary.top_match || 0}%</strong>
        </article>
        <article class="summary-card glass-card">
            <span>Resume Skills</span>
            <strong>${summary.resume_skill_count || skills.length}</strong>
        </article>
        <article class="summary-card glass-card">
            <span>Best Category</span>
            <strong>${summary.most_relevant_category || "Ready"}</strong>
        </article>
        <article class="summary-card glass-card">
            <span>Dataset Rows</span>
            <strong>${summary.dataset_rows || "100+"}</strong>
        </article>
    `;
    summaryGrid.hidden = false;
    qs("#datasetCount").textContent = summary.dataset_rows || "100+";
}

function createChip(label, type = "") {
    const chip = document.createElement("span");
    chip.className = `skill-chip ${type}`.trim();
    chip.textContent = label;
    return chip;
}

function renderRecommendations(recommendations) {
    const grid = qs("#recommendationGrid");
    grid.innerHTML = "";
    state.latestRecommendations = recommendations;

    recommendations.forEach((job, index) => {
        const card = document.createElement("article");
        card.className = "recommendation-card glass-card";
        card.style.animationDelay = `${index * 90}ms`;

        const matched = document.createElement("div");
        matched.className = "chip-row";
        (job.matched_skills || []).slice(0, 8).forEach((skill) => matched.appendChild(createChip(skill)));
        if (!matched.children.length) matched.appendChild(createChip("No direct skill overlap yet"));

        const missing = document.createElement("div");
        missing.className = "chip-row";
        (job.missing_skills || []).slice(0, 8).forEach((skill) => missing.appendChild(createChip(skill, "missing")));
        if (!missing.children.length) missing.appendChild(createChip("No major gaps found"));

        const suggestions = document.createElement("ul");
        suggestions.className = "suggestion-list";
        (job.suggestions || []).slice(0, 3).forEach((text) => {
            const item = document.createElement("li");
            item.textContent = text;
            suggestions.appendChild(item);
        });

        card.innerHTML = `
            ${index === 0 ? '<span class="best-match-badge">Best Match</span>' : ""}
            <div class="job-card-head">
                <h3>${job.job_title}</h3>
                <span class="match-badge">${job.match_percent}%</span>
            </div>
            <div class="job-meta">
                <span>${job.category}</span>
                <span>${job.location}</span>
            </div>
            <span class="confidence-badge">Confidence score ${Math.round((job.skill_score || job.match_percent || 0))}%</span>
            <div class="confidence-meter"><span style="--confidence-width: ${Math.min(100, Math.max(0, job.match_percent || 0))}%"></span></div>
            <p>${job.job_description}</p>
            <div class="skills-block">
                <strong>Matched skills</strong>
            </div>
            <div class="skills-block">
                <strong>Missing skills</strong>
            </div>
            <div class="skills-block">
                <strong>Suggestions</strong>
            </div>
            <button class="btn btn-secondary btn-wide view-details-button" type="button" data-job-index="${index}">View Details</button>
        `;
        card.querySelectorAll(".skills-block")[0].appendChild(matched);
        card.querySelectorAll(".skills-block")[1].appendChild(missing);
        card.querySelectorAll(".skills-block")[2].appendChild(suggestions);
        grid.appendChild(card);
    });

    grid.hidden = false;
}

function renderCharts(chartData) {
    const hasBarData = chartData?.bar?.labels?.length && chartData?.bar?.scores?.length;
    const hasPieData = chartData?.pie?.labels?.length && chartData?.pie?.values?.length;

    if (!hasBarData || !hasPieData) {
        console.warn("Analytics chart data missing; charts were not rendered.", chartData);
        return;
    }

    const data = {
        bar: {
            labels: chartData.bar.labels,
            scores: chartData.bar.scores,
        },
        pie: {
            labels: chartData.pie.labels,
            values: chartData.pie.values,
        },
    };
    console.log("Chart loaded");
    console.log(data);

    if (typeof Chart === "undefined") {
        console.error("Chart.js is not loaded. Check the CDN script in index.html.");
        return;
    }

    const jobCanvas = qs("#jobChart");
    const skillCanvas = qs("#skillChart");
    if (!jobCanvas || !skillCanvas) {
        console.error("Chart canvas not found", { jobCanvas, skillCanvas });
        return;
    }

    if (state.jobChart) state.jobChart.destroy();
    if (state.skillChart) state.skillChart.destroy();

    const jobGradient = jobCanvas.getContext("2d").createLinearGradient(0, 0, jobCanvas.clientWidth || 620, 0);
    jobGradient.addColorStop(0, "#7227ff");
    jobGradient.addColorStop(0.62, "#ff8b2c");
    jobGradient.addColorStop(1, "#18c7b8");

    state.jobChart = new Chart(jobCanvas, {
        type: "bar",
        data: {
            labels: data.bar.labels,
            datasets: [{
                label: "Match %",
                data: data.bar.scores,
                borderRadius: 8,
                barThickness: 28,
                maxBarThickness: 34,
                backgroundColor: jobGradient,
            }],
        },
        options: {
            indexAxis: "y",
            responsive: true,
            maintainAspectRatio: false,
            resizeDelay: 120,
            animation: {
                duration: 1100,
                easing: "easeOutQuart",
            },
            scales: {
                x: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { callback: (value) => `${value}%` },
                },
                y: {
                    ticks: {
                        color: "#4a5568",
                        font: { weight: "700" },
                    },
                    grid: { display: false },
                },
            },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "rgba(23, 32, 51, 0.92)",
                    padding: 12,
                    cornerRadius: 8,
                    callbacks: { label: (item) => `${item.raw}% match` },
                },
            },
        },
    });

    const percentageLabelPlugin = {
        id: "percentageLabelPlugin",
        afterDatasetsDraw(chart) {
            const { ctx, data: chartData } = chart;
            const values = chartData.datasets[0].data;
            const total = values.reduce((sum, value) => sum + Number(value || 0), 0);
            if (!total) return;

            ctx.save();
            ctx.fillStyle = "#172033";
            ctx.font = "800 13px Inter, sans-serif";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            chart.getDatasetMeta(0).data.forEach((arc, index) => {
                const value = Number(values[index] || 0);
                if (!value) return;
                const angle = (arc.startAngle + arc.endAngle) / 2;
                const radius = (arc.outerRadius + arc.innerRadius) / 2;
                const x = arc.x + Math.cos(angle) * radius;
                const y = arc.y + Math.sin(angle) * radius;
                ctx.fillText(`${Math.round((value / total) * 100)}%`, x, y);
            });
            ctx.restore();
        },
    };

    state.skillChart = new Chart(skillCanvas, {
        type: "doughnut",
        data: {
            labels: data.pie.labels,
            datasets: [{
                data: data.pie.values,
                backgroundColor: ["#18c7b8", "#ff8b2c", "#7227ff"],
                borderWidth: 0,
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            resizeDelay: 120,
            cutout: "62%",
            animation: {
                animateRotate: true,
                animateScale: true,
                duration: 1000,
                easing: "easeOutQuart",
            },
            plugins: {
                legend: {
                    position: "bottom",
                    labels: {
                        boxWidth: 12,
                        color: "#4a5568",
                        font: { weight: "800" },
                        padding: 18,
                        usePointStyle: true,
                    },
                },
                tooltip: {
                    backgroundColor: "rgba(23, 32, 51, 0.92)",
                    padding: 12,
                    cornerRadius: 8,
                },
            },
        },
        plugins: [percentageLabelPlugin],
    });
}

function initAnalyticsState() {
    const empty = qs("#analyticsEmpty");
    const content = qs("#analyticsContent");
    const stats = qs("#analyticsStats");

    if (empty) empty.hidden = false;
    if (content) {
        content.hidden = true;
        content.classList.remove("is-visible");
    }
    if (stats) {
        stats.hidden = true;
        stats.innerHTML = "";
    }

    if (state.jobChart) {
        state.jobChart.destroy();
        state.jobChart = null;
    }
    if (state.skillChart) {
        state.skillChart.destroy();
        state.skillChart = null;
    }
}

function renderAnalyticsStats(data) {
    const stats = qs("#analyticsStats");
    if (!stats) return;

    const recommendations = data.recommendations || [];
    const summary = data.summary || {};
    const topJob = recommendations[0] || {};
    const missingSkills = recommendations
        .flatMap((job) => job.missing_skills || [])
        .filter((skill, index, list) => list.indexOf(skill) === index);
    const matchedSkills = recommendations
        .flatMap((job) => job.matched_skills || [])
        .filter((skill, index, list) => list.indexOf(skill) === index);

    stats.innerHTML = `
        <article class="analytics-stat-card glass-card">
            <span>Best match</span>
            <strong>${topJob.job_title || "Ready"}</strong>
            <p>${summary.top_match || topJob.match_percent || 0}% alignment from your latest resume analysis.</p>
        </article>
        <article class="analytics-stat-card glass-card">
            <span>Skill signal</span>
            <strong>${matchedSkills.length}</strong>
            <p>Relevant skills detected across your recommended roles.</p>
        </article>
        <article class="analytics-stat-card glass-card">
            <span>Priority gap</span>
            <strong>${missingSkills[0] || "No major gap"}</strong>
            <p>${missingSkills.length ? `${missingSkills.slice(0, 4).join(", ")} should be your next learning focus.` : "Your top match has strong skill coverage."}</p>
        </article>
        <article class="analytics-stat-card glass-card">
            <span>Career lane</span>
            <strong>${summary.most_relevant_category || topJob.category || "General"}</strong>
            <p>Use this lane to tailor portfolio projects and applications.</p>
        </article>
    `;
    stats.hidden = false;
}

function renderAnalytics(data) {
    const recommendations = data?.recommendations || [];
    const hasAnalysisData = recommendations.length > 0 && data?.chart_data;
    const empty = qs("#analyticsEmpty");
    const content = qs("#analyticsContent");

    if (!hasAnalysisData) {
        initAnalyticsState();
        return;
    }

    if (empty) empty.hidden = true;
    if (content) {
        content.hidden = false;
        content.classList.remove("is-visible");
        window.requestAnimationFrame(() => content.classList.add("is-visible"));
    }

    renderAnalyticsStats(data);
    renderCharts(data.chart_data);
    console.log("Analytics rendered after analysis:", data.chart_data);
}

function renderResults(data) {
    state.latestAnalysis = data;
    qs("#emptyState").hidden = true;
    qs("#resultsToolbar").hidden = false;
    renderSummary(data);
    renderRecommendations(data.recommendations || []);
    renderAnalytics(data);
    qs("#results").scrollIntoView({ behavior: "smooth", block: "start" });
}

function openJobModal(job) {
    if (!job) return;

    qs("#modalTitle").textContent = job.job_title;
    qs("#modalDescription").textContent = job.job_description;
    qs("#modalMeta").innerHTML = `
        <span>${job.match_percent}% match</span>
        <span>${job.category}</span>
        <span>${job.location}</span>
    `;
    qs("#modalSkills").innerHTML = (job.skills || [])
        .map((skill) => `<span class="skill-chip">${skill}</span>`)
        .join("");
    qs("#modalApplyLink").href = `https://www.linkedin.com/jobs/search/?keywords=${encodeURIComponent(job.job_title)}&location=${encodeURIComponent(job.location)}`;
    qs("#modalSaveJob").dataset.jobTitle = job.job_title;
    qs("#jobModal").hidden = false;
    console.log("Opened job modal:", job);
}

function closeJobModal() {
    qs("#jobModal").hidden = true;
}

function saveJob(jobTitle) {
    const job = state.latestRecommendations.find((item) => item.job_title === jobTitle);
    if (!job) return;

    let savedJobs = [];
    try {
        savedJobs = JSON.parse(localStorage.getItem("jobgenie:savedJobs") || "[]");
    } catch (error) {
        console.warn("Saved jobs storage was reset:", error);
    }
    savedJobs.unshift({ ...job, savedAt: new Date().toISOString() });
    localStorage.setItem("jobgenie:savedJobs", JSON.stringify(savedJobs.slice(0, 20)));
    addMessage(`${job.job_title} has been saved to your workspace.`, "bot");
}

function saveResults() {
    if (!state.latestAnalysis) {
        setStatus("Analyze a resume before saving results.", "error");
        return;
    }
    localStorage.setItem("jobgenie:savedAnalysis", JSON.stringify({
        ...state.latestAnalysis,
        savedAt: new Date().toISOString(),
    }));
    setStatus("Results saved locally in this browser.", "success");
}

function downloadReport() {
    if (!state.latestAnalysis) {
        setStatus("Analyze a resume before downloading a report.", "error");
        return;
    }

    const recommendations = state.latestAnalysis.recommendations || [];
    const reportWindow = window.open("", "_blank", "width=900,height=720");
    if (!reportWindow) {
        setStatus("Please allow popups to generate the report.", "error");
        return;
    }

    reportWindow.document.write(`
        <html>
            <head>
                <title>JobGenie AI Career Report</title>
                <style>
                    body { font-family: Arial, sans-serif; color: #172033; padding: 32px; }
                    h1 { margin-bottom: 4px; }
                    article { border: 1px solid #ddd; border-radius: 8px; padding: 16px; margin: 14px 0; }
                    .score { font-weight: 800; color: #7227ff; }
                </style>
            </head>
            <body>
                <h1>JobGenie AI Career Report</h1>
                <p>Generated ${new Date().toLocaleString()}</p>
                <h2>Resume Skills</h2>
                <p>${(state.latestAnalysis.resume_skills || []).join(", ") || "No skills detected"}</p>
                <h2>Top Recommendations</h2>
                ${recommendations.map((job) => `
                    <article>
                        <h3>${job.job_title} <span class="score">${job.match_percent}%</span></h3>
                        <p>${job.category} - ${job.location}</p>
                        <p>${job.job_description}</p>
                        <strong>Missing skills:</strong> ${(job.missing_skills || []).join(", ") || "No major gaps"}
                    </article>
                `).join("")}
                <script>window.print();<\/script>
            </body>
        </html>
    `);
    reportWindow.document.close();
}

async function handleAnalyze(event) {
    event.preventDefault();
    const file = state.selectedFile || qs("#resumeInput").files[0];
    const validationError = validatePdf(file);

    if (validationError) {
        setStatus(validationError, "error");
        return;
    }

    try {
        setLoading(true);
        setStatus("JobGenie AI is preparing your analysis...");
        const uploadData = await runProcessingStep(0, () => uploadResume(file));
        await runProcessingStep(1);
        await runProcessingStep(2);
        const predictionData = await runProcessingStep(3, () => predictJobs(uploadData.text));
        await runProcessingStep(4);
        finishProcessingFlow();
        renderResults(predictionData);
        localStorage.setItem("jobgenie:lastAnalysis", JSON.stringify(predictionData));
        setStatus("Analysis complete. Recommendations are ready.", "success");
    } catch (error) {
        console.error("Analyze flow failed:", error);
        setStatus(error.message, "error");
        resetProcessingFlow();
    } finally {
        setLoading(false);
    }
}

function getStoredChatHistory() {
    try {
        return JSON.parse(localStorage.getItem(CHAT_HISTORY_KEY) || "[]");
    } catch (error) {
        console.warn("Chat history storage was reset:", error);
        localStorage.removeItem(CHAT_HISTORY_KEY);
        return [];
    }
}

function storeChatMessage(text, sender) {
    const history = getStoredChatHistory();
    history.push({ text, sender, createdAt: new Date().toISOString() });
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(history.slice(-40)));
}

function scrollChatToBottom() {
    const messages = qs("#chatMessages");
    if (!messages) return;
    messages.scrollTop = messages.scrollHeight;
}

function addMessage(text, sender, shouldPersist = true) {
    const messages = qs("#chatMessages");
    if (!messages) return null;

    const row = document.createElement("div");
    row.className = `message-row ${sender}`;

    const avatar = document.createElement("span");
    avatar.className = "message-avatar";
    avatar.textContent = sender === "user" ? "ME" : "AI";

    const message = document.createElement("div");
    message.className = `message ${sender}`;
    message.textContent = text;

    row.append(avatar, message);
    messages.appendChild(row);
    scrollChatToBottom();

    if (shouldPersist) {
        storeChatMessage(text, sender);
    }
    return row;
}

function addTypingIndicator() {
    const messages = qs("#chatMessages");
    if (!messages) return null;

    const row = document.createElement("div");
    row.className = "message-row bot";
    row.innerHTML = `
        <span class="message-avatar">AI</span>
        <div class="message bot"><span class="typing-indicator"><i></i><i></i><i></i></span></div>
    `;
    messages.appendChild(row);
    scrollChatToBottom();
    return row;
}

function loadChatHistory() {
    const messages = qs("#chatMessages");
    if (!messages) return;

    const history = getStoredChatHistory();
    if (!history.length) return;

    messages.innerHTML = "";
    history.forEach((item) => addMessage(item.text, item.sender, false));
    scrollChatToBottom();
}

async function sendChatPrompt(message) {
    const cleanMessage = String(message || "").trim();
    if (!cleanMessage) return;

    const input = qs("#chatInput");
    if (input) input.value = "";

    addMessage(cleanMessage, "user");
    console.log("Sending chatbot message:", cleanMessage);
    const typing = addTypingIndicator();

    try {
        await sleep(950 + Math.round(Math.random() * 450));
        const response = await fetch("/chatbot", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                message: cleanMessage,
                context: state.latestAnalysis || {},
            }),
        });
        const data = await parseJsonResponse(response);
        console.log("/chatbot JSON:", data);
        if (!response.ok) throw new Error(data.error || "Chatbot failed.");
        if (typing) typing.remove();
        addMessage(data.reply, "bot");
    } catch (error) {
        console.error("Chatbot error:", error);
        if (typing) typing.remove();
        addMessage(error.message, "bot");
    }
}

async function handleChat(event) {
    event.preventDefault();
    const input = qs("#chatInput");
    await sendChatPrompt(input ? input.value : "");
}

async function handleHeroSearch() {
    const query = qs("#heroSearch").value.trim();
    if (!query) {
        qs("#upload").scrollIntoView({ behavior: "smooth", block: "start" });
        return;
    }

    try {
        setStatus(`Searching roles and skills for "${query}"...`);
        const results = await searchJobs(query);
        renderSearchResults(results);
        setStatus(`Found ${results.count} matching role(s).`, "success");
    } catch (error) {
        console.error("Search failed:", error);
        setStatus(error.message, "error");
    }
}

function setupSearchSuggestions() {
    const input = qs("#heroSearch");
    const dropdown = qs("#searchSuggestions");
    const panel = qs(".search-panel");
    if (!input || !dropdown || !panel) return;

    const loadSuggestions = debounce(async () => {
        const query = input.value.trim();
        console.log("Search input changed:", query);
        if (query.length < 2) {
            hideSearchSuggestions();
            return;
        }

        try {
            const suggestions = await fetchSearchSuggestions(query);
            renderSearchSuggestions(suggestions);
        } catch (error) {
            console.error("Search suggestions failed:", error);
            hideSearchSuggestions();
        }
    }, 220);

    input.addEventListener("input", loadSuggestions);
    input.addEventListener("focus", () => {
        if (dropdown.children.length && input.value.trim().length >= 2) {
            dropdown.hidden = false;
        }
    });

    dropdown.addEventListener("click", (event) => {
        const item = event.target.closest(".suggestion-item");
        if (!item) return;
        console.log("Search suggestion clicked:", item.dataset.value);
        input.value = item.dataset.value || "";
        hideSearchSuggestions();
        input.focus();
        handleHeroSearch();
    });

    document.addEventListener("click", (event) => {
        if (!panel.contains(event.target)) {
            hideSearchSuggestions();
        }
    });

    input.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            hideSearchSuggestions();
        }
    });
}

function setupNavigation() {
    qsa("[data-scroll-target]").forEach((button) => {
        button.addEventListener("click", () => {
            const target = qs(button.dataset.scrollTarget);
            if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
        });
    });

    const navToggle = qs(".nav-toggle");
    const navLinks = qs(".nav-links");
    if (navToggle && navLinks) {
        navToggle.addEventListener("click", () => {
            console.log("Navigation toggle clicked");
            navLinks.classList.toggle("open");
        });
    }

    qsa(".nav-links a").forEach((link) => {
        link.addEventListener("click", () => navLinks?.classList.remove("open"));
    });

    const searchButton = qs("#heroSearchButton");
    const searchInput = qs("#heroSearch");
    const clearSearchButton = qs("#clearSearchResults");

    searchButton?.addEventListener("click", () => {
        console.log("Hero search button clicked");
        hideSearchSuggestions();
        handleHeroSearch();
    });
    searchInput?.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            event.preventDefault();
            hideSearchSuggestions();
            handleHeroSearch();
        }
    });
    clearSearchButton?.addEventListener("click", () => {
        console.log("Clear search results clicked");
        const results = qs("#searchResults");
        if (results) results.hidden = true;
        if (searchInput) searchInput.value = "";
        hideSearchSuggestions();
    });

    setupSearchSuggestions();
}

function setupUpload() {
    const input = qs("#resumeInput");
    const dropZone = qs("#dropZone");

    input.addEventListener("change", () => {
        const file = input.files[0];
        const validationError = validatePdf(file);
        if (validationError) {
            setStatus(validationError, "error");
            return;
        }
        showFile(file);
    });

    ["dragenter", "dragover"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropZone.classList.add("drag-over");
        });
    });

    ["dragleave", "drop"].forEach((eventName) => {
        dropZone.addEventListener(eventName, (event) => {
            event.preventDefault();
            dropZone.classList.remove("drag-over");
        });
    });

    dropZone.addEventListener("drop", (event) => {
        const file = event.dataTransfer.files[0];
        const validationError = validatePdf(file);
        if (validationError) {
            setStatus(validationError, "error");
            return;
        }
        input.files = event.dataTransfer.files;
        showFile(file);
    });

    qs("#clearFile").addEventListener("click", clearFile);
    qs("#resumeForm").addEventListener("submit", handleAnalyze);
}

function setupResultsActions() {
    qs("#recommendationGrid").addEventListener("click", (event) => {
        const button = event.target.closest(".view-details-button");
        if (!button) return;
        openJobModal(state.latestRecommendations[Number(button.dataset.jobIndex)]);
    });

    qs("#closeJobModal").addEventListener("click", closeJobModal);
    qs("#jobModal").addEventListener("click", (event) => {
        if (event.target.id === "jobModal") closeJobModal();
    });
    qs("#modalSaveJob").addEventListener("click", (event) => {
        saveJob(event.currentTarget.dataset.jobTitle);
    });
    qs("#saveResultsButton").addEventListener("click", saveResults);
    qs("#downloadReportButton").addEventListener("click", downloadReport);
}

function openAuthModal(selector) {
    const modal = qs(selector);
    if (!modal) {
        console.error("Auth modal not found:", selector);
        return;
    }

    modal.hidden = false;
    window.requestAnimationFrame(() => modal.classList.add("active"));
    console.log("Auth modal opened:", selector);

    const firstInput = modal.querySelector("input");
    if (firstInput) firstInput.focus();
}

function closeAuthModal(selector) {
    const modal = qs(selector);
    if (!modal) return;

    modal.classList.remove("active");
    modal.hidden = true;
    console.log("Auth modal closed:", selector);
}

function closeAllAuthModals() {
    closeAuthModal("#signInModal");
    closeAuthModal("#signUpModal");
}

function setAuthStatus(selector, message, type = "") {
    const status = qs(selector);
    if (!status) return;
    status.textContent = message;
    status.className = `auth-status ${type}`.trim();
}

function validateEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function updateAuthUI(user) {
    const guestButtons = qsa(".auth-guest");
    const profile = qs("#authProfile");
    const avatar = qs("#profileAvatar");
    const name = qs("#profileName");

    const isAuthenticated = Boolean(user);
    guestButtons.forEach((button) => {
        button.hidden = isAuthenticated;
    });
    if (profile) profile.hidden = !isAuthenticated;

    if (isAuthenticated) {
        const fullName = user.full_name || user.name || "Account";
        if (avatar) {
            avatar.textContent = user.initials || fullName.split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "JG";
        }
        if (name) name.textContent = fullName.split(/\s+/)[0] || "Account";
        localStorage.setItem("jobgenie:user", JSON.stringify(user));
    } else {
        localStorage.removeItem("jobgenie:user");
    }

    console.log("Auth UI updated:", { authenticated: isAuthenticated, user });
}

async function loadAuthStatus() {
    try {
        const response = await fetch("/auth/status");
        const data = await parseJsonResponse(response);
        console.log("/auth/status JSON:", data);
        updateAuthUI(data.authenticated ? data.user : null);
    } catch (error) {
        console.error("Auth status check failed:", error);
    }
}

async function submitSignUp(event) {
    event.preventDefault();
    console.log("Sign Up form submitted");

    const fullName = qs("#signupFullName")?.value.trim() || "";
    const email = qs("#signupEmail")?.value.trim() || "";
    const password = qs("#signupPassword")?.value || "";
    const confirmPassword = qs("#signupConfirmPassword")?.value || "";

    if (fullName.length < 2) {
        setAuthStatus("#signUpStatus", "Please enter your full name.", "error");
        return;
    }
    if (!validateEmail(email)) {
        setAuthStatus("#signUpStatus", "Please enter a valid email address.", "error");
        return;
    }
    if (password.length < 8) {
        setAuthStatus("#signUpStatus", "Password must be at least 8 characters.", "error");
        return;
    }
    if (password !== confirmPassword) {
        setAuthStatus("#signUpStatus", "Passwords do not match.", "error");
        return;
    }

    setAuthStatus("#signUpStatus", "Creating your account...");
    try {
        const response = await fetch("/signup", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                full_name: fullName,
                email,
                password,
                confirm_password: confirmPassword,
            }),
        });
        const data = await parseJsonResponse(response);
        console.log("/signup JSON:", data);
        if (!response.ok) throw new Error(data.error || "Could not create account.");

        setAuthStatus("#signUpStatus", data.message || "Account created successfully.", "success");
        updateAuthUI(data.user);
        setStatus(`Welcome, ${data.user?.full_name || fullName}. Your workspace is ready.`, "success");
        setTimeout(() => closeAuthModal("#signUpModal"), 650);
    } catch (error) {
        console.error("Signup failed:", error);
        setAuthStatus("#signUpStatus", error.message, "error");
    }
}

async function submitSignIn(event) {
    event.preventDefault();
    console.log("Sign In form submitted");

    const email = qs("#signinEmail")?.value.trim() || "";
    const password = qs("#signinPassword")?.value || "";
    const remember = Boolean(qs("#rememberMe")?.checked);

    if (!validateEmail(email)) {
        setAuthStatus("#signInStatus", "Please enter a valid email address.", "error");
        return;
    }
    if (!password) {
        setAuthStatus("#signInStatus", "Please enter your password.", "error");
        return;
    }

    setAuthStatus("#signInStatus", "Signing you in...");
    try {
        const response = await fetch("/signin", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password, remember }),
        });
        const data = await parseJsonResponse(response);
        console.log("/signin JSON:", data);
        if (!response.ok) throw new Error(data.error || "Could not sign in.");

        setAuthStatus("#signInStatus", data.message || "Signed in successfully.", "success");
        updateAuthUI(data.user);
        setStatus(`Welcome back, ${data.user?.full_name || "there"}.`, "success");
        setTimeout(() => closeAuthModal("#signInModal"), 650);
    } catch (error) {
        console.error("Signin failed:", error);
        setAuthStatus("#signInStatus", error.message, "error");
    }
}

async function logoutUser() {
    console.log("Logout clicked");
    try {
        const response = await fetch("/logout", { method: "POST" });
        const data = await parseJsonResponse(response);
        console.log("/logout JSON:", data);
        if (!response.ok) throw new Error(data.error || "Logout failed.");
        updateAuthUI(null);
        setStatus(data.message || "Logged out successfully.", "success");
    } catch (error) {
        console.error("Logout failed:", error);
        setStatus(error.message, "error");
    }
}

function setupAuth() {
    const signInButton = qs("#signInBtn");
    const signUpButton = qs("#signUpBtn");
    const signInForm = qs("#signInForm");
    const signUpForm = qs("#signUpForm");

    signInButton?.addEventListener("click", () => {
        console.log("Sign In button clicked");
        setAuthStatus("#signInStatus", "");
        openAuthModal("#signInModal");
    });

    signUpButton?.addEventListener("click", () => {
        console.log("Sign Up button clicked");
        setAuthStatus("#signUpStatus", "");
        openAuthModal("#signUpModal");
    });

    qsa("[data-close-auth]").forEach((button) => {
        button.addEventListener("click", () => {
            console.log("Auth close button clicked");
            closeAllAuthModals();
        });
    });

    ["#signInModal", "#signUpModal"].forEach((selector) => {
        const modal = qs(selector);
        modal?.addEventListener("click", (event) => {
            if (event.target === modal) {
                console.log("Auth backdrop clicked:", selector);
                closeAuthModal(selector);
            }
        });
    });

    qsa("[data-toggle-password]").forEach((button) => {
        button.addEventListener("click", () => {
            const input = qs(button.dataset.togglePassword);
            if (!input) return;
            input.type = input.type === "password" ? "text" : "password";
            button.textContent = input.type === "password" ? "Show" : "Hide";
            console.log("Password visibility toggled:", button.dataset.togglePassword);
        });
    });

    qs("#openSignUpFromSignIn")?.addEventListener("click", () => {
        console.log("Switch to Sign Up clicked");
        closeAuthModal("#signInModal");
        openAuthModal("#signUpModal");
    });

    qs("#openSignInFromSignUp")?.addEventListener("click", () => {
        console.log("Switch to Sign In clicked");
        closeAuthModal("#signUpModal");
        openAuthModal("#signInModal");
    });

    qs("#forgotPasswordButton")?.addEventListener("click", () => {
        console.log("Forgot password clicked");
        setAuthStatus("#signInStatus", "Password reset UI is ready. For this local demo, create a new account or sign in with your saved password.", "success");
    });

    signInForm?.addEventListener("submit", submitSignIn);
    signUpForm?.addEventListener("submit", submitSignUp);
    qs("#logoutButton")?.addEventListener("click", logoutUser);

    document.addEventListener("keydown", (event) => {
        if (event.key === "Escape") {
            closeAllAuthModals();
        }
    });

    loadAuthStatus();
}

function setupScrollReveal() {
    const sections = qsa("main > section, .site-footer");
    sections.forEach((section) => section.classList.add("reveal-on-scroll"));

    if (!("IntersectionObserver" in window)) {
        sections.forEach((section) => section.classList.add("is-visible"));
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                entry.target.classList.add("is-visible");
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.12 });

    sections.forEach((section) => observer.observe(section));
}

function animateCounter(element) {
    if (!element || element.dataset.counterAnimated === "true") return;

    const target = Number.parseFloat(element.dataset.countTarget || "0");
    const decimals = Number.parseInt(element.dataset.countDecimals || "0", 10);
    const suffix = element.dataset.countSuffix || "";
    const duration = 1100;
    const startTime = performance.now();

    element.dataset.counterAnimated = "true";

    function tick(now) {
        const progress = Math.min(1, (now - startTime) / duration);
        const eased = 1 - Math.pow(1 - progress, 3);
        const value = target * eased;
        element.textContent = `${value.toFixed(decimals)}${suffix}`;

        if (progress < 1) {
            window.requestAnimationFrame(tick);
        } else {
            element.textContent = `${target.toFixed(decimals)}${suffix}`;
        }
    }

    window.requestAnimationFrame(tick);
}

function setupMetricCounters() {
    const counters = qsa("[data-count-target]");
    if (!counters.length) return;

    if (!("IntersectionObserver" in window)) {
        counters.forEach(animateCounter);
        return;
    }

    const observer = new IntersectionObserver((entries) => {
        entries.forEach((entry) => {
            if (entry.isIntersecting) {
                animateCounter(entry.target);
                observer.unobserve(entry.target);
            }
        });
    }, { threshold: 0.45 });

    counters.forEach((counter) => observer.observe(counter));
}

function setupChatbot() {
    const launcher = qs("#chatbotLauncher");
    const panel = qs("#chatbotPanel");
    const input = qs("#chatInput");

    loadChatHistory();

    launcher?.addEventListener("click", () => {
        console.log("Chatbot launcher clicked");
        if (panel) panel.hidden = false;
        input?.focus();
        scrollChatToBottom();
    });
    qs("#closeChatbot")?.addEventListener("click", () => {
        console.log("Chatbot close clicked");
        if (panel) panel.hidden = true;
    });
    qs("#chatbotForm")?.addEventListener("submit", handleChat);

    qsa(".chat-suggestion, #chatFeaturePanel button").forEach((button) => {
        button.addEventListener("click", () => {
            const prompt = button.dataset.prompt || button.textContent.trim();
            console.log("Chat quick action clicked:", prompt);
            if (panel) panel.hidden = false;
            sendChatPrompt(prompt);
        });
    });
}

document.addEventListener("DOMContentLoaded", () => {
    console.log("JobGenie AI frontend loaded.");
    setupNavigation();
    setupUpload();
    setupChatbot();
    setupResultsActions();
    setupAuth();
    setupScrollReveal();
    setupMetricCounters();
    initAnalyticsState();
});
