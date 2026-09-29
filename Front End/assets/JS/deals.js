/* =========================================
   DEALMIND — DEALS OVERVIEW
========================================= */


/* =========================================
   NAVIGATION
========================================= */

const navItems =
    document.querySelectorAll(".nav-item");

const pageRoutes = {
    dashboard: "dashboard.html",
    deals: "deals.html",
    memory: "dealmemory.html",
    copilot: "aicopilot.html",
    learning: "learning.html",
    settings: "settings.html"
};


navItems.forEach((item) => {

    item.addEventListener(
        "click",
        () => {

            navItems.forEach((nav) => {

                nav.classList.remove("active");

            });

            item.classList.add("active");

            const destination = pageRoutes[item.dataset.page];

            if (destination) {
                window.location.href = destination;
            }

        }
    );

});


/* =========================================
   SEARCH
========================================= */

const searchInput =
    document.getElementById("dealSearch");

const dealRows =
    document.querySelectorAll(".deal-row");

const emptyState =
    document.getElementById("emptyState");


let activeFilter = "all";


function filterDeals() {

    const searchValue =
        searchInput.value
            .toLowerCase()
            .trim();


    let visibleDeals = 0;


    dealRows.forEach((deal) => {

        const searchData =
            deal.dataset.search.toLowerCase();

        const stage =
            deal.dataset.stage;

        const risk =
            deal.dataset.risk;


        const matchesSearch =
            searchData.includes(searchValue);


        let matchesFilter = true;


        if (activeFilter === "negotiation") {

            matchesFilter =
                stage === "negotiation";

        }


        if (activeFilter === "proposal") {

            matchesFilter =
                stage === "proposal";

        }


        if (activeFilter === "risk") {

            matchesFilter =
                risk === "high" ||
                risk === "medium";

        }


        const shouldShow =
            matchesSearch &&
            matchesFilter;


        deal.style.display =
            shouldShow
                ? "grid"
                : "none";


        if (shouldShow) {

            visibleDeals++;

        }

    });


    emptyState.classList.toggle(
        "visible",
        visibleDeals === 0
    );

}


searchInput.addEventListener(
    "input",
    filterDeals
);


/* =========================================
   FILTER BUTTONS
========================================= */

const filterButtons =
    document.querySelectorAll(".filter-button");


filterButtons.forEach((button) => {

    button.addEventListener(
        "click",
        () => {

            filterButtons.forEach((btn) => {

                btn.classList.remove("active");

            });


            button.classList.add("active");


            activeFilter =
                button.dataset.filter;


            filterDeals();

        }
    );

});


/* =========================================
   DEAL MODAL
========================================= */

const modal =
    document.getElementById("dealModal");

const modalClose =
    document.getElementById("modalClose");


const modalDealName =
    document.getElementById("modalDealName");

const modalDealDescription =
    document.getElementById(
        "modalDealDescription"
    );

const modalValue =
    document.getElementById("modalValue");

const modalStage =
    document.getElementById("modalStage");

const modalRisk =
    document.getElementById("modalRisk");

const modalCompetitor =
    document.getElementById(
        "modalCompetitor"
    );

const modalMemory =
    document.getElementById(
        "modalMemory"
    );

const modalOpenDeal =
    document.getElementById("modalOpenDeal");


const dealData = window.DealMindActiveDeals;


/* OPEN MODAL */

const viewButtons =
    document.querySelectorAll(".view-button");


viewButtons.forEach((button) => {

    button.addEventListener(
        "click",
        () => {

            const dealName =
                button.dataset.deal;

            const deal = dealData[dealName];
            const query = new URLSearchParams();
            if (deal && deal.dealId) {
                query.set("deal_id", deal.dealId);
            }
            query.set("deal_name", dealName);

            modalOpenDeal.href =
                `dealmemory.html?${query.toString()}`;

            if (!deal) return;


            modalDealName.textContent =
                dealName;

            modalDealDescription.textContent =
                deal.description;

            modalValue.textContent =
                deal.value;

            modalStage.textContent =
                deal.stage;

            modalRisk.textContent =
                deal.risk;

            modalCompetitor.textContent =
                deal.competitor;

            modalMemory.textContent =
                deal.memory;


            modal.classList.add("show");

        }
    );

});


/* CLOSE MODAL */

modalClose.addEventListener(
    "click",
    () => {

        modal.classList.remove("show");

    }
);


/* CLOSE WHEN CLICKING OUTSIDE */

modal.addEventListener(
    "click",
    (event) => {

        if (event.target === modal) {

            modal.classList.remove("show");

        }

    }
);


/* ESCAPE KEY */

document.addEventListener(
    "keydown",
    (event) => {

        if (event.key === "Escape") {

            modal.classList.remove("show");

        }

    }
);


/* =========================================
   AI RISK ANALYSIS
========================================= */

const analyzeButton =
    document.getElementById(
        "analyzeButton"
    );

const riskAnalysisDeals = [
    { name: "TechNova", risk: "Implementation concern" },
    { name: "Nova Systems", risk: "Competitor pressure" },
    { name: "Quantum Systems", risk: "Procurement concern" },
];

function openRiskAnalysis() {
    window.DealMindUI.showDialog({
        title: "AI Risk Analysis",
        message: `${riskAnalysisDeals.length} deals need attention`,
        size: "wide",
        note: "These are the existing static frontend demo values, not live AI or Hindsight risk results.",
        contentBuilder(body) {
            const list = document.createElement("ol");
            list.className = "risk-analysis-list";
            riskAnalysisDeals.forEach((deal) => {
                const item = document.createElement("li");
                const dealRecord = dealData[deal.name];
                const query = new URLSearchParams();
                if (dealRecord && dealRecord.dealId) {
                    query.set("deal_id", dealRecord.dealId);
                }
                query.set("deal_name", deal.name);

                const link = document.createElement("a");
                link.className = "risk-analysis-item";
                link.href = `dealmemory.html?${query.toString()}`;
                const name = document.createElement("span");
                name.className = "risk-analysis-item__name";
                name.textContent = deal.name;
                const risk = document.createElement("span");
                risk.className = "risk-analysis-item__risk";
                risk.textContent = `Risk: ${deal.risk}`;
                link.append(name, risk);
                item.appendChild(link);
                list.appendChild(item);
            });
            body.appendChild(list);
        },
    });
}


analyzeButton.addEventListener(
    "click",
    () => {

        analyzeButton.textContent =
            "Analyzing...";


        analyzeButton.disabled = true;


        setTimeout(() => {
            openRiskAnalysis();

            analyzeButton.textContent =
                "Analyze Risks →";

            analyzeButton.disabled = false;

        }, 1000);

    }
);
