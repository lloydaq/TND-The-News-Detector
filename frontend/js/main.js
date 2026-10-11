const themeButtons = document.querySelectorAll("[data-theme-choice]");
const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
let themePreference = localStorage.getItem("tnd-theme") || "system";

function applyTheme(preference) {
  themePreference = preference;
  const resolved = preference === "system" ? (systemTheme.matches ? "dark" : "light") : preference;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.themePreference = preference;
  themeButtons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.themeChoice === preference)));
  document.querySelectorAll(".theme-logo").forEach((logo) => {
    logo.src = resolved === "dark" ? logo.dataset.logoDark : logo.dataset.logoLight;
  });
}

applyTheme(themePreference);
themeButtons.forEach((button) => button.addEventListener("click", () => {
  const preference = button.dataset.themeChoice;
  localStorage.setItem("tnd-theme", preference);
  applyTheme(preference);
}));
systemTheme.addEventListener("change", () => {
  if (themePreference === "system") applyTheme("system");
});

if (document.getElementById("newsInput")) {
  const tabs = document.querySelectorAll(".input-tab"),
    label = document.getElementById("inputLabel"),
    hint = document.getElementById("inputHint"),
    message = document.getElementById("validationMessage"),
    terms = document.getElementById("terms"),
    overlay = document.getElementById("loadingOverlay"),
    analyzeButton = document.getElementById("analyzeButton"),
    clearButton = document.getElementById("clearButton"),
    pasteButton = document.getElementById("pasteButton");
  const termsButton = document.getElementById("termsButton");
  const termsDialog = document.getElementById("termsDialog");
  const termsCloseButtons = [
    document.getElementById("termsClose"),
    document.getElementById("termsCloseButton"),
  ].filter(Boolean);
  let termsTrigger;
  let inputType = "url";
  const field = () => document.getElementById("newsInput");
  const updateAnalyzeState = () => {
    const hasInput = Boolean(field().value.trim());
    analyzeButton.disabled = !hasInput || !terms.checked;
    clearButton.hidden = !hasInput;
    pasteButton.hidden = hasInput;
  };
  const bindFieldState = () => field().addEventListener("input", updateAnalyzeState);
  bindFieldState();
  terms.addEventListener("change", updateAnalyzeState);
  updateAnalyzeState();
  const closeTerms = () => {
    if (!termsDialog.open) return;
    termsDialog.close();
  };
  termsButton.addEventListener("click", () => {
    termsTrigger = document.activeElement;
    termsDialog.showModal();
    document.body.style.overflow = "hidden";
  });
  termsCloseButtons.forEach((button) =>
    button.addEventListener("click", closeTerms),
  );
  termsDialog.addEventListener("click", (event) => {
    if (event.target === termsDialog) closeTerms();
  });
  termsDialog.addEventListener("close", () => {
    document.body.style.overflow = "";
    if (termsTrigger instanceof HTMLElement) termsTrigger.focus();
  });
  termsDialog.addEventListener("keydown", (event) => {
    if (event.key !== "Tab") return;
    const focusable = termsDialog.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
    );
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });
  tabs.forEach((tab) =>
    tab.addEventListener("click", () => {
      inputType = tab.dataset.type;
      tabs.forEach((item) => {
        const active = item === tab;
        item.classList.toggle("active", active);
        item.setAttribute("aria-selected", active);
      });
      const old = field(),
        next = document.createElement(
          inputType === "url" ? "input" : "textarea",
        );
      next.id = "newsInput";
      if (inputType === "url") {
        next.type = "url";
        next.inputMode = "url";
        next.autocomplete = "url";
        next.placeholder = "Paste news article URL here...";
        label.textContent = "News article URL";
        hint.textContent = "Enter a public link to a news article.";
      } else {
        next.rows = 8;
        next.placeholder = "Paste the news article or claim here...";
        label.textContent = "News article or claim";
        hint.textContent = "Include enough context for a useful assessment.";
      }
      old.replaceWith(next);
      message.textContent = "";
      bindFieldState();
      updateAnalyzeState();
    }),
  );
  document.getElementById("pasteButton").addEventListener("click", async () => {
    if (
      field().value.trim() &&
      !confirm("Replace the text you have entered with clipboard content?")
    )
      return;
    try {
      const text = await navigator.clipboard.readText();
      if (!text.trim()) throw Error();
      field().value = text;
      message.textContent = "";
      updateAnalyzeState();
    } catch {
      message.textContent =
        "Clipboard access is unavailable. Please paste directly into the field.";
    }
  });
  clearButton.addEventListener("click", () => {
    field().value = "";
    message.textContent = "";
    updateAnalyzeState();
    field().focus();
  });
  let currentAnalysisController = null;
  const cancelBtn = document.getElementById("cancelAnalyzeButton");
  if (cancelBtn) {
    cancelBtn.addEventListener("click", () => {
      if (currentAnalysisController) {
        currentAnalysisController.abort();
      }
    });
  }

  document
    .getElementById("analyzeButton")
    .addEventListener("click", async () => {
      const value = field().value.trim();
      if (!value) {
        message.textContent =
          "Add a news URL or article text before analyzing.";
        field().focus();
        return;
      }
      if (inputType === "url") {
        try {
          new URL(value);
        } catch {
          message.textContent =
            "Enter a valid article URL, including https://.";
          field().focus();
          return;
        }
      }
      if (!terms.checked) {
        message.textContent =
          "Please agree to the Terms & Conditions to continue.";
        terms.focus();
        return;
      }
      message.textContent = "";
      analyzeButton.disabled = true;
      overlay.classList.add("visible");
      overlay.setAttribute("aria-hidden", "false");
      overlay
        .querySelectorAll(".loading-step")
        .forEach((step, i) =>
          setTimeout(() => step.classList.add("complete"), i * 520),
        );

      currentAnalysisController = new AbortController();

      try {
        const result = await analyzeNews(value, inputType, currentAnalysisController.signal);
        sessionStorage.setItem(
          "tndAnalysisResult",
          JSON.stringify({ ...result, input: value }),
        );
        setTimeout(() => (location.href = "results.html"), 1500);
      } catch (error) {
        overlay.classList.remove("visible");
        overlay.setAttribute("aria-hidden", "true");
        analyzeButton.disabled = false;
        updateAnalyzeState();

        if (error.isUserCancelled || (error.name === "AbortError" && error.message.includes("cancelled"))) {
          message.textContent = "Analysis was cancelled.";
        } else if (error.isTimeout || error.name === "TimeoutError") {
          message.textContent =
            "The analysis request timed out. Please try again or test a shorter excerpt.";
        } else if (error.status === 400) {
          message.textContent = error.message || "Invalid article URL or request format.";
        } else if (error.status === 422) {
          message.textContent = error.message || "The webpage did not contain enough extractable article content.";
        } else if (error.status === 502) {
          message.textContent = error.message || "Unable to fetch the external webpage.";
        } else if (error.status === 503) {
          message.textContent = error.message || "The local AI service (Ollama) is unavailable.";
        } else if (error instanceof TypeError || (error.name === "AbortError" && !error.isUserCancelled)) {
          message.textContent =
            "Unable to connect to the TND analysis server. Please make sure the backend is running at http://127.0.0.1:8000 and try again.";
        } else {
          message.textContent =
            error.message || "The analysis server returned an unexpected response. Please try again.";
        }
      } finally {
        currentAnalysisController = null;
      }
    });
}
function createClaim(claim, index) {
  const article = document.createElement("article");
  article.className = "claim";
  const content = document.createElement("div");
  const number = document.createElement("span");
  number.className = "claim-number";
  number.textContent = `Claim ${String(index + 1).padStart(2, "0")}`;
  const quote = document.createElement("blockquote");
  quote.textContent = `“${claim.text}”`;

  const status = document.createElement("span");
  const verStatus = (claim.verificationStatus || claim.verification_status || "").toUpperCase();
  let statusText = claim.status || "Needs Verification";
  let statusClass = "needs";

  if (verStatus === "SUPPORTED" || claim.status === "Supported") {
    statusText = "Supported";
    statusClass = "supported";
  } else if (verStatus === "CONTRADICTED") {
    statusText = "Contradicted";
    statusClass = "warning";
  } else if (verStatus === "MIXED_EVIDENCE") {
    statusText = "Mixed Evidence";
    statusClass = "needs";
  } else {
    statusText = "Needs Verification";
    statusClass = "needs";
  }

  status.className = `status ${statusClass}`;
  status.textContent = statusText;
  content.append(number, quote, status);

  const button = document.createElement("button");
  button.className = "evidence-button";
  button.type = "button";
  button.setAttribute("aria-expanded", "false");
  button.append("View Evidence ");
  const symbol = document.createElement("span");
  symbol.textContent = "+";
  button.append(symbol);

  const evidence = document.createElement("div");
  evidence.className = "evidence";
  evidence.hidden = true;

  if (Array.isArray(claim.evidence) && claim.evidence.length > 0) {
    claim.evidence.forEach((item) => {
      const itemEl = document.createElement("div");
      itemEl.className = "evidence-item";
      itemEl.style.marginBottom = "0.75rem";

      const heading = document.createElement("p");
      heading.style.fontWeight = "600";
      heading.style.marginBottom = "0.25rem";
      heading.textContent = `${item.source || "News Source"}: ${item.description || "Article lead"}`;
      itemEl.append(heading);

      if (item.relevance) {
        const relTag = document.createElement("span");
        relTag.className = `status ${item.relevance === "SUPPORTS" ? "supported" : item.relevance === "CONTRADICTS" ? "warning" : "needs"}`;
        relTag.style.marginRight = "0.5rem";
        relTag.style.fontSize = "0.75rem";
        relTag.textContent = item.relevance.replace(/_/g, " ");
        itemEl.append(relTag);
      }

      if (item.url) {
        const link = document.createElement("a");
        link.href = item.url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = "View source ↗";
        link.style.fontSize = "0.85rem";
        link.style.color = "var(--color-primary, #2563eb)";
        itemEl.append(link);
      }

      if (item.explanation) {
        const expl = document.createElement("p");
        expl.style.fontSize = "0.875rem";
        expl.style.marginTop = "0.25rem";
        expl.style.opacity = "0.85";
        expl.textContent = item.explanation;
        itemEl.append(expl);
      }

      evidence.append(itemEl);
    });
  } else {
    const emptyP = document.createElement("p");
    emptyP.style.fontStyle = "italic";
    emptyP.style.opacity = "0.75";
    emptyP.textContent = "No external evidence leads retrieved for this claim.";
    evidence.append(emptyP);
  }

  button.addEventListener("click", () => {
    const open = button.getAttribute("aria-expanded") === "true";
    button.setAttribute("aria-expanded", String(!open));
    button.firstChild.nodeValue = open ? "View Evidence " : "Hide Evidence ";
    symbol.textContent = open ? "+" : "–";
    evidence.hidden = open;
  });

  article.append(content, button, evidence);
  return article;
}

