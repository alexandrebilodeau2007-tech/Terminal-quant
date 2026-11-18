/* ===================== GRAPHIQUES (Lightweight Charts, template gris/orange + SMMA 50/200) ===================== */
const TEMPLATES = {
  "Devises I":   {tf:"60", syms:["DXY","EURUSD","GBPUSD","USDJPY"]},
  "Devises II":  {tf:"60", syms:["USDCAD","AUDUSD","NZDUSD","USDCHF"]},
  "Croisées I":  {tf:"60", syms:["EURJPY","GBPJPY","EURGBP","AUDJPY"]},
  "Croisées II": {tf:"60", syms:["EURCHF","CADJPY","AUDNZD","EURAUD"]},
  "Matières premières": {tf:"D", syms:["GOLD","SILVER","WTI","BRENT","NATGAS","COPPER","WHEAT","CORN"]},
  "Indices boursiers":  {tf:"D", syms:["SPX","NDX","DJI","TSX","DAX","FTSE","NIKKEI","ASX200"]},
  "Taux & macro":{tf:"D", syms:["US10Y","US2Y","VIX","GOLD"]},
};
const UP="#b2b5be", DOWN="#f7931a", C50="#4a90ff", C200="#f5c542";
let CH = Object.assign({tpl:"Devises I", layout:4, tf:"60", syms:TEMPLATES["Devises I"].syms.slice(), custom:{}}, store.get("chartsV2",{}));
let SYMS=[], LC=[], chTimer=null, chFull=false;
function saveCH(){ store.set("chartsV2",CH); }

function smma(vals,n){ const out=new Array(vals.length).fill(null); if(vals.length<n) return out; let s=0; for(let i=0;i<n;i++) s+=vals[i]; let p=s/n; out[n-1]=p; for(let i=n;i<vals.length;i++){ p=(p*(n-1)+vals[i])/n; out[i]=p; } return out; }
function fmtP(v,d){ return v==null?"—":Number(v).toLocaleString("fr-CA",{minimumFractionDigits:d,maximumFractionDigits:d}); }

