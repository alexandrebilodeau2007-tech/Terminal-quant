/* Macro Terminal — front-end (vanilla JS, aucune compilation) */
const TZ = "America/Toronto";
const CCYS = ["USD","EUR","GBP","JPY","CAD","AUD","NZD","CHF","CNY"];
const FLAGS = {USD:"🇺🇸",EUR:"🇪🇺",GBP:"🇬🇧",JPY:"🇯🇵",CAD:"🇨🇦",AUD:"🇦🇺",NZD:"🇳🇿",CHF:"🇨🇭",CNY:"🇨🇳"};
const CHART_PAGES = [
  {name:"Devises I",   syms:["CAPITALCOM:DXY","FX:EURUSD","FX:GBPUSD","FX:USDJPY"]},
  {name:"Devises II",  syms:["FX:USDCAD","FX:AUDUSD","FX:NZDUSD","FX:USDCHF"]},
  {name:"Croisées I",  syms:["FX:EURJPY","FX:GBPJPY","FX:EURGBP","FX:AUDJPY"]},
  {name:"Croisées II", syms:["FX:EURCHF","FX:CADJPY","FX:AUDNZD","FX:USDCNH"]},
  {name:"Taux & pétrole", syms:["OANDA:USB10YUSD","OANDA:DE10YBEUR","OANDA:UK10YBGBP","OANDA:WTICOUSD"]},
  {name:"Macro",       syms:["OANDA:XAUUSD","OANDA:XAGUSD","OANDA:SPX500USD","CAPITALCOM:VIX"]},
];
const TAPE = [["CAPITALCOM:DXY","DXY"],["FX:EURUSD","EUR/USD"],["FX:GBPUSD","GBP/USD"],["FX:USDJPY","USD/JPY"],["FX:USDCAD","USD/CAD"],
  ["FX:AUDUSD","AUD/USD"],["FX:NZDUSD","NZD/USD"],["FX:USDCHF","USD/CHF"],["OANDA:XAUUSD","OR"],["OANDA:USB10YUSD","T-NOTE 10A"],["OANDA:SPX500USD","S&P 500"],["CAPITALCOM:VIX","VIX"]];

const $ = (s, r=document) => r.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const fT = new Intl.DateTimeFormat("fr-FR",{timeZone:TZ,hour:"2-digit",minute:"2-digit",hour12:false});
const fD = new Intl.DateTimeFormat("fr-CA",{timeZone:TZ,weekday:"long",day:"numeric",month:"long"});
const fDs = new Intl.DateTimeFormat("fr-CA",{timeZone:TZ,weekday:"short",day:"numeric",month:"short"});
const fClock = new Intl.DateTimeFormat("fr-FR",{timeZone:TZ,hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false});
const store = { get:(k,d)=>{try{return JSON.parse(localStorage.getItem(k)) ?? d}catch{return d}}, set:(k,v)=>{try{localStorage.setItem(k,JSON.stringify(v))}catch{}} };

let CAL = {events:[]}, CCY_LIST = [], CHART_PAGE = store.get("chartPage",0), charts = {};

function toast(m){const t=$("#toast");t.textContent=m;t.style.display="block";clearTimeout(t._h);t._h=setTimeout(()=>t.style.display="none",2600)}

async function api(path, opts={}){
  const tok = store.get("token","");
  const r = await fetch(path,{...opts,headers:{"content-type":"application/json",...(tok?{"x-token":tok}:{}),...(opts.headers||{})}});
  if(r.status===401){ showLogin(); throw new Error("unauthorized"); }
  if(!r.ok) throw new Error(await r.text());
  return r.json();
}

function showLogin(){
  if(document.getElementById("login")) return;
  const d=document.createElement("div"); d.id="login";
  d.style.cssText="position:fixed;inset:0;background:#06080bf2;z-index:100;display:flex;align-items:center;justify-content:center";
  d.innerHTML=`<form class="panel" style="width:300px;margin:0"><div class="ph"><b>Macro Terminal</b> · accès</div>
    <div class="pb"><input id="pw" type="password" placeholder="Mot de passe" autocomplete="current-password" style="width:100%;margin-bottom:10px">
    <button class="btn" style="width:100%">ENTRER</button></div></form>`;
  document.body.appendChild(d);
  d.querySelector("form").onsubmit=e=>{e.preventDefault();store.set("token",d.querySelector("#pw").value);location.reload()};
  setTimeout(()=>d.querySelector("#pw").focus(),50);
}

/* ---------------- TradingView widgets ---------------- */
function tvWidget(el, script, cfg){
  el.innerHTML="";
  const w=document.createElement("div");w.className="tradingview-widget-container";w.style.height="100%";w.style.width="100%";
  const i=document.createElement("div");i.className="tradingview-widget-container__widget";i.style.height="100%";w.appendChild(i);
  const s=document.createElement("script");s.src="https://s3.tradingview.com/external-embedding/"+script;s.async=true;
  s.innerHTML=JSON.stringify(cfg);w.appendChild(s);el.appendChild(w);
}
function chartCfg(sym, interval){
  return {autosize:true,symbol:sym,interval,timezone:TZ,theme:"dark",style:"1",locale:"fr",
    backgroundColor:"#0c1015",gridColor:"rgba(255,255,255,0.04)",hide_side_toolbar:true,allow_symbol_change:true,
    save_image:false,calendar:false,support_host:"https://www.tradingview.com"};
}
function initTape(){
  tvWidget($("#tape"),"embed-widget-ticker-tape.js",{symbols:TAPE.map(([p,t])=>({proName:p,title:t})),
    showSymbolLogo:false,isTransparent:true,displayMode:"compact",colorTheme:"dark",locale:"fr"});
}

/* ---------------- navigation ---------------- */
function show(v){
  document.querySelectorAll(".modal").forEach(m=>m.remove());
  document.querySelectorAll(".view").forEach(x=>x.classList.toggle("on",x.id==="v-"+v));
  document.querySelectorAll("#tabs button").forEach(b=>b.classList.toggle("on",b.dataset.v===v));
  if(location.hash!=="#"+v) history.replaceState(null,"","#"+v);
  if(v==="graphiques") renderCharts();
  if(v==="devises") loadCurrencies();
  if(v==="nouvelles") loadNews();
  if(v==="accueil") loadDashboard();
  if(v==="macro") loadMacro();
  if(v==="alertes") renderAlerts();
  if(v==="saison") initSeason();
  if(v==="calendrier"){ renderFilters(); loadCalView(); }
  if(v==="fiches") loadFiches();
  window.scrollTo(0,0);
}
$("#tabs").addEventListener("click",e=>{const b=e.target.closest("button");if(b)show(b.dataset.v)});
window.addEventListener("hashchange",()=>{const v=location.hash.slice(1);if(document.getElementById("v-"+v))show(v)});

/* ---------------- header ---------------- */
function tick(){
  $("#clock").textContent = fClock.format(new Date())+" ET";
  const now=Date.now();
  const nx=(CAL.events||[]).find(e=>!e.released && new Date(e.time).getTime()>now-60000 && e.impact!=="low");
  if(nx){
    const ms=new Date(nx.time).getTime()-now, h=Math.floor(ms/3.6e6), m=Math.floor(ms%3.6e6/6e4), s=Math.floor(ms%6e4/1e3);
    const cd = ms<=0 ? "EN COURS" : (h>23? Math.floor(h/24)+"j "+(h%24)+"h" : h? `${h}h${String(m).padStart(2,"0")}` : `${m}m${String(s).padStart(2,"0")}s`);
    $("#nextEv").innerHTML=`PROCHAIN <b>${fT.format(new Date(nx.time))} ${nx.currency}</b> ${esc(nx.title)} · <b>${cd}</b>`;
  } else $("#nextEv").textContent="";
}
setInterval(tick,1000);

async function health(){
  try{
    const h=await api("/api/health");
    const ok=!h.errors?.length && !h.engine_error && h.week_updated;
    $("#statusDot").className="dot "+(ok?"ok":"bad");
    $("#statusTxt").textContent = h.week_updated ? "MAJ "+fT.format(new Date(h.week_updated)) : "chargement";
    return h;
  }catch{ $("#statusDot").className="dot bad"; $("#statusTxt").textContent="hors ligne"; }
}

/* ---------------- calendrier (style Forex Factory) ---------------- */
const RANGES=[["yesterday","Hier"],["today","Aujourd'hui"],["tomorrow","Demain"],["thisweek","Cette semaine"],["nextweek","Sem. prochaine"],["lastweek","Sem. passée"],["thismonth","Ce mois"]];
const IMPACTS=[["high","🔴 Élevé"],["medium","🟠 Moyen"],["low","🟡 Faible"],["holiday","⚪ Férié"]];
const CATS=["Croissance","Inflation","Emploi","Banque centrale","Obligations","Logement","Sondage conso.","Sondage entreprises","Discours","Divers"];
let CV = Object.assign({range:"thisweek",imp:["high","medium"],cats:[...CATS],ccy:[...CCYS],q:"",hidePast:false,open:true}, store.get("calView",{}));
let CALV = {events:[]}, EVDET = {}, FICHES = null;
function saveCV(){ store.set("calView",{...CV,q:""}); }

