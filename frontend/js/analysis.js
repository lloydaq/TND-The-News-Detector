const API_BASE_URL =
  (typeof window !== "undefined" && window.TND_API_BASE_URL) ||
  "http://127.0.0.1:8000";

async function analyzeNews(input, inputType, externalSignal = null) {
  let response;
  const timeoutMs = 180000;
  const controller = new AbortController();
  let timedOut = false;

  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort(new DOMException("The analysis request timed out.", "TimeoutError"));
  }, timeoutMs);

  if (externalSignal) {
    if (externalSignal.aborted) {
      clearTimeout(timer);
      throw externalSignal.reason || new DOMException("Analysis cancelled by user.", "AbortError");
    }
    externalSignal.addEventListener("abort", () => {
      clearTimeout(timer);
      controller.abort(externalSignal.reason || new DOMException("Analysis cancelled by user.", "AbortError"));
    });
  }

  try {
    response = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ type: inputType, content: input }),
      signal: controller.signal,
    });
  } catch (error) {
    clearTimeout(timer);
    if (timedOut || error.name === "TimeoutError") {
      const timeoutErr = new Error("The analysis request timed out (180s).");
      timeoutErr.name = "TimeoutError";
      timeoutErr.isTimeout = true;
      throw timeoutErr;
    }
    if (externalSignal && externalSignal.aborted) {
      const abortErr = new Error("Analysis cancelled by user.");
      abortErr.name = "AbortError";
      abortErr.isUserCancelled = true;
      throw abortErr;
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }

  if (!response.ok) {
    let errorDetail = "";
    try {
      const errData = await response.json();
      if (errData && errData.detail) {
        errorDetail =
          typeof errData.detail === "string"
            ? errData.detail
            : JSON.stringify(errData.detail);
      }
    } catch { }
    const err = new Error(
      errorDetail || `Analysis request failed (${response.status})`
    );
    err.status = response.status;
    throw err;
  }

  let result;
  try {
    result = await response.json();
  } catch {
    throw new Error("The analysis server returned invalid JSON.");
  }

  const riskLabels = new Set(["Low Risk", "Needs Verification", "High Risk"]);
  const reliabilityValues = new Set(["Unknown", "Low", "Moderate", "High"]);
  const signalStatuses = new Set(["positive", "warning", "unknown"]);
  const claimStatuses = new Set([
    "SUPPORTED",
    "CONTRADICTED",
    "INSUFFICIENT_EVIDENCE",
    "MIXED",
    "MIXED_EVIDENCE",
    "UNVERIFIABLE",
    "UNVERIFIED",
  ]);
  if (
    !result ||
    typeof result.title !== "string" ||
    typeof result.source !== "string" ||
    typeof result.publisher !== "string" ||
    !Number.isInteger(result.riskScore) ||
    result.riskScore < 0 ||
    result.riskScore > 100 ||
    !riskLabels.has(result.riskLabel) ||
    !reliabilityValues.has(result.sourceReliability) ||
    !["COMPLETE", "DEGRADED"].includes(result.analysisStatus || "COMPLETE") ||
    (result.degradationReasons !== undefined &&
      (!Array.isArray(result.degradationReasons) ||
        result.degradationReasons.some((reason) => typeof reason !== "string"))) ||
    (result.analysisExplanation !== undefined &&
      typeof result.analysisExplanation !== "string") ||
    !Array.isArray(result.signals) ||
    !Array.isArray(result.claims) ||
    result.signals.some(
      (signal) =>
        !signal ||
        typeof signal.name !== "string" ||
        !signalStatuses.has(signal.status),
    ) ||
    result.claims.some(
      (claim) =>
        !claim ||
        typeof claim.id !== "number" ||
        typeof claim.text !== "string" ||
        typeof claim.status !== "string" ||
        !Array.isArray(claim.evidence) ||
        !claimStatuses.has(
          (claim.verificationStatus || claim.verification_status || "").toUpperCase(),
        ),
    )
  ) {
    throw new Error("The analysis server returned an invalid response.");
  }
  return result;
}