function tplOptions(){
  const names=[...Object.keys(TEMPLATES),...Object.keys(CH.custom)];
  $("#chTpl").innerHTML = names.map(n=>`<option ${n===CH.tpl?"selected":""}>${esc(n)}</option>`).join("") + `<option value="__custom" ${CH.tpl==="__custom"?"selected":""}>Perso (non enregistré)</option>`;
  $("#chLayout").value=String(CH.layout); $("#tf").value=CH.tf;
}
function applyTpl(name){
  const t=TEMPLATES[name]||CH.custom[name]; if(!t) return;
  CH.tpl=name; CH.tf=t.tf||CH.tf; CH.syms=t.syms.slice(); CH.layout=t.layout||Math.min(8,Math.max(1,t.syms.length));
  if(![1,2,4,6,8].includes(CH.layout)) CH.layout=t.syms.length>6?8:t.syms.length>4?6:t.syms.length>2?4:t.syms.length>1?2:1;
}
async function renderCharts(){
  if(!window.LightweightCharts){ setTimeout(renderCharts,300); return; }
  if(!SYMS.length){ try{ SYMS=(await api("/api/symbols")).symbols; }catch{} }
  tplOptions();
  stopCharts();
  const n=CH.layout; while(CH.syms.length<n) CH.syms.push("EURUSD");
  const box=$("#charts"); box.className="charts l"+n;
  box.innerHTML = Array.from({length:n},(_,i)=>`<div class="chartbox" id="ch${i}">
      <div class="chhead"><input class="chsym" list="symlist" value="${esc(CH.syms[i])}" data-i="${i}" spellcheck="false">
        <span class="chname" id="chn${i}"></span><span class="chlast mono" id="chl${i}"></span>
        <span class="chlegend mono"><i style="background:${C50}"></i>SMMA 50 <i style="background:${C200}"></i>SMMA 200</span>
        <button class="chip chmax" data-i="${i}" title="Agrandir">⤢</button></div>
      <div class="chplot" id="chp${i}"></div></div>`).join("")
    + `<datalist id="symlist">${SYMS.map(s=>`<option value="${s.code}">${esc(s.name)}</option>`).join("")}</datalist>`;
  LC = CH.syms.slice(0,n).map((s,i)=>buildChart(i,s));
  chTimer=setInterval(()=>LC.forEach(c=>c&&c.refresh()), ["5","15"].includes(CH.tf)?20000:60000);
}
function stopCharts(){ if(chTimer){clearInterval(chTimer);chTimer=null;} LC.forEach(c=>c&&c.destroy()); LC=[]; }
/* Moteur commun : même template partout (fond noir, gris/orange, SMMA 50/200). */
function createLC(el, opts){
  const tfOf=()=>typeof opts.tf==="function"?opts.tf():opts.tf;
  const chart=LightweightCharts.createChart(el,{layout:{background:{type:"solid",color:"#000"},textColor:"#9aa4b1",fontFamily:"'IBM Plex Mono',monospace",fontSize:11},
    grid:{vertLines:{color:"#15181d"},horzLines:{color:"#15181d"}},rightPriceScale:{borderColor:"#262a30",scaleMargins:{top:0.08,bottom:0.08}},
    timeScale:{borderColor:"#262a30",timeVisible:!["D","W"].includes(tfOf()),secondsVisible:false,rightOffset:4},
    crosshair:{mode:0,vertLine:{color:"#555",labelBackgroundColor:"#2a2e39"},horzLine:{color:"#555",labelBackgroundColor:"#2a2e39"}},
    localization:{locale:"fr-CA"},handleScroll:true,handleScale:true});
  const candles=chart.addCandlestickSeries({upColor:UP,downColor:DOWN,borderUpColor:UP,borderDownColor:DOWN,wickUpColor:UP,wickDownColor:DOWN});
  const s50=chart.addLineSeries({color:C50,lineWidth:1,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false});
  const s200=chart.addLineSeries({color:C200,lineWidth:1,priceLineVisible:false,lastValueVisible:false,crosshairMarkerVisible:false});
  const ro=new ResizeObserver(()=>{ if(el.clientWidth) chart.applyOptions({width:el.clientWidth,height:el.clientHeight}); }); ro.observe(el);
  const obj={chart,sym:opts.sym,candles,s50,s200,ro,first:true,dead:false,timer:null,
    destroy(){ if(this.dead) return; this.dead=true; clearInterval(this.timer); try{ro.disconnect();chart.remove()}catch{} },
    setTf(){ chart.applyOptions({timeScale:{timeVisible:!["D","W"].includes(tfOf())}}); this.first=true; this.refresh(); },
    async refresh(){
      if(this.dead) return;
      if(!el.isConnected){ this.destroy(); return; }
      const tf=tfOf();
      try{
        const d=await api(`/api/ohlc?symbol=${encodeURIComponent(this.sym)}&interval=${tf}`);
        const off=["D","W"].includes(tf)?0:-new Date().getTimezoneOffset()*60; // heure locale pour l'axe
        const bars=d.bars.map(b=>({time:b.t+off,open:b.o,high:b.h,low:b.l,close:b.c}));
        if(this.dead) return;
        candles.setData(bars);
        const closes=d.bars.map(b=>b.c);
        const m50=smma(closes,50), m200=smma(closes,200);
        s50.setData(bars.map((b,k)=>m50[k]==null?null:{time:b.time,value:m50[k]}).filter(Boolean));
        s200.setData(bars.map((b,k)=>m200[k]==null?null:{time:b.time,value:m200[k]}).filter(Boolean));
        const dec=d.decimals??2; candles.applyOptions({priceFormat:{type:"price",precision:dec,minMove:Math.pow(10,-dec)}});
        const last=closes[closes.length-1], prev=d.prev_close||closes[closes.length-2];
        const chg=prev?((last/prev-1)*100):null;
        opts.onInfo&&opts.onInfo({name:d.name||this.sym,html:`${fmtP(last,dec)} <span class="${chg>=0?"pos":"neg"}">${chg==null?"":(chg>=0?"+":"")+chg.toFixed(2)+"%"}</span>`});
        if(this.first){ chart.timeScale().setVisibleLogicalRange({from:Math.max(0,bars.length-160),to:bars.length+4}); this.first=false; }
      }catch(e){ opts.onInfo&&opts.onInfo({name:this.sym,html:`<span class="neg">${esc(e.message.slice(0,70))}</span>`}); }
    }};
  obj.refresh();
  if(opts.every) obj.timer=setInterval(()=>{ if(!document.hidden) obj.refresh(); }, opts.every);
  return obj;
}
function buildChart(i,sym){
  const el=$("#chp"+i); if(!el) return null;
  return createLC(el,{sym,tf:()=>CH.tf,onInfo:({name,html})=>{ const n=$("#chn"+i), l=$("#chl"+i); if(n) n.textContent=name; if(l) l.innerHTML=html; }});
}