function surpriseCell(e){
  const s=e.surprise; if(!s) return '<span class="dim">—</span>';
  const c = s.ccy_bias==="positif"?"pos":s.ccy_bias==="négatif"?"neg":"neu";
  return `<span class="${c}">${esc(s.diff_str)}</span>`;
}
function calRows(events, {grouped=true}={}){
  const now=Date.now();
  const nextId=(events.find(e=>!e.released&&e.impact!=="holiday"&&new Date(e.time).getTime()>now-60000)||{}).id;
  const hasTE = events.some(e=>e.te_forecast_str);
  const cols = hasTE?9:8;
  let h=`<thead><tr><th>Heure</th><th>Dev.</th><th>Événement</th><th></th><th class="n">Réel</th><th class="n">Prév.</th><th class="n">Préc.</th>${hasTE?'<th class="n hide-m">TE</th>':""}<th class="n hide-m">Écart</th></tr></thead><tbody>`;
  let day="";
  for(const e of events){
    const d=fD.format(new Date(e.time));
    if(grouped && d!==day){day=d;h+=`<tr class="day"><td colspan="${cols}">${esc(d.toUpperCase())}</td></tr>`}
    const past=new Date(e.time).getTime()<now && (e.released||e.impact==="holiday");
    const act=e.released?`<span class="act ${e.surprise?.ccy_bias==="positif"?"pos":e.surprise?.ccy_bias==="négatif"?"neg":""}">${esc(e.actual_str)}</span>`:'<span class="dim">…</span>';
    const isNext=e.id===nextId;
    const time=e.impact==="holiday"?"Journée":fT.format(new Date(e.time));
    h+=`<tr class="evrow ${past?"past":""} ${isNext?"nextev":""}" data-t="${esc(e.title)}" data-c="${e.currency}" data-id="${esc(e.id)}" data-cols="${cols}">
      <td class="mono">${time}${isNext?`<div class="cd">${(c=>c==="EN COURS"?c:"dans "+c)(countdown(e.time))}</div>`:""}</td>
      <td><span class="ccy">${FLAGS[e.currency]||""} ${e.currency}</span></td>
      <td><div class="evt"><i class="imp ${e.impact}"></i><div>${esc(e.title)} <small>${esc(e.period||"")}${e.country&&!["US","GB","JP","CA","AU","NZ","CH","CN"].includes(e.country)?" · "+e.country:""}</small>
        <div class="src">${e.category?`<span class="cat">${esc(e.category)}</span> `:""}${esc((e.sources||[]).join(" · "))}</div></div></div></td>
      <td class="det">${e.fiche?'<span title="Ma fiche">📘</span>':""}<span class="fold">▸</span></td>
      <td class="n">${act}</td><td class="n">${esc(e.forecast_str)}</td><td class="n mute">${esc(e.previous_str)}</td>
      ${hasTE?`<td class="n hide-m mute">${esc(e.te_forecast_str||"—")}</td>`:""}
      <td class="n hide-m">${surpriseCell(e)}</td></tr>`;
  }
  return h+"</tbody>";
}

/* détail d'un événement (clic sur une ligne, partout dans l'app) */
document.addEventListener("click",async ev=>{
  const fb=ev.target.closest("[data-fiche]"); if(fb){ ev.stopPropagation(); openFiche(fb.dataset.fiche); return; }
  const tr=ev.target.closest("tr.evrow"); if(!tr || ev.target.closest("a")) return;
  const nx=tr.nextElementSibling;
  if(nx && nx.classList.contains("evdet")){ nx.remove(); tr.classList.remove("open"); return; }
  tr.classList.add("open");
  const row=document.createElement("tr"); row.className="evdet";
  row.innerHTML=`<td colspan="${tr.dataset.cols||8}"><div class="dbox"><div class="empty" style="padding:14px">Chargement…</div></div></td>`;
  tr.after(row);
  const key=tr.dataset.c+"|"+tr.dataset.t;
  try{
    EVDET[key] = EVDET[key] || await api(`/api/event?ccy=${encodeURIComponent(tr.dataset.c)}&title=${encodeURIComponent(tr.dataset.t)}`);
    row.querySelector(".dbox").innerHTML = detailHtml(EVDET[key], tr.dataset.t, tr.dataset.c);
    drawHist(row, EVDET[key]);
  }catch{ row.querySelector(".dbox").innerHTML='<div class="empty">Détail indisponible.</div>'; }
});
function detailHtml(d,title,ccy){
  const nxt=d.next?fDs.format(new Date(d.next))+" "+fT.format(new Date(d.next)):"—";
  const spec=[["Source",d.source],["Mesure",d.measures],["Effet habituel",d.usual_effect],["Catégorie",d.category],["Prochaine publication",nxt],["Pourquoi les traders s'y intéressent",d.why]];
  const hist=d.history||[];
  return `<div class="dgrid">
    <div><div class="dh">SPÉCIFICATIONS · ${FLAGS[ccy]||""} ${esc(ccy)} ${esc(title)}</div>
      <table class="spec">${spec.map(([k,v])=>`<tr><th>${k}</th><td>${esc(v)}</td></tr>`).join("")}</table>
      ${d.fiche?`<button class="btn sm" data-fiche="${esc(d.fiche)}">📘 OUVRIR MA FICHE</button>`:""}
    </div>
    <div><div class="dh">HISTORIQUE</div>
      ${hist.length?`<div class="hc"><canvas></canvas></div>
      <table class="hist"><tr><th>Date</th><th class="n">Réel</th><th class="n">Prév.</th><th class="n">Préc.</th></tr>
      ${hist.slice(0,8).map(h=>`<tr><td>${fDs.format(new Date(h.time))}</td><td class="n ${h.bias==="positif"?"pos":h.bias==="négatif"?"neg":""}">${esc(h.actual)}</td><td class="n">${esc(h.forecast)}</td><td class="n mute">${esc(h.previous)}</td></tr>`).join("")}</table>`
      :'<div class="empty" style="padding:14px">Pas encore d\'historique pour cet événement.</div>'}
    </div></div>`;
}
function drawHist(row,d){
  const cv=row.querySelector("canvas"); if(!cv||!window.Chart) return;
  const h=(d.history||[]).filter(x=>x.actual_num!=null).slice(0,14).reverse();
  new Chart(cv,{type:"bar",data:{labels:h.map(x=>fDs.format(new Date(x.time))),datasets:[{data:h.map(x=>x.actual_num),
    backgroundColor:h.map(x=>x.bias==="positif"?"#18c787":x.bias==="négatif"?"#ef4454":"#56606d")}]},
    options:{responsive:true,maintainAspectRatio:false,plugins:{legend:{display:false}},scales:{x:{ticks:{color:"#7d8896",font:{size:9}},grid:{display:false}},y:{ticks:{color:"#7d8896",font:{size:9}},grid:{color:"#1b222b"}}}}});
}

/* filtres */
function chipRow(list, sel, attr){ return list.map(([k,l])=>`<button class="chip ${sel.includes(k)?"on":""}" data-${attr}="${esc(k)}">${l}</button>`).join(""); }
function renderFilters(){
  $("#calRange").innerHTML = RANGES.map(([k,l])=>`<button class="chip ${CV.range===k?"on":""}" data-r="${k}">${l}</button>`).join("");
  $("#calImp").innerHTML = chipRow(IMPACTS, CV.imp, "i");
  $("#calCat").innerHTML = chipRow(CATS.map(c=>[c,c]), CV.cats, "k") + `<button class="chip" data-k="ALL">TOUS</button>`;
  $("#calCcy").innerHTML = chipRow(CCYS.map(c=>[c,FLAGS[c]+" "+c]), CV.ccy, "c") + `<button class="chip" data-c="ALL">TOUTES</button>`;
  $("#calPast").classList.toggle("on",CV.hidePast);
  $("#calFilters").style.display = CV.open?"":"none";
  $("#calToggle").textContent = CV.open?"FILTRES ▴":"FILTRES ▾";
  const n=[CV.imp.length<4,CV.cats.length<CATS.length,CV.ccy.length<CCYS.length,CV.hidePast].filter(Boolean).length;
  $("#calSum").textContent = `${RANGES.find(r=>r[0]===CV.range)[1]} · ${n} filtre${n>1?"s":""} actif${n>1?"s":""}`;
}
function toggleIn(arr,v,all){ return v==="ALL" ? (arr.length===all.length?[]:[...all]) : arr.includes(v)?arr.filter(x=>x!==v):[...arr,v]; }
$("#v-calendrier").addEventListener("click",e=>{
  const b=e.target.closest("button"); if(!b||!b.closest(".calbar")) return;
  if(b.dataset.r){ CV.range=b.dataset.r; saveCV(); renderFilters(); loadCalView(); return; }
  if(b.dataset.i){ CV.imp=toggleIn(CV.imp,b.dataset.i,IMPACTS.map(x=>x[0])); }
  else if(b.dataset.k){ CV.cats=toggleIn(CV.cats,b.dataset.k,CATS); }
  else if(b.dataset.c){ CV.ccy=toggleIn(CV.ccy,b.dataset.c,CCYS); }
  else if(b.id==="calPast"){ CV.hidePast=!CV.hidePast; }
  else if(b.id==="calToggle"){ CV.open=!CV.open; }
  else if(b.id==="calReset"){ CV={range:"thisweek",imp:["high","medium"],cats:[...CATS],ccy:[...CCYS],q:"",hidePast:false,open:true}; $("#calQ").value=""; saveCV(); renderFilters(); loadCalView(); return; }
  else if(b.id==="refreshCal"){ toast("Actualisation…"); api("/api/calendar/refresh",{method:"POST"}).then(()=>{loadCalView();loadCal();toast("À jour")}).catch(()=>toast("Échec")); return; }
  else return;
  saveCV(); renderFilters(); renderCal();
});
$("#calQ").addEventListener("input",e=>{CV.q=e.target.value.trim().toLowerCase(); renderCal();});

