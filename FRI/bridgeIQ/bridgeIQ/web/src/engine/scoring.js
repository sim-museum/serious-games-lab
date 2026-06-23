/* scoring.js — faithful transpile of backend/scoring.py
 * (calculate_contract_score + diff_to_imps + IMP table). Validated against the
 * Python in web/test/scoring.test.js. Browser-global on BIQ; node-exported. */
(function(){
"use strict";
const IMP_TABLE=[
  [20,0],[50,1],[90,2],[130,3],[170,4],
  [220,5],[270,6],[320,7],[370,8],[430,9],
  [500,10],[600,11],[750,12],[900,13],[1100,14],
  [1300,15],[1500,16],[1750,17],[2000,18],[2250,19],
  [2500,20],[3000,21],[3500,22],[4000,23],[Infinity,24]
];
function diffToImps(diff){
  const ad=Math.abs(diff);
  for(const [t,imps] of IMP_TABLE){ if(ad<t) return diff>=0?imps:-imps; }
  return diff>=0?24:-24;
}
// strain: 'C','D','H','S','N'. doubled/redoubled: booleans. Returns score from
// the declarer's perspective (positive = made, negative = down).
function contractScore(level,strain,doubled,redoubled,tricks,vulnerable){
  const target=6+level, result=tricks-target;
  if(result<0){
    const under=-result;
    if(redoubled){
      if(vulnerable) return under>0?-(400+600*(under-1)):0;
      let s=0; for(let i=0;i<under;i++) s+= i===0?200:(i<3?400:600); return -s;
    } else if(doubled){
      if(vulnerable) return under>0?-(200+300*(under-1)):0;
      let s=0; for(let i=0;i<under;i++) s+= i===0?100:(i<3?200:300); return -s;
    } else {
      return vulnerable? -100*under : -50*under;
    }
  }
  let trick;
  if(strain==='N') trick=40+30*(level-1);
  else if(strain==='S'||strain==='H') trick=30*level;
  else trick=20*level;
  if(doubled) trick*=2;
  if(redoubled) trick*=4;
  let score=trick;
  score += trick>=100 ? (vulnerable?500:300) : 50;        // game / partscore
  if(level===6) score += vulnerable?750:500;              // small slam
  else if(level===7) score += vulnerable?1500:1000;       // grand slam
  if(doubled) score+=50;
  if(redoubled) score+=100;
  if(result>0){
    if(redoubled) score += result*(vulnerable?400:200);
    else if(doubled) score += result*(vulnerable?200:100);
    else score += result*((strain==='N'||strain==='S'||strain==='H')?30:20);
  }
  return score;
}
const api={diffToImps,contractScore,IMP_TABLE};
if(typeof module!=='undefined') module.exports=api;
if(typeof window!=='undefined') window.BIQ=Object.assign(window.BIQ||{},api);
})();