/* Graphique autonome (onglet DEVISES, etc.) : même template, avec choix de l'unité de temps. */
const MINI_TF=[["15","15m"],["60","1h"],["240","4h"],["D","J"],["W","S"]];
function mountChart(box, sym, tf){
  if(!box) return null;
  if(!window.LightweightCharts){ setTimeout(()=>mountChart(box,sym,tf),300); return null; }
  if(box._lc) box._lc.destroy();
  tf=tf||store.get("miniTf","240");
  box.innerHTML=`<div class="chartbox mini"><div class="chhead"><b class="mono" style="font-size:12px">${esc(sym)}</b>
      <span class="chname"></span><span class="chlast mono"></span>
      <span class="chlegend mono"><i style="background:${C50}"></i>SMMA 50 <i style="background:${C200}"></i>SMMA 200</span>
      <span class="chips minitf">${MINI_TF.map(([k,l])=>`<button class="chip ${k===tf?"on":""}" data-tf="${k}">${l}</button>`).join("")}</span>
      <button class="chip" data-open title="Ouvrir dans GRAPHIQUES">⤢</button></div><div class="chplot"></div></div>`;
  let cur=tf;
  const lc=createLC(box.querySelector(".chplot"),{sym,tf:()=>cur,every:60000,
    onInfo:({name,html})=>{ box.querySelector(".chname").textContent=name; box.querySelector(".chlast").innerHTML=html; }});
  box._lc=lc;
  box.querySelector(".minitf").onclick=e=>{ const b=e.target.closest("button"); if(!b) return; cur=b.dataset.tf; store.set("miniTf",cur);
    box.querySelectorAll(".minitf button").forEach(x=>x.classList.toggle("on",x===b)); lc.setTf(); };
  box.querySelector("[data-open]").onclick=()=>{ CH.syms[0]=sym; CH.tf=cur; CH.layout=1; CH.tpl="__custom"; saveCH(); show("graphiques"); };
  return lc;
}
window.mountChart=mountChart;

$("#v-graphiques").addEventListener("change",e=>{
  const t=e.target;
  if(t.classList.contains("chsym")){ const i=+t.dataset.i; const v=t.value.trim().toUpperCase().replace("/",""); if(!v) return; CH.syms[i]=v; CH.tpl="__custom"; saveCH(); tplOptions(); const c=LC[i]; if(c){c.sym=v;c.first=true;c.refresh();} }
  else if(t.id==="chTpl"){ if(t.value!=="__custom"){ applyTpl(t.value); saveCH(); renderCharts(); } }
  else if(t.id==="chLayout"){ CH.layout=+t.value; CH.tpl="__custom"; saveCH(); renderCharts(); }
  else if(t.id==="tf"){ CH.tf=t.value; saveCH(); renderCharts(); }
});
$("#v-graphiques").addEventListener("click",e=>{
  const b=e.target.closest("button"); if(!b) return;
  if(b.id==="chSave"){ const name=prompt("Nom du modèle :",CH.tpl==="__custom"?"Mon modèle":CH.tpl); if(!name) return; CH.custom[name]={tf:CH.tf,layout:CH.layout,syms:CH.syms.slice(0,CH.layout)}; CH.tpl=name; saveCH(); tplOptions(); toast("Modèle enregistré"); }
  else if(b.id==="chFull"){ toggleFull(); }
  else if(b.classList.contains("chmax")){ const box=b.closest(".chartbox"); box.classList.toggle("max"); $("#charts").classList.toggle("hasmax",box.classList.contains("max")); }
});
function toggleFull(){
  chFull=!chFull; document.body.classList.toggle("chfull",chFull); $("#chFull").textContent=chFull?"✕":"⛶";
  const sec=$("#v-graphiques");
  if(chFull && sec.requestFullscreen) sec.requestFullscreen().catch(()=>{});
  else if(!chFull && document.fullscreenElement) document.exitFullscreen().catch(()=>{});
}
document.addEventListener("fullscreenchange",()=>{ if(!document.fullscreenElement && chFull){ chFull=false; document.body.classList.remove("chfull"); $("#chFull").textContent="⛶"; } });
document.addEventListener("keydown",e=>{ if(e.key==="Escape" && chFull) toggleFull(); });

