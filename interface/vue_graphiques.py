"""
interface/vue_graphiques.py — Fenêtre « graphiques seulement » (adresse ?view=charts).

Affiche uniquement la grille TradingView, sur toute la fenêtre : pas de menu,
pas de barre latérale, pas de bandeau. Pensé pour être ouvert dans une fenêtre
à part (par ex. sur un second écran).

Paramètres d'adresse acceptés :
    view=charts      active cette vue (obligatoire)
    cfg=<texte>      réglages encodés par le bouton de l'onglet TradingView (optionnel)
    layout=1|2|4     force le nombre de graphiques (optionnel, ex. ?view=charts&layout=4)
    fs=1             propose le plein écran à l'ouverture (ajouté par le bouton de CMP)
Sans cfg, ce sont les réglages de BASE (tradingview.toml) qui s'appliquent.

Commandes de la fenêtre : approcher la souris du HAUT de la fenêtre fait apparaître,
en haut à droite, un bouton plein écran et un petit « X » pour fermer.
Pourquoi le plein écran ? Un site web n'a pas le droit de retirer lui-même la barre
d'adresse du navigateur (sécurité anti-hameçonnage). La fenêtre « popup » la réduit
au minimum ; le plein écran (demandé par un clic, comme l'exigent les navigateurs)
la fait disparaître complètement. Échap ramène la fenêtre normale.
"""

from __future__ import annotations

import streamlit as st
import streamlit.components.v1 as components

from interface import tradingview as tv

# Masque tout ce qui n'est pas la grille et étire le cadre des graphiques sur 100 % de la fenêtre.
CSS_PLEIN_ECRAN = """
<style>
header[data-testid="stHeader"], [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stStatusWidget"], footer { display: none !important; }
.block-container, [data-testid="stMainBlockContainer"] { padding: 0 !important; max-width: 100% !important; }
[data-testid="stAppViewContainer"], [data-testid="stMain"], .main { padding: 0 !important; overflow: hidden !important; }
[data-testid="stVerticalBlock"] { gap: 0 !important; }
iframe { height: 100vh !important; width: 100% !important; display: block; border: 0; }
</style>
"""

# Bande invisible en haut de la fenêtre + boutons qui apparaissent au survol.
# (La souris au-dessus d'un graphique TradingView n'est pas visible pour la page :
#  chaque graphique est un cadre à part. D'où une bande de détection de 10 px en haut.)
COMMANDES = """
<style>
#tq_zone{position:fixed;top:0;left:0;right:0;height:10px;z-index:2147483646}
#tq_barre{position:fixed;top:8px;right:10px;z-index:2147483647;display:flex;gap:6px;
  opacity:0;pointer-events:none;transform:translateY(-6px);transition:opacity .15s,transform .15s}
#tq_barre.visible{opacity:1;pointer-events:auto;transform:none}
#tq_barre button{width:32px;height:32px;border-radius:16px;border:1px solid #2A3644;cursor:pointer;
  background:rgba(10,14,20,.92);color:#E6EDF3;display:flex;align-items:center;justify-content:center;padding:0}
#tq_barre button:hover{border-color:#FF9F1C;color:#FF9F1C}
#tq_barre #tq_fermer:hover{background:#FF5C5C;border-color:#FF5C5C;color:#fff}
#tq_invite{position:fixed;inset:0;z-index:2147483645;display:flex;align-items:center;justify-content:center;
  background:rgba(10,14,20,.6);cursor:pointer;font-family:-apple-system,Segoe UI,Roboto,sans-serif}
#tq_invite .boite{background:#121821;border:1px solid #FF9F1C;border-radius:10px;padding:20px 28px;
  color:#E6EDF3;text-align:center;font-size:15px;line-height:1.5}
#tq_invite .boite b{color:#FF9F1C}
#tq_invite .petit{font-size:12px;color:#8B98A9}
#tq_invite button{margin-top:10px;background:none;border:1px solid #2A3644;color:#8B98A9;border-radius:6px;
  padding:4px 10px;cursor:pointer;font-size:12px}
</style>
<div id="tq_zone"></div>
<div id="tq_barre">
  <button id="tq_plein" title="Full screen (Esc to exit)">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
      stroke-linecap="round"><path d="M4 9V4h5M20 9V4h-5M4 15v5h5M20 15v5h-5"/></svg></button>
  <button id="tq_fermer" title="Close">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6"
      stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button>
</div>
__INVITE__
<script>
(function () {
  const zone = document.getElementById("tq_zone"), barre = document.getElementById("tq_barre");
  let minuterie = null;
  const montrer = () => { clearTimeout(minuterie); barre.classList.add("visible"); };
  const cacher = (delai) => { clearTimeout(minuterie);
    minuterie = setTimeout(() => barre.classList.remove("visible"), delai); };
  zone.addEventListener("mouseenter", montrer); zone.addEventListener("mousemove", montrer);
  zone.addEventListener("mouseleave", () => cacher(1500));
  barre.addEventListener("mouseenter", montrer); barre.addEventListener("mouseleave", () => cacher(700));

  // Fenêtre la plus haute de la même origine (la page de l'app, ou l'enveloppe de Streamlit Cloud).
  function haut() { try { void window.top.document; return window.top; } catch (e) { return window.parent; } }
  // Exécute un petit script DANS la fenêtre du haut (fermer une fenêtre exige que ce soit elle qui le demande).
  function dansLeHaut(code) {
    try { const d = haut().document, s = d.createElement("script"); s.textContent = code;
      d.body.appendChild(s); s.remove(); return true; } catch (e) { return false; }
  }
  function enPleinEcran() {
    try { return !!(document.fullscreenElement || haut().document.fullscreenElement); }
    catch (e) { return !!document.fullscreenElement; }
  }
  // Plein écran du cadre des graphiques ; sinon de la page entière.
  function pleinEcran() {
    const essai = (el) => el && el.requestFullscreen ? el.requestFullscreen() : Promise.reject();
    return essai(document.documentElement).catch(() => essai(haut().document.documentElement)).catch(() => {});
  }
  function sortirPleinEcran() {
    for (const d of [document, haut().document]) {
      try { if (d.fullscreenElement) d.exitFullscreen().catch(() => {}); } catch (e) {}
    }
  }
  document.getElementById("tq_plein").addEventListener("click", () => {
    if (enPleinEcran()) sortirPleinEcran(); else pleinEcran();
  });
  document.getElementById("tq_fermer").addEventListener("click", () => {
    sortirPleinEcran();
    // Une fenêtre ouverte par le bouton de l'app se ferme ; sinon (favori, onglet normal)
    // le navigateur refuse : on revient alors à la fonction CMP du terminal.
    if (!dansLeHaut("window.close()")) { try { window.top.close(); } catch (e) {} }
    setTimeout(() => {
      dansLeHaut("location.href = location.pathname.replace(/[^/]*$/, '') + 'cmp';");
    }, 350);
  });

  const invite = document.getElementById("tq_invite");
  if (invite) {
    invite.addEventListener("click", () => { invite.remove(); pleinEcran(); });
    document.getElementById("tq_rester").addEventListener("click", (ev) => { ev.stopPropagation(); invite.remove(); });
  }
})();
</script>
"""