function renderCal(){
  const now=Date.now();
  const ev=(CALV.events||[]).filter(e=>CV.ccy.includes(e.currency)&&CV.imp.includes(e.impact)&&CV.cats.includes(e.category||"Divers")
    &&(!CV.q||(e.title+" "+e.currency+" "+(e.category||"")).toLowerCase().includes(CV.q))
    &&(!CV.hidePast||!(new Date(e.time).getTime()<now-60000&&(e.released||e.impact==="holiday"))));
  $("#calCount").textContent=`${ev.length} événement${ev.length>1?"s":""}`;
  const opened=[...document.querySelectorAll("#calTable tr.evrow.open")].map(r=>r.dataset.id);
  $("#calTable").innerHTML = ev.length? calRows(ev) : `<tr><td class="empty">Aucun événement pour ces filtres.${CALV.errors?.length?"<br>"+esc(CALV.errors.join(" | ")):""}</td></tr>`;
  opened.forEach(id=>{ const r=[...document.querySelectorAll("#calTable tr.evrow")].find(x=>x.dataset.id===id); if(r) r.click(); });
}
async function loadCalView(){
  try{ CALV = await api(`/api/calendar?impacts=high,medium,low,holiday&range=${CV.range}`); renderCal(); }catch(e){console.warn(e)}
}
async function loadCal(){
  try{ CAL = await api("/api/calendar"); tick(); if($("#v-semaine").classList.contains("on")&&!WEEK) loadWeekly(); }catch(e){console.warn(e)}
}

/* ---------------- fiches ---------------- */
async function getFiches(){ if(!FICHES){ FICHES=(await api("/api/fiches")).items||[]; } return FICHES; }
function ficheBody(f){
  const li=a=>`<ul>${(a||[]).map(x=>x.startsWith("– ")?`<li class="sub">${esc(x.slice(2))}</li>`:`<li>${esc(x)}</li>`).join("")}</ul>`;
  const tok=encodeURIComponent(store.get("token",""));
  const rel=(CAL.events||[]).filter(e=>e.fiche===f.id&&!e.released);
  return `<table class="spec">
      <tr><th>🌎 Pays</th><td>${esc(f.pays)}</td></tr><tr><th>⏱ Temporalité</th><td>${esc(f.temporalite)}</td></tr>
      <tr><th>📊 Croissance ou inflation</th><td>${esc(f.type)}</td></tr><tr><th>📅 Publication</th><td>${esc(f.publication)}</td></tr>
      <tr><th>⏳ Fréquence</th><td>${esc(f.frequence)}</td></tr><tr><th>🔥 Importance</th><td>${esc(f.importance)}</td></tr></table>
    <div class="dh">📖 EXPLICATION</div>${li(f.explication)}
    <div class="dh">❓ COMMENT ÇA FONCTIONNE</div>${li(f.fonctionnement)}
    <div class="dh">🔎 CE QU'IL FAUT REGARDER</div>${li(f.regarder)}
    ${rel.length?`<div class="dh">📆 CETTE SEMAINE</div><div class="mono" style="font-size:12px">${rel.map(e=>`${FLAGS[e.currency]} ${fDs.format(new Date(e.time))} ${fT.format(new Date(e.time))} · ${esc(e.title)}`).join("<br>")}</div>`:""}
    <details style="margin-top:12px"><summary class="mono" style="cursor:pointer;color:var(--acc2);font-size:12px">VOIR LA FICHE ORIGINALE</summary>
      <img loading="lazy" src="/api/fiches/img/${esc(f.img)}?token=${tok}" style="width:100%;margin-top:8px;border-radius:4px"></details>`;
}
async function openFiche(id){
  const f=(await getFiches()).find(x=>x.id===id); if(!f) return toast("Fiche introuvable");
  const d=document.createElement("div"); d.className="modal";
  d.innerHTML=`<div class="panel mbox"><div class="ph"><b>📘 ${esc(f.title)}</b> · ${esc(f.group)}<div class="r"><button class="chip" data-x>✕</button></div></div><div class="pb fiche">${ficheBody(f)}</div></div>`;
  d.onclick=e=>{ if(e.target===d||e.target.closest("[data-x]")) d.remove(); };
  document.body.appendChild(d);
}
async function loadFiches(){
  const el=$("#ficheList");
  try{
    const items=await getFiches();
    if(!items.length){ el.innerHTML='<div class="empty">Fiches indisponibles.</div>'; return; }
    const q=($("#ficheQ").value||"").toLowerCase();
    const groups=[...new Set(items.map(f=>f.group))];
    el.innerHTML=groups.map(g=>{
      const fs=items.filter(f=>f.group===g&&(!q||JSON.stringify(f).toLowerCase().includes(q)));
      if(!fs.length) return "";
      return `<div class="dh" style="margin:14px 0 8px">${esc(g.toUpperCase())}</div><div class="fgrid">${fs.map(f=>{
        const n=(CAL.events||[]).find(e=>e.fiche===f.id&&!e.released);
        return `<button class="fcard" data-fiche="${f.id}"><b>${esc(f.title)}</b><span>${esc(f.type)} · ${esc(f.frequence)}</span>
          <span class="imp-t">🔥 ${esc(f.importance)}</span>${n?`<span class="soon">📆 ${FLAGS[n.currency]} ${fDs.format(new Date(n.time))} ${fT.format(new Date(n.time))}</span>`:""}</button>`}).join("")}</div>`;
    }).join("") || '<div class="empty">Aucune fiche ne correspond.</div>';
  }catch{ el.innerHTML='<div class="empty">Fiches indisponibles.</div>'; }
}
$("#ficheQ").addEventListener("input",loadFiches);