/* ===================== FORCE FX ===================== */
const ST_WIN=[["td","TD"],["tw","TW"],["8h","8H"],["1d","1D"],["5d","5D"],["7d","7D"],["1m","1M"]];
const ST_COL={USD:"#ff7a1a",EUR:"#ff3b3b",JPY:"#3ee6e6",GBP:"#2ecc71",AUD:"#2f6bff",CHF:"#ffd21f",CAD:"#8a5cff",NZD:"#ff3fa4"};
let ST={win:store.get("stWin","1d"),per:store.get("pfPer","1D")}, stChart=null, pfChart=null, stTimer=null, stBusy=false;
const LIVE_MS=10000;
async function loadForce(){
  $("#stWin").innerHTML=ST_WIN.map(([k,l])=>`<button class="chip ${ST.win===k?"on":""}" data-w="${k}">${l}</button>`).join("");
  await Promise.all([loadStrength(), loadPerf()]);
  startForce();
}
function startForce(){
  stopForce();
  stTimer=setInterval(async()=>{
    if(document.hidden||stBusy||!$("#v-force").classList.contains("on")) return;
    stBusy=true; try{ await Promise.all([loadStrength(true), loadPerf(true)]); } finally { stBusy=false; }
  }, LIVE_MS);
}
function stopForce(){ if(stTimer){ clearInterval(stTimer); stTimer=null; } }
function liveTag(id,ok,asof){
  const el=$("#"+id); if(!el) return;
  el.className="livetag "+(ok?"on":"off");
  el.innerHTML=ok?`<i></i>EN DIRECT · ${(d=>[d.getHours(),d.getMinutes(),d.getSeconds()].map(x=>String(x).padStart(2,"0")).join(":"))(new Date((asof||Date.now()/1000)*1000))}`:"<i></i>HORS LIGNE";
}
document.addEventListener("visibilitychange",()=>{ if(!document.hidden && $("#v-force").classList.contains("on")){ loadStrength(true); loadPerf(true); } });
$("#stWin").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;ST.win=b.dataset.w;store.set("stWin",ST.win);
  $("#stWin").querySelectorAll("button").forEach(x=>x.classList.toggle("on",x.dataset.w===ST.win)); loadStrength();});
