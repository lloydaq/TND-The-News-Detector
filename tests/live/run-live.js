// Runs the live Playwright project with TND_LIVE set, on any OS shell.
const { spawnSync } = require('child_process');

const result = spawnSync('npx', ['playwright', 'test', ...process.argv.slice(2)], {
  stdio: 'inherit',
  shell: true,
  env: { ...process.env, TND_LIVE: '1' },
});
process.exit(result.status ?? 1);
