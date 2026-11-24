"""HTML pieces for the app: escaped strings only, no Streamlit calls (tested)."""
from html import escape
from urllib.parse import quote

from pome.app.views import GateValues

# Gossamer palette (light only, owner 2026-11-23): #FAFAFA #CDCDCF #939599 #2BCFCE #EC4D25.
# Text tokens are >= 4.5:1 on bg and panel; teal #2BCFCE is a fill (bars, tints) only and
# coral #EC4D25 an icon/outline colour (>= 3:1); their darker text twins carry words.
TOKENS = {
    "light": {"bg": "#FAFAFA", "panel": "#FFFFFF", "line": "#CDCDCF", "grey": "#939599",
              "text": "#1C1D1F", "muted": "#5E6065", "accent": "#0B7372", "stroke": "#0B7372",
              "teal": "#2BCFCE", "coral": "#EC4D25", "coraltext": "#C23A17",
              "tint": "rgba(43,207,206,.14)", "sel": "#2BCFCE", "seltext": "#1C1D1F"},
}

# Lucide icons (ISC licence), one stroke weight; drawn, never emoji.
_PATHS = {
    "pass": '<path d="M20 6 9 17l-5-5"/>',
    "fail": '<path d="M18 6 6 18"/><path d="m6 6 12 12"/>',
    "unverified": '<circle cx="12" cy="12" r="10"/><path d="M9.1 9a3 3 0 0 1 5.8 1c0 2-3 3-3 3"/>'
                  '<path d="M12 17h.01"/>',
    "not_tested": '<path d="M5 12h14"/>',
    "info": '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/>',
    "warn": '<path d="M12 9v4"/><path d="M12 17h.01"/><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 '
            '3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"/>',
}
_SHORT = {"not_recommended": "Not recommended", "eligible": "Eligible", "eligible_modeled": "Eligible (modeled)",
          "rejected": "Rejected", "unverified": "Unverified"}
_UNIT = {"usd_per_month": "USD/month", "inr_per_month": "/month", "inr_per_hour": "/hour",
         "inr_per_1m_tokens": "/1M tokens", "req_per_s": "req/s", "tok_per_s": "tok/s",
         "ratio": "", "ratio_gap": "", "bool": "", "region": ""}
_WORD = {"pass": "pass", "fail": "fail", "unverified": "unverified", "not_tested": "not tested"}


def icon(name: str) -> str:
    """Drawn icon as a CSS mask (st.html strips inline SVG); colour follows the text."""
    return f'<span class="ic ic-{name}" aria-hidden="true"></span>'


def _mask(name: str) -> str:
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
           'stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
           f'{_PATHS[name]}</svg>')
    url = "data:image/svg+xml," + quote(svg)
    return f'.ic-{name}{{-webkit-mask-image:url("{url}");mask-image:url("{url}")}}'


def badge(label: str) -> str:
    if not label:
        return ""
    cls = {"SELF-TESTED": "measured"}.get(label, label.lower())
    return f'<span class="bdg bdg-{escape(cls)}">{escape(label)}</span>'


def cell(status: str) -> str:
    """Pass is a bare check (with a screen-reader word); the others keep their word."""
    if status == "pass":
        return f'<span class="st st-pass">{icon("pass")}<span class="sr">pass</span></span>'
    return f'<span class="st st-{status}">{icon(status)}{_WORD[status]}</span>'


# Loads anime.js and motion.js once (self-hosted), then animates what changed on each rerun.
# Static text: no data is ever interpolated into this script.
MOTION = """<script>(function () {
  const go = () => requestAnimationFrame(() => setTimeout(() => window.pomeMotion(), 60));
  const load = (src, cb) => { const s = document.createElement("script");
    s.src = new URL(src, document.baseURI).href; s.onload = cb; document.head.appendChild(s); };
  if (window.anime && window.pomeMotion) return go();
  load("app/static/js/anime.umd.min.js", () => load("app/static/js/motion.js", go));
})();</script>"""


def css(theme: str) -> str:
    t = TOKENS[theme]
    v = ";".join(f"--{k}:{val}" for k, val in t.items())
    masks = "".join(_mask(n) for n in _PATHS)
    return f"<style>:root{{{v}}}{_CSS}{masks}</style>"


def stats(items: list[tuple[str, int]]) -> str:
    """One inline tally under the answer; motion.js counts each number up to data-count."""
    parts = " · ".join(
        f'<span class="kn num" data-count="{int(n)}">{int(n)}</span> {escape(label)}'
        for label, n in items)
    return f'<p class="tally">{parts}</p>'


def answer(text: str, *, recommended: bool, what_if: bool = False) -> str:
    # coral outline marks only the official recommendation, never a what-if
    cls = "ans" + (" ans-rec" if recommended and not what_if else "") + (" ans-wi" if what_if else "")
    # keep a comparison such as "0.75 < 0.80" on one line
    text = escape(text).replace(" &lt; ", "\u00a0&lt;\u00a0").replace(" &gt; ", "\u00a0&gt;\u00a0")
    text = text.replace(" (cost MODELED)", ' <span class="bdg bdg-modeled">MODELED</span>')
    return f'<p class="{cls}" role="status" aria-live="polite">{text}</p>'


def _chip(status: str) -> str:
    return f'<span class="chip chip-{escape(status)}">{escape(_SHORT[status])}</span>'