/* ---------------- semaine ---------------- */
let WEEK=null;
function md(t){
  const lines=esc(t).replace(/\*\*(.+?)\*\*/g,"<b>$1</b>").split("\n");
  let h="",ul=false;
  for(const l of lines){
    const s=l.trim();
    if(/^#{1,4}\s/.test(s)||/^\d\)\s/.test(s)&&s.length<80){ if(ul){h+="</ul>";ul=false} h+=`<h4>${s.replace(/^#+\s/,"")}</h4>`; }
    else if(/^[-•*]\s/.test(s)){ if(!ul){h+="<ul>";ul=true} h+=`<li>${s.slice(2)}</li>`; }
    else if(s){ if(ul){h+="</ul>";ul=false} h+=`<p>${s}</p>`; }
  }
  return h+(ul?"</ul>":"");
}
async function loadWeekly(){
  const el=$("#v-semaine");
  try{ WEEK = await api("/api/weekly"); }catch{ WEEK=null }
  if(!WEEK || !WEEK.week_start){
    el.innerHTML=`<div class="panel"><div class="ph"><b>Analyse de la semaine</b></div><div class="empty">Pas encore d'analyse pour cette semaine.<br><br><button class="btn" id="genW">GÉNÉRER MAINTENANT</button></div></div>`;
    $("#genW").onclick=genWeekly; return;
  }
  const ws=new Date(WEEK.week_start), we=new Date(new Date(WEEK.week_end).getTime()-1);
  const order=Object.entries(WEEK.per_currency).sort((a,b)=>(b[1].red*3+b[1].orange)-(a[1].red*3+a[1].orange));
  // valeurs réelles à jour depuis le calendrier en direct
  const live=Object.fromEntries((CAL.events||[]).map(e=>[e.id,e]));
  const allEv=Object.values(WEEK.by_day).flat().map(e=>live[e.id]||e);
  el.innerHTML=`
  <div class="panel"><div class="ph"><b>Semaine du ${fDs.format(ws)} au ${fDs.format(we)}</b>
     <div class="r"><button class="chip" id="genW">↻ RÉGÉNÉRER</button></div></div>
    <div class="pb">
      <div class="headline">${esc(WEEK.headline)}</div>
      <div class="kpis" style="margin-top:12px">
        <div class="kpi"><div class="l">Rouges</div><div class="v neg">${WEEK.counts.red}</div></div>
        <div class="kpi"><div class="l">Orange</div><div class="v" style="color:var(--orange)">${WEEK.counts.orange}</div></div>
        <div class="kpi"><div class="l">Générée</div><div class="v" style="font-size:13px">${fDs.format(new Date(WEEK.generated))} ${fT.format(new Date(WEEK.generated))}</div></div>
      </div>
    </div></div>
  ${WEEK.ai_analysis?`<div class="panel"><div class="ph"><b>Analyse</b> · stratège macro</div><div class="pb ai">${md(WEEK.ai_analysis)}</div></div>`:""}
  <div class="grid g3">${order.map(([c,d])=>`
    <div class="panel wk-ccy"><div class="ph"><b>${FLAGS[c]} ${c}</b> <span>${d.red} 🔴 · ${d.orange} 🟠</span>
      <div class="r"><span class="badge ${d.stance.toLowerCase()}">${esc(d.stance)}</span></div></div>
      <div class="pb"><div class="sum">${esc(d.summary)}</div>${d.bullets.length?`<ul>${d.bullets.map(b=>`<li>${esc(b)}</li>`).join("")}</ul>`:'<span class="dim mono" style="font-size:11px">Rien d\'orange ou de rouge.</span>'}</div></div>`).join("")}
  </div>
  <div class="panel"><div class="ph"><b>Liste de la semaine</b> · chaque annonce a une alerte</div>
    <div style="overflow-x:auto"><table class="cal">${allEv.length?calRows(allEv):'<tr><td class="empty">Aucune annonce.</td></tr>'}</table></div></div>`;
  $("#genW").onclick=genWeekly;
}
async function genWeekly(){toast("Génération de l'analyse…");try{await api("/api/weekly/generate",{method:"POST"});await loadWeekly();toast("Analyse prête")}catch(e){toast("Échec : "+e.message.slice(0,60))}}

/* ---------------- nouvelles ---------------- */
const NEWS_KW = {USD:["fed","fomc","powell","treasur","u.s.","us ","dollar","usd","nfp","payroll","white house"],
  EUR:["ecb","lagarde","euro","eur","germany","german","france","italy","bund"],GBP:["boe","bank of england","uk ","britain","gbp","sterling","gilt"],
  JPY:["boj","japan","yen","jpy","jgb"],CAD:["boc","bank of canada","canada","cad","loonie"],AUD:["rba","australia","aud"],
  NZD:["rbnz","new zealand","nzd"],CHF:["snb","swiss","chf"],CNY:["pboc","china","chinese","yuan","cny","cnh"]};
const CB_W=/\b(fed|fomc|ecb|boe|boj|boc|rba|rbnz|snb|pboc|central bank|lagarde|powell|bailey|ueda|macklem|rates?|inflation|policy)\b/i;
const HAWK_P=/\b(no rush|not in a hurry|no hurry|in no hurry|push(es|ed)? back|patient|premature to cut|hold rates)\b/i;
const HAWK_W=/\b(hawkish|hike|hikes|hiking|tighten\w*|raise rates|rate rise|higher for longer|sticky)\b/i;
const DOVE_W=/\b(dovish|cut|cuts|cutting|easing|ease|lower rates|stimulus)\b/i;
let NEWS_F = store.get("newsFilter",{ccy:"ALL",src:"ALL"}), NEWS=[];
async function loadNews(){
  try{ NEWS = await api("/api/news?limit=200"); }catch{ return }
  $("#newsCcy").innerHTML = ["ALL",...CCYS].map(c=>`<button class="chip ${NEWS_F.ccy===c?"on":""}" data-c="${c}">${c==="ALL"?"TOUT":FLAGS[c]+" "+c}</button>`).join("");
  $("#newsSrc").innerHTML = [["ALL","TOUTES SOURCES"],["FinancialJuice","FINANCIALJUICE"],["InvestingLive","INVESTINGLIVE"],["Investing.com","INVESTING.COM"]]
    .map(([k,l])=>`<button class="chip ${NEWS_F.src===k?"on":""}" data-s="${k}">${l}</button>`).join("");
  const now=Date.now();
  const list = NEWS.filter(n=>(NEWS_F.src==="ALL"||n.source===NEWS_F.src) &&
    (NEWS_F.ccy==="ALL"||NEWS_KW[NEWS_F.ccy].some(k=>(" "+n.title+" ").toLowerCase().includes(k)))).slice(0,120);
  $("#newsList").innerHTML = list.map(n=>{
    const t=n.time?new Date(n.time):null, fresh=t&&now-t<15*60000;
    const cb=CB_W.test(n.title);
    const tone=!cb?"":(HAWK_P.test(n.title)||HAWK_W.test(n.title))?'<span class="tone hawkish">HAWK</span>':DOVE_W.test(n.title)?'<span class="tone dovish">DOVE</span>':"";
    return `<a href="${esc(n.link)}" target="_blank" rel="noopener" style="${fresh?"border-left:2px solid var(--acc);padding-left:8px":""}">${tone}${esc(n.title)}
      <small>${t?fDs.format(t)+" "+fT.format(t):""} · ${esc(n.source||"")}</small></a>`}).join("") || '<div class="empty">Aucune nouvelle pour ce filtre.</div>';
  $("#newsUpd").textContent = "MAJ "+fT.format(new Date());
}
$("#newsCcy").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;NEWS_F.ccy=b.dataset.c;store.set("newsFilter",NEWS_F);loadNews()});
$("#newsSrc").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;NEWS_F.src=b.dataset.s;store.set("newsFilter",NEWS_F);loadNews()});


/* ---------------- accueil (tableau de bord) ---------------- */
function verdict(e){
  const b=e.surprise?.ccy_bias;
  return b==="positif"?`<span class="verdict good">BON ${e.currency}</span>`:b==="négatif"?`<span class="verdict bad">MAUVAIS ${e.currency}</span>`:`<span class="verdict neu">NEUTRE</span>`;
}
function countdown(t){const ms=new Date(t).getTime()-Date.now(); if(ms<=0) return "EN COURS"; const h=Math.floor(ms/3.6e6),m=Math.floor(ms%3.6e6/6e4); return h>23?Math.floor(h/24)+"j "+(h%24)+"h":h?`${h}h${String(m).padStart(2,"0")}`:`${m} min`;}
function kfmt(n){ if(n==null) return "—"; const a=Math.abs(n), s=n>0?"+":n<0?"−":""; return s+(a>=1000?(a/1000).toFixed(1)+"K":Math.round(a)); }
function cotCell(g){ if(!g) return '<span class="dim">—</span>';
  return `<div style="min-width:130px">${sentBar({long:g.pct_long,short:100-g.pct_long})}<div class="mono" style="font-size:10px;margin-top:3px"><span class="${g.net>0?"pos":"neg"}">net ${kfmt(g.net)}</span> <span class="mute">· sem. ${kfmt(g.change)}</span></div></div>`; }
function cotRead(r){ const g=r.groups.lev; if(!g||g.index==null) return '<span class="mute">—</span>';
  return g.index>=90?'<span class="pos">TRÈS LONG (extrême)</span>':g.index<=10?'<span class="neg">TRÈS COURT (extrême)</span>':g.index>=60?'<span class="pos">acheteur</span>':g.index<=40?'<span class="neg">vendeur</span>':'<span class="mute">neutre</span>'; }
