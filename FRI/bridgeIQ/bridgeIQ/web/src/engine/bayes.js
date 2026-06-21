/* bayes.js — Bayesian shape & honour estimator. Faithful transpile of
 * teaching_view.bayes_distribution: a Monte-Carlo posterior over the hidden
 * hands, sampling full deals of the unseen cards consistent with each hidden
 * seat's exact remaining count, shown voids, per-suit length caps and HCP
 * range, then aggregating per-(seat,suit) length probabilities and per-honour
 * location probabilities. Validated in web/test/bayes.test.js. */
(function(){
"use strict";
const SUITS=['S','H','D','C'];
const HONRANK={A:4,K:3,Q:2,J:1};
function mulberry32(seed){let a=seed>>>0;return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296;};}

/* opts:
 *   hidden:   [seatIdx]                       hidden seats
 *   need:     {seat:int}                      cards still to deal to each (net of fixed)
 *   voids:    {seat:Set('S'..'C')}            suits a seat is known void in
 *   suitMax:  {seat:{suit:int}}               per-suit length cap (from auction)
 *   suitMin:  {seat:{suit:int}}               per-suit length floor (default 0)
 *   hcp:      {seat:[min,max]}                HCP window (counts hcp of dealt+fixed)
 *   fixedHcp: {seat:int}                      HCP already proven in the seat (fixed cards)
 *   fixedLen: {seat:{suit:int}}              suit lengths already proven (fixed cards)
 *   free:     [card]                          unseen cards to distribute (card='Sx')
 *   honours:  [card]                          unseen honours to locate (subset of free)
 *   samples, maxAttempts, seed
 * returns {samples, length:{seat:{suit:{len:prob}}}, honour:{card:{seat:prob}}} or null */
function bayesDistribution(opts){
  const hidden=opts.hidden, free=opts.free, need=opts.need;
  const voids=opts.voids||{}, suitMax=opts.suitMax||{}, suitMin=opts.suitMin||{};
  const hcp=opts.hcp||{}, fixedHcp=opts.fixedHcp||{}, fixedLen=opts.fixedLen||{};
  const honours=opts.honours||[];
  const samples=opts.samples||120, maxAttempts=opts.maxAttempts||4000;
  const rng=mulberry32((opts.seed!=null?opts.seed:1)>>>0);
  if(!hidden.length) return null;
  let total=0; for(const s of hidden) total+=need[s];
  if(total!==free.length) return null;     // bookkeeping mismatch → caller falls back

  const lenAcc={}, honAcc={};
  for(const s of hidden){ lenAcc[s]={}; for(const su of SUITS) lenAcc[s][su]={}; }
  for(const c of honours){ honAcc[c]={}; }
  const smax=(s,su)=> (suitMax[s]&&suitMax[s][su]!=null)?suitMax[s][su]:13;
  const smin=(s,su)=> (suitMin[s]&&suitMin[s][su]!=null)?suitMin[s][su]:0;
  const flen=(s,su)=> (fixedLen[s]&&fixedLen[s][su])||0;

  let valid=0, attempts=0;
  while(valid<samples && attempts<maxAttempts){
    attempts++;
    const hand={}, perSuit={}, cap={};
    for(const s of hidden){ hand[s]=[]; perSuit[s]={S:flen(s,'S'),H:flen(s,'H'),D:flen(s,'D'),C:flen(s,'C')}; cap[s]=need[s]; }
    const pool=free.slice();
    // Fisher-Yates with seeded rng
    for(let i=pool.length-1;i>0;i--){const j=Math.floor(rng()*(i+1));[pool[i],pool[j]]=[pool[j],pool[i]];}
    let ok=true;
    for(const c of pool){
      const su=c[0];
      const opt=hidden.filter(s=>cap[s]>0 && !(voids[s]&&voids[s].has(su)) && perSuit[s][su]<smax(s,su));
      if(!opt.length){ok=false;break;}
      const s=opt[Math.floor(rng()*opt.length)];
      hand[s].push(c); perSuit[s][su]++; cap[s]--;
    }
    if(!ok) continue;
    if(hidden.some(s=>cap[s]!==0)) continue;
    // acceptance: HCP window + per-suit min
    let good=true;
    for(const s of hidden){
      if(hcp[s]){
        let h=fixedHcp[s]||0; for(const c of hand[s]) h+=HONRANK[c[1]]||0;
        if(h<hcp[s][0]||h>hcp[s][1]){good=false;break;}
      }
      for(const su of SUITS){ if(perSuit[s][su]<smin(s,su)){good=false;break;} }
      if(!good)break;
    }
    if(!good) continue;
    valid++;
    for(const s of hidden){
      for(const su of SUITS){ const L=perSuit[s][su]; lenAcc[s][su][L]=(lenAcc[s][su][L]||0)+1; }
      const ids=new Set(hand[s]);
      for(const hc of honours){ if(ids.has(hc)) honAcc[hc][s]=(honAcc[hc][s]||0)+1; }
    }
  }
  if(valid<Math.max(8,Math.floor(samples/5))) return null;
  const length={}, honour={};
  for(const s of hidden){ length[s]={}; for(const su of SUITS){ length[s][su]={}; for(const L in lenAcc[s][su]) length[s][su][L]=lenAcc[s][su][L]/valid; } }
  for(const c of honours){ honour[c]={}; for(const s in honAcc[c]) honour[c][s]=honAcc[c][s]/valid; }
  return {samples:valid, length, honour};
}

// honour confidence colour (mirrors teaching_view._honour_color)
function honourColor(p){ return p>0.85?'green':p>0.70?'orange':p>0.55?'red':null; }

const api={bayesDistribution,honourColor};
if(typeof module!=='undefined') module.exports=api;
if(typeof window!=='undefined') window.BIQ=Object.assign(window.BIQ||{},api);
})();
