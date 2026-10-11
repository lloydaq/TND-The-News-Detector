const API_BASE_URL =
  (typeof window !== "undefined" && window.TND_API_BASE_URL) ||
  "http://127.0.0.1:8000";

async function analyzeNews(input, inputType, externalSignal = null) {
  let response;
  const timeoutMs = 1200000;
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
      const timeoutErr = new Error("The analysis request timed out (120s).");
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

  if (
    !result ||
    typeof result.title !== "string" ||
    typeof result.source !== "string" ||
    typeof result.publisher !== "string" ||
    typeof result.riskScore !== "number" ||
    typeof result.riskLabel !== "string" ||
    typeof result.sourceReliability !== "string" ||
    !Array.isArray(result.signals) ||
    !Array.isArray(result.claims) ||
    result.signals.some(
      (signal) =>
        !signal ||
        typeof signal.name !== "string" ||
        typeof signal.status !== "string",
    ) ||
    result.claims.some(
      (claim) =>
        !claim ||
        typeof claim.id !== "number" ||
        typeof claim.text !== "string" ||
        typeof claim.status !== "string" ||
        !Array.isArray(claim.evidence),
    )
  ) {
    throw new Error("The analysis server returned an invalid response.");
  }
  return result;
}