function cotTable(rows){
  return `<div style="overflow-x:auto"><table class="cal"><thead><tr><th>Devise</th><th>Banques (dealers)</th><th>Asset managers</th><th>Hedge funds</th><th class="n">Indice 6 mois</th><th class="n">Lecture</th></tr></thead><tbody>
  ${rows.map(r=>`<tr><td><span class="ccy">${FLAGS[r.ccy]} ${r.ccy}</span><div class="dim mono" style="font-size:9px">${esc(r.date)}</div></td><td>${cotCell(r.groups.dealer)}</td><td>${cotCell(r.groups.asset)}</td><td>${cotCell(r.groups.lev)}</td>
    <td class="n mono">${r.groups.lev?.index??"—"}</td><td class="n mono" style="font-size:10px">${cotRead(r)}</td></tr>`).join("")}</tbody></table></div>`;
}
function sentBar(r){return `<div class="sbar"><div class="l" style="width:${r.long}%">${r.long>14?r.long+"%":""}</div><div class="s" style="width:${r.short}%">${r.short>14?r.short+"%":""}</div></div>`}
async function loadDashboard(){
  const el=$("#v-accueil"); let d;
  try{ d=await api("/api/dashboard"); }catch{ return }
  el.innerHTML=`<div class="dash">
   ${d.headline?`<div class="panel c12"><div class="ph"><b>Cette semaine</b> · ${d.counts?d.counts.red+" 🔴 · "+d.counts.orange+" 🟠":""}<div class="r"><button class="chip" onclick="show('semaine')">ANALYSE →</button></div></div><div class="pb"><div class="headline">${esc(d.headline)}</div></div></div>`:""}
   <div class="panel c6"><div class="ph"><b>Prochaines annonces</b> · 🔴/🟠<div class="r"><button class="chip" onclick="show('calendrier')">CALENDRIER →</button></div></div>
     ${d.upcoming.map(e=>`<div class="li"><span class="t">${fDs.format(new Date(e.time)).replace(".","")} ${fT.format(new Date(e.time))}</span><i class="imp ${e.impact}"></i><span class="ccy">${e.currency}</span><span class="grow">${esc(e.title)}</span><span class="v mute">${esc(e.forecast_str)}</span><span class="cd">${countdown(e.time)}</span></div>`).join("")||'<div class="empty">Rien à venir.</div>'}</div>
   <div class="panel c6"><div class="ph"><b>Derniers chiffres</b> · réel vs consensus</div>
     ${d.released.map(e=>`<div class="li"><span class="t">${fT.format(new Date(e.time))}</span><span class="ccy">${e.currency}</span><span class="grow">${esc(e.title)}</span><span class="v"><b>${esc(e.actual_str)}</b> <span class="mute">/ ${esc(e.forecast_str)}</span></span>${verdict(e)}</div>`).join("")||'<div class="empty">Aucun chiffre publié récemment.</div>'}</div>
   <div class="panel c12"><div class="ph"><b>Banques centrales</b> · ton et semaine<div class="r"><button class="chip" onclick="show('macro')">MACRO →</button></div></div>
     <div class="stgrid">${d.stances.sort((a,b)=>b.score-a.score).map(x=>`<div class="st" onclick="show('devises');openCurrency('${x.code}')" style="cursor:pointer"><div class="c">${x.flag} ${x.code}</div><div class="r">${x.rate!=null?x.rate+"%":"—"} · ${x.red}🔴 ${x.orange}🟠</div>${stanceBadge(x)}</div>`).join("")}</div></div>
   <div class="panel c6"><div class="ph"><b>Sentiment retail</b> · % long / % short</div>
     ${d.sentiment_configured?(d.sentiment.map(r=>`<div class="li"><span class="ccy" style="min-width:64px">${esc(r.symbol)}</span><span class="grow">${sentBar(r)}</span><span class="v ${r.signal.includes("HAUSSIER")?"pos":r.signal.includes("BAISSIER")?"neg":"mute"}" style="font-size:10px">${esc(r.signal)}</span></div>`).join("")||'<div class="empty">Chargement…</div>'):'<div class="empty">Chargement du sentiment Myfxbook…</div>'}</div>
   <div class="panel c6"><div class="ph"><b>Positionnement institutionnel</b> · COT hedge funds<div class="r"><button class="chip" onclick="show('macro')">DÉTAIL →</button></div></div>
     ${(d.cot||[]).map(r=>{const g=r.groups.lev; return g?`<div class="li"><span class="ccy" style="min-width:64px">${FLAGS[r.ccy]} ${r.ccy}</span><span class="grow">${sentBar({long:g.pct_long,short:100-g.pct_long})}</span><span class="v mono ${g.net>0?"pos":"neg"}" style="font-size:10px">${kfmt(g.net)}</span><span class="v mono" style="font-size:10px">${cotRead(r)}</span></div>`:""}).join("")||'<div class="empty">Chargement du rapport COT…</div>'}</div>
   <div class="panel c6"><div class="ph"><b>Fil de nouvelles</b><div class="r"><button class="chip" onclick="show('nouvelles')">TOUT →</button></div></div>
     <div class="pb news" style="padding-top:0">${d.news.map(n=>`<a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}<small>${n.time?fT.format(new Date(n.time)):""} · ${esc(n.source||"")}</small></a>`).join("")}</div></div>
  </div>`;
}
function stanceBadgeLbl(l){return `<span class="badge ${String(l).toLowerCase()}">${esc(l)}</span>`}

