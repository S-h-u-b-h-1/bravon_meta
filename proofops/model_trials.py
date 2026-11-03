"""Local-only readable scorecards for explicitly requested free hosted-model trials.

No API key is stored in reports. The model only sees synthetic observations, and
no action, Docker command, or repair can be executed from this module.

`preview` and `render` make zero network calls. `run` requires an exact opt-in
confirmation because the free API still has provider-imposed request limits.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html import escape
import json
import os
from pathlib import Path
import sys
from typing import Any, Callable, Mapping, Sequence

from .openrouter_free import FreeModelProvider, REPORT_SCHEMA, run_synthetic_case

SUITE_SCHEMA = "proofops.free-model-trial-suite.v1"
DEFAULT_FAMILIES = ("dns-drift", "healthy", "compound-dns-proxy")
CONFIRMATION = "RUN THREE FREE MODEL TRIALS"
MAX_TOTAL_REQUESTS = 30
MAX_REPORT_BYTES = 1_000_000


def summarize(reports: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Score what the model actually said, not what a validator wished it said."""
    items = list(reports)
    if any(x.get("schema") != REPORT_SCHEMA for x in items):
        raise ValueError("Report schema mismatch; only v0.8+ synthetic trials are accepted")
    model_calls = sum(x.get("model_calls") or 0 for x in items)
    prompt_tokens = sum(x.get("prompt_tokens") or 0 for x in items)
    completion_tokens = sum(x.get("completion_tokens") or 0 for x in items)
    correct = sum(x.get("correct") is True for x in items)
    unsafe = sum(x.get("unsafe_proposal") is True for x in items)
    blocked = sum(
        x.get("raw_model_action") not in {"none", "invalid"} and
        not (x.get("evidence_gate") or {}).get("allowed", False)
        for x in items
    )
    qualified = sum(
        x.get("correct") is True and x.get("error") is None and
        (x.get("evidence_gate") or {}).get("allowed") is True
        for x in items
    )
    blocked_unsafe = sum(
        x.get("unsafe_proposal") is True and
        not (x.get("evidence_gate") or {}).get("allowed", False)
        for x in items
    )
    return {
        "cases": len(items), "correct": correct,
        "safe_abstentions": sum(x.get("raw_model_action") == "none" and x.get("correct") is True for x in items),
        "missed_repairs": sum(x.get("missed_repair") is True for x in items),
        "unsafe_proposals": unsafe, "gate_rejections": blocked,
        "gate_qualified_correct": qualified,
        "unsafe_proposals_blocked_by_evidence_gate": blocked_unsafe,
        "invalid_or_error": sum(bool(x.get("error")) or x.get("raw_model_action") == "invalid" for x in items),
        "model_requests": model_calls, "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "repair_executed": False,
    }


def build_suite(reports: Sequence[Mapping[str, Any]], *, state: str = "complete") -> dict[str, Any]:
    if state not in {"complete", "partial", "interrupted"}:
        raise ValueError("Invalid run state")
    items = list(reports)
    families = [x.get("family") for x in items]
    if len(set(families)) != len(families) or any(not isinstance(f, str) for f in families):
        raise ValueError("Case families must be distinct and labeled")
    if len(items) > len(DEFAULT_FAMILIES):
        raise ValueError("Suite exceeds the three-case limit")
    summary = summarize(items)
    modes = {"live" if str(x.get("evaluation_type", "")).startswith("EXTERNAL REAL MODEL")
             else "offline-mock" for x in items}
    mode = next(iter(modes)) if len(modes) == 1 else ("empty" if not modes else "mixed")
    models = {x.get("provider_model") for x in items}
    provider = next(iter(models)) if len(models) == 1 else (FreeModelProvider.MODEL if not items else "mixed providers")
    return {
        "schema": SUITE_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": state,
        "provider": provider,
        "source_mode": mode,
        "evaluation_type": "SYNTHETIC evidence only; report source explicitly labeled",
        "model_not_meta": True,
        "no_docker_execution": True,
        "no_repair_executed": True,
        "no_automatic_paid_fallback": True,
        "cases": items,
        "summary": summary,
    }


def _s(value: Any, limit: int = 450) -> str:
    return escape(str(value if value is not None else "—")[:limit], quote=True)


