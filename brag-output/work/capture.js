// Usage: node capture.js <outDir> [t1,t2,...]   (no times = every frame)
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const FPS = 30, DURATION = 21.5;
const outDir = process.argv[2];
const times = process.argv[3]
  ? process.argv[3].split(",").map(Number)
  : Array.from({ length: Math.round(FPS * DURATION) }, (_, i) => i / FPS);

(async () => {
  fs.mkdirSync(outDir, { recursive: true });
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on("pageerror", (e) => console.error("pageerror:", e.message));
  await page.goto("http://127.0.0.1:8765/brag-output/work/comp.html", { waitUntil: "networkidle" });
  console.log(JSON.stringify(await page.evaluate(() => window.setup())));
  for (let i = 0; i < times.length; i++) {
    await page.evaluate((t) => window.render(t), times[i]);
    await page.evaluate(() => new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r))));
    const name = process.argv[3] ? `t${times[i].toFixed(2)}.png` : `f${String(i).padStart(4, "0")}.png`;
    await page.screenshot({ path: path.join(outDir, name) });
    if (i % 60 === 0) console.log("frame", i);
  }
  await browser.close();
})();
