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
let FILTER = store.get("calFilter",{ccy:CCYS,imp:["high","medium"]});

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
  document.querySelectorAll(".view").forEach(x=>x.classList.toggle("on",x.id==="v-"+v));
  document.querySelectorAll("#tabs button").forEach(b=>b.classList.toggle("on",b.dataset.v===v));
  if(location.hash!=="#"+v) history.replaceState(null,"","#"+v);
  if(v==="graphiques") renderCharts();
  if(v==="devises") loadCurrencies();
  if(v==="nouvelles") loadNews();
  if(v==="alertes") renderAlerts();
  if(v==="saison") initSeason();
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

/* ---------------- calendrier ---------------- */
function surpriseCell(e){
  const s=e.surprise; if(!s) return '<span class="dim">—</span>';
  const c = s.ccy_bias==="positif"?"pos":s.ccy_bias==="négatif"?"neg":"neu";
  return `<span class="${c}">${esc(s.diff_str)}</span>`;
}
function calRows(events, {grouped=true}={}){
  const now=Date.now();
  const nextId=(events.find(e=>!e.released&&new Date(e.time).getTime()>now-60000)||{}).id;
  const hasTE = events.some(e=>e.te_forecast_str);
  let h=`<thead><tr><th>Heure</th><th>Dev.</th><th>Événement</th><th class="n">Réel</th><th class="n">Cons.</th><th class="n">Préc.</th>${hasTE?'<th class="n hide-m">TE</th>':""}<th class="n hide-m">Écart</th></tr></thead><tbody>`;
  let day="";
  for(const e of events){
    const d=fD.format(new Date(e.time));
    if(grouped && d!==day){day=d;h+=`<tr class="day"><td colspan="${hasTE?8:7}">${esc(d.toUpperCase())}</td></tr>`}
    const past=new Date(e.time).getTime()<now && e.released;
    const act=e.released?`<span class="act ${e.surprise?.ccy_bias==="positif"?"pos":e.surprise?.ccy_bias==="négatif"?"neg":""}">${esc(e.actual_str)}</span>`:'<span class="dim">…</span>';
    h+=`<tr class="${past?"past":""} ${e.id===nextId?"nextev":""}">
      <td class="mono">${fT.format(new Date(e.time))}</td>
      <td><span class="ccy">${FLAGS[e.currency]||""} ${e.currency}</span></td>
      <td><div class="evt"><i class="imp ${e.impact}"></i><div>${esc(e.title)} <small>${esc(e.period||"")}${e.country&&!["US","GB","JP","CA","AU","NZ","CH","CN"].includes(e.country)?" · "+e.country:""}</small>
        <div class="src">${esc((e.sources||[]).join(" · "))}</div></div></div></td>
      <td class="n">${act}</td><td class="n">${esc(e.forecast_str)}</td><td class="n mute">${esc(e.previous_str)}</td>
      ${hasTE?`<td class="n hide-m mute">${esc(e.te_forecast_str||"—")}</td>`:""}
      <td class="n hide-m">${surpriseCell(e)}</td></tr>`;
  }
  return h+"</tbody>";
}
function renderFilters(){
  $("#calCcy").innerHTML = CCYS.map(c=>`<button class="chip ${FILTER.ccy.includes(c)?"on":""}" data-c="${c}">${FLAGS[c]} ${c}</button>`).join("")
    + `<button class="chip" data-c="ALL">TOUT</button>`;
  $("#calImp").innerHTML = [["high","🔴 ROUGE"],["medium","🟠 ORANGE"]].map(([k,l])=>`<button class="chip ${FILTER.imp.includes(k)?"on":""}" data-i="${k}">${l}</button>`).join("");
}
$("#calCcy").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;
  const c=b.dataset.c; if(c==="ALL") FILTER.ccy = FILTER.ccy.length===CCYS.length?[]:[...CCYS];
  else FILTER.ccy = FILTER.ccy.includes(c)?FILTER.ccy.filter(x=>x!==c):[...FILTER.ccy,c];
  store.set("calFilter",FILTER); renderFilters(); renderCal();});
$("#calImp").addEventListener("click",e=>{const b=e.target.closest("button");if(!b)return;const i=b.dataset.i;
  FILTER.imp = FILTER.imp.includes(i)?FILTER.imp.filter(x=>x!==i):[...FILTER.imp,i]; store.set("calFilter",FILTER); renderFilters(); renderCal();});
$("#refreshCal").onclick=async()=>{toast("Actualisation…");try{await api("/api/calendar/refresh",{method:"POST"});await loadCal();toast("À jour")}catch{toast("Échec")}};

function renderCal(){
  const ev=(CAL.events||[]).filter(e=>FILTER.ccy.includes(e.currency)&&FILTER.imp.includes(e.impact));
  $("#calTable").innerHTML = ev.length? calRows(ev) : `<tr><td class="empty">Aucun événement pour ces filtres.${CAL.errors?.length?"<br>"+esc(CAL.errors.join(" | ")):""}</td></tr>`;
}
async function loadCal(){
  try{ CAL = await api("/api/calendar"); renderCal(); tick(); if($("#v-semaine").classList.contains("on")&&!WEEK) loadWeekly(); }catch(e){console.warn(e)}
}

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
  prefs = prefs || {currencies:[...CCYS],impacts:["high","medium"],reminder:true,release:true,weekly:true};
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
     <div class="chips" id="pType">${[["reminder","⏰ RAPPEL AVANT"],["release","📈 CHIFFRE RÉEL"],["weekly","📊 ANALYSE DIMANCHE"]].map(([k,l])=>`<button class="chip ${prefs[k]?"on":""}" data-t="${k}">${l}</button>`).join("")}</div>
     <div style="margin-top:14px"><button class="btn" id="pSave" ${!sub?"disabled":""}>ENREGISTRER</button></div>
   </div></div>
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
const startView=(location.hash||"#semaine").slice(1); show(["semaine","calendrier","nouvelles","devises","graphiques","saison","alertes"].includes(startView)?startView:"semaine");
setInterval(()=>{ if(!document.hidden){ loadCal(); if($("#v-nouvelles").classList.contains("on")) loadNews(); } }, 20000);
setInterval(()=>{ if(!document.hidden){ health(); } }, 60000);
document.addEventListener("visibilitychange",()=>{ if(!document.hidden){ loadCal(); health(); } });
