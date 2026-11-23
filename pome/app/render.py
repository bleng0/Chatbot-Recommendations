"""HTML pieces for the app: escaped strings only, no Streamlit calls (tested)."""
from html import escape
from urllib.parse import quote

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
}
_SHORT = {"eligible": "Eligible", "eligible_modeled": "Eligible (modeled)",
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
    return f'<span class="bdg bdg-{escape(label.lower())}">{escape(label)}</span>'


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
    return f'<p class="{cls}" role="status" aria-live="polite">{text}</p>'


def _chip(status: str) -> str:
    return f'<span class="chip chip-{escape(status)}">{escape(_SHORT[status])}</span>'


def gate_table(rows: list[dict], gates: list[str], off: set[str],
               what_if: dict[str, str] | None = None,
               cost: dict[str, tuple[str, bool]] | None = None) -> str:
    head = "".join(
        f'<th scope="col" class="g{" off" if g in off else ""}">{g}'
        f'{"<small>off</small>" if g in off else ""}</th>' for g in gates)
    wi_head = '<th scope="col">What-if</th>' if what_if is not None else ""
    if cost is not None:
        wi_head += '<th scope="col">Monthly cost</th>'
    body = []
    for r in rows:
        cells = "".join(
            f'<td class="g{" off" if g in off else ""}">{cell(r["gates"][g])}</td>'
            if g in r["gates"] else '<td class="g">—</td>' for g in gates)
        wi = (f'<td class="stat">{_chip(what_if[r["config"]])}</td>'
              if what_if is not None else "")
        if cost is not None:
            txt, over = cost.get(r["config"], ("—", False))
            tag = ' <span class="ob">over budget</span>' if over else ""
            wi += f'<td class="num cost{" over" if over else ""}">{escape(txt)}{tag}</td>'
        body.append(f'<tr><th scope="row" class="cid">{escape(r["config"])}</th>'
                    f'<td class="stat">{_chip(r["status"])}</td>{wi}{cells}</tr>')
    return (f'<div class="tw"><table class="gm"><caption class="sr">Gate results per '
            f'configuration, failing first</caption><thead><tr><th scope="col">Configuration'
            f'</th><th scope="col">Official status</th>{wi_head}{head}</tr></thead>'
            f'<tbody>{"".join(body)}</tbody></table></div>')


def _details(summary: str, lines: list[tuple[str, str]]) -> str:
    inner = "".join(f"<dt>{escape(k)}</dt><dd>{escape(val)}</dd>" for k, val in lines if val)
    return (f"<details><summary>{escape(summary)}</summary>"
            f'<div class="dx"><dl>{inner}</dl></div></details>')


def gate_info_table(rows: list[dict[str, str]]) -> str:
    body = "".join(
        f'<tr><th scope="row" class="cid">{escape(r["gate"])}</th>'
        f'<td class="gi">{escape(r["checks"])}</td><td class="num">{escape(r["pass_if"])}</td></tr>'
        for r in rows)
    return (f'<div class="tw"><table class="gi-t"><thead><tr><th scope="col">Gate</th>'
            f'<th scope="col">What it checks</th><th scope="col">Passes if</th></tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def evidence_table(rows: list[dict[str, str]]) -> str:
    body = "".join(
        f'<tr><th scope="row" class="cid">{escape(r["config"])}</th>'
        f'<td>{_details(r["metric"], [("Source", r["source"]), ("Formula", r["formula"])])}</td>'
        f'<td class="num">{escape(r["value"])} <span class="unit">{escape(_UNIT.get(r["unit"], r["unit"]))}</span></td>'
        f'<td>{badge(r["provenance"])}</td><td class="num">{escape(r["retrieved"])}</td></tr>'
        for r in rows)
    return (f'<div class="tw"><table class="ev"><thead><tr><th scope="col">Configuration</th>'
            f'<th scope="col">Metric (open for source)</th><th scope="col">Value</th>'
            f'<th scope="col">Provenance</th><th scope="col">Retrieved</th></tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def variant_table(rows: list[dict]) -> str:
    body = []
    for r in rows:
        under = ", ".join(f"{k}: {v}" for k, v in (r["measured_under"] or {}).items())
        detail = _details(r["variant"], [("Source", r["source"]), ("Measured under", under),
                                         ("Note", r["note"])])
        fig = (f'{escape(r["figure"])} {badge(r["badge"])}' if r["figure"]
               else '<span class="muted">no published figure</span>')
        body.append(f'<tr><td>{detail}</td><td class="set">{escape(r["settings"])}</td>'
                    f'<td class="num">{fig}</td><td><span class="mt mt-{r["match"].lower()}">'
                    f'{escape(r["match"].title())}</span></td>'
                    f'<td class="num">{escape(r["retrieved"])}</td></tr>')
    return (f'<div class="tw"><table class="vt"><thead><tr><th scope="col">Setting</th>'
            f'<th scope="col">Stack · quant · hardware · load · lengths</th>'
            f'<th scope="col">Figure</th><th scope="col">Match</th>'
            f'<th scope="col">Retrieved</th></tr></thead><tbody>{"".join(body)}</tbody>'
            f"</table></div>")


_CSS = """
:root{--dur-fast:150ms;--dur:220ms;--dur-slow:480ms;--ease-out:cubic-bezier(.16,1,.3,1);
  --ease-in-out:cubic-bezier(.65,0,.35,1);--stagger:28ms}
html{-webkit-font-smoothing:antialiased}
.tally{margin:.75rem 0 0;font-size:.9375rem;color:var(--muted)}
.tally .kn{font-weight:500;color:var(--text)}
h1{font-size:2rem!important;line-height:1.2!important;max-width:40ch}
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
@keyframes open{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
.dx dl{margin:.4rem 0 .2rem;display:grid;grid-template-columns:auto 1fr;gap:.2rem .75rem;
  white-space:normal;max-width:64ch;font-size:.8125rem}
.dx dt{color:var(--muted)}.dx dd{margin:0;overflow-wrap:anywhere}
.vh{font-size:1rem;font-weight:600;margin:1.5rem 0 .5rem}
.one{margin:.35rem 0;color:var(--muted);font-size:.875rem}
/* Gossamer palette: teal = qualifies/selected, orange = fails/over budget,
   greys = structure. Coloured fills always carry a word, never colour alone. */
.chip{display:inline-block;font-size:.75rem;font-weight:500;padding:.15rem .5rem;
  border-radius:999px;border:1px solid var(--line);color:var(--muted);background:var(--bg)}
.chip-eligible,.chip-eligible_modeled{background:var(--tint);border-color:var(--teal);
  color:var(--accent)}
.chip-eligible_modeled{border-style:dashed}
.chip-rejected{color:var(--text)}
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
.vh code{background:var(--tint);padding:.05rem .35rem;border-radius:3px}
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
/* chart bars grow from their baseline (motion.js) */
.js-plotly-plot .bars path{transform-box:fill-box;transform-origin:0 50%}
/* Streamlit chrome in the Gossamer look */
[role="tab"]{transition:color var(--dur-fast) var(--ease-out)}
[data-testid="stSidebar"]{background:#F2F2F3}
@media (prefers-reduced-motion:reduce){
  .bdg,tbody tr{transition:none}
  table details[open] .dx{animation:fade 120ms ease-out}
  table details summary::before{transition:none}
  @keyframes fade{from{opacity:0}to{opacity:1}}
}
"""