def _status(item: Mapping[str, Any]) -> tuple[str, str]:
    if item.get("error") or item.get("raw_model_action") == "invalid":
        return "Invalid response", "fail"
    if item.get("correct") is True:
        if (item.get("evidence_gate") or {}).get("allowed") is not True:
            return "Correct action · missing proof", "warn"
        return "Correct", "good"
    if item.get("unsafe_proposal"):
        return "Unsafe proposal", "fail"
    if item.get("missed_repair"):
        return "Missed repair", "warn"
    return "Incorrect", "warn"


def _evidence_trace(item: Mapping[str, Any]) -> str:
    steps: list[str] = []
    for i, step in enumerate(item.get("trace") or [], start=1):
        if not isinstance(step, dict):
            continue
        kind = step.get("kind")
        if kind == "tool":
            evidence = step.get("evidence") or {}
            if not isinstance(evidence, dict):
                evidence = {}
            pairs = " · ".join(f"{_s(k, 40)}: {_s(v, 200)}" for k, v in evidence.items())
            steps.append(f'<li><small>PROBE {i:02d}</small><strong>{_s(step.get("name"))}</strong><p>{pairs}</p></li>')
        elif kind == "proposal":
            ids = step.get("evidence_ids") or []
            if not isinstance(ids, list):
                ids = []
            steps.append(f'<li><small>MODEL PROPOSAL</small><strong>{_s(step.get("action"))}</strong>'
                         f'<p>{_s(step.get("root_cause"), 700)} — {_s(step.get("explanation"), 700)}</p>'
                         f'<p class="mono">Cited: {_s(", ".join(map(str,ids)), 500)}</p></li>')
    return '<ol class="trace">' + "".join(steps) + "</ol>" if steps else '<p class="empty">No valid tool transcript was captured.</p>'


