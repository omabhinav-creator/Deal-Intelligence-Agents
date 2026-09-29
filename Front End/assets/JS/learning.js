/* ================================
   DEALMIND — LEARNING JS
   ================================ */

function showStaticDemoResult(title, message, sections = []) {
  window.DealMindUI.showDialog({
    title,
    message,
    sections,
    note: "Static demo content; these values are not live AI or Hindsight results.",
  });
}


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


      showStaticDemoResult(
        "Deal Analysis Complete",
        "DealMind analyzed 47 deals and identified:",
        [
          {
            items: [
              "8 recurring winning patterns",
              "14 similar historical deals",
              "23 lessons from previous conversations",
            ],
          },
          {
            title: "New insight",
            text: "Phased implementation has appeared in several successful enterprise deals.",
          },
        ],
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

    showStaticDemoResult(
      "Winning Patterns",
      "More patterns will appear as DealMind analyzes additional deals.",
      [{
        items: [
          "1. Phased Implementation — 75% success",
          "2. ROI Before Pricing — 67% success",
          "3. CTO-Focused Technical Proof — 71% success",
        ],
      }],
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

    showStaticDemoResult(
      "Similar Deals",
      "14 deals match the current TechNova deal profile.",
      [{
        title: "The strongest matches share",
        items: [
          "Enterprise customer profile",
          "Negotiation stage",
          "Technical stakeholder involvement",
          "Implementation concerns",
        ],
      }],
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


      if (analyses[deal]) {
        showStaticDemoResult("Deal Autopsy", analyses[deal]);
      }

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

    showStaticDemoResult(
      "Deal Autopsy",
      "DealMind has analyzed your recently closed deals.\n\n" +
        "Won deals are analyzed for successful strategies.\n" +
        "Lost deals are analyzed for missed signals and lessons.\n\n" +
        "These insights feed into future deal recommendations.",
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