/* ---------------- macro (comparatif pays + triage) ---------------- */
let COT=null, MX=null, MX_SORT=store.get("mxSort",{key:"rate",dir:-1}), SENT=null;
async function loadMacro(){
  const el=$("#v-macro");
  try{ MX=await api("/api/macro"); SENT=await api("/api/sentiment"); COT=await api("/api/cot"); }catch{ el.innerHTML='<div class="empty">Serveur injoignable.</div>'; return }
  renderMacro();
}
function mxVal(r,k){ const c=r[k]; if(!c) return null; if(k==="stance") return c.score; return c.value ?? null; }
function renderMacro(){
  const el=$("#v-macro"); const cols=MX.columns;
  const rows=[...MX.rows].sort((a,b)=>{const x=mxVal(a,MX_SORT.key),y=mxVal(b,MX_SORT.key); if(x==null) return 1; if(y==null) return -1; return (x-y)*MX_SORT.dir;});
  const cell=(r,k)=>{const c=r[k]; if(!c) return '<span class="dim">—</span>';
    if(k==="stance") return stanceBadgeLbl(c.label);
    if(k==="rate") return `${esc(c.str)}${c.change?` <span class="${c.change>0?"neg":"pos"}" style="font-size:10px">${c.change>0?"+":""}${c.change}pb</span>`:""}`;
    const cls=c.bias==="positif"?"heat-pos":c.bias==="négatif"?"heat-neg":"";
    return `<span class="${cls}" title="${esc(c.period||"")} · préc. ${esc(c.prev)}">${esc(c.str)}</span>`;};
  const sent=SENT?.data?.rows||[];
  el.innerHTML=`
   <div class="panel"><div class="ph"><b>Macro comparée</b> · clique sur une colonne pour trier · vert/rouge = dernier chiffre bon/mauvais pour la devise</div>
    <div style="overflow-x:auto"><table class="cal mx"><thead><tr><th data-k="code">Devise</th>${cols.map(c=>`<th class="n ${MX_SORT.key===c.key?"sorted":""}" data-k="${c.key}">${esc(c.label)}${MX_SORT.key===c.key?(MX_SORT.dir>0?" ▲":" ▼"):""}</th>`).join("")}</tr></thead>
    <tbody>${rows.map(r=>`<tr style="cursor:pointer" data-c="${r.code}"><td><span class="ccy">${r.flag} ${r.code}</span> <small class="dim">${esc(r.bank.split("(")[0])}</small></td>${cols.map(c=>`<td class="n">${cell(r,c.key)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>
    <p class="note" style="padding:0 12px 12px">Source : calendrier TradingView (données Trading Economics). Touche une ligne pour ouvrir la fiche du pays.</p></div>
   <div class="panel"><div class="ph"><b>Sentiment retail</b> · Myfxbook Community Outlook${SENT?.data?.updated?" · MAJ "+fT.format(new Date(SENT.data.updated*1000)):""}</div>
    ${SENT?.configured?`<div style="overflow-x:auto"><table class="cal"><thead><tr><th>Paire</th><th style="min-width:180px">Long / Short</th><th class="n">Positions</th><th class="n hide-m">Prix moy. long</th><th class="n hide-m">Prix moy. short</th><th class="n">Lecture</th></tr></thead><tbody>
      ${sent.map(r=>`<tr><td class="ccy">${esc(r.symbol)}</td><td>${sentBar(r)}</td><td class="n mute">${r.positions??"—"}</td><td class="n hide-m mute">${r.avg_long??"—"}</td><td class="n hide-m mute">${r.avg_short??"—"}</td><td class="n ${r.signal.includes("HAUSSIER")?"pos":r.signal.includes("BAISSIER")?"neg":"mute"}">${esc(r.signal)}</td></tr>`).join("")}
    </tbody></table></div>`:'<div class="empty">Chargement du sentiment Myfxbook… (mis à jour toutes les 5 min)</div>'}
   </div>
   <div class="panel"><div class="ph"><b>Positionnement institutionnel</b> · rapport COT de la CFTC${COT?.updated?" · MAJ "+fDs.format(new Date(COT.updated*1000)):""}</div>
    ${COT?.rows?.length?cotTable(COT.rows):'<div class="empty">Chargement du rapport COT…</div>'}
    <p class="note" style="padding:0 12px 12px"><b>Banques (dealers)</b> : grandes banques et intermédiaires, souvent en contrepartie de leurs clients (couverture). <b>Asset managers</b> : fonds de pension, fonds communs, assureurs. <b>Hedge funds</b> : argent spéculatif, le groupe le plus suivi pour le sentiment. Barre = % long vs short, « sem. » = variation de la position nette sur la semaine. Indice 6 mois : 0 = position la plus courte des 26 dernières semaines, 100 = la plus longue (au-dessus de 90 ou sous 10 = positionnement extrême, risque de retournement). Données au mardi, publiées le vendredi 15 h 30.</p></div>`;
  el.querySelector("thead").onclick=e=>{const th=e.target.closest("th");if(!th)return;const k=th.dataset.k;if(k==="code")return;
    MX_SORT=MX_SORT.key===k?{key:k,dir:-MX_SORT.dir}:{key:k,dir:-1};store.set("mxSort",MX_SORT);renderMacro();};
  el.querySelector("tbody").onclick=e=>{const tr=e.target.closest("tr");if(tr){show("devises");openCurrency(tr.dataset.c)}};
}

/* ---------------- devises ---------------- */
function stanceBadge(s){const l=(s?.label||"—");return `<span class="badge ${l.toLowerCase()}">${esc(l)}</span>`}
async function loadCurrencies(){
  if($("#ccyDetail").style.display==="block") return;
  try{ CCY_LIST = await api("/api/currencies"); }catch{ $("#ccyGrid").innerHTML='<div class="empty">Serveur injoignable.</div>'; return }
  $("#ccyGrid").innerHTML = CCY_LIST.map(c=>`
   <div class="ccard" data-c="${c.code}">
     <div class="h"><span style="font-size:20px">${c.flag}</span><span class="code">${c.code}</span><span class="spacer"></span>${stanceBadge(c.stance)}</div>
     <div class="bank">${esc(c.bank)}</div>
     <div class="row"><span>Taux directeur</span><span>${c.policy_rate?.rate!=null?c.policy_rate.rate+"%":"—"}${c.policy_rate?.last_change_bp?` <span class="${c.policy_rate.last_change_bp>0?"neg":"pos"}">(${c.policy_rate.last_change_bp>0?"+":""}${c.policy_rate.last_change_bp} pb)</span>`:""}</span></div>
     <div class="row"><span>Inflation</span><span>${esc(c.cpi?.value||"—")}</span></div>
     <div class="row"><span>Inflation core</span><span>${esc(c.core_cpi?.value||"—")}</span></div>
     <div class="row"><span>Semaine</span><span><span class="neg">${c.red_count} 🔴</span> · <span style="color:var(--orange)">${c.orange_count} 🟠</span></span></div>
     <div class="nx">${c.next?`▸ ${fDs.format(new Date(c.next.time))} ${fT.format(new Date(c.next.time))} — ${esc(c.next.title)}`:"▸ Aucun événement à venir"}</div>
   </div>`).join("");
}
$("#ccyGrid").addEventListener("click",e=>{const c=e.target.closest(".ccard");if(c)openCurrency(c.dataset.c)});
async function openCurrency(code){
  const el=$("#ccyDetail"); $("#ccyGrid").style.display="none"; el.style.display="block";
  el.innerHTML='<div class="empty">Chargement…</div>';
  let d; try{ d=await api("/api/currency/"+code) }catch{ el.innerHTML='<div class="empty">Erreur.</div>'; return }
  const pos=Math.max(0,Math.min(100,(d.stance.score+4)/8*100));
  const pr=d.policy_rate;
  el.innerHTML=`
  <button class="back" id="back">← TOUTES LES DEVISES</button>
  <div class="panel"><div class="ph"><b>${d.flag} ${d.code}</b> · ${esc(d.name)} · ${esc(d.bank)}<div class="r">${stanceBadge(d.stance)}</div></div>
    <div class="pb grid g2">
      <div>
        <div class="mono mute" style="font-size:11px;letter-spacing:.1em">TON DE LA BANQUE CENTRALE · SCORE ${d.stance.score>0?"+":""}${d.stance.score}</div>
        <div class="gauge"><i style="left:calc(${pos}% - 1px)"></i></div><div class="gl"><span>DOVISH</span><span>NEUTRE</span><span>HAWKISH</span></div>
        <div style="margin-top:10px">${d.stance.components.map(c=>`<div class="comp"><span>${esc(c.label)}</span><span class="${c.score>0?"neg":c.score<0?"pos":"neu"}">${c.score>0?"+":""}${c.score}</span></div>`).join("")||'<div class="dim mono">Pas assez de données encore.</div>'}</div>
        <p class="note">Hawkish = biais vers des taux plus élevés (favorable à la devise). Dovish = biais vers des baisses. Score calculé à partir des décisions de taux, de l'inflation vs la cible (${d.target}%) et du ton des nouvelles récentes.</p>
      </div>
      <div class="kpis" style="align-content:flex-start">
        <div class="kpi"><div class="l">Taux directeur</div><div class="v">${pr?.rate!=null?pr.rate+"%":"—"}</div><div class="mute mono" style="font-size:10px">${pr?fDs.format(new Date(pr.time)):""}</div></div>
        <div class="kpi"><div class="l">Dernier mouvement</div><div class="v ${pr?.last_change_bp>0?"neg":pr?.last_change_bp<0?"pos":""}">${pr?.last_change_bp?(pr.last_change_bp>0?"+":"")+pr.last_change_bp+" pb":"0 pb"}</div></div>
        <div class="kpi"><div class="l">Inflation</div><div class="v">${esc(d.cpi?.value||"—")}</div><div class="mute mono" style="font-size:10px">${esc(d.cpi?.period||"")}</div></div>
        <div class="kpi"><div class="l">Core</div><div class="v">${esc(d.core_cpi?.value||"—")}</div><div class="mute mono" style="font-size:10px">${esc(d.core_cpi?.period||"")}</div></div>
        <div class="kpi"><div class="l">Cible</div><div class="v">${d.target}%</div></div>
        ${pr?.moves_12m?.length?`<div style="width:100%" class="mono mute">${pr.moves_12m.map(m=>`${fDs.format(new Date(m.time))} : ${m.from}% → ${m.to}% (${m.bp>0?"+":""}${m.bp} pb)`).join("<br>")}</div>`:""}
      </div>
    </div></div>
  <div class="grid g2">
    <div class="panel"><div class="ph"><b>Données clés</b> · dernières publications</div>
      <div style="overflow-x:auto"><table class="cal"><thead><tr><th>Indicateur</th><th class="n">Réel</th><th class="n">Cons.</th><th class="n">Préc.</th></tr></thead><tbody>
      ${d.key_data.map(k=>`<tr><td><div class="evt"><i class="imp ${k.impact}"></i><div>${esc(k.title)} <small>${esc(k.period||"")}${k.country!==d.countries[0]?" · "+k.country:""}</small></div></div></td>
        <td class="n act ${k.surprise?.ccy_bias==="positif"?"pos":k.surprise?.ccy_bias==="négatif"?"neg":""}">${esc(k.actual)}</td><td class="n">${esc(k.forecast)}</td><td class="n mute">${esc(k.previous)}</td></tr>`).join("")||'<tr><td class="empty">Historique en cours de chargement.</td></tr>'}
      </tbody></table></div></div>
    <div class="panel"><div class="ph"><b>Graphique</b> · ${esc(d.index_symbol)}</div><div id="ccyChart" style="height:380px"></div></div>
  </div>
  <div class="panel"><div class="ph"><b>À venir</b> · 🔴 / 🟠</div><div style="overflow-x:auto"><table class="cal">${d.upcoming.length?calRows(d.upcoming):'<tr><td class="empty">Rien cette semaine.</td></tr>'}</table></div></div>
  <div class="grid g2">
    <div class="panel"><div class="ph"><b>Signaux de ton</b> · nouvelles 14 j</div><div class="pb news">${d.tone_news.map(n=>`<a href="${esc(n.link)}" target="_blank" rel="noopener"><span class="tone ${n.tone}">${n.tone.toUpperCase()}</span>${esc(n.title)}<small>${esc(n.source||"")} ${n.time?"· "+fDs.format(new Date(n.time)):""}</small></a>`).join("")||'<div class="dim mono">Aucun signal récent.</div>'}</div></div>
    <div class="panel"><div class="ph"><b>Nouvelles</b> · FinancialJuice / InvestingLive / Investing.com</div><div class="pb news">${d.news.map(n=>`<a href="${esc(n.link)}" target="_blank" rel="noopener">${esc(n.title)}<small>${esc(n.source||"")} ${n.time?"· "+fDs.format(new Date(n.time))+" "+fT.format(new Date(n.time)):""}</small></a>`).join("")||'<div class="dim mono">Aucune nouvelle.</div>'}</div></div>
  </div>`;
  $("#back").onclick=()=>{el.style.display="none";$("#ccyGrid").style.display="";loadCurrencies()};
  tvWidget($("#ccyChart"),"embed-widget-advanced-chart.js",chartCfg(d.index_symbol,"240"));
}

/* ---------------- graphiques ---------------- */
function renderCharts(){
  $("#pager").innerHTML = CHART_PAGES.map((p,i)=>`<button class="chip ${i===CHART_PAGE?"on":""}" data-p="${i}">${i+1}. ${esc(p.name)}</button>`).join("");
  const page=CHART_PAGES[CHART_PAGE]; const tf=$("#tf").value;
  $("#charts").innerHTML = page.syms.map((_,i)=>`<div class="chartbox" id="ch${i}"></div>`).join("");
  page.syms.forEach((s,i)=>tvWidget($("#ch"+i),"embed-widget-advanced-chart.js",chartCfg(s,tf)));
}
$("#pager").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;CHART_PAGE=+b.dataset.p;store.set("chartPage",CHART_PAGE);renderCharts()});
$("#tf").onchange=renderCharts;

