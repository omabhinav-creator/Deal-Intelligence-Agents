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
        if (error.kind === "authentication") return "Please sign in again to access DealMind data.";
        if (error.status === 429 && error.endpoint?.endsWith("/autopsy")) return `Deal Autopsy is temporarily unavailable because the AI provider rate limit has been reached.${error.retryAfter ? ` Retry after: ${error.retryAfter}.` : " Please try again later."}`;
        if (error.kind === "backend" && error.endpoint?.endsWith("/memories")) return "Hindsight is temporarily unavailable. Please try again shortly.";
        if (error.kind === "backend") return error.message || "Deal Intelligence is temporarily unavailable. Please try again shortly.";
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
        const requestedId = new URLSearchParams(window.location.search).get("deal_id") || api.getSelectedDeal()?.id;
        const deal = requestedId ? deals.find((item) => item.id === requestedId) || null : null;
        if (deal) selectDeal(deal);
        return deal;
    }
    function dateLabel(value) {
        if (!value) return "Date not recorded";
        const date = new Date(value);
        return Number.isNaN(date.valueOf()) ? "Date not recorded" : date.toLocaleString();
    }
    function renderResult(container, value, heading = "") {
        if (!container) return;
        container.querySelectorAll(".api-result").forEach((item) => item.remove());
        container.querySelectorAll(":scope > .api-state").forEach((item) => item.remove());
        const result = make("section", "api-result");
        if (heading) result.append(make("h3", "", heading));
        const renderObject = (host, object, title = "") => {
            const group = title ? make("section", "api-result__group") : host;
            if (title) group.append(make("h4", "", title.replaceAll("_", " ")));
            Object.entries(object).forEach(([key, item]) => renderValue(group, item, key));
            if (title) host.append(group);
        };
        const renderValue = (host, data, key = "") => {
            if (data === null || data === undefined || data === "") return;
            if (/memory_id|evidence_ids/i.test(key)) {
                (Array.isArray(data) ? data : [data]).filter(Boolean).forEach((id) => {
                    const details = make("details", "api-result__ids");
                    details.append(make("summary", "", "View memory ID"), make("code", "", String(id)));
                    host.append(details);
                });
                return;
            }
            if (/_id$/i.test(key) || key === "id") {
                const details = make("details", "api-result__ids");
                details.append(make("summary", "", "View source ID"), make("code", "", String(data)));
                host.append(details);
                return;
            }
            if (Array.isArray(data)) {
                if (!data.length) return;
                const group = make("section", "api-result__group");
                if (key) group.append(make("h4", "", key.replaceAll("_", " ")));
                data.forEach((entry) => {
                    const card = make("article", "api-result__item");
                    if (typeof entry === "object" && entry !== null) renderObject(card, entry);
                    else card.append(make("p", "", String(entry)));
                    group.append(card);
                });
                host.append(group); return;
            }
            if (typeof data === "object") { renderObject(host, data, key); return; }
            const field = make("p", "api-result__field");
            if (key) field.append(make("strong", "", `${key.replaceAll("_", " ")}: `));
            field.append(document.createTextNode(String(data)));
            host.append(field);
        };
        renderValue(result, value);
        if (!result.children.length || value?.empty === true || value?.insufficient_information === true) {
            result.replaceChildren(make("p", "api-result__empty", "No intelligence available for this deal yet."));
        }
        container.append(result);
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
            row.addEventListener("click", () => { selectDeal(deal); window.location.assign(`dealmemory.html?deal_id=${encodeURIComponent(deal.id)}`); });
            row.addEventListener("keydown", (event) => {
                if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault();
                    selectDeal(deal);
                    window.location.assign(`dealmemory.html?deal_id=${encodeURIComponent(deal.id)}`);
                }
            });
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
        const aiHeading = $("h3", aiCard);
        const aiDescription = $("p", aiCard);
        const briefButton = $("#briefButton");
        if (aiHeading) aiHeading.textContent = "Loading DealMind intelligence…";
        if (aiDescription) aiDescription.textContent = "";
        if (briefButton) {
            briefButton.disabled = true;
            briefButton.textContent = "Select a deal to generate a brief";
        }
        if (dealsHost) $$(".deal", dealsHost).forEach((item) => item.remove());
        if (memoriesHost) $$(".memory", memoriesHost).forEach((item) => item.remove());
        metricCards.forEach((card) => {
            const value = $(".metric-value", card); if (value) value.textContent = "—";
            const sub = $(".metric-sub", card); if (sub) sub.textContent = "";
        });
        try {
            const [deals, metrics] = await Promise.all([loadDeals(), api.request("/api/dashboard/metrics")]);
            const values = [metrics.open_deal_count, metrics.at_risk_count, metrics.interaction_count];
            const labels = ["Open Deals", "At-Risk Deals", "Recorded Interactions"];
            const emptyLabels = [
                deals.length ? "No open deals" : "No deal records yet",
                deals.length ? "No at-risk open deals" : "No deal records yet",
                "No interactions recorded",
            ];
            metricCards.forEach((card, index) => {
                const label = $(".metric-label", card);
                const value = $(".metric-value", card);
                const sub = $(".metric-sub", card);
                if (label && labels[index]) label.textContent = labels[index];
                if (value && values[index] !== undefined) value.textContent = String(values[index]);
                if (sub) sub.textContent = values[index] ? "From your saved DealMind records" : emptyLabels[index];
            });
            if (dealsHost) {
                if (deals.length) deals.forEach((deal) => dealsHost.append(renderDealRow(deal, true)));
                else state(dealsHost, "No deals yet. Your saved deals will appear here.");
            }
            const selected = currentDeal(deals);
            if (briefButton) {
                briefButton.disabled = !selected;
                briefButton.textContent = selected ? "Generate Deal Brief →" : "Select a deal to generate a brief";
            }
            if (memoriesHost && deals.length) {
                const memoryDeals = selected ? [selected] : deals;
                const memoryResults = await Promise.all(memoryDeals.map(async (deal) => {
                    try {
                        const result = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/memories`);
                        return { deal, memories: result.memories || [], error: null };
                    } catch (error) {
                        return { deal, memories: [], error };
                    }
                }));
                const recentMemories = memoryResults.flatMap(({ deal, memories }) =>
                    memories.map((memory) => ({ deal, memory })),
                ).sort((left, right) => {
                    const leftDate = Date.parse(left.memory.interaction_date || "") || 0;
                    const rightDate = Date.parse(right.memory.interaction_date || "") || 0;
                    return rightDate - leftDate;
                }).slice(0, 4);
                if (recentMemories.length) {
                    recentMemories.forEach(({ deal, memory }) => {
                        const item = make("div", "memory");
                        item.append(make("div", "memory-icon", "◈"));
                        const content = make("div", "memory-content");
                        content.append(make("div", "memory-title", deal.company_name), make("div", "memory-description", memory.content), make("div", "memory-time", dateLabel(memory.interaction_date)));
                        item.append(content);
                        memoriesHost.append(item);
                    });
                } else if (memoryResults.every((result) => result.error)) {
                    state(memoriesHost, errorText(memoryResults[0].error), "error");
                } else {
                    state(memoriesHost, selected
                        ? "No Hindsight memories have been recorded for this deal."
                        : "No Hindsight memories have been recorded for these deals.");
                }
            } else if (memoriesHost) state(memoriesHost, "No deal memory is available yet.");
            if (aiCard) {
                const heading = $("h3", aiCard);
                const description = $("p", aiCard);
                if (heading) heading.textContent = selected ? `Deal intelligence for ${selected.company_name}.` : `${deals.length} saved deal${deals.length === 1 ? "" : "s"} in your workspace.`;
                if (description) description.textContent = selected ? "Recommendations and risk signals use retained Hindsight evidence for this deal." : "Select a saved deal to view its evidence-backed intelligence.";
            }
        } catch (error) {
            state(dealsHost, errorText(error), "error");
            state(memoriesHost, errorText(error), "error");
            if (aiHeading) aiHeading.textContent = "Deal Intelligence is temporarily unavailable.";
            if (aiDescription) aiDescription.textContent = "Check your connection and try again.";
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
        const modalLogo = $(".deal-modal .company-logo");
        if (modalLogo) modalLogo.textContent = initials(deal.company_name);
        $("#modalMemory").textContent = "Loading deal-scoped Hindsight memory…";
        const openLink = $("#modalOpenDeal");
        if (openLink) openLink.href = `dealmemory.html?deal_id=${encodeURIComponent(deal.id)}`;
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
        const summaryCards = $$(".summary-card");
        summaryCards.forEach((card) => { const metric = $("strong", card); if (metric) metric.textContent = "—"; });
        const insight = $(".ai-insight");
        const insightTitle = $("h3", insight);
        const insightText = $("p", insight);
        if (insightTitle) insightTitle.textContent = "Loading saved deals…";
        if (insightText) insightText.textContent = "";
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
            table.hidden = false;
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
            const riskCount = deals.filter((deal) => ["high", "medium"].includes((deal.risk_level || "").toLowerCase()) && !["won", "lost", "stalled"].includes((deal.status || "").toLowerCase())).length;
            const pipelineValue = deals.reduce((total, deal) => total + (Number(deal.value) || 0), 0);
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
            $("#analyzeButton")?.addEventListener("click", async (event) => {
                const button = event.currentTarget;
                const insight = $(".ai-content");
                button.disabled = true;
                if (insight) {
                    insight.querySelectorAll(".api-state, .risk-memory-list").forEach((node) => node.remove());
                    state(insight, "Checking each saved deal's retained Hindsight memories…", "loading");
                }
                try {
                    const scans = await Promise.all(deals.map(async (deal) => ({
                        deal,
                        memories: (await api.request(`/api/deals/${encodeURIComponent(deal.id)}/memories`)).memories || [],
                    })));
                    insight?.querySelectorAll(".api-state").forEach((node) => node.remove());
                    const findings = scans.map(({ deal, memories }) => ({
                        deal,
                        memories: memories.filter((memory) => /risk|objection|concern|unresolved/.test(memory.memory_type || "")),
                    })).filter((scan) => scan.memories.length);
                    const title = $("h3", insight);
                    const summary = $("p", insight);
                    if (title) title.textContent = findings.length ? `${findings.length} deal${findings.length === 1 ? "" : "s"} have recorded risk-related evidence.` : "No risk-related memories were found.";
                    if (summary) summary.textContent = findings.length ? "Items below are retained Hindsight memories, not generated risk predictions." : "This does not indicate a risk-free deal; no matching memories were available.";
                    if (!findings.length) { state(insight, "No retained risk, objection, concern, or unresolved-issue memories were found."); return; }
                    const list = make("div", "risk-memory-list");
                    findings.forEach(({ deal, memories }) => {
                        const card = make("article", "risk-memory-card");
                        card.append(make("h4", "", deal.company_name));
                        memories.forEach((memory) => {
                            card.append(make("p", "", memory.content));
                            if (memory.memory_id) { const details = make("details"); details.append(make("summary", "", "View memory ID"), make("code", "", memory.memory_id)); card.append(details); }
                        });
                        list.append(card);
                    });
                    insight.append(list);
                } catch (error) {
                    state(insight, errorText(error), "error");
                } finally { button.disabled = false; }
            });
            setFilter();
        } catch (error) {
            state(empty, errorText(error), "error"); empty?.classList.add("visible");
            if (insightTitle) insightTitle.textContent = "Deal Intelligence is temporarily unavailable.";
            if (insightText) insightText.textContent = "Check your connection and try again.";
            $("#analyzeButton")?.addEventListener("click", () => state($(".ai-content"), errorText(error), "error"));
        }

        $("#modalClose")?.addEventListener("click", () => $("#dealModal")?.classList.remove("show"));
        $("#dealModal")?.addEventListener("click", (event) => { if (event.target === $("#dealModal")) $("#dealModal").classList.remove("show"); });
        document.addEventListener("keydown", (event) => {
            if (event.key === "Escape") $("#dealModal")?.classList.remove("show");
        });
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
            primary?.before(actions);
            saveInteraction.addEventListener("click", async () => {
                const deal = api.getSelectedDeal();
                if (!deal || !notes.value.trim()) { feedback.textContent = "Enter an interaction before retaining it."; return; }
                saveInteraction.disabled = true; feedback.textContent = "Extracting structured deal intelligence and retaining memory…";
                try {
                    const result = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/interactions`, { method: "POST", body: JSON.stringify({ notes: notes.value.trim(), interaction_date: new Date().toISOString(), source: "DealMind web app", company: deal.company_name }) });
                    feedback.textContent = `Interaction retained. ${result.retained_memory_count ?? 0} memory record(s) added.`;
                    notes.value = "";
                    const recalled = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/memories`);
                    $("#modalMemory").textContent = recalled.memories?.[0]?.content || "The interaction was retained; no recallable memory is available yet.";
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
        if (memory.memory_id) {
            const ids = make("details", "memory-id-details");
            ids.append(make("summary", "", "View memory ID"), make("code", "", memory.memory_id));
            tags.append(ids);
        }
        content.append(tags); item.append(content); return item;
    }

    async function renderMemoryPage() {
        const timeline = $(".timeline");
        if (!timeline) return;
        timeline.replaceChildren();
        const dealHeader = $(".deal-header-card");
        const memoryStats = $(".memory-stats");
        const emptyState = $("#dealSelectionEmpty");
        if (emptyState) emptyState.hidden = true;
        const headerTitle = $(".deal-header-card h2");
        const headerMeta = $(".deal-header-card p");
        const headerValue = $(".deal-value strong");
        const headerLogo = $(".deal-header-card .company-logo");
        const stageBadge = $(".deal-header-card .stage-badge");
        const riskBadge = $(".deal-header-card .risk-badge");
        const briefButtons = $$('[data-deal-brief-trigger]');
        briefButtons.forEach((button) => { button.disabled = true; });
        if (headerTitle) headerTitle.textContent = "Loading selected deal…";
        if (headerMeta) headerMeta.textContent = "Loading current deal details";
        if (headerValue) headerValue.textContent = "—";
        if (headerLogo) headerLogo.textContent = "…";
        if (stageBadge) stageBadge.textContent = "Loading";
        if (riskBadge) riskBadge.textContent = "Loading";
        $$(".memory-stats .stat-card strong").forEach((node) => { node.textContent = "—"; });
        $$(".category-btn strong").forEach((node) => { node.textContent = "—"; });
        $$(".key-item strong").forEach((node) => { node.textContent = "Not recorded in deal memory"; });
        const insightSummary = $(".insight-card p");
        if (insightSummary) insightSummary.textContent = "Loading deal-scoped Hindsight evidence…";
        $$(".insight-point").forEach((item) => item.remove());
        state(timeline, "Loading deal-scoped Hindsight memories…", "loading");
        try {
            const deals = await loadDeals();
            const deal = currentDeal(deals);
            if (!deal) {
                if (headerTitle) headerTitle.textContent = "No deal selected";
                if (headerMeta) headerMeta.textContent = "Choose a saved deal from Deals to view its memory.";
                if (headerValue) headerValue.textContent = "—";
                if (headerLogo) headerLogo.textContent = "?";
                if (stageBadge) stageBadge.textContent = "No deal selected";
                if (riskBadge) riskBadge.textContent = "Not available";
                $$(".memory-stats .stat-card strong").forEach((node) => { node.textContent = "0"; });
                if (dealHeader) dealHeader.hidden = true;
                if (memoryStats) memoryStats.hidden = true;
                if (emptyState) { emptyState.hidden = false; emptyState.textContent = "Choose a saved deal from Deals to view its memory."; }
                state(timeline, "No deal is selected.");
                return;
            }
            briefButtons.forEach((button) => { button.disabled = false; });
            const data = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/memories`);
            const title = $(".deal-header-card h2");
            const meta = $(".deal-header-card p");
            const value = $(".deal-value strong");
            const logo = $(".deal-header-card .company-logo");
            if (title) title.textContent = deal.company_name;
            if (meta) meta.textContent = `${deal.stage} · ${deal.status} · ${deal.risk_level} risk`;
            if (value) value.textContent = money(deal.value);
            if (logo) logo.textContent = initials(deal.company_name);
            const stageBadge = $(".deal-header-card .stage-badge");
            const riskBadge = $(".deal-header-card .risk-badge");
            if (stageBadge) { stageBadge.textContent = displayValue(deal.stage); stageBadge.className = `stage-badge ${statusClass(deal.stage)}`; }
            if (riskBadge) { riskBadge.textContent = `${displayValue(deal.risk_level)} Risk`; riskBadge.className = `risk-badge ${statusClass(deal.risk_level)}`; }
            const memories = data.memories || [];
            if (emptyState) emptyState.hidden = true;
            timeline.replaceChildren();
            if (!memories.length) state(timeline, "No memories recorded for this deal yet.");
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
            $("#filterBtn")?.addEventListener("click", () => {
                const types = [...new Set(memories.map((memory) => memory.memory_type).filter(Boolean))];
                const options = [{ value: "all", label: "All memories" }, ...types.map((type) => ({ value: type, label: type.replaceAll("_", " ") }))];
                window.DealMindUI.showSelector({
                    title: "Filter memory",
                    message: "Choose a recorded category for this deal.",
                    selectedValue: "all",
                    options,
                    onSelect(type) { $$(".timeline-item", timeline).forEach((item) => { item.hidden = type !== "all" && !item.classList.contains(`memory-type-${statusClass(type)}`) && $(".memory-type", item)?.textContent !== type.replaceAll("_", " "); }); },
                });
            });
            $(".insight-card p")?.replaceChildren(document.createTextNode(memories.length ? `${memories.length} deal-scoped memories recalled from Hindsight.` : "No deal-specific evidence has been recalled yet."));
            $$(".insight-point").forEach((item) => item.remove());
            const firstMemory = (pattern) => memories.find((memory) => pattern.test(memory.memory_type || ""))?.content;
            const keyValues = [firstMemory(/stakeholder/), firstMemory(/competitor/), firstMemory(/concern|objection|risk/)].map((value) => value || "Not recorded in deal memory");
            $$(".key-item strong").forEach((node, index) => { node.textContent = keyValues[index] || "Not recorded in deal memory"; });
        } catch (error) {
            if (dealHeader) dealHeader.hidden = true;
            if (memoryStats) memoryStats.hidden = true;
            if (emptyState) { emptyState.hidden = false; emptyState.textContent = errorText(error); }
            state(timeline, errorText(error), "error");
        }
    }

    function renderChatMessage(text, type = "ai") {
        const area = $("#chatArea");
        const item = make("div", `message ${type === "ai" ? "ai-message" : "user-message"}`);
        if (type === "ai") item.append(make("div", "message-avatar", "H"));
        const content = make("div", "message-content");
        content.append(make("span", "message-name", type === "ai" ? "DealMind · evidence" : "You"), make("p", "", text));
        item.append(content); area?.append(item); if (area) area.scrollTop = area.scrollHeight;
    }
    async function renderCopilot() {
        const area = $("#chatArea");
        if (!area) return;
        area.replaceChildren();
        const selectorHost = $(".deal-selector-card");
        const select = document.createElement("select");
        select.setAttribute("aria-label", "Select a deal");
        const initialName = $("#selectedDealName"); if (initialName) initialName.textContent = "No deal selected";
        const initialLogo = $("#selectedDealLogo"); if (initialLogo) initialLogo.textContent = "?";
        ["#selectedDealValue span", "#selectedDealStage span", "#selectedDealRisk span"].forEach((selector) => {
            const node = $(selector); if (node) node.textContent = "Not available";
        });
        const input = $("#chatInput");
        const send = $("#sendBtn");
        let deals = [];
        let deal = null;
        try {
            deals = await loadDeals();
            deal = currentDeal(deals);
            const placeholder = document.createElement("option");
            placeholder.value = ""; placeholder.textContent = "Select a saved deal"; placeholder.disabled = true; placeholder.selected = !deal;
            select.append(placeholder);
            deals.forEach((item) => { const option = document.createElement("option"); option.value = item.id; option.textContent = item.company_name; option.selected = item.id === deal?.id; select.append(option); });
            if (selectorHost) {
                $("#changeDealBtn")?.replaceWith(select);
                if (!$("#changeDealBtn")) selectorHost.append(select);
            }
            const title = $(".deal-selector-card h2");
            const contextGrid = $(".context-grid");
            const updateContext = async () => {
                if (!contextGrid) return;
                contextGrid.replaceChildren();
                if (!deal) { state(contextGrid, "Select a deal to load its recorded context."); return; }
                const requestedDealId = deal.id;
                try {
                    const recalled = await api.request(`/api/deals/${encodeURIComponent(requestedDealId)}/memories`);
                    if (deal?.id !== requestedDealId) return;
                    const categories = [
                        ["Stakeholder", /stakeholder/], ["Competitor", /competitor/],
                        ["Risk or objection", /risk|objection|concern/], ["Requirements and actions", /requirement|commitment|request|sales_action/],
                    ];
                    categories.forEach(([label, pattern]) => {
                        const memory = recalled.memories?.find((item) => pattern.test(item.memory_type || ""));
                        const card = make("div", "context-card");
                        const detail = make("div");
                        detail.append(make("span", "", label), make("strong", "", memory?.content || "Not recorded"));
                        if (memory?.memory_id) { const ids = make("details"); ids.append(make("summary", "", "View memory ID"), make("code", "", memory.memory_id)); detail.append(ids); }
                        card.append(detail); contextGrid.append(card);
                    });
                } catch (error) { state(contextGrid, errorText(error), "error"); }
            };
            const setDeal = (chosen) => {
                if (!chosen) return;
                deal = selectDeal(chosen);
                if (title) title.textContent = deal.company_name;
                const heading = $(".chat-header p"); if (heading) heading.textContent = `Evidence and intelligence for ${deal.company_name}`;
                const valueNode = $("#selectedDealValue span"); if (valueNode) valueNode.textContent = money(deal.value);
                const stageNode = $("#selectedDealStage span"); if (stageNode) stageNode.textContent = deal.stage || "Not recorded";
                const riskNode = $("#selectedDealRisk span"); if (riskNode) riskNode.textContent = `${deal.risk_level || "Not recorded"} risk`;
                const riskHost = $("#selectedDealRisk"); if (riskHost) riskHost.className = `${statusClass(deal.risk_level)}-risk`;
                const logo = $("#selectedDealLogo"); if (logo) logo.textContent = initials(deal.company_name);
                $$(".message", area).forEach((message) => message.remove());
                renderChatMessage(`Selected ${deal.company_name}. New requests are scoped to this deal.`);
                updateContext();
            };
            if (deal) setDeal(deal);
            else {
                if (title) title.textContent = "No deal selected";
                $$(".deal-meta span", selectorHost).forEach((item) => { item.textContent = "Not available"; });
                updateContext();
            }
            select.addEventListener("change", () => setDeal(deals.find((item) => item.id === select.value)));
            if (!deal) renderChatMessage("Select a saved deal to request its evidence-backed intelligence.");
            const promptPanel = make("div", "quick-prompts"); promptPanel.id = "quickPrompts";
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
                if (!action) { renderChatMessage("No evidence-backed recommendation is available for this deal yet."); return; }
                path = `/api/deals/${encodeURIComponent(deal.id)}/why`; method = "POST"; body = JSON.stringify({ action });
            } else if (q.includes("next") || q.includes("action") || q.includes("recommend")) path = `/api/deals/${encodeURIComponent(deal.id)}/recommendations`;
            else {
                const data = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/memories`);
                const terms = q.split(/\W+/).filter((term) => term.length > 2);
                const matches = (data.memories || []).filter((memory) => terms.some((term) => memory.content.toLowerCase().includes(term)));
                if (!matches.length) { renderChatMessage("No retained memory matched that question for the selected deal."); return; }
                matches.forEach((memory) => {
                    const message = make("div", "message ai-message");
                    message.append(make("div", "message-avatar", "H"));
                    const detail = make("div", "message-content");
                    detail.append(make("span", "message-name", "DealMind · Hindsight evidence"), make("p", "", memory.content));
                    if (memory.interaction_date) detail.append(make("small", "", dateLabel(memory.interaction_date)));
                    if (memory.interaction_source) detail.append(make("small", "", `Source: ${memory.interaction_source}`));
                    if (memory.memory_id) { const ids = make("details"); ids.append(make("summary", "", "View memory ID"), make("code", "", memory.memory_id)); detail.append(ids); }
                    message.append(detail); area.append(message);
                });
                return;
            }
            const result = await api.request(path, { method, body });
            const message = make("div", "message ai-message");
            message.append(make("div", "message-avatar", "H"));
            const resultHost = make("div", "message-content");
            resultHost.append(make("span", "message-name", "DealMind · result"));
            renderResult(resultHost, result);
            message.append(resultHost); area.append(message);
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
        const bindOnce = (selector, key, handler) => {
            const button = $(selector);
            if (button && !button.dataset[key]) { button.dataset[key] = "true"; button.addEventListener("click", handler); }
        };
        bindOnce("#analyzeBtn", "refreshBound", async () => { await renderLearning(); });
        bindOnce("#patternsBtn", "scrollBound", () => patternList.scrollIntoView({ behavior: "smooth" }));
        bindOnce("#autopsyBtn", "scrollBound", () => autopsyGrid?.scrollIntoView({ behavior: "smooth" }));
        patternList.replaceChildren(); similarList?.replaceChildren(); autopsyGrid?.replaceChildren();
        lessonsGrid?.replaceChildren();
        $$(".learning-stats .stat-card strong").forEach((node) => { node.textContent = "—"; });
        try {
            const data = await api.request("/api/learning");
            const patterns = data.patterns?.patterns || [];
            const history = data.history || [];
            const noInsights = data.empty === true || (!patterns.length && !history.length);
            const emptyMessage = noInsights ? "No learning insights available yet." : "Not enough historical data yet.";
            if (patterns.length) patterns.forEach((pattern, index) => {
                const item = make("article", "pattern-item");
                item.append(make("div", "pattern-number", String(index + 1).padStart(2, "0")));
                const info = make("div", "pattern-info");
                info.append(make("h4", "", pattern.description), make("p", "", pattern.interpretation || "Observed association; this does not establish causality."));
                info.append(make("div", "pattern-meta", `${pattern.occurrence_count || 1} occurrence(s) · ${pattern.supporting_deal_ids?.length || 0} supporting deal(s) · ${pattern.evidence?.length || 0} evidence item(s)`));
                (pattern.evidence || []).forEach((evidence) => {
                    if (evidence.content) info.append(make("p", "pattern-evidence", evidence.content));
                    if (evidence.memory_id) { const ids = make("details"); ids.append(make("summary", "", "View memory ID"), make("code", "", evidence.memory_id)); info.append(ids); }
                });
                if (pattern.uncertainty) info.append(make("p", "", `Uncertainty: ${pattern.uncertainty}`));
                item.append(info); patternList.append(item);
            });
            else state(patternList, emptyMessage);
            const lessonMemories = history.filter((item) => item.memory_type === "lesson_learned");
            const outcomeMemories = history.filter((item) => item.memory_type === "deal_outcome");
            const statCards = $$(".learning-stats .stat-card");
            const setStat = (index, value) => {
                const node = $("strong", statCards[index]);
                if (node) node.textContent = String(value);
            };
            setStat(0, patterns.length);
            setStat(1, "—");
            setStat(2, lessonMemories.length);
            setStat(3, new Set(history.map((item) => item.deal_id).filter(Boolean)).size);
            const lessonsSection = $(".lessons-section");
            const lessonsCaption = $(".lessons-section .section-header p");
            if (lessonsCaption) lessonsCaption.textContent = "Retained outcome lessons with their source deal and Hindsight memory.";
            if (lessonsGrid && lessonMemories.length) lessonMemories.forEach((item) => {
                const lesson = make("article", "lesson-card");
                const detail = make("div");
                detail.append(make("h4", "", item.content));
                if (item.interaction_date) detail.append(make("p", "", dateLabel(item.interaction_date)));
                if (item.deal_id || item.memory_id) { const ids = make("details"); ids.append(make("summary", "", "View source IDs")); if (item.deal_id) ids.append(make("code", "", `Deal ID: ${item.deal_id}`)); if (item.memory_id) ids.append(make("code", "", `Memory ID: ${item.memory_id}`)); detail.append(ids); }
                lesson.append(detail); lessonsGrid.append(lesson);
            });
            else if (lessonsGrid) state(lessonsGrid, emptyMessage);
            const deals = await loadDeals().catch(() => []);
            const similarCaption = $(".similar-card .section-header p");
            const deal = currentDeal(deals);
            if (similarCaption) similarCaption.textContent = deal ? `Historical matches for ${deal.company_name}, based on Hindsight evidence.` : "Not enough historical data yet.";
            const renderSimilar = async () => {
                if (!deal) { setStat(1, 0); state(similarList, "Select a deal to compare against evidence-backed historical deals."); return; }
                state(similarList, "Comparing recalled Hindsight evidence…", "loading");
                try {
                    const result = await api.request(`/api/deals/${encodeURIComponent(deal.id)}/similar`);
                    similarList.replaceChildren();
                    setStat(1, result.similar_deals?.length || 0);
                    if (!result.similar_deals?.length) { state(similarList, "Not enough historical data yet."); return; }
                    const dealNames = new Map(deals.map((record) => [record.id, record.company_name]));
                    result.similar_deals.forEach((match) => {
                        const item = make("article", "similar-deal");
                        item.append(make("h4", "similar-info", match.company_name || dealNames.get(match.historical_deal_id) || "Historical deal"));
                        if (match.similarity_reason) item.append(make("p", "", match.similarity_reason));
                        (match.matching_characteristics || []).forEach((characteristic) => {
                            item.append(make("p", "", characteristic.characteristic));
                            const ids = [...(characteristic.current_memory_ids || []), ...(characteristic.historical_memory_ids || [])];
                            if (ids.length) { const details = make("details"); details.append(make("summary", "", "View supporting memory IDs")); ids.forEach((id) => details.append(make("code", "", id))); item.append(details); }
                        });
                        [...(match.current_evidence || []), ...(match.historical_evidence || [])].forEach((evidence) => {
                            if (evidence.content) item.append(make("p", "similar-evidence", evidence.content));
                            if (evidence.memory_id) { const details = make("details"); details.append(make("summary", "", "View memory ID"), make("code", "", evidence.memory_id)); item.append(details); }
                        });
                        if (match.historical_outcome?.statement) item.append(make("p", "", `Historical outcome: ${match.historical_outcome.statement}`));
                        if (match.useful_lesson?.statement) item.append(make("p", "", `Lesson: ${match.useful_lesson.statement}`));
                        if (match.historical_deal_id) { const details = make("details"); details.append(make("summary", "", "View deal ID"), make("code", "", match.historical_deal_id)); item.append(details); }
                        similarList.append(item);
                    });
                } catch (error) { state(similarList, errorText(error), "error"); }
            };
            bindOnce("#similarBtn", "refreshBound", renderSimilar);
            if (similarList) {
                setStat(1, deal ? "—" : 0);
                state(similarList, deal
                    ? "Choose Similar Deals to compare against historical evidence."
                    : "Select a deal to compare against evidence-backed historical deals.");
            }
            const outcomes = new Map();
            outcomeMemories.forEach((item) => { if (item.outcome && !outcomes.has(item.deal_id)) outcomes.set(item.deal_id, item); });
            if (autopsyGrid && outcomes.size) outcomes.forEach((item) => {
                const card = make("article", "autopsy-card");
                const company = deals.find((record) => record.id === item.deal_id)?.company_name || "Deal outcome";
                card.append(make("h4", "", company), make("span", `outcome ${statusClass(item.outcome)}`, item.outcome), make("p", "", item.content));
                if (item.deal_id || item.memory_id) { const sourceIds = make("details"); sourceIds.append(make("summary", "", "View source IDs")); if (item.deal_id) sourceIds.append(make("code", "", `Deal ID: ${item.deal_id}`)); if (item.memory_id) sourceIds.append(make("code", "", `Memory ID: ${item.memory_id}`)); card.append(sourceIds); }
                const button = make("button", "autopsy-btn", "View evidence-backed autopsy"); button.type = "button";
                const result = make("div", "api-state");
                button.addEventListener("click", async () => {
                    button.disabled = true; result.textContent = "Analyzing deal history…";
                    try { const autopsy = await api.request(`/api/deals/${encodeURIComponent(item.deal_id)}/autopsy`, { method: "POST", body: JSON.stringify({ outcome: item.outcome }) }); result.textContent = ""; renderResult(result, autopsy, "Deal Autopsy"); }
                    catch (error) { result.textContent = errorText(error); }
                    finally { button.disabled = false; }
                });
                card.append(button, result); autopsyGrid.append(card);
            });
            else if (autopsyGrid) state(autopsyGrid, "Not enough historical data yet.");
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
