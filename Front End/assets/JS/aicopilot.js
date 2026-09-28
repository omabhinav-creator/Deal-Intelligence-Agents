/* ================================
   DEALMIND — AI COPILOT JS
   ================================ */


/* ================================
   CHAT ELEMENTS
   ================================ */

const chatArea =
  document.getElementById("chatArea");

const chatInput =
  document.getElementById("chatInput");

const sendBtn =
  document.getElementById("sendBtn");



/* ================================
   AI RESPONSES
   ================================ */

function getAIResponse(question) {

  const q =
    question.toLowerCase();


  if (
    q.includes("changed") ||
    q.includes("change")
  ) {

    return `
      <strong>What changed recently?</strong><br><br>

      The biggest change is that TechNova's
      implementation concern has become more important
      in the recent conversations.

      <br><br>

      • CTO is now more involved<br>
      • Salesforce has been mentioned as a competitor<br>
      • Pricing remains a concern<br>
      • The phased implementation approach received a positive response
    `;

  }


  if (
    q.includes("next") ||
    q.includes("action")
  ) {

    return `
      <strong>Recommended next action:</strong><br><br>

      Schedule a focused conversation with Rahul,
      the CTO, around implementation and integration.

      <br><br>

      Instead of leading with another pricing discussion,
      show how the phased rollout reduces migration risk.

      <br><br>

      <strong>Why?</strong> This directly addresses
      the concern that has appeared most consistently
      in the deal memory.
    `;

  }


  if (
    q.includes("brief") ||
    q.includes("summary")
  ) {

    return `
      <strong>TechNova Deal Brief</strong><br><br>

      <strong>Deal:</strong> $120K<br>
      <strong>Stage:</strong> Negotiation<br>
      <strong>Risk:</strong> Medium<br>
      <strong>Decision Maker:</strong> Rahul Mehta, CTO<br>
      <strong>Competitor:</strong> Salesforce<br>
      <strong>Main Concern:</strong> Implementation cost<br><br>

      The customer has shown interest but remains
      concerned about implementation effort and pricing.
      A phased rollout has received a positive response.
    `;

  }


  if (
    q.includes("risk") ||
    q.includes("risks")
  ) {

    return `
      <strong>Current Deal Risks</strong><br><br>

      1. <strong>Implementation risk</strong> —
      the CTO is concerned about integration effort.<br><br>

      2. <strong>Pricing risk</strong> —
      implementation cost has already been questioned.<br><br>

      3. <strong>Competitive risk</strong> —
      Salesforce is being evaluated as an alternative.
    `;

  }


  return `
    Based on the current TechNova deal memory,
    the key themes are <strong>pricing</strong>,
    <strong>implementation</strong>, and
    <strong>Salesforce</strong>.

    <br><br>

    You can ask me things like:
    <br><br>

    • What changed?<br>
    • What should I do next?<br>
    • Give me a deal brief<br>
    • What are the main risks?
  `;

}



/* ================================
   ADD MESSAGE
   ================================ */

function addMessage(
  text,
  type = "user"
) {

  const message =
    document.createElement("div");

  message.className =
    `message ${type === "ai"
      ? "ai-message"
      : "user-message"}`;


  if (type === "ai") {

    message.innerHTML = `

      <div class="message-avatar">
        <i class="fa-solid fa-brain"></i>
      </div>

      <div class="message-content">

        <span class="message-name">
          DealMind
        </span>

        <p>
          ${text}
        </p>

      </div>

    `;

  } else {

    message.style.justifyContent =
      "flex-end";

    message.innerHTML = `

      <div class="message-content"
           style="max-width: 75%;">

        <span
          class="message-name"
          style="
            text-align:right;
            color:var(--mauve);
          "
        >
          You
        </span>

        <p
          style="
            background:var(--purple);
            color:var(--color-6);
            border-radius:12px 4px 12px 12px;
          "
        >
          ${text}
        </p>

      </div>

    `;

  }


  chatArea.appendChild(message);

  chatArea.scrollTop =
    chatArea.scrollHeight;

}



/* ================================
   SEND MESSAGE
   ================================ */

function sendMessage() {

  const question =
    chatInput.value.trim();

  if (!question) return;


  addMessage(
    question,
    "user"
  );


  chatInput.value = "";

  sendBtn.disabled = true;


  setTimeout(() => {

    const response =
      getAIResponse(question);

    addMessage(
      response,
      "ai"
    );

    sendBtn.disabled = false;

    chatInput.focus();

  }, 700);

}


sendBtn.addEventListener(
  "click",
  sendMessage
);


chatInput.addEventListener(
  "keydown",
  (event) => {

    if (event.key === "Enter") {

      sendMessage();

    }

  }
);



/* ================================
   QUICK PROMPTS
   ================================ */

const promptButtons =
  document.querySelectorAll(
    ".prompt-btn"
  );


promptButtons.forEach(button => {

  button.addEventListener(
    "click",
    () => {

      const prompt =
        button.dataset.prompt;

      chatInput.value =
        prompt;

      sendMessage();

    }
  );

});



/* ================================
   GENERATE DEAL BRIEF
   ================================ */

const generateBriefBtn =
  document.getElementById(
    "generateBriefBtn"
  );


generateBriefBtn.addEventListener(
  "click",
  () => {

    const original =
      generateBriefBtn.innerHTML;

    generateBriefBtn.innerHTML = `
      <i class="fa-solid fa-spinner fa-spin"></i>
      Generating...
    `;

    generateBriefBtn.disabled = true;


    setTimeout(() => {

      generateBriefBtn.innerHTML =
        original;

      generateBriefBtn.disabled =
        false;


      addMessage(
        "Give me a deal brief",
        "user"
      );


      setTimeout(() => {

        addMessage(
          getAIResponse("deal brief"),
          "ai"
        );

      }, 500);

    }, 1000);

  }
);



/* ================================
   WHAT CHANGED
   ================================ */

const changedBtn =
  document.getElementById(
    "changedBtn"
  );


changedBtn.addEventListener(
  "click",
  () => {

    addMessage(
      "What changed?",
      "user"
    );


    setTimeout(() => {

      addMessage(
        getAIResponse("what changed"),
        "ai"
      );

    }, 500);

  }
);



/* ================================
   NEXT BEST ACTION
   ================================ */

const nextActionBtn =
  document.getElementById(
    "nextActionBtn"
  );


nextActionBtn.addEventListener(
  "click",
  () => {

    addMessage(
      "What should I do next?",
      "user"
    );


    setTimeout(() => {

      addMessage(
        getAIResponse(
          "what should I do next"
        ),
        "ai"
      );

    }, 500);

  }
);



/* ================================
   CHANGE DEAL
   ================================ */

const changeDealBtn =
  document.getElementById(
    "changeDealBtn"
  );


changeDealBtn.addEventListener(
  "click",
  () => {

    alert(
      "Deal Selector\n\n" +
      "Currently selected: TechNova\n\n" +
      "In the connected version, this button " +
      "will let you select another active deal."
    );

  }
);