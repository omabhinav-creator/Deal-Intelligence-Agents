/* ================================
   DEALMIND — DEAL MEMORY JS
   ================================ */

const dealQuery = new URLSearchParams(window.location.search);
const requestedDealId = dealQuery.get("deal_id");
const requestedDealName = dealQuery.get("deal_name");
const knownDeals = window.DealMindActiveDeals || {};
const requestedDeal = Object.entries(knownDeals).find(([name, deal]) =>
  (requestedDealId && deal.dealId === requestedDealId)
  || (!requestedDealId && name === requestedDealName && deal.dealId),
);
const selectedDealId = requestedDealId || requestedDeal?.[1]?.dealId || null;
const selectedDealName = requestedDealName || requestedDeal?.[0] || "Selected deal";
const isTechNovaDeal = selectedDealId === knownDeals.TechNova?.dealId
  && (!requestedDealName || requestedDealName === "TechNova");
const briefTrigger = document.querySelector("[data-deal-brief-trigger]");
if (briefTrigger) {
  briefTrigger.dataset.dealName = selectedDealName;
  briefTrigger.disabled = !selectedDealId;
}

if (!isTechNovaDeal) {
  const emptyState = document.getElementById("dealSelectionEmpty");
  const dealHeader = document.querySelector(".deal-header-card");
  const memoryStats = document.querySelector(".memory-stats");
  const memoryLayout = document.querySelector(".memory-layout");
  const heading = document.createElement("h2");
  heading.textContent = selectedDealName;
  const message = document.createElement("p");
  message.textContent = selectedDealId
    ? "No deal-specific intelligence is available yet because this page has no verified memory data for the selected deal. No other deal's evidence is shown."
    : "This deal has no canonical deal ID configured, so DealMind cannot check its Hindsight memories. No deal-specific intelligence is shown.";
  emptyState.appendChild(heading);
  emptyState.appendChild(message);
  if (selectedDealId) {
    const briefButton = document.createElement("button");
    briefButton.type = "button";
    briefButton.className = "primary-btn";
    briefButton.dataset.dealBriefTrigger = "";
    briefButton.dataset.dealName = selectedDealName;
    briefButton.textContent = "Load Deal Brief from API";
    emptyState.appendChild(briefButton);
  }
  emptyState.hidden = false;

  [dealHeader, memoryStats, memoryLayout].forEach((section) => {
    if (section) section.hidden = true;
  });
}

if (isTechNovaDeal) {
  const demoNotice = document.createElement("p");
  demoNotice.className = "deal-memory-demo-notice";
  demoNotice.setAttribute("role", "note");
  demoNotice.textContent = "The timeline, counts, and category summaries on this page are static TechNova demo content. The Deal Brief button loads the selected deal's current API result.";
  document.querySelector(".deal-header-card")?.after(demoNotice);
}


/* ================================
   FILTER BUTTON
   ================================ */

const filterBtn = document.getElementById("filterBtn");
const memoryFilters = [
  "All",
  "Requirements",
  "Objection",
  "Competitor",
  "Stakeholder",
  "Strategy",
];
let activeMemoryFilter = "All";

filterBtn.addEventListener("click", () => {
  const items = document.querySelectorAll(".timeline-item");
  window.DealMindUI.showSelector({
    title: "Filter memory",
    message: "Choose a category to show in the memory timeline.",
    selectedValue: activeMemoryFilter,
    options: memoryFilters.map((filter) => ({ value: filter, label: filter })),
    onSelect(filter) {
      if (!memoryFilters.includes(filter)) {
        window.DealMindUI.showToast("Choose a listed memory category.", "error");
        return;
      }
      activeMemoryFilter = filter;
      items.forEach((item) => {
        const type = item.querySelector(".memory-type")?.textContent.trim();
        item.style.display = filter === "All" || type?.toLowerCase() === filter.toLowerCase()
          ? "grid"
          : "none";
      });
    },
  });
});


/* ================================
   GENERATE DEAL BRIEF
   ================================ */

/* ================================
   CATEGORY BUTTONS
   ================================ */

const categoryButtons =
  document.querySelectorAll(".category-btn");

categoryButtons.forEach(button => {

  button.addEventListener("click", () => {

    const category =
      button.dataset.category;

    const messages = {

      objections:
        "TechNova has raised 4 objections so far. The biggest recurring concern is implementation cost.",

      stakeholders:
        "5 stakeholders have been identified across Sales, Technology, and Management.",

      competitors:
        "2 competitors have been identified. Salesforce is currently the most frequently mentioned.",

      pricing:
        "Pricing has appeared in 3 recorded interactions, including the initial implementation-cost objection."

    };

    window.DealMindUI.showDialog({
      title: category.charAt(0).toUpperCase() + category.slice(1),
      message: messages[category],
      note: "Static demo summary; this is not a live Hindsight result.",
    });

  });

});


/* ================================
   TIMELINE HOVER EFFECT
   ================================ */

const timelineItems =
  document.querySelectorAll(".timeline-item");

timelineItems.forEach(item => {

  item.addEventListener("mouseenter", () => {
    item.querySelector(".timeline-dot").style.transform =
      "scale(1.2)";
  });

  item.addEventListener("mouseleave", () => {
    item.querySelector(".timeline-dot").style.transform =
      "scale(1)";
  });

});