/* ---------------- saisonnalité ---------------- */
let seasonInit=false;
function mmdd(d){return String(d.getMonth()+1).padStart(2,"0")+"-"+String(d.getDate()).padStart(2,"0")}
async function initSeason(){
  if(seasonInit) return; seasonInit=true;
  try{ const syms=await api("/api/seasonality/symbols"); $("#sSym").innerHTML=syms.map(s=>`<option>${esc(s)}</option>`).join(""); }catch{}
  const t=new Date(); $("#sStart").value=mmdd(t); $("#sEnd").value=mmdd(new Date(t.getTime()+30*864e5));
  $("#sGo").onclick=runSeason; runSeason();
}
function doyLabel(i){const d=new Date(2023,0,1);d.setDate(i+1);return mmdd(d)}
function mkChart(id,cfg){ if(charts[id]) charts[id].destroy(); charts[id]=new Chart(document.getElementById(id),cfg); }
const gridC="rgba(255,255,255,0.05)", tickC="#7d8896";
async function runSeason(){
  const out=$("#sOut"); out.innerHTML='<div class="empty">Calcul de la saisonnalité…</div>';
  const q=new URLSearchParams({symbol:$("#sSym").value||"EURUSD",years:$("#sYears").value,start:$("#sStart").value,end:$("#sEnd").value});
  let r; try{ r=await api("/api/seasonality?"+q) }catch(e){ out.innerHTML=`<div class="empty">Données indisponibles : ${esc(e.message.slice(0,120))}</div>`; return }
  const w=r.window, M=["Jan","Fév","Mar","Avr","Mai","Juin","Juil","Août","Sep","Oct","Nov","Déc"];
  out.innerHTML=`
   ${w?`<div class="panel"><div class="ph"><b>Fenêtre ${esc(w.start)} → ${esc(w.end)}</b> · ${w.n} années</div><div class="pb"><div class="kpis">
     <div class="kpi"><div class="l">Moyenne</div><div class="v ${w.avg>0?"pos":"neg"}">${w.avg>0?"+":""}${w.avg}%</div></div>
     <div class="kpi"><div class="l">Médiane</div><div class="v ${w.median>0?"pos":"neg"}">${w.median>0?"+":""}${w.median}%</div></div>
     <div class="kpi"><div class="l">Années gagnantes</div><div class="v">${w.win_rate}%</div></div>
     <div class="kpi"><div class="l">Meilleure</div><div class="v pos">+${w.best}%</div></div>
     <div class="kpi"><div class="l">Pire</div><div class="v neg">${w.worst}%</div></div></div></div></div>`:""}
   <div class="panel"><div class="ph"><b>${esc(r.symbol)}</b> · courbe saisonnière ${r.years[0]}–${r.years[r.years.length-1]} vs ${new Date().getFullYear()}<div class="r mono">dernier ${r.last_price}</div></div>
     <div class="pb"><div class="canvas-wrap"><canvas id="cSeason"></canvas></div></div></div>
   <div class="grid g2">
     <div class="panel"><div class="ph"><b>Rendement moyen par mois</b></div><div class="pb"><div class="canvas-wrap"><canvas id="cMonth"></canvas></div></div></div>
     ${w?`<div class="panel"><div class="ph"><b>Fenêtre · année par année</b></div><div class="pb"><div class="canvas-wrap"><canvas id="cWin"></canvas></div></div></div>`:""}
   </div>
   <div class="panel"><div class="ph"><b>Statistiques mensuelles</b></div><div style="overflow-x:auto"><table class="cal"><thead><tr><th>Mois</th><th class="n">Moy.</th><th class="n">Médiane</th><th class="n">% positif</th><th class="n">N</th></tr></thead><tbody>
     ${r.monthly.map(m=>`<tr><td>${M[m.month-1]}</td><td class="n ${m.avg>0?"pos":"neg"}">${m.avg??"—"}%</td><td class="n">${m.median??"—"}%</td><td class="n">${m.win_rate??"—"}%</td><td class="n mute">${m.n}</td></tr>`).join("")}
   </tbody></table></div></div>`;
  if(typeof Chart==="undefined") return;
  Chart.defaults.color=tickC; Chart.defaults.font.family="JetBrains Mono, ui-monospace, monospace"; Chart.defaults.font.size=10;
  const cur=new Array(366).fill(null); r.current.forEach(p=>cur[p.doy-1]=p.v);
  mkChart("cSeason",{type:"line",data:{labels:r.seasonal.map((_,i)=>doyLabel(i)),datasets:[
      {label:"Moyenne saisonnière",data:r.seasonal,borderColor:"#ff9f1a",borderWidth:2,pointRadius:0,tension:.15},
      {label:String(new Date().getFullYear()),data:cur,borderColor:"#4aa3ff",borderWidth:1.5,pointRadius:0,spanGaps:true}]},
    options:{maintainAspectRatio:false,interaction:{mode:"index",intersect:false},scales:{x:{grid:{color:gridC},ticks:{maxTicksLimit:12}},y:{grid:{color:gridC},ticks:{callback:v=>v+"%"}}},
      plugins:{legend:{labels:{boxWidth:10}},tooltip:{callbacks:{label:c=>`${c.dataset.label}: ${c.parsed.y?.toFixed(2)}%`}}}}});
  mkChart("cMonth",{type:"bar",data:{labels:M,datasets:[{label:"Moy. %",data:r.monthly.map(m=>m.avg),backgroundColor:r.monthly.map(m=>m.avg>0?"#18c787":"#ef4454")}]},
    options:{maintainAspectRatio:false,scales:{x:{grid:{display:false}},y:{grid:{color:gridC}}},plugins:{legend:{display:false},
      tooltip:{callbacks:{afterLabel:c=>`Positif ${r.monthly[c.dataIndex].win_rate}% des années`}}}}});
  if(w) mkChart("cWin",{type:"bar",data:{labels:w.per_year.map(p=>p.year),datasets:[{data:w.per_year.map(p=>p.ret),backgroundColor:w.per_year.map(p=>p.ret>0?"#18c787":"#ef4454")}]},
    options:{maintainAspectRatio:false,scales:{x:{grid:{display:false}},y:{grid:{color:gridC},ticks:{callback:v=>v+"%"}}},plugins:{legend:{display:false}}}});
}