async function loadStrength(live=false){
  const win=ST.win;
  let d; try{ d=await api("/api/strength?window="+win); }catch(e){ liveTag("stLive",false); if(!live) $("#stLegend").innerHTML=`<span class="neg">${esc(e.message)}</span>`; return; }
  if(win!==ST.win) return;
  liveTag("stLive",true,d.asof);
  const ccys=Object.keys(d.series).sort((a,b)=>d.latest[b]-d.latest[a]);
  $("#stLegend").innerHTML=ccys.map(c=>`<span class="stl" style="--c:${ST_COL[c]}"><b>${c}</b> ${d.latest[c]>0?"+":""}${d.latest[c].toFixed(1)}</span>`).join("");
  const labels=d.times.map(t=>new Date(t*1000));
  const fmt=["1m","7d","5d"].includes(ST.win)?{day:"numeric",month:"short"}:{hour:"2-digit",minute:"2-digit"};
  const cfg={type:"line",data:{labels:labels.map(x=>x.toLocaleString("fr-CA",fmt)),datasets:ccys.map(c=>({label:c,data:d.series[c],borderColor:ST_COL[c],borderWidth:1.3,pointRadius:0,tension:0.15}))},
    options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:"index",intersect:false},
      plugins:{legend:{display:false},tooltip:{callbacks:{label:x=>` ${x.dataset.label} ${x.parsed.y>0?"+":""}${x.parsed.y.toFixed(1)} pb`}}},
      scales:{x:{ticks:{color:"#7d8896",maxTicksLimit:8,font:{size:10}},grid:{color:"#15181d"}},y:{position:"right",ticks:{color:"#7d8896",font:{size:10}},grid:{color:"#15181d"}}}}};
  if(stChart && stChart.$win===win && live){
    stChart.data.labels=cfg.data.labels;
    cfg.data.datasets.forEach(ds=>{ const cur=stChart.data.datasets.find(x=>x.label===ds.label); if(cur) cur.data=ds.data; });
    stChart.update("none");
  } else { if(stChart) stChart.destroy(); stChart=new Chart($("#stCanvas"),cfg); stChart.$win=win; }
}
function heatColor(v){ if(v==null) return "#1a1d22"; const a=Math.min(Math.abs(v)/1.5,1); return v>=0?`rgba(24,160,110,${0.15+0.7*a})`:`rgba(220,60,70,${0.15+0.7*a})`; }
async function loadPerf(live=false){
  const per=ST.per;
  let d; try{ d=await api("/api/fxperf?period="+per); }catch(e){ liveTag("pfLive",false); if(!live) $("#pfHeat").innerHTML=`<tr><td class="neg">${esc(e.message)}</td></tr>`; return; }
  if(per!==ST.per) return;
  liveTag("pfLive",true,d.asof);
  $("#pfPer").innerHTML=d.periods.map(p=>`<button class="chip ${ST.per===p?"on":""}" data-p="${p}">${p}</button>`).join("");
  $("#pfPairs").innerHTML=`<thead><tr><th>Paire</th><th class="n">Prix</th><th class="n">Var.</th></tr></thead><tbody>${d.pairs.map(p=>`<tr><td class="ccy">${p.pair.slice(0,3)}/${p.pair.slice(3)}</td><td class="n mono">${fmtP(p.price,p.pair.includes("JPY")?3:5)}</td><td class="n mono ${p.chg_pct>=0?"pos":"neg"}">${p.chg_pct>=0?"+":""}${p.chg_pct.toFixed(2)}%</td></tr>`).join("")}</tbody>`;
  $("#pfHeat").innerHTML=`<tr><th></th>${d.ccys.map(c=>`<th>${c}</th>`).join("")}<th>MOY.</th></tr>`+d.matrix.map(r=>`<tr><th>${FLAGS[r.ccy]||""} ${r.ccy}</th>${d.ccys.map(c=>{const v=r.cells[c];return `<td style="background:${heatColor(v)}">${v==null?"":(v>0?"+":"")+v.toFixed(2)+"%"}</td>`}).join("")}<td class="mono ${r.avg>=0?"pos":"neg"}"><b>${r.avg>0?"+":""}${r.avg.toFixed(2)}%</b></td></tr>`).join("");
  const n=d.normalized; const pairs=Object.keys(n.series||{});
  const PCOL={EURUSD:"#ff3b3b",GBPUSD:"#2ecc71",USDJPY:"#3ee6e6",USDCAD:"#8a5cff",AUDUSD:"#2f6bff",NZDUSD:"#ff3fa4",USDCHF:"#ffd21f"};
  const fmt=["1D"].includes(ST.per)?{hour:"2-digit",minute:"2-digit"}:{day:"numeric",month:"short"};
  const cfg={type:"line",data:{labels:(n.times||[]).map(t=>new Date(t*1000).toLocaleString("fr-CA",fmt)),datasets:pairs.map(p=>({label:p,data:n.series[p],borderColor:PCOL[p]||"#999",borderWidth:1.3,pointRadius:0,tension:0.1}))},
    options:{responsive:true,maintainAspectRatio:false,animation:false,interaction:{mode:"index",intersect:false},
      plugins:{legend:{labels:{color:"#9aa4b1",boxWidth:10,font:{size:10}}},tooltip:{callbacks:{label:x=>` ${x.dataset.label} ${x.parsed.y>0?"+":""}${x.parsed.y.toFixed(2)}%`}}},
      scales:{x:{ticks:{color:"#7d8896",maxTicksLimit:8,font:{size:10}},grid:{color:"#15181d"}},y:{position:"right",ticks:{color:"#7d8896",font:{size:10},callback:v=>v+"%"},grid:{color:"#15181d"}}}}};
  if(pfChart && pfChart.$per===per && live){
    pfChart.data.labels=cfg.data.labels;
    cfg.data.datasets.forEach(ds=>{ const cur=pfChart.data.datasets.find(x=>x.label===ds.label); if(cur) cur.data=ds.data; });
    pfChart.update("none");
  } else { if(pfChart) pfChart.destroy(); pfChart=new Chart($("#pfCanvas"),cfg); pfChart.$per=per; }
}
$("#pfPer").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;ST.per=b.dataset.p;store.set("pfPer",ST.per);loadPerf();});

