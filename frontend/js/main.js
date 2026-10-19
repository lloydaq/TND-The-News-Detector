const systemTheme = window.matchMedia("(prefers-color-scheme: dark)");
let themePreference = localStorage.getItem("tnd-theme") || "system";

function applyTheme(preference) {
  themePreference = preference;
  const resolved = preference === "system" ? (systemTheme.matches ? "dark" : "light") : preference;
  document.documentElement.dataset.theme = resolved;
  document.documentElement.dataset.themePreference = preference;
  document.querySelectorAll("[data-theme-choice]").forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.themeChoice === preference)));
  document.querySelectorAll(".theme-logo").forEach((logo) => {
    logo.src = resolved === "dark" ? logo.dataset.logoDark : logo.dataset.logoLight;
  });
}

applyTheme(themePreference);
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-theme-choice]");
  if (!button) return;
  const preference = button.dataset.themeChoice;
  localStorage.setItem("tnd-theme", preference);
  applyTheme(preference);
});
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
  const MAX_CONTENT_LENGTH = 100000;
  const loadingSteps = overlay.querySelectorAll(".loading-step");
  let loadingStepTimers = [];
  const resetLoadingSteps = () => {
    loadingStepTimers.forEach(clearTimeout);
    loadingStepTimers = [];
    loadingSteps.forEach((step) => step.classList.remove("complete"));
  };
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
      // Typing re-enables the button via updateAnalyzeState, so the disabled
      // state alone cannot prevent a second request while one is in flight.
      if (currentAnalysisController) return;
      const value = field().value.trim();
      if (!value) {
        message.textContent =
          "Add a news URL or article text before analyzing.";
        field().focus();
        return;
      }
      if (value.length > MAX_CONTENT_LENGTH) {
        message.textContent =
          "This content is too long. Please submit at most 100,000 characters.";
        field().focus();
        return;
      }
      if (inputType === "url") {
        try {
          const { protocol } = new URL(value);
          if (protocol !== "http:" && protocol !== "https:") throw Error();
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
      resetLoadingSteps();
      loadingSteps.forEach((step, i) =>
        loadingStepTimers.push(
          setTimeout(() => step.classList.add("complete"), i * 520),
        ),
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
        resetLoadingSteps();
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
        } else if (error.status === 413) {
          message.textContent = error.message || "This content is too large to analyze.";
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
  } else if (verStatus === "MIXED" || verStatus === "MIXED_EVIDENCE") {
    statusText = "Mixed Evidence";
    statusClass = "needs";
  } else if (verStatus === "INSUFFICIENT_EVIDENCE" || verStatus === "UNVERIFIED") {
    statusText = "Insufficient Evidence";
    statusClass = "needs";
  } else if (verStatus === "UNVERIFIABLE") {
    statusText = "Unable to Verify";
    statusClass = "needs";
  } else {
    statusText = "Needs Verification";
    statusClass = "needs";
  }

  status.className = `status ${statusClass}`;
  status.textContent = statusText;
  content.append(number, quote, status);

  const evidence = document.createElement("div");
  evidence.className = "evidence";
  const hasEvidence = Array.isArray(claim.evidence) && claim.evidence.length > 0;
  evidence.hidden = hasEvidence;

  if (hasEvidence) {
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
        try {
          const sourceUrl = new URL(item.url);
          if (sourceUrl.protocol === "http:" || sourceUrl.protocol === "https:") {
            const link = document.createElement("a");
            link.href = sourceUrl.href;
            link.target = "_blank";
            link.rel = "noopener noreferrer";
            link.textContent = "View source ↗";
            link.style.fontSize = "0.85rem";
            link.style.color = "var(--accent)";
            itemEl.append(link);
          }
        } catch {
          // Ignore malformed persisted evidence URLs.
        }
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
    emptyP.textContent =
      verStatus === "INSUFFICIENT_EVIDENCE" || verStatus === "UNVERIFIED"
        ? "No sufficient supporting evidence was retrieved, so this claim remains unverified."
        : verStatus === "UNVERIFIABLE"
          ? "This claim could not be verified because the verification service did not return a usable result."
          : "No external evidence leads retrieved for this claim.";
    evidence.append(emptyP);
  }

  if (hasEvidence) {
    const button = document.createElement("button");
    button.className = "evidence-button";
    button.type = "button";
    button.setAttribute("aria-expanded", "false");
    button.append("View Evidence ");
    const symbol = document.createElement("span");
    symbol.textContent = "+";
    button.append(symbol);
    button.addEventListener("click", () => {
      const open = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", String(!open));
      button.firstChild.nodeValue = open ? "View Evidence " : "Hide Evidence ";
      symbol.textContent = open ? "+" : "–";
      evidence.hidden = open;
    });
    article.append(content, button, evidence);
  } else {
    article.append(content, evidence);
  }
  return article;
}

// Maps backend degradationReasons (see analyzer.py and ollama_client.py) to
// reader-facing text. Order matters: the specific cases come first.
function friendlyDegradationReason(reason) {
  const text = typeof reason === "string" ? reason.toLowerCase() : "";
  const provider = text.startsWith("gnews:") ? "GNews" : text.startsWith("gdelt:") ? "GDELT" : "";
  const evidenceSource = provider ? `The ${provider} evidence source` : "An evidence source";
  if (text.includes("not configured")) return `${evidenceSource} is not configured.`;
  if (text.includes("rate limit")) return `${evidenceSource} rate limit was reached.`;
  if (text.includes("authentication")) return `${evidenceSource} could not authenticate.`;
  if (text.includes("quota")) return `${evidenceSource} quota was exhausted.`;
  if (text.includes("no results")) return `${evidenceSource} returned no results for at least one claim.`;
  if (text.includes("characters of the content were analyzed")) {
    return "The content was long, so only the first part was analyzed.";
  }
  if (text.includes("deadline")) return "The analysis time limit was reached before every claim was checked.";
  if (text.includes("extraction")) return "Article extraction was incomplete.";
  if (text.includes("fabricated")) return "The verifier referred to evidence that was not retrieved, so it was ignored.";
  if (text.startsWith("ollama")) {
    if (text.includes("timed out")) return "The local AI model (Ollama) timed out.";
    if (text.includes("model is unavailable")) return "The configured AI model is not installed in Ollama.";
    if (text.includes("connection failed")) return "The local AI service (Ollama) could not be reached.";
    return "The local AI service (Ollama) returned an unusable response.";
  }
  if (provider && text.includes("timed out")) return `${evidenceSource} timed out.`;
  if (provider && (text.includes("network") || text.includes("request failed"))) {
    return `${evidenceSource} could not be reached.`;
  }
  if (provider && text.includes("malformed")) return `${evidenceSource} returned unusable data.`;
  if (text.includes("invalid") || text.includes("incomplete")) {
    return "Part of the AI output was unusable and was left out.";
  }
  if (text.includes("verification service unavailable")) return "Evidence verification was unavailable.";
  return "Some analysis services were unavailable.";
}

function riskLevel(result) {
  const signals = Array.isArray(result.signals) ? result.signals : [];
  const claims = Array.isArray(result.claims) ? result.claims : [];
  // A degraded result with no signals and no claims means the AI analysis never
  // produced anything; the backend's baseline score is not an assessment.
  if (result.analysisStatus === "DEGRADED" && !signals.length && !claims.length) {
    return "unassessed";
  }
  return { "Low Risk": "low", "Needs Verification": "moderate", "High Risk": "high" }[
    result.riskLabel
  ] || "moderate";
}

function renderResults(result) {
  const level = riskLevel(result);
  const assessed = level !== "unassessed";
  document.querySelector(".risk-summary").dataset.level = level;
  document.getElementById("riskScore").textContent = assessed ? result.riskScore ?? "Not available" : "—";
  document.getElementById("resultInput").textContent = result.input || result.title || "Not available";
  document.getElementById("riskLabel").textContent = assessed
    ? result.riskLabel || "Not available"
    : "Not assessed";
  document.getElementById("sourceValue").textContent = result.source || "Not available";
  document.getElementById("publisherValue").textContent = result.publisher || "Not available";
  document.getElementById("reliabilityValue").textContent =
    result.sourceReliability || "Not available";
  const meter = document.getElementById("riskMeter");
  meter.setAttribute(
    "aria-label",
    assessed ? `Risk score: ${result.riskScore} out of 100` : "Risk score not assessed",
  );
  meter.querySelector("span").style.width = assessed ? `${result.riskScore}%` : "0%";
  const explanation = !assessed
    ? "The AI analysis produced no signals or claims, so no risk score was calculated. See the reasons below."
    : result.analysisExplanation ||
      "This result is an AI-assisted heuristic assessment, not a probability.";
  const displayExplanation = explanation
    .replace(
      " The analysis was degraded, so the result should not be treated as a complete assessment.",
      "",
    )
    .trim();
  document.getElementById("assessmentNote").textContent = displayExplanation;

  const degradedNotice = document.getElementById("degradedNotice");
  const degradationReasons = document.getElementById("degradationReasons");
  const isDegraded = result.analysisStatus === "DEGRADED";
  degradedNotice.hidden = !isDegraded;
  degradationReasons.replaceChildren();
  if (isDegraded) {
    const reasons = Array.isArray(result.degradationReasons) && result.degradationReasons.length
      ? result.degradationReasons
      : ["Some analysis services were unavailable."];
    const friendlyReasons = [...new Set(reasons.map(friendlyDegradationReason))];
    friendlyReasons.forEach((reason) => {
      const item = document.createElement("li");
      item.textContent = reason;
      degradationReasons.append(item);
    });
  }

  const signalList = document.getElementById("signalList");
  signalList.replaceChildren();
  const signals = Array.isArray(result.signals) ? result.signals : [];
  signals.forEach((signal) => {
    const item = document.createElement("li");
    item.className = signal.status || "";
    item.textContent = signal.name || "Not available";
    signalList.append(item);
  });
  if (!signals.length) {
    const emptySignals = document.createElement("li");
    emptySignals.className = "unknown";
    emptySignals.textContent =
      "No content signals were returned by the analysis service.";
    signalList.append(emptySignals);
  }
  const claimsList = document.getElementById("claimsList");
  claimsList.replaceChildren();
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