def _gate_observations(lines: list[tuple[str, str, tuple[str, ...]]]) -> str:
    parts = []
    for label, value, sources in lines:
        name = f'<span class="gate-value-label">{escape(label)}</span>' if label else ""
        provenance = " ".join(badge(source) for source in sources)
        parts.append(
            f'<div class="gate-value">{name}<span class="num">{escape(value)}</span>'
            f' {provenance}</div>'
        )
    return "".join(parts)


def gate_table(rows: list[dict], gates: list[str], off: set[str],
               what_if: dict[str, str] | None = None,
               cost: dict[str, tuple[str, bool]] | None = None,
               labels: dict[str, str] | None = None,
               error: dict[str, tuple[str, bool]] | None = None,
               notes: dict[str, str] | None = None,
               short: dict[str, str] | None = None, *,
               values: dict[str, GateValues] | None = None) -> str:
    """Gate matrix with optional evidence lines below the check statuses."""
    labels, notes, short = labels or {}, notes or {}, short or {}
    head = "".join(
        f'<th scope="col" class="g{" off" if g in off else ""}" data-gate="{escape(g)}">'
        f'{escape(labels.get(g, g))}<span class="gs">{escape(short.get(g, ""))}</span>'
        f'{"<small>off</small>" if g in off else ""}</th>' for g in gates)
    cols = ['<col class="c-id">', '<col class="c-st">']
    wi_head = ""
    if what_if is not None:
        wi_head += '<th scope="col">What-if</th>'
        cols.append('<col class="c-wi">')
    if cost is not None:
        wi_head += '<th scope="col" class="r">Monthly cost</th>'
        cols.append('<col class="c-cost">')
    if error is not None:
        wi_head += '<th scope="col" class="r">Error rate</th>'
        cols.append('<col class="c-err">')
    cols += ['<col class="c-g">'] * len(gates)

    def _num(txt: str, over: bool, why: str) -> str:
        if not over:
            return f'<td class="num r">{escape(txt)}</td>'
        return (f'<td class="num r over" title="{why}">{icon("warn")}{escape(txt)}'
                f'<span class="sr"> ({why.lower()})</span></td>')

    body = []
    for r in rows:
        observed = (values or {}).get(r["config"], {})
        cells = []
        for g in gates:
            status = cell(r["gates"][g]) if g in r["gates"] else ""
            details = _gate_observations(observed.get(g, []))
            cells.append(f'<td class="g{" off" if g in off else ""}">{status + details or "—"}</td>')
        note = (f'<small class="nr">{escape(notes[r["config"]])}</small>'
                if r["config"] in notes else "")
        wi = (f'<td class="stat">{_chip(what_if[r["config"]])}{note}</td>'
              if what_if is not None else "")
        if cost is not None:
            wi += _num(*cost.get(r["config"], ("—", False)), "Over the monthly budget")
        if error is not None:
            wi += _num(*error.get(r["config"], ("—", False)), "Over the error limit")
        body.append(f'<tr><th scope="row" class="cid" title="{escape(r["config"])}">'
                    f'{escape(r["config"])}</th>'
                    f'<td class="stat">{_chip(r["status"])}</td>{wi}{"".join(cells)}</tr>')
    extra_class = " gm-values" if values is not None else ""
    return (f'<div class="tw"><table class="gm fx{extra_class}"><caption class="sr">Gate results per '
            f'configuration</caption><colgroup>{"".join(cols)}</colgroup><thead><tr>'
            f'<th scope="col">Configuration</th><th scope="col">Recommended status</th>'
            f'{wi_head}{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')


def answer_card(*, model: str, config: str, host: str, region: str, cost: str, modeled: bool,
                passing: int, total: int, decision_hash: str, source: str = "") -> str:
    """The answer to the page question: one slot each for model and hosting plan, then cost."""
    bdg = '<span class="bdg bdg-modeled">MODELED</span>' if modeled else ""
    src = f"<span>{escape(source)}</span>" if source else ""
    return (
        '<div class="ac" role="status" aria-live="polite"><dl class="slots">'
        f'<div class="slot k"><dt>Model</dt><dd>{escape(model)}<small>{escape(config)}</small>'
        '</dd></div>'
        f'<div class="slot k"><dt>Hosting plan</dt><dd>{escape(host)}<small>{escape(region)}'
        '</small></dd></div>'
        f'<div class="slot"><dt>Monthly cost</dt><dd>{escape(cost)}{bdg}</dd></div></dl>'
        f'<div class="ac-foot">{src}<span><b class="kn num" data-count="{passing}">{passing}'
        f'</b> of <b class="num">{total}</b> configurations pass every gate</span>'
        f'<span><b class="kn num" data-count="{total - passing}">{total - passing}</b> rejected'
        '</span></div><details class="repro"><summary>Same inputs, same result</summary>'
        f'<p>decision <code>{escape(decision_hash)}…</code> · profile banking_mvp · re-running '
        'with these inputs gives the same hash.</p></details></div>')