/* ===================== TAUX BC (probabilités) ===================== */
let RT=null, rtBank=store.get("rtBank","USD"), rtChart=null;
async function loadRates(){
  try{ RT=await api("/api/rates"); }catch(e){ $("#rtBody").innerHTML=`<div class="empty">${esc(e.message)}</div>`; return; }
  const banks=Object.keys(RT.banks||{});
  if(!banks.length){ $("#rtBody").innerHTML='<div class="empty">Calcul en cours… reviens dans une minute.</div>'; return; }
  $("#rtBanks").innerHTML=banks.map(c=>`<button class="chip ${c===rtBank?"on":""}" data-b="${c}">${FLAGS[c]||""} ${c}</button>`).join("");
  renderRates();
}
$("#rtBanks").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;rtBank=b.dataset.b;store.set("rtBank",rtBank);renderRates();});
function renderRates(){
  const b=RT.banks[rtBank]; const body=$("#rtBody");
  if(!b.ok){ body.innerHTML=`<div class="empty"><b>${esc(b.bank)}</b> · ${esc(b.error||"non disponible")}<br><span class="dim">Prochaines réunions : ${b.meetings.slice(0,4).map(m=>fDs.format(new Date(m+"T12:00:00"))).join(" · ")}</span></div>`; return; }
  const n=b.next||{}; const dir=n.hike>n.cut?"hike":"cut"; const pDir=Math.max(n.hike||0,n.cut||0);
  const days=d=>Math.round((new Date(d+"T12:00:00")-Date.now())/864e5);
  const bar=(l,v,cls)=>`<div class="scen"><span>${l}</span><div class="sbarh"><div class="${cls}" style="width:${v}%"></div></div><b class="mono">${v}%</b></div>`;
  body.innerHTML=`
   <div class="rtcards">
     <div class="rtc"><small>Prochain mouvement</small><b>${esc(b.next_move||"—")}</b></div>
     <div class="rtc"><small>Probabilité</small><b class="${b.next_move==="Hausse"?"pos":b.next_move==="Baisse"?"neg":""}">${b.probability??"—"}%</b></div>
     <div class="rtc"><small>Variation attendue</small><b class="${n.change_bps>0?"pos":n.change_bps<0?"neg":""}">${n.change_bps>0?"+":""}${n.change_bps??"—"} pb</b></div>
     <div class="rtc"><small>Taux actuel</small><b>${b.current!=null?b.current.toFixed(2)+"%":"—"}</b></div>
     <div class="rtc"><small>Réunion</small><b>${n.date?fDs.format(new Date(n.date+"T12:00:00")):"—"}</b></div>
   </div>
   <div class="rtgrid">
     <div><div class="dh">DISTRIBUTION DES SCÉNARIOS · ${esc(b.bank)}</div>
       ${bar("Hausse",n.hike||0,"hk")}${bar("Statu quo",n.hold||0,"hd")}${bar("Baisse",n.cut||0,"ct")}
       <div class="dh" style="margin-top:14px">RÉUNIONS</div>
       <div style="overflow-x:auto"><table class="cal rtt"><thead><tr><th>Réunion</th><th class="n">Jours</th><th class="n">Taux implicite</th><th class="n">Δ pb</th><th class="n">Baisse</th><th class="n">Statu quo</th><th class="n">Hausse</th></tr></thead><tbody>
       ${b.rows.map(r=>`<tr><td class="mono">${fDs.format(new Date(r.date+"T12:00:00"))}</td><td class="n mono mute">${days(r.date)}j</td><td class="n mono"><b>${r.rate.toFixed(2)}%</b></td><td class="n mono ${r.change_bps>0?"pos":r.change_bps<0?"neg":"mute"}">${r.change_bps>0?"+":""}${r.change_bps}</td><td class="n mono ${r.cut>=50?"neg":"mute"}">${r.cut}%</td><td class="n mono">${r.hold}%</td><td class="n mono ${r.hike>=50?"pos":"mute"}">${r.hike}%</td></tr>`).join("")}</tbody></table></div></div>
     <div><div class="dh">COURBE À TERME IMPLICITE</div><div class="stchart" style="height:340px"><canvas id="rtCanvas"></canvas></div>
       <p class="note">Taux directeur implicite à chaque réunion, déduit des futures de taux (${rtBank==="USD"?"Fed funds 30 jours":rtBank==="CAD"?"CORRA 3 mois":rtBank==="EUR"?"Euribor 3 mois":rtBank==="GBP"?"SONIA 3 mois":"SARON 3 mois"}). Probabilité = variation attendue ÷ 25 pb. Estimation indicative, pas une prévision.</p></div>
   </div>`;
  const labels=b.rows.map(r=>fDs.format(new Date(r.date+"T12:00:00")));
  const ds=[{label:"Courbe actuelle",data:b.rows.map(r=>r.rate),borderColor:"#22c3a6",backgroundColor:"#22c3a6",borderWidth:2,pointRadius:3,tension:0.25}];
  if(b.last_week_curve){ const lw=b.last_week_curve; const m=lw.map(p=>p.rate); ds.push({label:"Semaine dernière",data:b.rows.map(r=>{const t=new Date(r.date).getTime();let best=lw[0];for(const p of lw){if(Math.abs(new Date(p.date)-t)<Math.abs(new Date(best.date)-t))best=p;}return best?best.rate:null;}),borderColor:"#ef4454",borderDash:[4,4],borderWidth:1.5,pointRadius:0,tension:0.25}); }
  if(rtChart) rtChart.destroy();
  rtChart=new Chart($("#rtCanvas"),{type:"line",data:{labels,datasets:ds},options:{responsive:true,maintainAspectRatio:false,animation:false,
    plugins:{legend:{labels:{color:"#9aa4b1",boxWidth:10,font:{size:10}}}},
    scales:{x:{ticks:{color:"#7d8896",font:{size:10}},grid:{color:"#15181d"}},y:{position:"right",ticks:{color:"#7d8896",font:{size:10},callback:v=>v.toFixed(2)+"%"},grid:{color:"#15181d"}}}}});
}
window.loadForce=loadForce; window.stopForce=stopForce; window.loadRates=loadRates; window.stopCharts=stopCharts;
window.renderCharts=renderCharts;
/* Si l'app s'ouvre directement sur un de ces onglets, charger maintenant (ce fichier arrive après app.js). */
(function(){ const on=id=>document.querySelector("#v-"+id)?.classList.contains("on");
  if(on("taux")) loadRates(); if(on("force")) loadForce(); if(on("graphiques")) renderCharts(); })();