/* ---------------- alertes / notifications ---------------- */
const isIOS=/iPad|iPhone|iPod/.test(navigator.userAgent)||(navigator.platform==="MacIntel"&&navigator.maxTouchPoints>1);
const standalone=matchMedia("(display-mode: standalone)").matches||navigator.standalone===true;
function b64ToU8(b){const p="=".repeat((4-b.length%4)%4);const s=atob((b+p).replace(/-/g,"+").replace(/_/g,"/"));return Uint8Array.from([...s].map(c=>c.charCodeAt(0)))}
async function currentSub(){ if(!("serviceWorker" in navigator)) return null; const reg=await navigator.serviceWorker.ready; return reg.pushManager?.getSubscription(); }
async function renderAlerts(){
  const el=$("#v-alertes"); const h=await health()||{};
  const supported="serviceWorker" in navigator && "PushManager" in window;
  const sub=supported? await currentSub():null;
  let prefs=null; if(sub){ try{ prefs=(await api("/api/push/get",{method:"POST",body:JSON.stringify({endpoint:sub.endpoint})})).prefs }catch{} }
  prefs = prefs || {currencies:[...CCYS],impacts:["high","medium"],reminder:true,release:true,weekly:true,live:true};
  if(prefs.live===undefined) prefs.live=true;
  let st={}; try{ st=await api("/api/settings"); }catch{}
  el.innerHTML=`
   ${isIOS&&!standalone?`<div class="ios"><b>📱 Sur iPhone :</b> les notifications fonctionnent seulement si le site est installé.<br>
     1. Touche <b>Partager</b> (carré avec flèche) dans Safari<br>2. <b>Sur l'écran d'accueil</b><br>3. Ouvre l'app <b>Macro</b> depuis l'écran d'accueil, puis reviens ici et touche <b>Activer</b>.</div>`:""}
   <div class="panel" id="phoneLink" style="display:none"><div class="ph"><b>Lien pour ton téléphone</b></div>
     <div class="pb" style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">
       <div id="qr" style="background:#fff;padding:8px;border-radius:4px;line-height:0"></div>
       <div><div class="mono" style="font-size:13px;word-break:break-all" id="pubUrl"></div>
       <p class="note">Scanne le code avec l'appareil photo de ton iPhone, ouvre dans Safari, puis Partager → « Sur l'écran d'accueil ».<br>Ce lien change si la fenêtre « Lien téléphone » est fermée ou si l'ordinateur redémarre.</p></div>
     </div></div>
   <div class="panel"><div class="ph"><b>Notifications</b><div class="r">${sub?'<span class="badge dovish">ACTIVES</span>':'<span class="badge neutre">INACTIVES</span>'}</div></div>
     <div class="pb">
       ${supported?"":'<p class="note">Ce navigateur ne supporte pas les notifications push.</p>'}
       <div class="chips"><button class="btn" id="pushOn" ${!supported?"disabled":""}>${sub?"RÉ-ACTIVER":"ACTIVER LES NOTIFICATIONS"}</button>
       <button class="btn ghost" id="pushTest" ${!sub?"disabled":""}>ENVOYER UN TEST</button></div>
       <p class="note">Tu reçois : un rappel ${"<b>avant</b>"} chaque annonce 🔴/🟠, le <b>chiffre réel</b> dès sa sortie (avec consensus, précédent et écart), et l'<b>analyse du dimanche</b>.</p>
     </div></div>
   <div class="panel"><div class="ph"><b>Préférences</b></div><div class="pb">
     <div class="mono mute" style="font-size:11px;margin-bottom:6px">DEVISES</div>
     <div class="chips" id="pCcy">${CCYS.map(c=>`<button class="chip ${prefs.currencies.includes(c)?"on":""}" data-c="${c}">${FLAGS[c]} ${c}</button>`).join("")}</div>
     <div class="mono mute" style="font-size:11px;margin:12px 0 6px">IMPACT</div>
     <div class="chips" id="pImp">${[["high","🔴 ROUGE"],["medium","🟠 ORANGE"]].map(([k,l])=>`<button class="chip ${prefs.impacts.includes(k)?"on":""}" data-i="${k}">${l}</button>`).join("")}</div>
     <div class="mono mute" style="font-size:11px;margin:12px 0 6px">TYPES</div>
     <div class="chips" id="pType">${[["reminder","⏰ RAPPEL AVANT"],["release","🟢🔴 CHIFFRE RÉEL"],["live","🎙️ BANQUIERS EN DIRECT"],["weekly","📊 ANALYSE DIMANCHE"]].map(([k,l])=>`<button class="chip ${prefs[k]?"on":""}" data-t="${k}">${l}</button>`).join("")}</div>
     <div style="margin-top:14px"><button class="btn" id="pSave" ${!sub?"disabled":""}>ENREGISTRER</button></div>
   </div></div>
   <div class="panel"><div class="ph"><b>Sentiment retail</b> · compte Myfxbook (optionnel) ${st.myfxbook_configured?'<span class="badge dovish">CONNECTÉ</span>':''}</div><div class="pb">
     <p class="note" style="margin-top:0">Le % de traders long/short est lu automatiquement sur la page publique Myfxbook, sans compte. Si un jour elle bloque l'accès, tu pourras entrer ici un compte Myfxbook gratuit comme solution de secours.</p>
     <div class="chips"><input id="mfxE" type="email" placeholder="Courriel Myfxbook" value="${esc(st.myfxbook_email||"")}" style="flex:1;min-width:200px">
     <input id="mfxP" type="password" placeholder="Mot de passe Myfxbook" style="flex:1;min-width:160px">
     <button class="btn" id="mfxSave">CONNECTER</button></div></div></div>
   <div class="panel"><div class="ph"><b>État du serveur</b></div><div class="pb mono" style="font-size:12px;line-height:1.8">
     Dernière MAJ calendrier : ${h.week_updated?fDs.format(new Date(h.week_updated))+" "+fT.format(new Date(h.week_updated)):"—"}<br>
     Sources en erreur : ${h.errors?.length?`<span class="neg">${esc(h.errors.join(" | "))}</span>`:'<span class="pos">aucune</span>'}<br>
     Analyse IA du dimanche : ${h.ai?'<span class="pos">active</span>':'<span class="mute">désactivée (version automatique sans IA)</span>'}<br>
     Trading Economics API : ${h.te?'<span class="pos">active</span>':'<span class="mute">non configurée</span>'}<br>
     Mot de passe : ${h.auth?'<span class="pos">oui</span>':'<span class="neg">non (recommandé si le site est public)</span>'}
   </div></div>`;
  try{
    const {url}=await api("/api/public-url");
    if(url && location.hostname!==new URL(url).hostname){
      $("#phoneLink").style.display="block"; $("#pubUrl").textContent=url;
      if(typeof qrcode!=="undefined"){ const q=qrcode(0,"M"); q.addData(url); q.make(); $("#qr").innerHTML=q.createImgTag(4,0); }
    }
  }catch{}
  const P={...prefs};
  $("#pCcy").onclick=e=>{const b=e.target.closest("button");if(!b)return;const c=b.dataset.c;P.currencies=P.currencies.includes(c)?P.currencies.filter(x=>x!==c):[...P.currencies,c];b.classList.toggle("on")};
  $("#pImp").onclick=e=>{const b=e.target.closest("button");if(!b)return;const i=b.dataset.i;P.impacts=P.impacts.includes(i)?P.impacts.filter(x=>x!==i):[...P.impacts,i];b.classList.toggle("on")};
  $("#pType").onclick=e=>{const b=e.target.closest("button");if(!b)return;const t=b.dataset.t;P[t]=!P[t];b.classList.toggle("on")};
  $("#pSave").onclick=async()=>{const s=await currentSub();if(!s)return;await api("/api/push/prefs",{method:"POST",body:JSON.stringify({endpoint:s.endpoint,prefs:P})});toast("Préférences enregistrées")};
  $("#mfxSave").onclick=async()=>{
    await api("/api/settings",{method:"POST",body:JSON.stringify({myfxbook_email:$("#mfxE").value,myfxbook_password:$("#mfxP").value})});
    try{ await api("/api/sentiment/refresh",{method:"POST"}); toast("Myfxbook connecté ✅"); }catch(e){ toast("Échec Myfxbook : "+e.message.slice(0,60)); }
    renderAlerts();
  };
  $("#pushTest").onclick=async()=>{const r=await api("/api/push/test",{method:"POST"});toast(r.sent?"Test envoyé":"Aucun abonné")};
  $("#pushOn").onclick=async()=>{
    try{
      const perm=await Notification.requestPermission(); if(perm!=="granted"){toast("Permission refusée");return}
      const reg=await navigator.serviceWorker.ready; const {key}=await api("/api/push/key");
      let s=await reg.pushManager.getSubscription();
      if(!s) s=await reg.pushManager.subscribe({userVisibleOnly:true,applicationServerKey:b64ToU8(key)});
      await api("/api/push/subscribe",{method:"POST",body:JSON.stringify({subscription:s.toJSON(),prefs:P})});
      toast("Notifications activées ✅"); renderAlerts();
    }catch(e){ toast("Erreur : "+e.message.slice(0,60)) }
  };
}

/* ---------------- démarrage ---------------- */
if("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js",{scope:"/"}).catch(console.warn);
renderFilters(); initTape(); health(); tick();
loadCal().then(loadWeekly);
const startView=(location.hash||"#accueil").slice(1); show(["accueil","semaine","calendrier","fiches","nouvelles","macro","devises","graphiques","saison","alertes"].includes(startView)?startView:"accueil");
setInterval(()=>{ if(!document.hidden&&$("#v-calendrier").classList.contains("on")) loadCalView(); }, 60000);
setInterval(()=>{ if(!document.hidden){ loadCal(); if($("#v-nouvelles").classList.contains("on")) loadNews(); if($("#v-accueil").classList.contains("on")) loadDashboard(); } }, 20000);
setInterval(()=>{ if(!document.hidden){ health(); } }, 60000);
document.addEventListener("visibilitychange",()=>{ if(!document.hidden){ loadCal(); health(); } });
