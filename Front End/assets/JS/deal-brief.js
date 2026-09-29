(() => {
  const panelMount = document.getElementById("dealBriefPanelMount");
  if (!panelMount) return;

  const triggerButtons = document.querySelectorAll("[data-deal-brief-trigger]");
  const apiBase = document.documentElement.dataset.apiBase || "http://127.0.0.1:8000";

  panelMount.innerHTML = `
    <section class="deal-brief-panel" id="dealBriefPanel" aria-labelledby="dealBriefTitle" aria-live="polite" hidden>
      <header class="deal-brief-panel__header">
        <div>
          <p class="deal-brief-panel__eyebrow">AI DEAL BRIEF</p>
          <h2 id="dealBriefTitle">Deal Brief</h2>
        </div>
        <button class="deal-brief-panel__close" type="button" aria-label="Hide Deal Brief">&times;</button>
      </header>
      <div class="deal-brief-panel__body" id="dealBriefContent"></div>
    </section>
  `;

  const panel = panelMount.querySelector("#dealBriefPanel");
  const content = panelMount.querySelector("#dealBriefContent");
  const closeButton = panelMount.querySelector(".deal-brief-panel__close");

  closeButton.addEventListener("click", () => {
    panel.hidden = true;
  });

  function appendMemoryIdDetails(parent, memoryIds) {
    if (!memoryIds.length) return;

    const details = document.createElement("details");
    details.className = "deal-brief-evidence__id-details";
    const summary = document.createElement("summary");
    summary.textContent = memoryIds.length === 1
      ? "View memory ID"
      : `View ${memoryIds.length} memory IDs`;
    details.appendChild(summary);

    memoryIds.forEach((memoryId, index) => {
      const idLabel = document.createElement("span");
      idLabel.className = "deal-brief-evidence__id-label";
      idLabel.textContent = memoryIds.length === 1 ? "Memory ID" : `Memory ID ${index + 1}`;
      const idValue = document.createElement("code");
      idValue.className = "deal-brief-evidence__id-value";
      idValue.textContent = memoryId;
      details.appendChild(idLabel);
      details.appendChild(idValue);
    });

    parent.appendChild(details);
  }

  function addSection(parent, label, entries) {
    const usable = entries.filter((entry) => entry && entry.text);
    if (!usable.length) return;

    const section = document.createElement("section");
    section.className = "deal-brief-panel__section";

    const heading = document.createElement("h3");
    heading.textContent = label;
    section.appendChild(heading);

    const list = document.createElement("ul");
    usable.forEach((entry) => {
      const item = document.createElement("li");
      const text = document.createElement("p");
      text.textContent = entry.text;
      item.appendChild(text);

      if (entry.evidenceIds.length) {
        appendMemoryIdDetails(item, entry.evidenceIds);
      }
      list.appendChild(item);
    });
    section.appendChild(list);
    parent.appendChild(section);
  }

  function factEntries(value) {
    if (!value) return [];
    return (Array.isArray(value) ? value : [value]).map((fact) => ({
      text: typeof fact === "string" ? fact : fact.statement,
      evidenceIds: typeof fact === "object" && Array.isArray(fact.evidence_ids)
        ? fact.evidence_ids
        : [],
    }));
  }

  function formatEvidenceDate(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;
    return new Intl.DateTimeFormat("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      timeZone: "UTC",
    }).format(date);
  }

  function addEvidenceCard(parent, memoryId, evidence) {
    const card = document.createElement("article");
    card.className = "deal-brief-evidence";

    if (evidence && evidence.content) {
      const contentText = document.createElement("p");
      contentText.className = "deal-brief-evidence__content";
      contentText.textContent = evidence.content;
      card.appendChild(contentText);
    }

    const metadataFields = [
      ["Date", evidence && formatEvidenceDate(evidence.interaction_date)],
      ["Source", evidence && evidence.interaction_source],
      ["Stakeholder", evidence && evidence.stakeholder_name],
      ["Company", evidence && evidence.customer_company],
    ].filter(([, value]) => typeof value === "string" && value.trim());

    if (metadataFields.length) {
      const metadata = document.createElement("dl");
      metadata.className = "deal-brief-evidence__metadata";
      metadataFields.forEach(([label, value]) => {
        const item = document.createElement("div");
        const term = document.createElement("dt");
        term.textContent = label;
        const description = document.createElement("dd");
        description.textContent = value;
        item.appendChild(term);
        item.appendChild(description);
        metadata.appendChild(item);
      });
      card.appendChild(metadata);
    }

    appendMemoryIdDetails(card, [memoryId]);
    parent.appendChild(card);
  }

  function renderBrief(brief) {
    content.replaceChildren();

    const stage = factEntries(brief.current_deal_status);
    addSection(content, "Deal stage", stage);

    const value = brief.deal_value ?? brief.value;
    if (value !== undefined && value !== null && String(value).trim()) {
      addSection(content, "Deal value", [{ text: String(value), evidenceIds: [] }]);
    }

    addSection(
      content,
      "Main concern",
      factEntries(brief.stakeholder_concerns).concat(factEntries(brief.main_objections)),
    );
    addSection(content, "Competitors", factEntries(brief.competitors));
    addSection(
      content,
      "Decision maker / key stakeholders",
      factEntries(brief.key_stakeholders),
    );
    addSection(
      content,
      "Positive signals",
      factEntries(brief.positive_signals ?? brief.buying_signals),
    );
    addSection(
      content,
      "Suggested focus / recommendation",
      (brief.recommended_preparation || []).map((item) => ({
        text: [item.action, item.rationale].filter(Boolean).join(" — "),
        evidenceIds: Array.isArray(item.evidence_ids) ? item.evidence_ids : [],
      })),
    );

    const citedIds = new Set();
    const collectCitations = (value) => {
      for (const fact of Array.isArray(value) ? value : value ? [value] : []) {
        for (const id of fact?.evidence_ids || []) citedIds.add(id);
      }
    };
    [
      brief.customer_summary,
      brief.current_deal_status,
      brief.key_stakeholders,
      brief.stakeholder_concerns,
      brief.main_objections,
      brief.competitors,
      brief.pricing_discussions,
      brief.customer_requirements,
      brief.previous_commitments,
      brief.recent_developments,
      brief.positive_signals,
      brief.buying_signals,
      brief.recommended_preparation,
    ].forEach(collectCitations);

    const evidenceById = new Map(
      (brief.supporting_evidence || []).map((evidence) => [evidence.memory_id, evidence]),
    );
    const citedEvidence = [...citedIds];
    if (citedEvidence.length) {
      const section = document.createElement("section");
      section.className = "deal-brief-panel__section deal-brief-panel__evidence-section";
      const heading = document.createElement("h3");
      heading.textContent = "Supporting Evidence";
      section.appendChild(heading);
      citedEvidence.forEach((id) => addEvidenceCard(section, id, evidenceById.get(id)));
      content.appendChild(section);
    }

    if (!content.children.length) {
      const emptyState = document.createElement("p");
      emptyState.className = "deal-brief-panel__empty";
      emptyState.textContent = brief.insufficient_information
        ? "There is not enough deal memory to create a brief yet."
        : "The Deal Brief contains no fields to display.";
      content.appendChild(emptyState);
    }
  }

  async function loadBrief(button) {
    const dealId = window.DealMindActiveDeals?.[button.dataset.dealName]?.dealId
      || new URLSearchParams(window.location.search).get("deal_id");
    panel.hidden = false;
    content.replaceChildren();

    const loading = document.createElement("p");
    loading.className = "deal-brief-panel__loading";
    loading.setAttribute("role", "status");
    loading.textContent = "Loading Deal Brief…";
    content.appendChild(loading);

    triggerButtons.forEach((trigger) => {
      trigger.disabled = true;
      trigger.setAttribute("aria-busy", "true");
    });

    try {
      if (!dealId) throw new Error("This dashboard view has no deal ID configured.");
      const response = await fetch(
        `${apiBase}/api/deals/${encodeURIComponent(dealId)}/brief`,
        { headers: { Accept: "application/json" } },
      );
      if (!response.ok) throw new Error("The Deal Brief service returned an error.");
      const brief = await response.json();
      renderBrief(brief);
    } catch (_error) {
      content.replaceChildren();
      const error = document.createElement("p");
      error.className = "deal-brief-panel__error";
      error.setAttribute("role", "alert");
      error.textContent = "We couldn’t load the Deal Brief. Check the API connection and try again.";
      content.appendChild(error);
    } finally {
      triggerButtons.forEach((trigger) => {
        trigger.disabled = false;
        trigger.removeAttribute("aria-busy");
      });
    }
  }

  triggerButtons.forEach((button) => {
    button.addEventListener("click", () => loadBrief(button));
  });
})();
