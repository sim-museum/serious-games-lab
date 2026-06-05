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
const order = ['engine.js', 'game.js', 'bots.js', 'analytics.js', 'tomlogic.js', 'tom.js', 'logfile.js', 'ui.js', 'trainers.js', 'main.js'];
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
// guard: no external network references allowed (truly self-contained).
// Match real external resources — a markup src/href pointing at a URL, or any
// http(s)/cdn reference — but NOT JS property assignments like `a.href = url`
// (which we use for the in-memory blob download).
const bad = html.match(/(?:src|href)\s*=\s*["'](?!#)(?:https?:|\/\/)|https?:\/\/[^"'\s]|\bcdn\./gi);
if (bad) { console.error('  WARNING external refs:', bad); process.exit(1); }
console.log('  self-contained: no external network references');
