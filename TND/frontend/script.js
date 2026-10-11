const statusText = document.getElementById("statusText");
const statusButton = document.getElementById("statusButton");

statusButton.addEventListener("click", () => {
  const states = [
    "Report generated successfully",
    "Dashboard refreshed",
    "New insights ready",
    "Project data synced",
  ];

  const nextState = states[Math.floor(Math.random() * states.length)];
  statusText.textContent = nextState;

  const subtleColors = [
    "rgba(34, 197, 94, 0.14)",
    "rgba(59, 130, 246, 0.14)",
    "rgba(168, 85, 247, 0.14)",
  ];
  const accent = subtleColors[Math.floor(Math.random() * subtleColors.length)];
  statusText.style.background = accent;
});
