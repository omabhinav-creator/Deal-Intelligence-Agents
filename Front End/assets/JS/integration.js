document.addEventListener("DOMContentLoaded", () => {
    const api = window.DealMindAPI;
    const $ = (selector, parent = document) => parent.querySelector(selector);
    const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
    const make = (tag, className, text) => {
        const element = document.createElement(tag);
        if (className) element.className = className;
        if (text !== undefined) element.textContent = text;
        return element;
    };
    const displayValue = (value) => value === null || value === undefined || value === "" ? "Not recorded" : String(value);
    const money = (value) => Number.isFinite(Number(value)) ? new Intl.NumberFormat(undefined, { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(value)) : "Not recorded";
    const errorText = (error) => {
        if (error.kind === "network") return "Network error: the DealMind API is unreachable at the configured address.";
        if (error.kind === "authentication") return error.message;
        if (error.kind === "backend") return `Backend error: ${error.message}`;
        return error.message || "The request could not be completed.";
    };
    function state(container, text, kind = "empty") {
        if (!container) return;
        $$(".api-state", container).forEach((item) => item.remove());
        const message = make("p", `api-state ${kind}`, text);
        message.setAttribute("role", kind === "error" ? "alert" : "status");
        container.append(message);
    }
    function addNav() {
        const routes = { dashboard: "dashboard.html", deals: "deals.html", memory: "dealmemory.html", copilot: "aicopilot.html", learning: "learning.html", settings: "settings.html" };
        $$('[data-page]').forEach((item) => item.addEventListener("click", () => {
            const destination = routes[item.dataset.page];
            if (destination) window.location.assign(destination);
        }));
    }
    async function loadDeals() {
        const result = await api.request("/api/deals");
        return Array.isArray(result) ? result : [];
    }
    function selectDeal(deal) {
        api.setSelectedDeal(deal);
        return deal;
    }
    function currentDeal(deals) {
        const selected = api.getSelectedDeal();
        return selectDeal(deals.find((deal) => deal.id === selected?.id) || deals[0] || null);
    }
    function dateLabel(value) {
        if (!value) return "Date not recorded";
        const date = new Date(value);
        return Number.isNaN(date.valueOf()) ? "Date not recorded" : date.toLocaleString();
    }
    function initials(value) {
        return (value || "?").trim().split(/\s+/).slice(0, 2).map((part) => part[0]).join("").toUpperCase() || "?";
    }
    function statusClass(value) {
        return (value || "unknown").toLowerCase().replace(/[^a-z0-9_-]/g, "-");
    }
    function renderDealRow(deal, compact = false) {
        const row = make("div", compact ? "deal" : "deal-row");
        if (!compact) {
            row.dataset.stage = (deal.stage || "").toLowerCase();
            row.dataset.risk = (deal.risk_level || "").toLowerCase();
            row.dataset.search = [deal.company_name, deal.stage, deal.status, deal.risk_level].join(" ").toLowerCase();
        }
        const company = make("div", compact ? "deal-name" : "deal-company");
        company.append(make("div", "company-logo", initials(deal.company_name)));
        const companyInfo = make("div", compact ? "company-info" : "");
        companyInfo.append(make("strong", "", deal.company_name), make("span", "", deal.status || "Deal"));
        company.append(companyInfo);
        row.append(company);

        if (compact) {
            row.append(make("div", "deal-value", money(deal.value)));
            row.append(make("div", "stage", displayValue(deal.stage)));
            const risk = make("div", `risk risk-${statusClass(deal.risk_level)}`);
            risk.append(make("span", "risk-dot"), document.createTextNode(` ${displayValue(deal.risk_level)}`));
            row.append(risk);
            row.tabIndex = 0;
            row.addEventListener("click", () => { selectDeal(deal); window.location.assign("dealmemory.html"); });
            return row;
        }

        row.append(make("div", "value", money(deal.value)));
        const stage = make("div");
        stage.append(make("span", `stage-badge ${statusClass(deal.stage)}`, displayValue(deal.stage)));
        row.append(stage);
        const risk = make("div");
        const riskLabel = make("span", `risk-badge ${statusClass(deal.risk_level)}`, displayValue(deal.risk_level));
        riskLabel.prepend(make("i"));
        risk.append(riskLabel);
        row.append(risk, make("div", "competitor", "Not recorded"), make("div", "activity", "Not recorded"));
        const button = make("button", "view-button", "View");
        button.type = "button";
        button.addEventListener("click", () => openDeal(deal));
        row.append(button);
        return row;
    }

    async function renderDashboard() {
        const sections = $$(".content-grid .section-card");
        const metricCards = $$(".metric-card");
        const dealsHost = sections[0];
        const memoriesHost = sections[1];
        const aiCard = $(".ai-card");
        if (dealsHost) $$(".deal", dealsHost).forEach((item) => item.remove());
        if (memoriesHost) $$(".memory", memoriesHost).forEach((item) => item.remove());
        try {
            const [deals, metrics] = await Promise.all([loadDeals(), api.request("/api/dashboard/metrics")]);
            const values = [metrics.open_deal_count, metrics.at_risk_count, metrics.interaction_count];
            const labels = ["Open Deals", "At-Risk Deals", "Recorded Interactions"];
            metricCards.forEach((card, index) => {
                const label = $(".metric-label", card);
                const value = $(".metric-value", card);
                const sub = $(".metric-sub", card);
                if (label && labels[index]) label.textContent = labels[index];
                if (value && values[index] !== undefined) value.textContent = String(values[index]);
                if (sub) sub.textContent = values[index] ? "From your saved DealMind records" : "No records yet";
            });
            if (dealsHost) {
                if (deals.length) deals.slice(0, 4).forEach((deal) => dealsHost.append(renderDealRow(deal, true)));
                else state(dealsHost, "No deals yet. Your saved deals will appear here.");
            }
            if (memoriesHost && deals.length) {
                const selected = currentDeal(deals);
                const result = await api.request(`/api/deals/${encodeURIComponent(selected.id)}/memories`);
                const memories = result.memories || [];
                if (memories.length) memories.slice(0, 4).forEach((memory) => {
                    const item = make("div", "memory");
                    item.append(make("div", "memory-icon", "◈"));
                    const content = make("div", "memory-content");
                    content.append(make("div", "memory-title", selected.company_name), make("div", "memory-description", memory.content), make("div", "memory-time", dateLabel(memory.interaction_date)));
                    item.append(content);
                    memoriesHost.append(item);
                });
                else state(memoriesHost, "No Hindsight memories have been recorded for this deal.");
            } else if (memoriesHost) state(memoriesHost, "No deal memory is available yet.");
            if (aiCard) {
                const heading = $("h3", aiCard);
                const description = $("p", aiCard);
                if (heading) heading.textContent = deals.length ? `${deals.length} saved deal${deals.length === 1 ? "" : "s"} in your workspace.` : "Deal intelligence starts with recorded deal evidence.";
                if (description) description.textContent = deals.length ? "Recommendations and risk signals appear when Hindsight has deal-specific evidence." : "Add deal and interaction records to build Hindsight memory and evidence-backed guidance.";
            }
            const briefButton = $("#briefButton");
            if (briefButton) briefButton.onclick = async () => {
                const deal = currentDeal(deals);
                if (!deal) { state(aiCard, "No deal is available to brief yet."); return; }
                briefButton.disabled = true;
                state(aiCard, "Generating a brief from this deal's Hindsight evidence…", "loading");
                try { state(aiCard, JSON.stringify(await api.request(`/api/deals/${encodeURIComponent(deal.id)}/brief`), null, 2)); }
                catch (error) { state(aiCard, errorText(error), "error"); }
                finally { briefButton.disabled = false; }
            };
        } catch (error) {
            state(dealsHost, errorText(error), "error");
            state(memoriesHost, errorText(error), "error");
        }
    }

    function openDeal(deal) {
        selectDeal(deal);
        const modal = $("#dealModal");
        if (!modal) return;
        $("#modalDealName").textContent = deal.company_name;
        $("#modalDealDescription").textContent = `${deal.stage} · ${deal.status}`;
        $("#modalValue").textContent = money(deal.value);
        $("#modalStage").textContent = displayValue(deal.stage);
        $("#modalRisk").textContent = displayValue(deal.risk_level);
        $("#modalCompetitor").textContent = "Not recorded";
        $("#modalMemory").textContent = "Loading deal-scoped Hindsight memory…";
        modal.classList.add("show");
        api.request(`/api/deals/${encodeURIComponent(deal.id)}/memories`).then((result) => {
            $("#modalMemory").textContent = result.memories?.[0]?.content || "No Hindsight memory has been recorded for this deal.";
        }).catch((error) => { $("#modalMemory").textContent = errorText(error); });
    }

    async function renderDeals() {
        const table = $(".deal-table");
        const empty = $("#emptyState");
        const search = $("#dealSearch");
        if (!table) return;
        $$(".deal-row", table).forEach((row) => row.remove());
        const setFilter = () => {
            const query = (search?.value || "").trim().toLowerCase();
            const filter = $(".filter-button.active")?.dataset.filter || "all";
            let visible = 0;
            $$(".deal-row", table).forEach((row) => {
                const matchesFilter = filter === "all" || (filter === "risk" ? ["high", "medium"].includes(row.dataset.risk) : row.dataset.stage === filter);
                const show = matchesFilter && row.dataset.search.includes(query);
                row.hidden = !show;
                if (show) visible += 1;
            });
            if (empty) {
                empty.classList.toggle("visible", visible === 0);
                const title = $("h3", empty);
                const detail = $("p", empty);
                if (title) title.textContent = query || filter !== "all" ? "No matching deals" : "No deals yet";
                if (detail) detail.textContent = query || filter !== "all" ? "Try another search or filter." : "Saved deals will appear here when they are added.";
            }
        };
        try {
            const deals = await loadDeals();
            const toolbar = $(".deals-toolbar");
            if (toolbar && !$("#newDealForm")) {
                const toggle = make("button", "primary-btn", "Add deal");
                toggle.type = "button";
                const form = make("form", "deal-create-form"); form.id = "newDealForm"; form.hidden = true;
                const company = document.createElement("input"); company.name = "company_name"; company.required = true; company.maxLength = 160; company.placeholder = "Company name";
                const value = document.createElement("input"); value.name = "value"; value.type = "number"; value.min = "0"; value.step = "0.01"; value.required = true; value.placeholder = "Deal value";
                const stage = document.createElement("select"); stage.name = "stage";
                [["discovery", "Discovery"], ["qualification", "Qualification"], ["proposal", "Proposal"], ["negotiation", "Negotiation"]].forEach(([id, label]) => { const option = document.createElement("option"); option.value = id; option.textContent = label; stage.append(option); });
                const risk = document.createElement("select"); risk.name = "risk_level";
                [["low", "Low risk"], ["medium", "Medium risk"], ["high", "High risk"]].forEach(([id, label]) => { const option = document.createElement("option"); option.value = id; option.textContent = label; risk.append(option); });
                const statusField = document.createElement("input"); statusField.name = "status"; statusField.value = "active"; statusField.required = true; statusField.maxLength = 40; statusField.setAttribute("aria-label", "Deal status");
                const submit = make("button", "primary-btn", "Save deal"); submit.type = "submit";
                const feedback = make("p", "api-state"); feedback.setAttribute("role", "status");
                [company, value, stage, risk, statusField, submit, feedback].forEach((control) => form.append(control));
                toggle.addEventListener("click", () => { form.hidden = !form.hidden; company.focus(); });
                form.addEventListener("submit", async (event) => {
                    event.preventDefault(); submit.disabled = true; feedback.textContent = "Saving deal…";
                    try {
                        await api.request("/api/deals", { method: "POST", body: JSON.stringify({ company_name: company.value.trim(), value: Number(value.value), stage: stage.value, risk_level: risk.value, status: statusField.value.trim() }) });
                        window.location.reload();
                    } catch (error) { feedback.textContent = errorText(error); submit.disabled = false; }
                });
                toolbar.append(toggle, form);
            }
            const summaryCards = $$(".summary-card");
            const riskCount = deals.filter((deal) => ["high", "medium"].includes((deal.risk_level || "").toLowerCase()) && !["won", "lost", "stalled"].includes((deal.status || "").toLowerCase())).length;
            const pipelineValue = deals.reduce((total, deal) => total + (Number(deal.value) || 0), 0);
            const insight = $(".ai-insight");
            const insightTitle = $("h3", insight);
            const insightText = $("p", insight);
            if (insightTitle) insightTitle.textContent = riskCount ? `${riskCount} saved deal${riskCount === 1 ? "" : "s"} ${riskCount === 1 ? "has" : "have"} elevated risk.` : "No saved deal has elevated risk.";
            if (insightText) insightText.textContent = "Risk counts use the stored deal risk field. Memory-based analysis requires retained evidence for the selected deal.";
            [money(pipelineValue), String(deals.length), String(riskCount), "—"].forEach((value, index) => {
                const card = summaryCards[index];
                const metric = $("strong", card);
                const label = $("span", card);
                if (metric) metric.textContent = value;
                if (label && index === 3) label.textContent = "Close dates not tracked";
            });
            deals.forEach((deal) => table.append(renderDealRow(deal)));
            search?.addEventListener("input", setFilter);
            $$(".filter-button").forEach((button) => button.addEventListener("click", () => {
                $$(".filter-button").forEach((item) => item.classList.toggle("active", item === button));
                setFilter();
            }));
            $("#analyzeButton")?.addEventListener("click", () => {
                const insight = $(".ai-content");
                state(insight, deals.length ? "Risk analysis requires recorded memory for each selected deal." : "No deals are available to analyze yet.");
            });
            setFilter();
        } catch (error) { state(empty, errorText(error), "error"); empty?.classList.add("visible"); }

        $("#modalClose")?.addEventListener("click", () => $("#dealModal")?.classList.remove("show"));
        $("#dealModal")?.addEventListener("click", (event) => { if (event.target === $("#dealModal")) $("#dealModal").classList.remove("show"); });
        const modalContent = $(".deal-modal");
        if (modalContent && !$(".deal-actions", modalContent)) {
            const actions = make("section", "deal-actions");
            const interactionLabel = make("label", "", "Record sales interaction");
            const notes = make("textarea");
            notes.rows = 3;
            notes.placeholder = "Add customer notes or a meeting summary";
            const saveInteraction = make("button", "modal-primary", "Retain interaction");
            saveInteraction.type = "button";
            const outcome = document.createElement("select");
            outcome.setAttribute("aria-label", "Record deal outcome");
            [["", "Record outcome"], ["won", "Won"], ["lost", "Lost"], ["stalled", "Stalled"]].forEach(([value, label]) => {
                const option = document.createElement("option"); option.value = value; option.textContent = label; outcome.append(option);
            });
            const saveOutcome = make("button", "modal-primary", "Save outcome and learn");
            saveOutcome.type = "button";
            const feedback = make("p", "api-state");
            feedback.setAttribute("role", "status");
            interactionLabel.append(notes);
            actions.append(interactionLabel, saveInteraction, outcome, saveOutcome, feedback);
            const primary = $(".modal-primary", modalContent);
            primary?.addEventListener("click", () => window.location.assign("aicopilot.html"));
            primary?.before(actions);
            saveInteraction.addEventListener("click", async () => {
                const deal = api.getSelectedDeal();
                if (!deal || !notes.value.trim()) { feedback.textContent = "Enter an interaction before retaining it."; return; }
                saveInteraction.disabled = true; feedback.textContent = "Extracting structured deal intelligence and retaining memory…";
                try {
                    const result = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/interactions`, { method: "POST", body: JSON.stringify({ notes: notes.value.trim(), interaction_date: new Date().toISOString(), source: "DealMind web app", company: deal.company_name }) });
                    feedback.textContent = `Interaction retained. ${result.retained_memory_count ?? 0} memory record(s) added.`;
                    notes.value = "";
                } catch (error) { feedback.textContent = errorText(error); }
                finally { saveInteraction.disabled = false; }
            });
            saveOutcome.addEventListener("click", async () => {
                const deal = api.getSelectedDeal();
                if (!deal || !outcome.value) { feedback.textContent = "Choose an outcome first."; return; }
                saveOutcome.disabled = true; feedback.textContent = "Recording outcome and generating evidence-backed learning…";
                try {
                    const result = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/outcome`, { method: "POST", body: JSON.stringify({ outcome: outcome.value, company: deal.company_name, outcome_date: new Date().toISOString() }) });
                    feedback.textContent = result.insufficient_evidence ? `Outcome saved. ${result.message || "Not enough historical data yet."}` : `Outcome saved. ${result.retained_memories?.length || 0} outcome/lesson memories retained.`;
                } catch (error) { feedback.textContent = errorText(error); }
                finally { saveOutcome.disabled = false; }
            });
        }
    }

    function renderMemory(memory) {
        const item = make("article", "timeline-item");
        item.append(make("div", "timeline-dot purple-dot"));
        const content = make("div", "timeline-content");
        const top = make("div", "timeline-top");
        top.append(make("span", "day", dateLabel(memory.interaction_date)), make("span", `memory-type ${statusClass(memory.memory_type)}`, displayValue(memory.memory_type).replaceAll("_", " ")));
        content.append(top, make("h4", "", memory.stakeholder_name || memory.interaction_source || "Deal memory"), make("p", "", memory.content));
        const tags = make("div", "memory-tags");
        if (memory.stakeholder_name) tags.append(make("span", "", `Stakeholder: ${memory.stakeholder_name}`));
        if (memory.interaction_source) tags.append(make("span", "", `Source: ${memory.interaction_source}`));
        tags.append(make("span", "", `Memory ID: ${memory.memory_id}`));
        content.append(tags); item.append(content); return item;
    }

    async function renderMemoryPage() {
        const timeline = $(".timeline");
        if (!timeline) return;
        timeline.replaceChildren();
        const memoryLayout = $(".memory-layout");
        if (memoryLayout && !$(".memory-pipeline", memoryLayout)) {
            const pipeline = make("ol", "memory-pipeline");
            ["Retain interaction", "Recall deal memory", "Personalized intelligence", "Record outcome", "Learn from evidence", "Improve future guidance"].forEach((label, index) => {
                const item = make("li", "", label);
                item.dataset.step = String(index + 1);
                pipeline.append(item);
            });
            memoryLayout.prepend(pipeline);
        }
        try {
            const deals = await loadDeals();
            const deal = currentDeal(deals);
            if (!deal) { state(timeline, "No deal is selected. Add a saved deal to begin building Hindsight memory."); return; }
            const data = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/memories`);
            const title = $(".deal-header-card h2");
            const meta = $(".deal-header-card p");
            const value = $(".deal-value strong");
            if (title) title.textContent = deal.company_name;
            if (meta) meta.textContent = `${deal.stage} · ${deal.status} · ${deal.risk_level} risk`;
            if (value) value.textContent = money(deal.value);
            const memories = data.memories || [];
            if (!memories.length) state(timeline, "No Hindsight memories have been retained for this deal yet.");
            memories.forEach((memory) => timeline.append(renderMemory(memory)));
            const counts = {
                interaction: memories.length,
                objection: memories.filter((memory) => /objection|concern|risk/.test(memory.memory_type || "")).length,
                stakeholder: memories.filter((memory) => /stakeholder/.test(memory.memory_type || "")).length,
                competitor: memories.filter((memory) => /competitor/.test(memory.memory_type || "")).length,
            };
            $$(".memory-stats .stat-card strong").forEach((node, index) => { node.textContent = String(Object.values(counts)[index] || 0); });
            $$(".category-btn").forEach((button) => {
                const key = button.dataset.category;
                const types = { objections: /objection|concern|risk/, stakeholders: /stakeholder/, competitors: /competitor/, pricing: /pricing/ };
                const count = memories.filter((memory) => types[key]?.test(memory.memory_type || "")).length;
                const number = $("strong", button); if (number) number.textContent = String(count);
                button.onclick = () => {
                    const filters = { objections: /objection|concern|risk/, stakeholders: /stakeholder/, competitors: /competitor/, pricing: /pricing/ };
                    $$(".timeline-item", timeline).forEach((item) => {
                        const type = $(".memory-type", item)?.textContent.toLowerCase() || "";
                        item.hidden = !filters[key]?.test(type);
                    });
                };
            });
            $("#filterBtn")?.addEventListener("click", () => $$(".timeline-item", timeline).forEach((item) => { item.hidden = false; }));
            $(".insight-card p")?.replaceChildren(document.createTextNode(memories.length ? `${memories.length} deal-scoped memories recalled from Hindsight.` : "No deal-specific evidence has been recalled yet."));
            $$(".insight-point").forEach((item) => item.remove());
            const briefButton = $("#briefBtn");
            if (briefButton) briefButton.onclick = async () => {
                const card = $(".insight-card"); state(card, "Generating a brief from deal-scoped Hindsight evidence…", "loading");
                try { const brief = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/brief`); state(card, JSON.stringify(brief, null, 2)); }
                catch (error) { state(card, errorText(error), "error"); }
            };
            $$(".key-item strong").forEach((node) => { node.textContent = "Not recorded in deal memory"; });
        } catch (error) { state(timeline, errorText(error), "error"); }
    }

    function renderChatMessage(text, type = "ai") {
        const area = $("#chatArea");
        const item = make("div", `message ${type === "ai" ? "ai-message" : "user-message"}`);
        if (type === "ai") item.append(make("div", "message-avatar", "H"));
        const content = make("div", "message-content");
        content.append(make("span", "message-name", type === "ai" ? "DealMind · evidence" : "You"), make("pre", "", text));
        item.append(content); area?.append(item); if (area) area.scrollTop = area.scrollHeight;
    }
    async function renderCopilot() {
        const area = $("#chatArea");
        if (!area) return;
        area.replaceChildren();
        const selectorHost = $(".deal-selector-card");
        const select = document.createElement("select");
        select.setAttribute("aria-label", "Select a deal");
        const input = $("#chatInput");
        const send = $("#sendBtn");
        let deals = [];
        let deal = null;
        try {
            deals = await loadDeals();
            deal = currentDeal(deals);
            deals.forEach((item) => { const option = document.createElement("option"); option.value = item.id; option.textContent = item.company_name; option.selected = item.id === deal?.id; select.append(option); });
            if (selectorHost) {
                $("#changeDealBtn")?.replaceWith(select);
                if (!$("#changeDealBtn")) selectorHost.append(select);
            }
            const title = $(".deal-selector-card h2");
            const setDeal = (chosen) => {
                deal = selectDeal(chosen);
                if (title) title.textContent = deal.company_name;
                const heading = $(".chat-header p"); if (heading) heading.textContent = `Evidence and intelligence for ${deal.company_name}`;
                $$(".deal-meta span", selectorHost).forEach((item, index) => { item.textContent = [money(deal.value), deal.stage, `${deal.risk_level} risk`][index] || ""; });
            };
            if (deal) setDeal(deal);
            select.addEventListener("change", () => setDeal(deals.find((item) => item.id === select.value)));
            if (!deal) { state(area, "No deal is available. Add a deal before asking DealMind for intelligence."); return; }
            renderChatMessage("Deal-specific Hindsight evidence is available to query. Briefs, changes, recommendations, and explanations use the selected deal only.");
            const promptPanel = make("div", "quick-prompts");
            ["Give me a deal brief", "What changed?", "What should I do next?", "What risks are in memory?"].forEach((prompt) => {
                const button = make("button", "prompt-btn", prompt); button.type = "button";
                button.addEventListener("click", () => { if (input) input.value = prompt; send?.click(); });
                promptPanel.append(button);
            });
            area.append(promptPanel);
            const whyCard = $(".why-card");
            if (whyCard) {
                $$("p, .reason", whyCard).forEach((item) => item.remove());
                const whyButton = make("button", "text-action", "Explain recommendation with evidence");
                whyButton.id = "whyActionBtn"; whyButton.type = "button"; whyCard.append(whyButton);
            }
            const sidebar = $(".copilot-sidebar");
            if (sidebar && !$("#similarActionBtn")) {
                const similarButton = make("button", "text-action", "Compare similar historical deals");
                similarButton.id = "similarActionBtn"; similarButton.type = "button"; sidebar.append(similarButton);
            }
            const contextGrid = $(".context-grid");
            if (contextGrid) {
                contextGrid.replaceChildren();
                const recalled = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/memories`);
                const categories = [
                    ["Stakeholder", /stakeholder/], ["Competitor", /competitor/],
                    ["Risk or objection", /risk|objection|concern/], ["Requirements and actions", /requirement|commitment|request|sales_action/],
                ];
                categories.forEach(([label, pattern]) => {
                    const memory = recalled.memories?.find((item) => pattern.test(item.memory_type || ""));
                    const card = make("div", "context-card");
                    const detail = make("div"); detail.append(make("span", "", label), make("strong", "", memory?.content || "Not recorded"), make("small", "", memory ? `Memory ${memory.memory_id}` : "No supporting evidence"));
                    card.append(detail); contextGrid.append(card);
                });
            }
        } catch (error) { state(area, errorText(error), "error"); return; }

        const requestAnswer = async (question) => {
            if (!deal) { renderChatMessage("Select a deal before requesting intelligence."); return; }
            const q = question.toLowerCase();
            let path = "";
            let method = "GET";
            let body;
            if (q.includes("brief") || q.includes("summary")) path = `/api/deals/${encodeURIComponent(deal.id)}/brief`;
            else if (q.includes("change")) path = `/api/deals/${encodeURIComponent(deal.id)}/changes`;
            else if (q.includes("similar")) path = `/api/deals/${encodeURIComponent(deal.id)}/similar`;
            else if (q.includes("why")) {
                const recommendations = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/recommendations`);
                const action = recommendations.recommendations?.[0]?.action;
                if (!action) { renderChatMessage(JSON.stringify(recommendations, null, 2)); return; }
                path = `/api/deals/${encodeURIComponent(deal.id)}/why`; method = "POST"; body = JSON.stringify({ action });
            } else if (q.includes("next") || q.includes("action") || q.includes("recommend")) path = `/api/deals/${encodeURIComponent(deal.id)}/recommendations`;
            else {
                const data = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/memories`);
                const terms = q.split(/\W+/).filter((term) => term.length > 2);
                const matches = (data.memories || []).filter((memory) => terms.some((term) => memory.content.toLowerCase().includes(term)));
                renderChatMessage(JSON.stringify({ deal_id: deal.id, memories: matches, empty: !matches.length }, null, 2)); return;
            }
            const result = await api.request(path, { method, body });
            renderChatMessage(JSON.stringify(result, null, 2));
        };
        const sendQuestion = async () => {
            const question = input?.value.trim(); if (!question) return;
            renderChatMessage(question, "user"); input.value = ""; send.disabled = true;
            const loading = make("p", "api-state loading", "Loading deal evidence and intelligence…"); area.append(loading);
            try { await requestAnswer(question); }
            catch (error) { renderChatMessage(errorText(error)); }
            finally { loading.remove(); send.disabled = false; input?.focus(); }
        };
        send?.addEventListener("click", sendQuestion);
        input?.addEventListener("keydown", (event) => { if (event.key === "Enter") sendQuestion(); });
        $$(".prompt-btn").forEach((button) => { button.onclick = () => { if (input) input.value = button.dataset.prompt || button.textContent; sendQuestion(); }; });
        const actions = [["#generateBriefBtn", "Give me a deal brief"], ["#changedBtn", "What changed?"], ["#nextActionBtn", "What should I do next?"], ["#whyActionBtn", "Why this recommendation?"], ["#similarActionBtn", "Find similar deals"]];
        actions.forEach(([selector, question]) => { const button = $(selector); if (button) button.onclick = () => { if (input) input.value = question; sendQuestion(); }; });
        const interactionHost = $(".context-section");
        if (interactionHost && !$("#copilotInteractionForm")) {
            const form = make("form", "copilot-interaction-form"); form.id = "copilotInteractionForm";
            const notes = make("textarea"); notes.required = true; notes.placeholder = "Record a sales interaction for the selected deal";
            const submit = make("button", "primary-btn", "Extract and retain interaction"); submit.type = "submit";
            const result = make("p", "api-state"); result.setAttribute("role", "status"); form.append(notes, submit, result); interactionHost.prepend(form);
            form.addEventListener("submit", async (event) => {
                event.preventDefault(); submit.disabled = true; result.textContent = "Groq extraction and Hindsight retention in progress…";
                try { const retained = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/interactions`, { method: "POST", body: JSON.stringify({ notes: notes.value.trim(), interaction_date: new Date().toISOString(), source: "DealMind web app", company: deal.company_name }) }); result.textContent = `Retained ${retained.retained_memory_count ?? 0} memory record(s).`; notes.value = ""; }
                catch (error) { result.textContent = errorText(error); }
                finally { submit.disabled = false; }
            });
        }
    }

    async function renderLearning() {
        const patternList = $(".pattern-list");
        const similarList = $(".similar-list");
        const autopsyGrid = $(".autopsy-grid");
        const lessonsGrid = $(".lessons-grid");
        if (!patternList) return;
        patternList.replaceChildren(); similarList?.replaceChildren(); autopsyGrid?.replaceChildren();
        lessonsGrid?.replaceChildren();
        try {
            const data = await api.request("/api/learning");
            const patterns = data.patterns?.patterns || [];
            const history = data.history || [];
            if (patterns.length) patterns.forEach((pattern, index) => {
                const item = make("article", "pattern-item");
                item.append(make("div", "pattern-number", String(index + 1).padStart(2, "0")));
                const info = make("div", "pattern-info");
                info.append(make("h4", "", pattern.description), make("p", "", pattern.interpretation || "Observed association; this does not establish causality."));
                info.append(make("div", "pattern-meta", `${pattern.supporting_deal_ids?.length || 0} supporting deal(s) · ${pattern.evidence?.length || 0} evidence item(s)`));
                item.append(info); patternList.append(item);
            });
            else state(patternList, "Not enough historical data yet.");
            const lessonMemories = history.filter((item) => item.memory_type === "lesson_learned");
            const outcomeMemories = history.filter((item) => item.memory_type === "deal_outcome");
            const statCards = $$(".learning-stats .stat-card");
            [patterns.length, 0, lessonMemories.length, new Set(history.map((item) => item.deal_id)).size].forEach((count, index) => { const value = $("strong", statCards[index]); if (value) value.textContent = String(count); });
            const lessonsSection = $(".lessons-section");
            const lessonsCaption = $(".lessons-section .section-header p");
            if (lessonsCaption) lessonsCaption.textContent = "Retained outcome lessons with their source deal and Hindsight memory.";
            if (lessonsGrid && lessonMemories.length) lessonMemories.forEach((item) => {
                const lesson = make("article", "lesson-card");
                const detail = make("div");
                detail.append(make("span", "", `Deal ${item.deal_id}`), make("h4", "", item.content), make("p", "", `Memory ${item.memory_id} · ${dateLabel(item.interaction_date)}`));
                lesson.append(detail); lessonsGrid.append(lesson);
            });
            else if (lessonsGrid) state(lessonsGrid, "Not enough historical data yet.");
            const deals = await loadDeals(); const deal = currentDeal(deals);
            const similarCaption = $(".similar-card .section-header p");
            if (similarCaption) similarCaption.textContent = deal ? `Historical matches for ${deal.company_name}, based on Hindsight evidence.` : "Not enough historical data yet.";
            const renderSimilar = async () => {
                if (!deal) { state(similarList, "Select a deal to compare against evidence-backed historical deals."); return; }
                state(similarList, "Comparing recalled Hindsight evidence…", "loading");
                try {
                    const result = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/similar`);
                    similarList.replaceChildren();
                    if (statCards[1]) $("strong", statCards[1]).textContent = String(result.similar_deals?.length || 0);
                    if (!result.similar_deals?.length) { state(similarList, "Not enough historical data yet."); return; }
                    result.similar_deals.forEach((match) => { const item = make("article", "similar-deal"); item.append(make("div", "similar-info", `${match.deal_id}: ${match.similarity_explanation}`), make("small", "", `${match.evidence?.length || 0} supporting historical evidence item(s)`)); similarList.append(item); });
                } catch (error) { state(similarList, errorText(error), "error"); }
            };
            if (similarList) await renderSimilar();
            $("#similarBtn")?.addEventListener("click", renderSimilar);
            const outcomes = new Map();
            outcomeMemories.forEach((item) => { if (item.outcome && !outcomes.has(item.deal_id)) outcomes.set(item.deal_id, item); });
            if (autopsyGrid && outcomes.size) outcomes.forEach((item) => {
                const card = make("article", "autopsy-card");
                card.append(make("h4", "", item.deal_id), make("span", `outcome ${statusClass(item.outcome)}`, item.outcome), make("p", "", item.content));
                const button = make("button", "autopsy-btn", "View evidence-backed autopsy"); button.type = "button";
                const result = make("pre", "api-state");
                button.addEventListener("click", async () => {
                    button.disabled = true; result.textContent = "Analyzing deal history…";
                    try { const autopsy = await api.request(`/api/deals/${encodeURIComponent(item.deal_id)}/autopsy`, { method: "POST", body: JSON.stringify({ outcome: item.outcome }) }); result.textContent = JSON.stringify(autopsy, null, 2); }
                    catch (error) { result.textContent = errorText(error); }
                    finally { button.disabled = false; }
                });
                card.append(button, result); autopsyGrid.append(card);
            });
            else if (autopsyGrid) state(autopsyGrid, "Not enough historical data yet.");
            $("#analyzeBtn")?.addEventListener("click", async (event) => { const button = event.currentTarget; button.disabled = true; try { await renderLearning(); } catch (error) { state(patternList, errorText(error), "error"); } finally { button.disabled = false; } });
            $("#patternsBtn")?.addEventListener("click", () => { patternList.scrollIntoView({ behavior: "smooth" }); });
            $("#autopsyBtn")?.addEventListener("click", () => { autopsyGrid?.scrollIntoView({ behavior: "smooth" }); });
        } catch (error) { state(patternList, errorText(error), "error"); state(similarList, errorText(error), "error"); state(autopsyGrid, errorText(error), "error"); state(lessonsGrid, errorText(error), "error"); }
    }

    addNav();
    const path = window.location.pathname.toLowerCase();
    if (path.endsWith("/dashboard.html")) renderDashboard();
    else if (path.endsWith("/deals.html")) renderDeals();
    else if (path.endsWith("/dealmemory.html")) renderMemoryPage();
    else if (path.endsWith("/aicopilot.html")) renderCopilot();
    else if (path.endsWith("/learning.html")) renderLearning();
});