/* ================================
   DEALMIND — LEARNING JS
   ================================ */


/* ================================
   ANALYZE MY DEALS
   ================================ */

const analyzeBtn =
  document.getElementById("analyzeBtn");


analyzeBtn.addEventListener(
  "click",
  () => {

    const original =
      analyzeBtn.innerHTML;

    analyzeBtn.innerHTML = `
      <i class="fa-solid fa-spinner fa-spin"></i>
      Analyzing...
    `;

    analyzeBtn.disabled = true;


    setTimeout(() => {

      analyzeBtn.innerHTML =
        original;

      analyzeBtn.disabled =
        false;


      alert(
        "Deal Analysis Complete\n\n" +
        "DealMind analyzed 47 deals and identified:\n\n" +
        "• 8 recurring winning patterns\n" +
        "• 14 similar historical deals\n" +
        "• 23 lessons from previous conversations\n\n" +
        "New insight:\n" +
        "Phased implementation has appeared in several successful enterprise deals."
      );

    }, 1400);

  }
);



/* ================================
   VIEW ALL — WINNING PATTERNS
   ================================ */

const patternsBtn =
  document.getElementById("patternsBtn");


patternsBtn.addEventListener(
  "click",
  () => {

    alert(
      "Winning Patterns\n\n" +
      "1. Phased Implementation — 75% success\n" +
      "2. ROI Before Pricing — 67% success\n" +
      "3. CTO-Focused Technical Proof — 71% success\n\n" +
      "More patterns will appear as DealMind analyzes additional deals."
    );

  }
);



/* ================================
   VIEW ALL — SIMILAR DEALS
   ================================ */

const similarBtn =
  document.getElementById("similarBtn");


similarBtn.addEventListener(
  "click",
  () => {

    alert(
      "Similar Deals\n\n" +
      "14 deals match the current TechNova deal profile.\n\n" +
      "The strongest matches share:\n" +
      "• Enterprise customer profile\n" +
      "• Negotiation stage\n" +
      "• Technical stakeholder involvement\n" +
      "• Implementation concerns"
    );

  }
);



/* ================================
   DEAL AUTOPSY
   ================================ */

const autopsyButtons =
  document.querySelectorAll(
    ".autopsy-btn"
  );


autopsyButtons.forEach(button => {

  button.addEventListener(
    "click",
    () => {

      const deal =
        button.dataset.deal;


      const analyses = {

        "Atlas Labs":
          "Atlas Labs — WON\n\n" +
          "Deal Value: $145K\n\n" +
          "Key factor: Strong ROI case\n" +
          "Winning move: Executive demo\n\n" +
          "Lesson: Connecting the product directly to measurable business outcomes helped move the deal forward.",

        "Quantum Logic":
          "Quantum Logic — LOST\n\n" +
          "Deal Value: $110K\n\n" +
          "Key factor: Competitor pricing\n" +
          "Missed signal: Procurement concern\n\n" +
          "Lesson: Procurement concerns should have been identified earlier in the negotiation.",

        "MedSys":
          "MedSys — WON\n\n" +
          "Deal Value: $210K\n\n" +
          "Key factor: Multiple stakeholders\n" +
          "Winning move: Consensus building\n\n" +
          "Lesson: Bringing multiple stakeholders into the conversation helped create alignment before the final decision."

      };


      alert(
        analyses[deal]
      );

    }
  );

});



/* ================================
   VIEW ALL — AUTOPSY
   ================================ */

const autopsyBtn =
  document.getElementById("autopsyBtn");


autopsyBtn.addEventListener(
  "click",
  () => {

    alert(
      "Deal Autopsy\n\n" +
      "DealMind has analyzed your recently closed deals.\n\n" +
      "Won deals are analyzed for successful strategies.\n" +
      "Lost deals are analyzed for missed signals and lessons.\n\n" +
      "These insights feed into future deal recommendations."
    );

  }
);



/* ================================
   HOVER EFFECTS
   ================================ */

const cards =
  document.querySelectorAll(
    ".pattern-item, .similar-deal, .autopsy-card, .lesson-card"
  );


cards.forEach(card => {

  card.addEventListener(
    "mouseenter",
    () => {

      card.style.transform =
        "translateY(-2px)";

      card.style.transition =
        "transform 0.2s ease";

    }
  );


  card.addEventListener(
    "mouseleave",
    () => {

      card.style.transform =
        "translateY(0)";

    }
  );

});