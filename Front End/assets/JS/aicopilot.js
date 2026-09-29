/* Deal selector and honest placeholder behavior for the unconnected Copilot. */
const chatArea = document.getElementById("chatArea");
const chatInput = document.getElementById("chatInput");
const sendBtn = document.getElementById("sendBtn");
const activeDeals = window.DealMindActiveDeals || {};
const dealNameElement = document.getElementById("selectedDealName");
const dealLogo = document.getElementById("selectedDealLogo");
const dealValue = document.getElementById("selectedDealValue");
const dealStage = document.getElementById("selectedDealStage");
const dealRisk = document.getElementById("selectedDealRisk");
const savedName = localStorage.getItem("dealMindSelectedDeal");
let selectedDealName = Object.hasOwn(activeDeals, savedName) ? savedName : "TechNova";

function updateSelectedDeal() {
  const deal = activeDeals[selectedDealName];
  if (!deal) return;
  dealNameElement.textContent = selectedDealName;
  dealLogo.textContent = selectedDealName.split(/\s+/).map((part) => part[0]).join("").slice(0, 2).toUpperCase();
  dealValue.querySelector("span").textContent = deal.value;
  dealStage.querySelector("span").textContent = deal.stage;
  dealRisk.className = `${deal.risk.toLowerCase()}-risk`;
  dealRisk.querySelector("span").textContent = `${deal.risk} Risk`;
}

function addChatMessage(text, type) {
  const message = document.createElement("div");
  message.className = `message ${type === "assistant" ? "ai-message" : "user-message"}`;
  const content = document.createElement("div");
  content.className = "message-content";
  const label = document.createElement("span");
  label.className = "message-name";
  label.textContent = type === "assistant" ? "DealMind" : "You";
  const paragraph = document.createElement("p");
  paragraph.textContent = text;
  content.append(label, paragraph);
  message.appendChild(content);
  chatArea.appendChild(message);
  chatArea.scrollTop = chatArea.scrollHeight;
}

function submitQuestion(question) {
  const cleanQuestion = question.trim();
  if (!cleanQuestion) return;
  addChatMessage(cleanQuestion, "user");
  addChatMessage(
    "Copilot chat is not connected to a live API yet. No AI answer is being generated. Use Open Deal Intelligence for the supported Deal Brief request when a canonical deal ID exists.",
    "assistant",
  );
}

function selectedDealUrl() {
  const deal = activeDeals[selectedDealName];
  const query = new URLSearchParams();
  if (deal?.dealId) query.set("deal_id", deal.dealId);
  query.set("deal_name", selectedDealName);
  return `dealmemory.html?${query.toString()}`;
}

function updateDemoContextVisibility() {
  const isTechNovaDemo = selectedDealName === "TechNova";
  ["staticWhyDemo", "staticContextDemo"].forEach((id) => {
    const section = document.getElementById(id);
    if (section) section.hidden = !isTechNovaDemo;
  });
}

sendBtn.addEventListener("click", () => {
  submitQuestion(chatInput.value);
  chatInput.value = "";
  chatInput.focus();
});

chatInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    event.preventDefault();
    sendBtn.click();
  }
});

document.querySelectorAll(".prompt-btn").forEach((button) => {
  button.addEventListener("click", () => submitQuestion(button.dataset.prompt || ""));
});

document.getElementById("generateBriefBtn").addEventListener("click", () => {
  window.location.href = selectedDealUrl();
});

document.getElementById("changedBtn").addEventListener("click", () => {
  submitQuestion("What changed?");
});

document.getElementById("nextActionBtn").addEventListener("click", () => {
  submitQuestion("What should I do next?");
});

document.getElementById("changeDealBtn").addEventListener("click", () => {
  const options = Object.entries(activeDeals).map(([name, deal]) => ({
    value: name,
    label: name,
    description: [deal.value, deal.stage, `${deal.risk} risk`].join(" · "),
  }));
  window.DealMindUI.showSelector({
    title: "Select an active deal",
    message: "These are existing frontend demo records; only configured canonical IDs can be sent to an API.",
    options,
    selectedValue: selectedDealName,
    onSelect(name) {
      const selected = activeDeals[name];
      if (!selected) return;
      selectedDealName = name;
      localStorage.setItem("dealMindSelectedDeal", name);
      localStorage.setItem("dealMindSelectedDealId", selected.dealId || "");
      updateSelectedDeal();
      updateDemoContextVisibility();
      chatArea.replaceChildren();
      addChatMessage(`${name} selected. These records are demo content; Copilot has no live chat API.`, "assistant");
      const memoryLink = document.querySelector(".view-memory");
      if (memoryLink) memoryLink.href = selectedDealUrl();
    },
  });
});

updateSelectedDeal();
const memoryLink = document.querySelector(".view-memory");
if (memoryLink) memoryLink.href = selectedDealUrl();
updateDemoContextVisibility();
