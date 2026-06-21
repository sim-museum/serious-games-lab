/* Validate the Bayesian estimator's invariants + convergence. RNG can't be
 * byte-matched to Python, so we check the properties the algorithm must satisfy
 * (these hold for biq's Python sampler too). Scenarios use mid-hand sizes so
 * the rejection sampler finds worlds (fully-determined 13-card hands return
 * null in both ports — the documented fall-back-to-vacant-space case). */
const B=require('../src/engine/bayes.js');
let fails=0; const ok=(c,m)=>{if(!c){console.log('FAIL:',m);fails++;}};
const honoursOf=cards=>cards.filter(c=>'AKQJ'.includes(c[1]));

// Scenario 1: E & W hidden, 26 free = all hearts + all diamonds, 13 each, no
// constraints (no rejection).
(function(){
  const free=[];for(const su of ['H','D'])for(const r of ['A','K','Q','J','T','9','8','7','6','5','4','3','2'])free.push(su+r);
  const r=B.bayesDistribution({hidden:[1,3],need:{1:13,3:13},free,honours:honoursOf(free),samples:3000,seed:7});
  ok(r&&r.samples>=2000,'s1 produced samples'); if(!r)return;
  for(const c of honoursOf(free)){const p=(r.honour[c][1]||0)+(r.honour[c][3]||0);ok(Math.abs(p-1)<1e-9,'s1 '+c+' sums to 1');}
  let sym=0;for(const c of honoursOf(free))if(Math.abs((r.honour[c][1]||0)-0.5)<0.06)sym++;
  ok(sym>=6,'s1 honours ~50/50 ('+sym+'/8)');
  for(const s of [1,3])for(const su of ['S','H','D','C']){const t=Object.values(r.length[s][su]).reduce((a,b)=>a+b,0);ok(Math.abs(t-1)<1e-9,`s1 len ${s}${su} sums 1`);}
  ok((r.length[1]['S']['0']||0)>0.999,'s1 E no spades');
})();

// Scenario 2: void respected. E void in hearts; mid-hand sizes so it samples.
(function(){
  const free=['HA','HK','DA','DK','DQ','DJ','DT','D9'];   // 2 hearts, 6 diamonds
  const r=B.bayesDistribution({hidden:[1,3],need:{1:4,3:4},voids:{1:new Set(['H'])},free,honours:honoursOf(free),samples:2000,seed:3});
  ok(r,'s2 produced'); if(!r)return;
  ok((r.honour['HA'][3]||0)>0.999 && (r.honour['HK'][3]||0)>0.999,'s2 heart honours all in W');
  ok((r.length[1]['H']['0']||0)>0.999,'s2 E always void in hearts');
  for(const c of honoursOf(free)){const p=(r.honour[c][1]||0)+(r.honour[c][3]||0);ok(Math.abs(p-1)<1e-9,'s2 '+c+' sums to 1');}
})();

// Scenario 3: suitMax cap respected. W holds at most 1 heart.
(function(){
  const free=['HA','HK','HQ','HJ','DA','DK','DQ','DJ'];   // 4 hearts, 4 diamonds
  const r=B.bayesDistribution({hidden:[1,3],need:{1:4,3:4},suitMax:{3:{H:1}},free,honours:honoursOf(free),samples:2000,seed:5});
  ok(r,'s3 produced'); if(!r)return;
  const over=Object.keys(r.length[3]['H']).some(L=>+L>1 && r.length[3]['H'][L]>0);
  ok(!over,'s3 W never holds >1 heart');
})();

// Scenario 4: HCP window respected. E limited to 0-2 HCP.
(function(){
  const free=['HA','HK','HQ','HJ','D5','D4','D3','D2'];   // honours 4+3+2+1, spots 0
  const r=B.bayesDistribution({hidden:[1,3],need:{1:4,3:4},hcp:{1:[0,2]},free,honours:honoursOf(free),samples:2000,seed:11});
  ok(r,'s4 produced'); if(!r)return;
  let eHon=0;for(const c of honoursOf(free))eHon+=(r.honour[c][1]||0);
  ok(eHon<=1.0+1e-9,'s4 E honour-points expectation ≤2 ('+eHon.toFixed(3)+' honours)');
})();

console.log(fails?`BAYES FAILS: ${fails}`:'BAYES ESTIMATOR INVARIANTS OK');
process.exit(fails?1:0);
