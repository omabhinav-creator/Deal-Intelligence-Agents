/* ================================
   DEALMIND — DEAL MEMORY JS
   ================================ */


/* ================================
   FILTER BUTTON
   ================================ */

const filterBtn = document.getElementById("filterBtn");

filterBtn.addEventListener("click", () => {

  const items = document.querySelectorAll(".timeline-item");

  const filters = [
    "All",
    "Requirements",
    "Objection",
    "Competitor",
    "Stakeholder",
    "Strategy"
  ];

  const selected = prompt(
    "Filter memory by:\n\n" +
    "1. All\n" +
    "2. Requirements\n" +
    "3. Objection\n" +
    "4. Competitor\n" +
    "5. Stakeholder\n" +
    "6. Strategy"
  );

  if (!selected) return;

  const index = parseInt(selected) - 1;

  if (index < 0 || index >= filters.length) {
    alert("Please choose a number between 1 and 6.");
    return;
  }

  const filter = filters[index];

  items.forEach(item => {

    if (filter === "All") {
      item.style.display = "grid";
      return;
    }

    const type = item
      .querySelector(".memory-type")
      .textContent
      .trim();

    if (type.toLowerCase() === filter.toLowerCase()) {
      item.style.display = "grid";
    } else {
      item.style.display = "none";
    }

  });

});


/* ================================
   GENERATE DEAL BRIEF
   ================================ */

const briefBtn = document.getElementById("briefBtn");

briefBtn.addEventListener("click", () => {

  const originalHTML = briefBtn.innerHTML;

  briefBtn.innerHTML = `
    <i class="fa-solid fa-spinner fa-spin"></i>
    Generating...
  `;

  briefBtn.disabled = true;

  setTimeout(() => {

    briefBtn.innerHTML = originalHTML;
    briefBtn.disabled = false;

    alert(
      "AI Deal Brief\n\n" +
      "TechNova is currently in the negotiation stage.\n\n" +
      "• Deal Value: $120K\n" +
      "• Main Concern: Implementation cost\n" +
      "• Competitor: Salesforce\n" +
      "• Decision Maker: Rahul Mehta, CTO\n" +
      "• Positive Signal: Customer responded well to a phased implementation plan\n\n" +
      "Suggested focus: Address implementation risk and connect the pricing discussion to measurable business value."
    );

  }, 1200);

});


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

    alert(
      category.charAt(0).toUpperCase() +
      category.slice(1) +
      "\n\n" +
      messages[category]
    );

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