// Run the Kramnik Nibbler's own move generator under node: perft on FENs (EPIC NN, sprint NN-2).
// node tools/nibbler_perft.js <nibbler resources/app/renderer dir> <depth> <FEN>
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const [dir, depth, ...fenParts] = process.argv.slice(2);
let code = "var KRAMNIK = true;\n";
for (const f of ["20_utils.js", "30_point.js", "31_sliders.js", "40_position.js", "41_fen.js", "42_perft.js"]) {
  code += fs.readFileSync(path.join(dir, f), "utf8").replace(/^"use strict";/m, "") + "\n";
}
code += "this.__result = perft(LoadFEN(" + JSON.stringify(fenParts.join(" ")) + "), " + Number(depth) + ", false);";
const ctx = {console};
vm.createContext(ctx);
vm.runInContext(code, ctx);
console.log(ctx.__result);
