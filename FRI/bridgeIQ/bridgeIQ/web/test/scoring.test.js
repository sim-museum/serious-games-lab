/* Cross-validate scoring.js against backend/scoring.py over many contracts. */
const {execFileSync}=require('child_process');
const path=require('path');
const S=require('../src/engine/scoring.js');
const ROOT=path.resolve(__dirname,'../..');
const PY=path.resolve(ROOT,'../venv/bin/python');

const SUIT={C:'CLUBS',D:'DIAMONDS',H:'HEARTS',S:'SPADES',N:'NOTRUMP'};
// Build a batch of (level,strain,doubled,redoubled,tricks,vul) cases.
const cases=[];
for(let level=1;level<=7;level++)
 for(const strain of ['C','D','H','S','N'])
  for(const dbl of [[false,false],[true,false],[false,true]])
   for(let tricks=0;tricks<=13;tricks++)
    for(const vul of [false,true])
     cases.push({level,strain,doubled:dbl[0],redoubled:dbl[1],tricks,vul});

// Expected from Python (one subprocess, JSON in/out).
const pyCode=`
import sys,json
from backend.models import Contract, Suit
from backend.scoring import calculate_contract_score, diff_to_imps
cases=json.load(sys.stdin)
S={'C':Suit.CLUBS,'D':Suit.DIAMONDS,'H':Suit.HEARTS,'S':Suit.SPADES,'N':Suit.NOTRUMP}
out=[]
for c in cases:
    con=Contract(level=c['level'],suit=S[c['strain']],doubled=c['doubled'],redoubled=c['redoubled'])
    out.append(calculate_contract_score(con,c['tricks'],c['vul']))
imps=[diff_to_imps(d) for d in [-5000,-2400,-1099,-499,-99,-19,0,19,99,499,1099,2400,5000]]
print(json.dumps({'scores':out,'imps':imps}))
`;
let py;
try{ py=execFileSync(PY,['-c',pyCode],{cwd:ROOT,input:JSON.stringify(cases)}).toString(); }
catch(e){ console.log('SKIP scoring cross-test (python unavailable):',e.message.split('\n')[0]); process.exit(0); }
const exp=JSON.parse(py);
let fails=0;
cases.forEach((c,i)=>{
  const got=S.contractScore(c.level,c.strain,c.doubled,c.redoubled,c.tricks,c.vul);
  if(got!==exp.scores[i]){ if(fails<10) console.log('MISMATCH',JSON.stringify(c),'js',got,'py',exp.scores[i]); fails++; }
});
const impDiffs=[-5000,-2400,-1099,-499,-99,-19,0,19,99,499,1099,2400,5000];
impDiffs.forEach((d,i)=>{ const g=S.diffToImps(d); if(g!==exp.imps[i]){console.log('IMP MISMATCH',d,'js',g,'py',exp.imps[i]);fails++;} });
console.log(`scoring: ${cases.length} contract cases + ${impDiffs.length} IMP cases`);
console.log(fails?`SCORING FAILS: ${fails}`:'SCORING PARITY OK');
process.exit(fails?1:0);
