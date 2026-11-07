// ---------------------------------------------------------------------------
//  Citazioni cliccabili e finestra modale (condiviso tra crash test, stampa e confronto)
//  Una citazione [S12] o [L3@41:20] diventa un bottone: cliccandolo si legge
//  il testo vero della slide o della videolezione, preso dal server.
// ---------------------------------------------------------------------------
(function () {
  const esc = t => String(t ?? "").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  const RE_CIT = /\[?\b(S\d{1,3}|L\d{1,2}@\d{1,3}:\d{2})\b\]?/g;
  const cache = {};
  let corsoCorrente = "";

  function chip(id) {
    return `<button type="button" class="cit" data-fonte="${esc(id)}" title="Leggi la fonte">${id.startsWith("S") ? "📄" : "🎬"} ${esc(id)}</button>`;
  }

  // sostituisce le citazioni nel testo (non dentro bottoni, link o codice) con i chip cliccabili
  function linka(el, corso) {
    if (!el) return;
    if (corso) corsoCorrente = corso;
    const w = document.createTreeWalker(el, NodeFilter.SHOW_TEXT, {
      acceptNode: n => n.parentElement.closest("button,a,code,pre,textarea,.cit,.fonte-box") ? NodeFilter.FILTER_REJECT
        : (RE_CIT.test(n.nodeValue) ? (RE_CIT.lastIndex = 0, NodeFilter.FILTER_ACCEPT) : NodeFilter.FILTER_REJECT)
    });
    const nodi = []; while (w.nextNode()) nodi.push(w.currentNode);
    nodi.forEach(n => {
      const span = document.createElement("span");
      span.innerHTML = esc(n.nodeValue).replace(RE_CIT, (m, id) => chip(id));
      n.replaceWith(...span.childNodes);
    });
  }

  async function leggi(id, corso) {
    const k = (corso || corsoCorrente) + "|" + id;
    if (!cache[k]) {
      cache[k] = fetch(`/api/fonte/${encodeURIComponent(corso || corsoCorrente)}/${encodeURIComponent(id)}`)
        .then(async r => r.ok ? r.json() : Promise.reject(new Error((await r.json()).detail || "Fonte non trovata")));
      cache[k].catch(() => delete cache[k]);
    }
    return cache[k];
  }

  function boxFonte(f) {
    if (f.tipo === "slide") {
      return `<div class="fonte-box"><div class="fb-tit">📄 Slide ${esc(f.id.slice(1))} · Lezione ${f.lezione}${f.titolo ? ` · <b>${esc(f.titolo)}</b>` : ""}</div>
        <div class="fb-testo">${esc(f.testo)}</div></div>`;
    }
    const righe = (f.contesto && f.contesto.length ? f.contesto : [{id: f.id, testo: f.testo, corrente: true}])
      .map(x => `<div class="fb-riga ${x.corrente ? "on" : ""}"><span class="t">${esc(x.id.split("@")[1])}</span>${esc(x.testo)}</div>`).join("");
    const nota = f.richiesto && f.richiesto !== f.id ? `<div class="fb-nota">Citato come ${esc(f.richiesto)}: riga più vicina ${esc(f.id)}.</div>` : "";
    return `<div class="fonte-box"><div class="fb-tit">🎬 Videolezione ${f.lezione} · minuto ${esc(f.id.split("@")[1])}</div>${nota}${righe}</div>`;
  }

  // --- finestra modale ----------------------------------------------------
  let modale;
  function apri(html, opz = {}) {
    if (!modale) {
      modale = document.createElement("div");
      modale.className = "modale";
      modale.innerHTML = `<div class="modale-fondo"></div><div class="modale-box" role="dialog" aria-modal="true"><button type="button" class="sec modale-x" aria-label="Chiudi">✕</button><div class="modale-corpo"></div></div>`;
      document.body.appendChild(modale);
      modale.querySelector(".modale-fondo").onclick = chiudi;
      modale.querySelector(".modale-x").onclick = chiudi;
      document.addEventListener("keydown", e => { if (e.key === "Escape") chiudi(); });
    }
    modale.querySelector(".modale-box").classList.toggle("larga", !!opz.larga);
    const corpo = modale.querySelector(".modale-corpo");
    corpo.innerHTML = html;
    modale.classList.add("aperta");
    document.body.style.overflow = "hidden";
    corpo.scrollTop = 0;
    return corpo;
  }
  function chiudi() { if (modale) { modale.classList.remove("aperta"); document.body.style.overflow = ""; } }

  async function mostraFonte(id) {
    const corpo = apri(`<h3 style="margin-top:0">Fonte ${esc(id)}</h3><p class="vuoto">Carico il materiale…</p>`);
    try { corpo.innerHTML = `<h3 style="margin-top:0">Fonte ${esc(id)}</h3>` + boxFonte(await leggi(id)); }
    catch (e) { corpo.innerHTML = `<h3 style="margin-top:0">Fonte ${esc(id)}</h3><p class="err">${esc(e.message)}</p>`; }
  }

  // un click su qualsiasi chip apre la fonte; dentro una modale la mostra sotto il chip
  document.addEventListener("click", async e => {
    const b = e.target.closest(".cit[data-fonte]");
    if (!b) return;
    e.preventDefault();
    const dentro = b.closest(".modale-corpo");
    if (!dentro) return mostraFonte(b.dataset.fonte);
    let box = b.nextElementSibling;
    if (box && box.classList.contains("fonte-inline")) { box.remove(); b.classList.remove("on"); return; }
    box = document.createElement("div"); box.className = "fonte-inline"; box.innerHTML = '<p class="vuoto">Carico…</p>';
    b.after(box); b.classList.add("on");
    try { box.innerHTML = boxFonte(await leggi(b.dataset.fonte)); } catch (err) { box.innerHTML = `<p class="err">${esc(err.message)}</p>`; }
  });

  window.Fonti = {linka, chip, leggi, boxFonte, apri, chiudi, imposta: c => { corsoCorrente = c; }};
})();