INVITE = """
<div id="tq_invite"><div class="boite">
  <b>Click anywhere for full screen</b><br>
  <span class="petit">No browser bar, only the charts · move the mouse to the top for the X · Esc to exit</span><br>
  <button id="tq_rester">Stay in this window</button>
</div></div>
"""


def reglages_depuis_adresse() -> dict:
    """Réglages de la fenêtre : ceux de l'adresse s'ils sont valides, sinon la base commune."""
    parametres = st.query_params
    reglages = None
    if "cfg" in parametres:
        brut = tv.decoder(parametres["cfg"])
        reglages = tv.valider(brut) if brut else None
    if reglages is None:
        reglages = tv.charger_base()
    disposition = parametres.get("layout")
    if disposition in ("1", "2", "4"):
        reglages["display"]["layout"] = int(disposition)
    return reglages


def commandes(invite: bool) -> str:
    """Boutons survolables (plein écran, fermer) et, si demandé, l'invitation au plein écran."""
    return COMMANDES.replace("__INVITE__", INVITE if invite else "")


def afficher() -> None:
    st.markdown(CSS_PLEIN_ECRAN, unsafe_allow_html=True)
    page, hauteur = tv.html_grille(reglages_depuis_adresse(), plein_ecran=True)
    page += commandes(st.query_params.get("fs") == "1")
    # La hauteur passée ici n'est qu'une valeur de départ : le CSS ci-dessus étire le cadre à 100vh.
    components.html(page, height=max(hauteur, 600))


def bouton_ouvrir(adresse_relative: str) -> str:
    """Bouton de CMP : ouvre la grille dans une fenêtre « popup » à part (sans onglets ni barre
    de favoris), à la taille de l'écran. Si le navigateur bloque la fenêtre, ouvre un onglet."""
    return f"""
<style>
html,body{{margin:0;background:transparent}}
a{{display:flex;align-items:center;justify-content:center;gap:8px;box-sizing:border-box;height:40px;width:100%;
  border-radius:8px;background:#FF9F1C;color:#0A0E14;text-decoration:none;
  font:600 14px/1 -apple-system,Segoe UI,Roboto,"Source Sans Pro",sans-serif}}
a:hover{{background:#FFB347}}
</style>
<a id="ouvrir" href="{adresse_relative}" target="_blank" rel="noopener">
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"
    stroke-linecap="round"><path d="M14 4h6v6M20 4l-9 9M19 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V6a1 1 0 0 1 1-1h5"/></svg>
  Open charts in a separate window (charts only)
</a>
<script>
document.getElementById("ouvrir").addEventListener("click", function (ev) {{
  const adresse = new URL(this.getAttribute("href"), document.baseURI).href;
  const s = window.screen, l = s.availLeft || 0, t = s.availTop || 0;
  const options = "popup=yes,left=" + l + ",top=" + t + ",width=" + s.availWidth + ",height=" + s.availHeight;
  const fenetre = window.open(adresse, "tq_graphiques", options);
  if (fenetre) {{ ev.preventDefault(); try {{ fenetre.focus(); }} catch (e) {{}} }}
  // sinon : fenêtre bloquée -> le lien ouvre simplement un nouvel onglet
}});
</script>
"""
