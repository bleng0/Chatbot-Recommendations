/* POME motion (anime.js v4). Content is fully visible without this file.
   Timings and easings come from the CSS motion tokens (--dur-*, --ease-*), so CSS hovers and
   these scripted moments share one rhythm. Runs after every Streamlit rerun:
   - first load: one entrance sequence (heading, answer, counts, gate rows, icons);
   - later reruns: only what changed animates (answer, counts, rows, switched-off columns);
   - tab switches, charts entering view and opened details get their own short moves;
   - prefers-reduced-motion: every move becomes a 120 ms fade, count-ups jump to the value. */
(function () {
  const { animate, stagger } = window.anime;
  const css = getComputedStyle(document.documentElement);
  const ms = (name, fallback) => parseFloat(css.getPropertyValue(name)) || fallback;
  const DUR = { fast: ms("--dur-fast", 150), base: ms("--dur", 220), slow: ms("--dur-slow", 480) };
  const STEP = ms("--stagger", 28);
  const reduce = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const fade = (t) => animate(t, { opacity: [0, 1], duration: 120, ease: "out" });
  const seen = (window.__pomeSeen = window.__pomeSeen ||
    { first: true, ans: {}, table: "", off: "", counts: {}, charts: new WeakSet(),
      tabsBound: new WeakSet() });

  function countUp(el, from) {
    const to = Number(el.dataset.count);
    if (reduce() || !Number.isFinite(to)) { el.textContent = String(to); return; }
    const box = { v: from };
    animate(box, { v: to, duration: DUR.slow, ease: "outExpo",
                   onUpdate: () => { el.textContent = String(Math.round(box.v)); } });
  }

  function entrance() {
    // one authored moment on load: the verdict wipes in, its numbers count up, then the
    // gate icons settle in a wave. Everything else is already visible and stays still.
    const verdict = document.querySelector(".ans:not(.ans-wi)");
    const rows = document.querySelectorAll(".gm tbody tr");
    const icons = document.querySelectorAll(".gm td.g .ic");
    if (reduce()) { if (verdict) fade(verdict); }
    else {
      if (verdict) animate(verdict, { clipPath: ["inset(0 100% 0 0)", "inset(0 0% 0 0)"],
                                      duration: DUR.slow, ease: "outExpo" });
      // the two words the question asks about get their underline drawn, then the answer
      // slots that answer them rise in
      animate(document.querySelectorAll("h1.q .k"), { "--u": [0, 1], duration: 640, ease: "outExpo",
                                                     delay: stagger(160, { start: 200 }) });
      const slots = document.querySelectorAll(".ac .slot");
      if (slots.length) animate(slots, { opacity: [0, 1], y: [10, 0], duration: DUR.slow,
                                         ease: "outExpo", delay: stagger(90, { start: 520 }) });
      if (rows.length) animate([rows[0]], { backgroundColor: ["rgba(43,207,206,.28)", "rgba(43,207,206,0)"],
                                          duration: 900, ease: "outQuart", delay: DUR.slow });
      // icons pop in a diagonal wave: row then column order
      if (icons.length) animate(icons, { scale: [0.4, 1], opacity: [0, 1], duration: DUR.base, ease: "outBack",
                       delay: stagger(6, { start: 360 }) });
    }
    document.querySelectorAll(".kn[data-count]").forEach((el) => {
      seen.counts[el.nextSibling ? el.nextSibling.textContent : ""] = el.dataset.count;
      countUp(el, 0);
    });
  }

  function answers() {
    document.querySelectorAll(".ans").forEach((el) => {
      const key = el.classList.contains("ans-wi") ? "wi" : "official";
      if (seen.ans[key] === el.textContent) return;
      const was = seen.ans[key];
      seen.ans[key] = el.textContent;
      if (seen.first && key === "official") return; // part of the entrance
      if (reduce()) return fade(el);
      // the verdict wipes in left to right; a new what-if block also slides down
      animate(el, { clipPath: ["inset(0 100% 0 0)", "inset(0 0% 0 0)"], opacity: [0.2, 1],
                    duration: DUR.base, ease: "outExpo" });
      if (key === "wi" && was === undefined) {
        animate(el.closest(".wi") || el, { opacity: [0, 1], translateY: [-8, 0],
                                           duration: DUR.base, ease: "outQuart" });
      }
    });
  }

  function counts() {
    document.querySelectorAll(".kn[data-count]").forEach((el) => {
      const key = el.nextSibling ? el.nextSibling.textContent : "";
      const before = seen.counts[key];
      if (before === el.dataset.count) return;
      seen.counts[key] = el.dataset.count;
      countUp(el, Number(before) || 0);
      if (!reduce()) animate(el, { color: ["#0B7372", "#1C1D1F"], duration: DUR.slow,
                                   ease: "outQuart" });
    });
  }

  function gateRows() {
    const table = document.querySelector(".gm");
    if (!table) return;
    const sig = table.querySelector("tbody").textContent;
    if (seen.table === sig) return;
    const first = seen.table === "";
    seen.table = sig;
    if (first) return; // the entrance already moved them
    const rows = table.querySelectorAll("tbody tr");
    if (reduce()) return fade(rows);
    animate(rows, { opacity: [0, 1], translateY: [4, 0], duration: DUR.base, ease: "outQuart",
                    delay: stagger(STEP / 2) });
  }

  function offColumns() {
    const now = [...document.querySelectorAll(".gm thead th.off")].map((th) => th.textContent);
    const before = seen.off ? seen.off.split("|") : [];
    seen.off = now.join("|");
    const fresh = now.filter((g) => !before.includes(g));
    const back = before.filter((g) => !now.includes(g));
    const heads = [...document.querySelectorAll(".gm thead th")];
    const column = (g) => {
      const label = g.replace(/off$/, "");
      const col = heads.findIndex((th) => th.textContent.replace(/off$/, "") === label);
      return col < 0 ? [] : document.querySelectorAll(`.gm tr > :nth-child(${col + 1})`);
    };
    fresh.forEach((g) => animate(column(g), { opacity: [1, 0.42],
      duration: reduce() ? 120 : DUR.base, ease: "outQuart", delay: stagger(reduce() ? 0 : 8) }));
    back.forEach((g) => animate(column(g), { opacity: [0.42, 1],
      duration: reduce() ? 120 : DUR.base, ease: "outQuart", delay: stagger(reduce() ? 0 : 8) }));
  }

  function tabs() {
    document.querySelectorAll("[role='tab']").forEach((tab) => {
      if (seen.tabsBound.has(tab)) return;
      seen.tabsBound.add(tab);
      tab.addEventListener("click", () => setTimeout(() => {
        const panel = [...document.querySelectorAll("[role='tabpanel']")]
          .find((p) => !p.hidden && p.offsetParent !== null);
        if (!panel) return;
        const kids = panel.querySelectorAll(
          ".tw, .vh, .one, .js-plotly-plot, [data-testid='stExpander'], [data-testid='stMarkdown']");
        if (reduce()) return fade(kids);
        animate(kids, { opacity: [0, 1], translateY: [8, 0], duration: DUR.base,
                        ease: "outQuart", delay: stagger(STEP) });
        charts();
      }, 30));
    });
  }

  function charts() {
    document.querySelectorAll(".js-plotly-plot").forEach((plot) => {
      if (seen.charts.has(plot) || plot.offsetParent === null) return;
      const bars = plot.querySelectorAll(".bars .point path");
      if (!bars.length) return;
      seen.charts.add(plot);
      if (reduce()) return fade(bars);
      animate(bars, { scaleX: [0, 1], duration: DUR.slow, ease: "outExpo",
                      delay: stagger(STEP * 1.5) });
      animate(plot.querySelectorAll(".bars .point text, .textpoint text"),
              { opacity: [0, 1], duration: DUR.base, ease: "out",
                delay: stagger(STEP * 1.5, { start: DUR.base }) });
    });
  }

  window.pomeMotion = function () {
    if (seen.first) entrance();
    answers();
    counts();
    gateRows();
    offColumns();
    tabs();
    charts();
    seen.first = false;
  };
})();
