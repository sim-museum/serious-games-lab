/* Build the single self-contained pokerIQ.html from src/ modules.
 * Each module is browser-safe (IIFE that exposes a global; require() calls are
 * guarded behind isNode checks and never run in the browser). We inline them in
 * dependency order inside one <script>, with the CSS in one <style>.
 * Run: node build.js   ->   ../pokerIQ.html
 */
const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, 'src');
const OUT = path.join(__dirname, '..', 'pokerIQ.html');

const css = fs.readFileSync(path.join(SRC, 'styles.css'), 'utf8');
const order = ['engine.js', 'game.js', 'bots.js', 'analytics.js', 'tomlogic.js', 'tom.js', 'logfile.js', 'ui.js', 'trainers.js', 'files.js', 'prefs.js', 'claude.js', 'netplay.js', 'main.js'];
const js = order.map(f => `// ===== ${f} =====\n` + fs.readFileSync(path.join(SRC, f), 'utf8')).join('\n\n');

const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>PokerIQ — Texas Hold'em trainer</title>
<style>
${css}
</style>
</head>
<body>
<div id="app"></div>
<script>
${js}
</script>
</body>
</html>
`;

fs.writeFileSync(OUT, html);
const kb = (Buffer.byteLength(html) / 1024).toFixed(0);
console.log(`built ${path.relative(path.join(__dirname, '..', '..', '..'), OUT)} — ${kb} KB, ${html.split('\n').length} lines`);
// guard: no external resources are LOADED at page-load (truly self-contained —
// no external <script>/<link>/<img>, no CDN). Opt-in *runtime* endpoints that
// the user explicitly triggers (the Anthropic API for Claude analysis; STUN for
// WebRTC online play) are allowed — they don't make the file non-self-contained,
// they're network actions the user invokes, mirroring the desktop app's CLI /
// LAN features. Strip those known runtime hosts before scanning.
const RUNTIME_HOSTS = [
  'https://api.anthropic.com',     // Claude hand-analysis (user supplies a key)
  'https://console.anthropic.com', // referenced in help text only
  'stun:',                         // WebRTC peer connectivity (online play)
];
let scan = html;
for (const h of RUNTIME_HOSTS) scan = scan.split(h).join('runtime-endpoint');
// Match real external resources — a markup src/href pointing at a URL, a CDN
// reference, or any remaining bare http(s) URL — but NOT JS property assignments
// like `a.href = url` (the in-memory blob download).
const bad = scan.match(/(?:src|href)\s*=\s*["'](?!#)(?:https?:|\/\/)|https?:\/\/[^"'\s]|\bcdn\./gi);
if (bad) { console.error('  WARNING external refs:', bad); process.exit(1); }
console.log('  self-contained: no external resources loaded (runtime API/STUN endpoints are opt-in)');