def baseline_cards(cards: list[dict]) -> str:
    """Our pick next to what simple rules would pick: cost, change versus ours, gates failed."""
    out = []
    for c in cards:
        if c["delta_usd"] > 0:
            cls = "up"
        elif c["delta_usd"] < 0:
            cls = "down"
        else:
            cls = "eq"
        delta = f'<span class="bl-d {cls}">{escape(c["delta"])}</span>' if c["delta"] else ""
        n = len(c["fails"])
        verdict = ('<span class="bl-ok">Passes every gate</span>' if not n else
                   f'<span class="bl-bad">Fails {n} check{"s" if n > 1 else ""}</span>'
                   '<span class="bl-fs">' + "".join(
                       f'<span class="bl-f">{escape(f)}</span>' for f in c["fails"]) + "</span>")
        out.append(
            f'<article class="bl-c"><h3>{escape(c["title"])}</h3>'
            f'<p class="bl-r">{escape(c["rule"])}</p><p class="bl-p">{escape(c["config"])}</p>'
            f'<p class="bl-m">{escape(c["model"])} · {escape(c["host"])}</p>'
            f'<p class="bl-cost">{escape(c["cost"])}{badge(c["badge"])}</p>{delta}'
            f'<div class="bl-v">{verdict}</div></article>')
    return f'<div class="bl">{"".join(out)}</div>'


def _details(summary: str, lines: list[tuple[str, str]]) -> str:
    inner = "".join(f"<dt>{escape(k)}</dt><dd>{escape(val)}</dd>" for k, val in lines if val)
    return (f"<details><summary>{escape(summary)}</summary>"
            f'<div class="dx"><dl>{inner}</dl></div></details>')


def config_fan(items: list[dict], focus: str) -> str:
    """Configurations tab: a horizontal fan of config cards (the focused one sharp, the rest
    blurred) above that config's build steps. Static text only in the script."""
    cards, panels = [], []
    for it in items:
        cid = escape(it["config"])
        cur = ' aria-current="true"' if it["config"] == focus else ""
        cards.append(
            f'<button type="button" class="fan-card" data-cid="{cid}"{cur}>'
            f'<span class="fc-id">{cid}</span><span class="fc-model">{escape(it["model"])}</span>'
            f'<span class="fc-host">{escape(it["host"])}</span>'
            f'<span class="fc-foot">{_chip(it["status"])}<span class="num">{escape(it["cost"])}'
            f'</span></span></button>')
        steps = "".join(
            f'<li><span class="fs-n num">{i}</span><span class="fs-t">{escape(t)}</span>'
            f'<span class="fs-d">{escape(d)}</span></li>'
            for i, (t, d) in enumerate(it["steps"], 1))
        hidden = "" if it["config"] == focus else " hidden"
        panels.append(f'<section class="fan-steps" data-cid="{cid}"{hidden}>'
                      f'<h3>How to build <code>{cid}</code></h3><ol>{steps}</ol></section>')
    return (f'<div class="fan"><div class="fan-main"><p class="fan-live" aria-live="polite">'
            f'</p>{"".join(panels)}</div><div class="fan-side"><button type="button" '
            f'class="fan-prev" aria-label="Previous configuration">&uarr;</button>'
            f'<div class="fan-rail" tabindex="0" aria-label="Configurations">{"".join(cards)}'
            f'</div><button type="button" class="fan-next" aria-label="Next configuration">'
            f'&darr;</button></div></div>{_FAN_JS}')


_FAN_JS = """<script>(function () {
  const root = [...document.querySelectorAll(".fan")].pop();
  if (!root || root.dataset.ready) return;
  root.dataset.ready = "1";
  const rail = root.querySelector(".fan-rail");
  const cards = [...rail.querySelectorAll(".fan-card")];
  const live = root.querySelector(".fan-live");
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  let current = null;
  function show(card) {
    if (card === current) return;
    current = card;
    cards.forEach((c) => c.toggleAttribute("aria-current", c === card));
    const cid = card.dataset.cid;
    root.querySelectorAll(".fan-steps").forEach((p) => { p.hidden = p.dataset.cid !== cid; });
    live.textContent = cid + " (" + (cards.indexOf(card) + 1) + " of " + cards.length + ")";
    const items = root.querySelectorAll('.fan-steps:not([hidden]) li');
    if (window.anime && !still) window.anime.animate(items, { opacity: [0, 1],
      translateX: [-10, 0], duration: 320, ease: "outExpo", delay: window.anime.stagger(45) });
  }
  function fan() {
    const box = rail.getBoundingClientRect();
    const mid = box.top + rail.clientHeight / 2;
    let best = cards[0], bestD = Infinity;
    cards.forEach((c) => {
      const r = c.getBoundingClientRect();
      const d = (r.top + r.height / 2 - mid) / r.height;   // distance in card heights
      const a = Math.min(Math.abs(d), 3);
      c.style.transform = `rotate(${Math.max(-6, Math.min(6, d * 2.5))}deg) ` +
        `translateX(${a * 8}px) scale(${1 - a * 0.05})`;
      c.style.filter = a < 0.5 ? "none" : `blur(${Math.min(a * 0.6, 1.2)}px)`;
      c.style.opacity = String(1 - Math.min(a * 0.15, 0.45));
      if (Math.abs(d) < bestD) { bestD = Math.abs(d); best = c; }
    });
    show(best);
  }
  let raf = 0;
  rail.addEventListener("scroll", () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(fan); },
                        { passive: true });
  const go = (c) => c && c.scrollIntoView({ behavior: still ? "auto" : "smooth",
                                            block: "center", inline: "nearest" });
  const step = (n) => go(cards[Math.max(0, Math.min(cards.length - 1, cards.indexOf(current) + n))]);
  root.querySelector(".fan-prev").addEventListener("click", () => step(-1));
  root.querySelector(".fan-next").addEventListener("click", () => step(1));
  cards.forEach((c) => c.addEventListener("click", () => go(c)));
  rail.addEventListener("keydown", (e) => {
    if (e.key === "ArrowDown") { e.preventDefault(); step(1); }
    if (e.key === "ArrowUp") { e.preventDefault(); step(-1); }
  });
  const first = rail.querySelector("[aria-current]") || cards[0];
  const start = () => { rail.scrollTop = first.offsetTop - (rail.clientHeight - first.offsetHeight) / 2; fan(); };
  new ResizeObserver(() => { if (rail.clientWidth) start(); }).observe(rail);
})();</script>"""


