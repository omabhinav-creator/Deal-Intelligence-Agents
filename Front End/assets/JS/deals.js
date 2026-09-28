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


const dealData = {

    "TechNova": {

        description:
            "Enterprise CRM",

        value:
            "$120K",

        stage:
            "Negotiation",

        risk:
            "Medium",

        competitor:
            "Salesforce",

        memory:
            "CTO raised implementation concerns during the previous conversation."

    },


    "Acme Corp": {

        description:
            "Business Platform",

        value:
            "$85K",

        stage:
            "Proposal",

        risk:
            "Low",

        competitor:
            "HubSpot",

        memory:
            "Customer requested revised pricing before moving forward."

    },


    "Nova Systems": {

        description:
            "AI Infrastructure",

        value:
            "$210K",

        stage:
            "Negotiation",

        risk:
            "High",

        competitor:
            "Oracle",

        memory:
            "Customer mentioned Oracle as an alternative during the latest discussion."

    },


    "GlobalLink": {

        description:
            "Sales Automation",

        value:
            "$65K",

        stage:
            "Discovery",

        risk:
            "Low",

        competitor:
            "Microsoft",

        memory:
            "A new stakeholder joined the deal and requested a product overview."

    },


    "Vertex Labs": {

        description:
            "Analytics Suite",

        value:
            "$145K",

        stage:
            "Proposal",

        risk:
            "Medium",

        competitor:
            "HubSpot",

        memory:
            "Customer asked about integration capabilities."

    },


    "Quantum Systems": {

        description:
            "Cloud Platform",

        value:
            "$180K",

        stage:
            "Negotiation",

        risk:
            "High",

        competitor:
            "AWS",

        memory:
            "Procurement team raised concerns about contract terms."

    }

};


/* OPEN MODAL */

const viewButtons =
    document.querySelectorAll(".view-button");


viewButtons.forEach((button) => {

    button.addEventListener(
        "click",
        () => {

            const dealName =
                button.dataset.deal;

            const deal =
                dealData[dealName];


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


analyzeButton.addEventListener(
    "click",
    () => {

        analyzeButton.textContent =
            "Analyzing...";


        analyzeButton.disabled = true;


        setTimeout(() => {

            alert(
                "AI Risk Analysis\n\n" +
                "3 deals need attention:\n\n" +
                "• TechNova — Implementation concern\n" +
                "• Nova Systems — Competitor pressure\n" +
                "• Quantum Systems — Procurement concern"
            );


            analyzeButton.textContent =
                "Analyze Risks →";

            analyzeButton.disabled = false;

        }, 1000);

    }
);