function renderResults(result) {
  document.getElementById("riskScore").textContent = result.riskScore ?? "Not available";
  document.getElementById("resultInput").textContent = result.input || result.title || "Not available";
  document.getElementById("riskLabel").textContent = result.riskLabel || "Not available";
  document.getElementById("assessmentNote").textContent =
    result.assessmentNote || "This result is an AI-assisted assessment.";
  document.getElementById("sourceValue").textContent = result.source || "Not available";
  document.getElementById("publisherValue").textContent = result.publisher || "Not available";
  document.getElementById("reliabilityValue").textContent =
    result.sourceReliability || "Not available";
  const meter = document.getElementById("riskMeter");
  meter.setAttribute("aria-label", `Misinformation risk: ${result.riskScore} percent`);
  meter.querySelector("span").style.width = `${result.riskScore}%`;
  const signalList = document.getElementById("signalList");
  (Array.isArray(result.signals) ? result.signals : []).forEach((signal) => {
    const item = document.createElement("li");
    item.className = signal.status || "";
    item.textContent = signal.name || "Not available";
    signalList.append(item);
  });
  const claimsList = document.getElementById("claimsList");
  if (Array.isArray(result.claims) && result.claims.length > 0) {
    result.claims.forEach((claim, index) =>
      claimsList.append(createClaim(claim, index)),
    );
  } else {
    const noClaimsP = document.createElement("p");
    noClaimsP.style.fontStyle = "italic";
    noClaimsP.style.opacity = "0.75";
    noClaimsP.style.padding = "1rem 0";
    noClaimsP.textContent = "No verifiable factual claims were extracted from this content.";
    claimsList.append(noClaimsP);
  }
}


if (document.getElementById("riskScore")) {
  const saved = sessionStorage.getItem("tndAnalysisResult");
  let result;
  try {
    result = saved ? JSON.parse(saved) : null;
  } catch {
    result = null;
  }
  const hasResult =
    result &&
    typeof result === "object" &&
    typeof result.title === "string" &&
    typeof result.riskScore === "number";
  document.getElementById("resultsContent").hidden = !hasResult;
  document.getElementById("resultFallback").hidden = hasResult;
  if (hasResult) renderResults(result);
  document.getElementById("analyzeAnother").addEventListener("click", () => {
    sessionStorage.removeItem("tndAnalysisResult");
  });
}