def config_table(rows: list[dict[str, str]]) -> str:
    cols = [("config", "Configuration"), ("model", "Model"), ("host", "Host"),
            ("region", "Region"), ("serving", "Serving"), ("quant", "Quant")]
    head = "".join(f'<th scope="col">{t}</th>' for _, t in cols)
    body = "".join("<tr>" + "".join(
        f'<td class="{"cid" if k == "config" else ""}">{escape(r[k])}</td>' for k, _ in cols)
        + "</tr>" for r in rows)
    return (f'<div class="tw"><table class="ct"><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def evidence_display(sections: dict) -> str:
    parts = ['<div class="evidence"><h2>Configurations</h2>']
    if not sections:
        parts.append('<p class="one">No evidence recorded.</p>')
    for cid, groups in sections.items():
        count = sum(map(len, groups.values()))
        noun = "metric" if count == 1 else "metrics"
        parts.append(f'<details class="ev-config"><summary><code>{escape(cid)}</code>'
                     f'<span class="muted">{count} {noun}</span></summary>')
        if not groups:
            parts.append('<p class="one">No evidence recorded.</p>')
        for group, rows in groups.items():
            parts.append(f'<h3>{escape(group)}</h3><dl class="ev-metrics">')
            for row in rows:
                label = escape(row.get("label", row["metric"]))
                description = escape(row.get("description", ""))
                unit = _UNIT.get(row["unit"], row["unit"]) if description else row["unit"]
                value = escape(row["value"])
                suffix = f'<span class="unit">{escape(unit)}</span>' if unit else ""
                detail = _details("Source details", [
                    ("Metric key", row["metric"]), ("Recorded ratio", row.get("raw", "")),
                    ("Source", row["source"]), ("Retrieved", row["retrieved"]),
                    ("Formula", row["formula"]),
                ])
                parts.append(f'<div class="ev-metric"><dt>{label}'
                             f'<span class="ev-description">{description}</span></dt>'
                             f'<dd class="ev-value"><span class="num">{value} {suffix}</span>'
                             f'{badge(row["provenance"])}</dd><dd class="ev-details">{detail}</dd>'
                             '</div>')
            parts.append('</dl>')
        parts.append('</details>')
    return "".join(parts) + "</div>"


def deployment_summary(*, config: str, runtime: str, precision: str, host: str,
                       price: str, provenance: str, rental: str, units: int, ops: str) -> str:
    return (
        '<div class="deployment deployment-summary">'
        '<section><h2>POME configuration</h2>'
        f'<p class="deployment-setup">{escape(runtime)} · {escape(precision)}</p>'
        f'<p>{escape(host)}</p><p><code>{escape(config)}</code></p></section>'
        '<section><h2>Monthly estimate from sidebar settings</h2>'
        f'<p class="deployment-price"><strong>{escape(price)}</strong>{badge(provenance)}</p>'
        f'<p>{escape(rental)}</p>'
        f'<p class="muted">{units} rental {"unit" if units == 1 else "units"}'
        f' · {escape(ops)}/month operations</p></section></div>'
    )


def _deployment_variant(row: dict) -> str:
    figures = []
    sources = []
    for result in row["results"]:
        figures.append(f'<li><span>{escape(result["figure"])}</span>{badge(result["badge"])}</li>')
        source = escape(result["source"])
        if result["source"].startswith(("https://", "http://")):
            source = f'<a href="{source}" target="_blank" rel="noopener noreferrer">Published source</a>'
        sources.append(
            f'<div class="deployment-source"><dt>{escape(result["figure"])}</dt>'
            f'<dd>{source}</dd>'
            f'<dd>Retrieved <time>{escape(result["retrieved"])}</time></dd>'
            f'<dd>{escape(result["conditions"])}</dd></div>'
        )
    evidence = (f'<ul class="deployment-results">{"".join(figures)}</ul>' if figures else
                '<p class="deployment-results muted">Setup guidance only</p>')
    lines = [("Variant ID", row["variant"]), *row["conditions"], ("Note", row["note"])]
    details = "".join(f'<dt>{escape(k)}</dt><dd>{escape(v)}</dd>' for k, v in lines if v)
    source_details = f'<dl class="deployment-sources">{"".join(sources)}</dl>' if sources else ""
    return (
        '<article class="deployment-variant">'
        f'<h4>{escape(row["stack"])}</h4><p>{escape(row["quant"])}</p>'
        f'<p class="muted">Hardware · {escape(row["hardware"])}</p>{evidence}'
        '<details><summary>Setup and source details</summary>'
        f'<div class="dx"><dl>{details}</dl></div>{source_details}</details></article>'
    )


def deployment_evidence(rows: list[dict]) -> str:
    matched = [row for row in rows if row["match"] == "MATCH"]
    references = [row for row in rows if row["match"] == "REFERENCE"]
    parts = [
        '<section class="deployment deployment-evidence"><h2>Published setups for this model</h2>',
        '<p>Each result applies to the runtime, precision and hardware in its own card.</p>',
    ]
    if matched:
        parts.append('<h3>POME workload matches</h3>'
                     '<p>Benchmark conditions are close enough for POME’s workload.</p>'
                     '<div class="deployment-grid">')
        parts.extend(_deployment_variant(row) for row in matched)
        parts.append('</div>')
    else:
        parts.append('<p class="deployment-no-match">No published benchmark matches the POME '
                     'workload for this model.</p>')
    if references:
        parts.append('<h3>Reference setups</h3>'
                     '<p>Setup guides, model weight sizes and benchmarks under other conditions.</p>'
                     '<div class="deployment-grid">')
        parts.extend(_deployment_variant(row) for row in references)
        parts.append('</div>')
    return "".join(parts) + "</section>"


_CSS = """
:root{--dur-fast:150ms;--dur:220ms;--dur-slow:480ms;--ease-out:cubic-bezier(.16,1,.3,1);
  --ease-in-out:cubic-bezier(.65,0,.35,1);--stagger:28ms}
html{-webkit-font-smoothing:antialiased}
.tally{margin:.75rem 0 0;font-size:.9375rem;color:var(--muted)}
.tally .kn{font-weight:500;color:var(--text)}
h1.q{font-size:clamp(1.9rem,1.2rem + 2.2vw,2.75rem)!important;line-height:1.12!important;letter-spacing:-.02em;
 font-weight:600!important;text-wrap:balance;max-width:24ch;margin:0 0 1.5rem!important;padding:0!important}
h1.q .k{position:relative;color:var(--accent);white-space:nowrap}
h1.q .k::after{content:"";position:absolute;left:0;right:0;bottom:-.08em;height:.12em;border-radius:2px;
 background:var(--teal);transform-origin:left;transform:scaleX(var(--u,1))}
::selection{background:rgba(43,207,206,.35);color:var(--text)}
.ac{border:1px solid var(--teal);border-radius:8px;background:var(--panel);padding:1.25rem 1.5rem;max-width:56rem;
 box-shadow:0 1px 2px rgba(28,29,31,.06),0 6px 18px -8px rgba(11,115,114,.18)}
.ac .slots{display:grid;grid-template-columns:repeat(3,auto);gap:1rem 2.5rem;align-items:start;
 justify-content:start;margin:0}
.ac .slot dt{font-size:.8125rem;color:var(--muted);margin:0 0 .15rem}
.ac .slot dd{margin:0;font-size:1.375rem;font-weight:600;line-height:1.2}
.ac .slot dd small{display:block;font-size:.8125rem;font-weight:400;color:var(--muted);margin-top:.15rem}
.ac .slot.k dd{color:var(--accent)}
.ac .slot .bdg{vertical-align:.2em;margin-left:.4rem}
.ac-foot{display:flex;flex-wrap:wrap;gap:.25rem 1.25rem;margin-top:1rem;padding-top:.85rem;
 border-top:1px solid #E6E6E8;font-size:.875rem;color:var(--muted)}
.ac-foot b{color:var(--text);font-weight:600}
.ac details.repro{margin-top:.75rem;font-size:.8125rem;color:var(--muted)}
.ac details.repro summary{cursor:pointer;width:max-content}
.ac details.repro p{margin:.3rem 0 0}
.ac details.repro code{font-size:.75rem}
@media (max-width:760px){.ac .slots{grid-template-columns:1fr}}
.bl{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));border:1px solid var(--line);border-radius:8px;
 background:var(--panel);overflow:hidden;margin:.5rem 0 1rem}
.bl-c{padding:1.1rem 1.1rem 1.2rem;border-left:1px solid #E6E6E8;display:flex;flex-direction:column;gap:.3rem}
.bl-c:first-child{border-left:0;background:var(--tint)}
.bl-c h3{margin:0!important;padding:0!important;font-size:.8125rem!important;font-weight:600;color:var(--muted)}
.bl-c:first-child h3{color:var(--accent)}
.bl-c p{margin:0}
.bl-r{font-size:.75rem;color:var(--muted);min-height:2.4em}
.bl-p{font:500 .9375rem "Fira Code",monospace;word-break:break-all;margin-top:.25rem!important}
.bl-m{font-size:.8125rem;color:var(--muted)}
.bl-cost{font-size:1.375rem;font-weight:600;margin-top:.4rem!important}
.bl-cost .bdg{margin-left:.4rem;vertical-align:.25em}
.bl-d{font:500 .8125rem "Fira Code",monospace}
.bl-d.up{color:var(--coraltext)}.bl-d.down{color:var(--accent)}.bl-d.eq{color:var(--muted)}
.bl-v{margin-top:.6rem;padding-top:.6rem;border-top:1px solid #E6E6E8;font-size:.8125rem}
.bl-ok{color:var(--accent);font-weight:500}.bl-bad{color:var(--coraltext);font-weight:500}
.bl-fs{display:flex;flex-wrap:wrap;gap:.3rem;margin-top:.35rem}
.bl-f{font:500 .6875rem/1 "Fira Sans",sans-serif;padding:.28rem .45rem;border-radius:999px;border:1px solid var(--coral);
 color:var(--coraltext);background:var(--panel)}
.bl-note{font-size:.8125rem;color:var(--muted);max-width:80ch}
@media (max-width:1000px){.bl{grid-template-columns:1fr 1fr}.bl-c:nth-child(3){border-left:0}.bl-c{border-top:1px solid #E6E6E8}}
@media (max-width:560px){.bl{grid-template-columns:1fr}.bl-c{border-left:0}}
.gm.fx{table-layout:fixed;width:max-content;min-width:100%}
.gm.fx col.c-id{width:12.75rem}.gm.fx col.c-st{width:8.25rem}.gm.fx col.c-wi{width:8.75rem}
.gm.fx col.c-cost{width:7rem}.gm.fx col.c-err{width:5rem}.gm.fx col.c-g{width:3.25rem}
.gm.fx th,.gm.fx td{padding:.45rem .5rem}
.gm.fx .cid{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.gm.fx td.g,.gm.fx th.g{padding-inline:.15rem}
.gm th.g .gs{display:block;font-weight:400;font-size:.6875rem;color:var(--muted);line-height:1.25;white-space:normal}
.gm .r{text-align:right;white-space:nowrap}
.gm td.over{color:var(--coraltext)}
.gm td.over .ic{color:var(--coral);margin-right:.3rem}
::selection{background:var(--sel);color:var(--seltext)}
*{scrollbar-color:var(--line) transparent}
:focus-visible{outline:2px solid var(--accent)!important;outline-offset:2px}
code,.num,.cid,.hash{font-family:"Fira Code",ui-monospace,monospace;
  font-variant-numeric:tabular-nums}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip-path:inset(50%);white-space:nowrap}
.muted,.note{color:var(--muted)}
.note{font-size:.875rem;display:flex;gap:.4rem;align-items:flex-start;margin:0 0 1rem}
.note .ic{width:1rem;height:1rem;flex:none;margin-top:.15rem}
.hash{font-size:.75rem;color:var(--muted);margin:.25rem 0 1.5rem}
.ans{font-size:1.375rem;line-height:1.35;font-weight:500;margin:0;padding:.875rem 1.125rem;
  border:1px solid var(--line);border-radius:6px;background:var(--panel);max-width:72ch;}
.ans-rec{border-color:var(--teal);background:color-mix(in srgb,var(--teal) 7%,var(--panel))}
.ans-wi{font-size:1.125rem;border-style:dashed}
.wi h3{font-size:1rem;font-weight:600;margin:1.75rem 0 .5rem}
.wi h3 .muted{font-weight:400}
.tw{overflow-x:auto;border:1px solid var(--line);border-radius:6px;background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:.875rem}
th,td{padding:.45rem .6rem;text-align:left;border-bottom:1px solid var(--line);
  vertical-align:top;white-space:nowrap}
tbody tr:last-child>*{border-bottom:0}
thead th{font-weight:500;color:var(--muted);font-size:.8125rem;position:sticky;top:0;
  background:var(--panel)}
tbody tr{transition:background-color var(--dur-fast) var(--ease-out)}
tbody tr:hover{background:var(--tint)}
th.cid{font-weight:400}
.gm th:first-child,.gm td:first-child{position:sticky;left:0;background:var(--panel);z-index:1}
.gm thead th:first-child{z-index:2}
td.set{white-space:normal;min-width:22rem;color:var(--muted)}
.gm td.g,.gm th.g{text-align:center;padding-inline:.3rem}
.gm .st{font-size:.8125rem}
.gm th.g small{display:block;font-size:.6875rem;font-weight:400}
.gm .off{opacity:.42}
.gm.fx.gm-values col.c-g{width:7.5rem}
.gm-values tbody td.g{vertical-align:top}
.gm-values .gate-value{font-size:.75rem;line-height:1.5;text-align:left;
  margin:.3rem .25rem;white-space:normal;overflow-wrap:anywhere}
.gm-values .gate-value-label{display:block;color:var(--muted)}
.gm-values td.off:has(.gate-value){opacity:1}
.gm-values td.off .st{opacity:.42}
.gm thead th.off{text-decoration:line-through}
.st{display:inline-flex;align-items:center;gap:.25rem;white-space:nowrap}
.ic{display:inline-block;width:1.05rem;height:1.05rem;flex:none;background:currentColor;
  -webkit-mask:no-repeat center/contain;mask:no-repeat center/contain}
.st-pass{color:var(--accent)}
.st-fail{font-weight:500}
.st-fail .ic{color:var(--coral)}
.st-fail{color:var(--coraltext)}
.st-unverified,.st-not_tested{color:var(--muted)}
.bdg{display:inline-block;white-space:nowrap;font:500 .6875rem/1 "Fira Sans",sans-serif;
  letter-spacing:.04em;padding:.22rem .45rem;color:var(--text);vertical-align:middle}
.bdg-measured{border:1px solid var(--stroke);border-radius:3px}
.bdg-published{border-radius:999px;background:var(--tint);border:1px solid transparent}
.bdg{transition:transform var(--dur-fast) var(--ease-out)}
tr:hover .bdg{transform:translateY(-1px)}
.bdg-vendor-doc{border-radius:999px;border:1px solid var(--line)}
.bdg-modeled{border:1px dashed var(--muted);border-radius:3px}
.unit{color:var(--muted);font-size:.75rem}
.mt{font-size:.8125rem}
.mt-match{color:var(--accent);font-weight:500}
.mt-reference{color:var(--muted)}
table details summary{cursor:pointer;list-style:none;display:inline-flex;align-items:center;
  gap:.35rem;border-radius:3px}
table details summary::-webkit-details-marker{display:none}
table details summary::before{content:"";width:.4rem;height:.4rem;border-right:1.5px solid
  currentColor;border-bottom:1.5px solid currentColor;transform:rotate(-45deg);
  transition:transform var(--dur) var(--ease-out)}
table details[open] summary::before{transform:rotate(45deg)}
table details[open] .dx{animation:open var(--dur) var(--ease-out)}
.evidence h2{font-size:1.25rem;margin:.5rem 0 .75rem}
.ev-config{border:1px solid var(--line);border-radius:6px;margin-bottom:.5rem;
  background:var(--panel);padding:.65rem .85rem;overflow-wrap:anywhere}
.ev-config>summary,.ev-details summary{cursor:pointer}
.ev-config>summary code{margin-right:.75rem}
.ev-config>summary span{font-size:.8125rem}
.ev-config h3{font-size:1rem;margin:1rem 0 .25rem;padding-bottom:.25rem;
  border-bottom:1px solid var(--line)}
.ev-metrics{margin:0}
.ev-metric{display:grid;grid-template-columns:minmax(0,2fr) minmax(0,1fr);
  gap:.2rem 1rem;padding:.55rem .25rem;border-bottom:1px solid var(--line)}
.ev-metric:last-child{border-bottom:0}
.ev-metric dt{font-weight:500}
.ev-description{display:block;color:var(--muted);font-size:.875rem;font-weight:400}
.ev-description:empty{display:none}
.ev-metric dd{margin:0}
.ev-value{display:flex;align-items:baseline;gap:.4rem;flex-wrap:wrap}
.ev-details{grid-column:1/-1;color:var(--muted);font-size:.8125rem}
@media (max-width:600px){
  .ev-metric{grid-template-columns:minmax(0,1fr)}
}
@keyframes open{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
.dx dl{margin:.4rem 0 .2rem;display:grid;grid-template-columns:auto 1fr;gap:.2rem .75rem;
  white-space:normal;max-width:64ch;font-size:.8125rem}
.dx dt{color:var(--muted)}.dx dd{margin:0;overflow-wrap:anywhere}
.deployment{overflow-wrap:anywhere}
.deployment h2{font-size:1.25rem;padding:0;margin:0 0 .35rem}
.deployment h3{font-size:1rem;padding:0;margin:1.25rem 0 .25rem}
.deployment h4{font-size:1rem;padding:0;margin:0 0 .2rem}
.deployment p{margin:0 0 .25rem;font-size:.875rem}
.deployment-summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,20rem),1fr));
  gap:1px;border:1px solid var(--line);border-radius:8px;background:var(--line);overflow:hidden}
.deployment-summary>section{background:var(--panel);padding:1rem 1.15rem}
.deployment-summary>section:last-child{background:color-mix(in srgb,var(--teal) 8%,var(--panel))}
.deployment-summary h2{color:var(--muted);font-size:.875rem;font-weight:500;margin-bottom:.5rem}
.deployment-summary .deployment-setup,.deployment-price strong{font-size:1.2rem;font-weight:600}
.deployment-price{display:flex;align-items:center;gap:.5rem;flex-wrap:wrap}
.deployment-evidence{padding-top:.4rem}
.deployment-evidence>p{color:var(--muted)}
.deployment-evidence .deployment-no-match{margin:.75rem 0;padding:.55rem .75rem;
  border-left:2px solid var(--grey);background:var(--bg)}
.deployment-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,17rem),1fr));
  align-items:start;gap:.65rem;margin:.6rem 0}
.deployment-variant{padding:.8rem .9rem;border:1px solid var(--line);border-radius:6px;
  background:var(--panel)}
.deployment-variant .deployment-results{list-style:none;padding:.55rem 0 0;margin:.55rem 0;
  border-top:1px solid var(--line);font-size:.875rem}
.deployment-results li{display:flex;align-items:center;gap:.4rem;flex-wrap:wrap;margin-bottom:.25rem}
.deployment-variant details{color:var(--muted);font-size:.8125rem}
.deployment-variant summary{cursor:pointer}
.deployment-variant summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
.deployment-variant .dx dl{grid-template-columns:minmax(0,auto) minmax(0,1fr)}
.deployment-sources{margin:.55rem 0 0}
.deployment-source{border-top:1px solid var(--line);margin-top:.4rem;padding-top:.4rem}
.deployment-source dt{font-weight:500;color:var(--text)}
.deployment-source dd{margin:0}
.deployment-source dd:empty{display:none}
.one{margin:.35rem 0;color:var(--muted);font-size:.875rem}
/* Gossamer palette: teal = qualifies/selected, orange = fails/over budget,
   greys = structure. Coloured fills always carry a word, never colour alone. */
.chip{display:inline-block;font-size:.75rem;font-weight:500;padding:.15rem .5rem;
  border-radius:999px;border:1px solid var(--line);color:var(--muted);background:var(--bg)}
.chip-eligible,.chip-eligible_modeled{background:var(--tint);border-color:var(--teal);
  color:var(--accent)}
.chip-eligible_modeled{border-style:dashed}
.chip-rejected{color:var(--text)}
.chip-not_recommended{color:var(--coraltext);border-color:var(--coral);background:#fff}
.nr{color:var(--coraltext)}small.nr{display:block;font-size:.75rem;margin-top:.2rem}
thead th{background:var(--bg)!important;border-bottom:2px solid var(--line)}
.gm tbody tr:nth-child(even)>*{background:color-mix(in srgb,var(--bg) 60%,var(--panel))}
.gm tbody tr:hover>*{background:var(--tint)}
.gm thead th.off{color:var(--grey)}
.bdg-measured{border-color:var(--teal)!important;background:var(--tint)}
.bdg-vendor-doc{border-color:var(--grey)!important}
.bdg-modeled{border-color:var(--grey)!important}
.bdg-published{background:rgba(43,207,206,.22)!important}
.wi{margin-top:1.25rem}
.ans-wi{border-color:var(--grey);background:var(--bg)}
.mt-match{background:var(--tint);padding:.1rem .4rem;border-radius:3px}
*{scrollbar-color:var(--line) transparent}
[data-testid="stSidebar"] h2{border-bottom:2px solid var(--teal);padding-bottom:.3rem;
  display:inline-block}
[data-testid="stExpander"] details{border-color:var(--line)!important}
[data-testid="stExpander"] summary:hover{color:var(--accent)}
[role="tab"][aria-selected="true"]{color:var(--accent)!important}
::selection{background:var(--teal);color:var(--text)}
td.gi{font-size:.9375rem;color:var(--text)}
.gi-t th.cid{font-weight:500;color:var(--accent)}
.foot{margin-top:2.5rem;padding-top:1rem;border-top:1px solid var(--line);font-size:.8125rem;color:var(--muted)}
.gm td.cost{text-align:right}
.gm td.over{color:var(--coraltext)}
.ob{font:500 .6875rem/1 "Fira Sans",sans-serif;margin-left:.3rem}
.fan{margin-top:.5rem;display:grid;grid-template-columns:minmax(0,1fr) 19rem;gap:2rem;
  align-items:start}
.fan-side{display:flex;flex-direction:column;align-items:center;gap:.5rem}
.fan-side>button{width:2.25rem;height:2.25rem;border-radius:999px;border:1px solid var(--line);
  background:var(--panel);color:var(--text);cursor:pointer;font-size:1rem;
  transition:border-color var(--dur-fast) var(--ease-out),background var(--dur-fast) var(--ease-out)}
.fan-side>button:hover{border-color:var(--teal);background:var(--tint)}
.fan-live{margin:0 0 .5rem;font:500 .8125rem "Fira Code",monospace;color:var(--accent)}
.fan-rail{display:flex;flex-direction:column;gap:.75rem;overflow-y:auto;height:30rem;width:100%;
  scroll-snap-type:y mandatory;padding:12rem .75rem;scrollbar-width:none;outline-offset:4px}
.fan-rail::-webkit-scrollbar{display:none}
.fan-card{flex:0 0 auto;scroll-snap-align:center;display:flex;flex-direction:column;gap:.3rem;
  text-align:left;padding:.85rem 1rem;border-radius:10px;border:1px solid var(--line);
  background:var(--panel);color:var(--text);cursor:pointer;font:inherit;
  box-shadow:0 6px 18px rgba(28,29,31,.06);transform-origin:0% 50%;
  transition:box-shadow var(--dur) var(--ease-out),border-color var(--dur) var(--ease-out)}
@media (max-width:900px){.fan{grid-template-columns:1fr}.fan-side{order:-1}}
.fan-card[aria-current]{border-color:var(--teal);box-shadow:0 14px 32px rgba(11,115,114,.18)}
.fc-id{font:500 .9375rem "Fira Code",monospace}
.fc-model{font-size:.8125rem;color:var(--muted)}
.fc-host{font-size:.8125rem;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.fc-foot{display:flex;justify-content:space-between;align-items:center;margin-top:.35rem}
.fan-steps h3{font-size:1.05rem;font-weight:600;margin:.25rem 0 .75rem}
.fan-steps ol{list-style:none;margin:0;padding:0;display:grid;gap:.1rem;max-width:72ch;
  position:relative}
.fan-steps li{display:grid;grid-template-columns:2rem 1fr;column-gap:.75rem;padding:.55rem 0;
  border-bottom:1px solid var(--line)}
.fan-steps li:last-child{border-bottom:0}
.fs-n{grid-row:span 2;width:1.75rem;height:1.75rem;border-radius:999px;display:grid;
  place-items:center;background:var(--tint);color:var(--accent);font-weight:500;font-size:.8125rem}
.fs-t{font-weight:500}
.fs-d{color:var(--muted);font-size:.875rem}
@media (prefers-reduced-motion:reduce){.fan-card{transition:none}}
.ct td,.ct th{white-space:normal;font-size:.8125rem;padding:.35rem .5rem}
.ct td.cid{font-family:"Fira Code",monospace;white-space:nowrap}
/* chart bars grow from their baseline (motion.js) */
.js-plotly-plot .bars path{transform-box:fill-box;transform-origin:0 50%}
/* Streamlit chrome in the Gossamer look */
[role="tab"]{transition:color var(--dur-fast) var(--ease-out)}
[data-testid="stSidebar"]{background:#F2F2F3}
[data-testid="stCaptionContainer"]{opacity:1!important;color:var(--muted)!important}
[data-testid="stCaptionContainer"] p{color:var(--muted)!important}
@media (prefers-reduced-motion:reduce){
  .bdg,tbody tr{transition:none}
  table details[open] .dx{animation:fade 120ms ease-out}
  table details summary::before{transition:none}
  @keyframes fade{from{opacity:0}to{opacity:1}}
}
"""
