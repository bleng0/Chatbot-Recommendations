/* POME motion (anime.js v4). Content is visible without this file; it only animates changes.
   Runs after every Streamlit rerun; animates only what changed since the last run. */
(function () {
  const { animate, stagger } = window.anime;
  const reduce = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const seen = (window.__pomeSeen = window.__pomeSeen || { ans: {}, table: "", off: "" });

  function answers() {
    document.querySelectorAll(".ans").forEach((el) => {
      const key = el.classList.contains("ans-wi") ? "wi" : "official";
      if (seen.ans[key] === el.textContent) return;
      seen.ans[key] = el.textContent;
      if (reduce()) return animate(el, { opacity: [0, 1], duration: 120, ease: "out" });
      // the one authored moment: the verdict wipes in left to right
      animate(el, { clipPath: ["inset(0 100% 0 0)", "inset(0 0% 0 0)"], opacity: [0.2, 1],
                    duration: 220, ease: "outExpo" });
    });
  }

  function gateRows() {
    const table = document.querySelector(".gm");
    if (!table) return;
    const sig = table.querySelector("tbody").textContent;
    if (seen.table === sig) return;
    const first = seen.table === "";
    seen.table = sig;
    if (first) return; // no entrance choreography on page load
    const rows = table.querySelectorAll("tbody tr");
    if (reduce()) return animate(rows, { opacity: [0.4, 1], duration: 120, ease: "out" });
    animate(rows, { opacity: [0, 1], translateY: [4, 0], duration: 180, ease: "outQuart",
                    delay: stagger(14) });
  }

  function offColumns() {
    const now = [...document.querySelectorAll(".gm thead th.off")].map((th) => th.textContent);
    const before = seen.off ? seen.off.split("|") : [];
    seen.off = now.join("|");
    const fresh = now.filter((g) => !before.includes(g));
    if (!fresh.length) return;
    const heads = [...document.querySelectorAll(".gm thead th")];
    fresh.forEach((g) => {
      const col = heads.findIndex((th) => th.textContent === g);
      const cells = document.querySelectorAll(`.gm tr > :nth-child(${col + 1})`);
      animate(cells, { opacity: [1, 0.42], duration: reduce() ? 120 : 200, ease: "outQuart" });
    });
  }

  window.pomeMotion = function () {
    answers();
    gateRows();
    offColumns();
  };
})();
