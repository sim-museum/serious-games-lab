#!/usr/bin/env node
/* build.js — assembles the validated engine modules in web/src/engine/ into the
 * single-file biq.html, replacing the region between the ENGINE markers. As more
 * of the Python engine is ported (bidder, DDS, no-peek cardplay, auction
 * inference, teaching view), each lands as a module here and is injected by this
 * build. Run: `node web/build.js` (or `npm run build`). */
const fs=require('fs'), path=require('path');
const ROOT=path.resolve(__dirname,'..');
const HTML=path.join(ROOT,'biq.html');
const ENGDIR=path.join(__dirname,'src','engine');
const START='/*ENGINE-START*/', END='/*ENGINE-END*/';

// deterministic order so the build is stable
const ORDER=['models.js','scoring.js','auction.js','bayes.js','bidder.js','dds.js','play.js'];
const files=fs.readdirSync(ENGDIR).filter(f=>f.endsWith('.js'))
  .sort((a,b)=>{const ia=ORDER.indexOf(a),ib=ORDER.indexOf(b);return (ia<0?99:ia)-(ib<0?99:ib)||a.localeCompare(b);});
const engine=files.map(f=>`/* --- engine/${f} --- */\n`+fs.readFileSync(path.join(ENGDIR,f),'utf8').trim()).join('\n\n');

let html=fs.readFileSync(HTML,'utf8');
const s=html.indexOf(START), e=html.indexOf(END);
if(s<0||e<0){console.error('ENGINE markers not found in biq.html');process.exit(1);}
html=html.slice(0,s+START.length)+'\n'+engine+'\n'+html.slice(e);
fs.writeFileSync(HTML,html);
console.log('built biq.html — injected '+files.length+' engine module(s): '+files.join(', '));
