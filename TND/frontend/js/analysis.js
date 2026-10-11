async function analyzeNews(input, inputType) {
  let response;
  try {
    response = await fetch("http://127.0.0.1:8000/api/analyze", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ type: inputType, content: input }),
      signal: AbortSignal.timeout(10000),
    });
  } catch (error) {
    if (error.name === "TimeoutError") error.name = "AbortError";
    throw error;
  }
  if (!response.ok) {
    throw new Error(`Analysis request failed (${response.status})`);
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