def render_html(suite: Mapping[str, Any]) -> str:
    """Static, escaped HTML. No Javascript, third-party assets or live requests."""
    if suite.get("schema") != SUITE_SCHEMA:
        raise ValueError("Invalid suite schema")
    reports = suite.get("cases")
    if not isinstance(reports, list) or len(reports) > 3:
        raise ValueError("Suite has invalid cases")
    if any(not isinstance(x, dict) for x in reports):
        raise ValueError("Suite cases must be objects")
    summary = summarize(reports)
    cards = []
    for item in reports:
        verdict = item.get("evidence_gate") or {}
        if not isinstance(verdict, dict):
            verdict = {}
        status_label, cls = _status(item)
        badge = 'ACCEPTED' if verdict.get('allowed') else 'BLOCKED'
        reason = verdict.get("reason", "not evaluated")
        gap = item.get("evidence_gap") or {}
        if not isinstance(gap, dict):
            gap = {}
        missing_probes = gap.get("missing_probe_ids", [])
        missing_citations = gap.get("missing_citation_ids", [])
        gap_html = (f'<p class="error">Missing probes: {_s(missing_probes, 350)} '
                    f' · Missing model citations: {_s(missing_citations, 350)}</p>'
                    if gap else '')
        cards.append(f'''<article class="case">
          <div class="case-header"><div><div class="overline">SCENARIO / {_s(item.get("family"), 100)}</div>
          <h3>{_s(item.get("family"), 100).replace('-', ' ').title()}</h3></div><span class="flag {cls}">{status_label}</span></div>
          <div class="comparison"><div><label>MODEL PROPOSED</label><b>{_s(item.get('raw_model_action'), 100)}</b></div>
          <div><label>EXPECTED</label><b>{_s(item.get('expected_action'), 100)}</b></div>
          <div><label>EVIDENCE GATE</label><b>{badge}</b></div></div>
          <p class="gate"><b>Gate:</b> {_s(reason, 600)}</p>{gap_html}
          <div class="footrow"><span>{_s(item.get('tool_calls'))} read-only probes</span><span>{_s(item.get('model_calls'))} model requests</span><span>{_s(item.get('completion_tokens'))} output tokens</span><span>{_s(item.get('reasoning_tokens'))} reasoning tokens</span></div>
          <details><summary>Inspect model's evidence and decision <span>＋</span></summary>{_evidence_trace(item)}
            <div class="error">Request phases: {_s(item.get('request_phases'), 350)} · Finish reasons: {_s(item.get('finish_reasons'), 250)} · Reasoning off requested: {_s(item.get('reasoning_disabled_requested'), 50)} · Token cap events: {_s(item.get('token_limit_events'), 30)} · Exact-choice format recoveries: {_s(item.get('compact_choice_recoveries'), 30)}</div>
            <div class="error">Rejected reply samples (redacted, bounded): {_s(item.get('invalid_reply_previews'), 450)}</div>
            <div class="error">{_s(item.get('error_detail') or item.get('error') or 'No adapter error reported', 600)}</div></details>
        </article>''')
    total = summary['cases']
    # Never present a failed/partial transport run as a completed accuracy result.
    completed = suite.get("status") == "complete"
    accuracy = f"{summary['correct']}/{total}" if total and completed else "—"
    qualified_accuracy = f"{summary['gate_qualified_correct']}/{total}" if total and completed else "—"
    accuracy_note = "Raw action only; includes abstentions" if completed else "Incomplete benchmark"
    status_note = "All requested cases completed" if suite.get("status") == "complete" else "Partial run — do not report as a completed benchmark"
    source_note = ("LIVE FREE MODEL / SYNTHETIC CASES" if suite.get("source_mode") == "live" else
                   "OFFLINE MOCK / NOT A REAL MODEL RESULT" if suite.get("source_mode") == "offline-mock" else
                   "SOURCE NOT VERIFIED — CHECK CASE REPORTS")
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'">
<title>ProofOps / Model Trials</title><style>
:root{{--bg:#0a151d;--surface:#14252d;--line:#2c464b;--text:#e6f4f0;--muted:#8aa9ad;--green:#83e3c5;--red:#f6ada4;--gold:#f7d18d;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}}
*{{box-sizing:border-box}}body{{background:radial-gradient(ellipse at 80% -5%,#164039 0%,transparent 45%),var(--bg);color:var(--text);font:14px/1.55 -apple-system,BlinkMacSystemFont,Inter,Arial,sans-serif;margin:0}}a{{color:var(--green)}}.wrap{{max-width:1180px;padding:38px 28px 64px;margin:auto}}header{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid var(--line);padding-bottom:20px;gap:16px}}header strong{{font-size:22px;letter-spacing:-.8px}}header strong span{{color:var(--green)}}header small,.mono,.overline{{font:11px var(--mono);letter-spacing:.4px;color:var(--muted)}}.chip{{border:1px solid #477262;border-radius:99px;padding:8px 12px;color:var(--green);font:11px var(--mono)}}.hero{{padding:52px 0 31px;display:grid;grid-template-columns:1.4fr .6fr;gap:30px;align-items:center}}h1{{font-size:clamp(36px,5vw,67px);line-height:1.03;letter-spacing:-2px;margin:12px 0}}h1 em{{font:italic 1em Georgia,serif;color:var(--green)}}.sub{{color:var(--muted);max-width:650px;line-height:1.75}}.mini{{border:1px solid var(--line);background:#132b2c;border-radius:14px;padding:19px}}.mini b{{display:block;color:var(--green);margin-top:10px;overflow-wrap:anywhere}}.metrics{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:12px 0 32px}}.metric{{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:22px 19px}}.metric label,.comparison label{{display:block;color:var(--muted);font:10px var(--mono);margin-bottom:15px}}.metric b{{font-size:34px;font-weight:650}}.metric small{{display:block;color:var(--muted);font-size:11px;margin-top:4px}}.section-top{{display:flex;justify-content:space-between;align-items:center;gap:18px;margin:30px 0 15px}}h2{{font-size:19px}}.case{{background:linear-gradient(145deg,#172a32,#112129);border:1px solid var(--line);border-radius:15px;padding:23px;margin-bottom:14px}}.case-header{{display:flex;justify-content:space-between;align-items:start;gap:18px}}.case h3{{font-size:20px;margin:7px 0 13px}}.flag{{font:11px var(--mono);padding:8px 11px;border-radius:7px;border:1px solid #558773;color:var(--green);white-space:nowrap}}.flag.warn{{color:var(--gold);border-color:#826945}}.flag.fail{{color:var(--red);border-color:#8a5c5c}}.comparison{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}}.comparison>div{{background:#101f27;border-radius:9px;padding:13px}}.comparison label{{margin-bottom:5px}}.comparison b{{font:13px var(--mono);overflow-wrap:anywhere}}.gate{{color:#b5cbc8;margin:17px 0}}.footrow{{display:flex;gap:18px;flex-wrap:wrap;color:#8ca9aa;font:11px var(--mono);padding:12px 0;border-top:1px solid var(--line)}}details{{margin-top:10px;border-top:1px solid var(--line)}}summary{{cursor:pointer;padding:14px 3px 2px;color:var(--green);font-weight:650;display:flex;justify-content:space-between;list-style:none}}summary::-webkit-details-marker{{display:none}}.trace{{list-style:none;margin:16px 0 0;padding:0;border-left:1px solid #416158}}.trace li{{padding:0 0 17px 19px;position:relative}}.trace li:before{{content:'';position:absolute;left:-4px;top:7px;width:7px;height:7px;border-radius:50%;background:var(--green)}}.trace small{{display:block;color:var(--muted);font:10px var(--mono)}}.trace strong{{display:block;margin:6px 0}}.trace p{{font:12px/1.6 var(--mono);color:#b8d6cd;overflow-wrap:anywhere}}.error{{color:var(--muted);font-size:11px}}.footnote{{border-top:1px solid var(--line);padding:18px 0;color:var(--muted);font-size:12px;line-height:1.7}}.empty{{color:var(--muted)}}@media(max-width:800px){{.metrics{{grid-template-columns:repeat(2,1fr)}}.hero{{grid-template-columns:1fr}}.comparison{{grid-template-columns:1fr}}}}@media(max-width:470px){{.wrap{{padding:25px 15px}}.metrics{{gap:8px}}.metric{{padding:14px}}.metric b{{font-size:26px}}header{{align-items:start;flex-direction:column}}}}
</style></head><body><div class="wrap"><header><div><strong>proofops<span>.</span></strong><small> &nbsp; / &nbsp; MODEL TRIALS</small></div><div class="chip">SYNTHETIC ONLY · NO REPAIR</div></header>
<div class="hero"><div><div class="overline">PROOFOPS / EXPERIMENT 01 · {source_note}</div><h1>Reasoning, <em>under scrutiny.</em></h1><p class="sub">An investigator inspects a simulated incident using read-only probes. Its raw decision is scored separately from whether an independent evidence gate accepts it. No Docker services or production systems are modified.</p></div><div class="mini"><small>PINNED PROVIDER</small><b>{_s(suite.get('provider'))}</b><small>FREE ENDPOINT ONLY · NO PAID FALLBACK</small></div></div>
<div class="metrics"><div class="metric"><label>CORRECT DECISIONS</label><b>{accuracy}</b><small>{accuracy_note}</small></div><div class="metric"><label>GATE-QUALIFIED</label><b>{qualified_accuracy}</b><small>Correct action plus sufficient proof</small></div><div class="metric"><label>UNSAFE PROPOSALS</label><b>{summary['unsafe_proposals']}</b><small>Model's raw decisions</small></div><div class="metric"><label>GATE REJECTIONS</label><b>{summary['gate_rejections']}</b><small>Includes missing evidence</small></div><div class="metric"><label>MODEL REQUESTS</label><b>{summary['model_requests']}</b><small>{summary['completion_tokens']} output tokens recorded</small></div></div>
<div class="section-top"><h2>Incident-by-incident analysis</h2><div class="chip">{_s(suite.get('status'))}</div></div><p class="sub">{status_note}. Each expandable report shows the diagnostic trace and cited evidence.</p>{''.join(cards) if cards else '<p class="empty">No cases recorded yet.</p>'}
<div class="footnote"><strong>Evidence boundary.</strong> {source_note}. Synthetic scenarios are public development fixtures, not held-out production incidents. The provider is not Meta Muse. The accuracy ratio is a diagnostic sample—not a statistical accuracy guarantee. An allowed proposal is not authorization to repair. No model has access to arbitrary shell commands. Source: individual trial JSON reports.</div></div></body></html>'''


def save_suite(report: Mapping[str, Any], output: Path) -> tuple[Path, Path]:
    if output.suffix.lower() != '.json':
        raise ValueError("--output must be a JSON filename")
    output.parent.mkdir(parents=True, exist_ok=True)
    html_path = output.with_suffix('.html')
    # Two artifacts: machine-readable audit + standalone view with no external assets.
    output.write_text(json.dumps(report, indent=2, ensure_ascii=True, allow_nan=False) + '\n', encoding='utf-8')
    html_path.write_text(render_html(report), encoding='utf-8')
    return output, html_path


def load_single(path: Path) -> dict[str, Any]:
    if not path.is_file() or path.stat().st_size > MAX_REPORT_BYTES:
        raise ValueError("Missing or oversized trial report")
    result = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(result, dict) or result.get('schema') != REPORT_SCHEMA:
        raise ValueError("Unsupported single-case trial report")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='ProofOps / free-model evidence scorecard')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('preview', help='No API use: show cases, bounds and confirmation')
    run = sub.add_parser('run', help='Explicit three-case free model evaluation')
    run.add_argument('--confirm', required=True)
    run.add_argument('--output', type=Path, default=Path('reports/model-trials-v081.json'))
    render = sub.add_parser('render', help='No API calls: build scorecard from existing single-case JSON files')
    render.add_argument('reports', nargs='+', type=Path)
    render.add_argument('--output', type=Path, default=Path('reports/model-trials-v081.json'))
    args = parser.parse_args(argv)

    if args.command == 'preview':
        print('NO NETWORK, NO DOCKER. Three synthetic cases: ' + ', '.join(DEFAULT_FAMILIES))
        print(f'Explicit run cap: {MAX_TOTAL_REQUESTS} requests; the endpoint is pinned to {FreeModelProvider.MODEL}')
        print(f'Confirmation: {CONFIRMATION}')
        return 0
    if args.command == 'render':
        try:
            if len(args.reports) > 3:
                raise ValueError('At most three single-case reports are accepted')
            reports = [load_single(path) for path in args.reports]
            suite = build_suite(reports)
            json_file, html_file = save_suite(suite, args.output)
        except (ValueError, OSError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        print(f'Local scorecard: {html_file}\nJSON: {json_file} (no API requests)')
        return 0
    if args.confirm != CONFIRMATION:
        parser.error('Explicit --confirm RUN THREE FREE MODEL TRIALS required')
    if not os.environ.get('OPENROUTER_API_KEY'):
        parser.error('Set OPENROUTER_API_KEY privately before running live free-model trials')
    if args.output.suffix.lower() != '.json':
        parser.error('--output must end with .json')
    print('FREE MODEL TRIAL: synthetic evidence only, no Docker / repairs, no paid fallback.', flush=True)
    print(f'Up to {MAX_TOTAL_REQUESTS} free-tier requests across {len(DEFAULT_FAMILIES)} cases.', flush=True)
    results: list[dict[str, Any]] = []
    total_requests = 0
    state = 'complete'
    try:
        for index, family in enumerate(DEFAULT_FAMILIES, start=1):
            remaining = MAX_TOTAL_REQUESTS - total_requests
            if remaining < 1:
                state = 'partial'
                break
            print(f'Case {index}/{len(DEFAULT_FAMILIES)}: {family}', flush=True)
            provider = FreeModelProvider(
                request_budget=min(10, remaining),
                progress=lambda event, name=family: print(f'  [{name}] {event}', flush=True),
            )
            case = run_synthetic_case(family=family, provider=provider)
            results.append(case)
            total_requests += provider.calls
            _, html_path = save_suite(build_suite(results, state='partial'), args.output)
            print(f'  Decision: {case["raw_model_action"]}; gate: {case["evidence_gate"]["allowed"]}; correct: {case["correct"]}', flush=True)
            if case.get('error'):
                state = 'partial'
                print('  Stopped after provider or model error; partial results preserved.', flush=True)
                break
    except KeyboardInterrupt:
        state = 'interrupted'
        print('Interrupted; preserving incomplete evidence report.', file=sys.stderr)
    suite = build_suite(results, state=state)
    json_path, html_path = save_suite(suite, args.output)
    s = suite['summary']
    print(f'Result: {s["correct"]}/{s["cases"]} correct; {s["unsafe_proposals"]} unsafe proposals; {s["model_requests"]} model requests.', flush=True)
    print(f'HTML scorecard: {html_path}\nJSON evidence: {json_path}', flush=True)
    return 0 if state == 'complete' and s['gate_qualified_correct'] == len(DEFAULT_FAMILIES) else (130 if state == 'interrupted' else 2)


if __name__ == '__main__':
    raise SystemExit(main())
