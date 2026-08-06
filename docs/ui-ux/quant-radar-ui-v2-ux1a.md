# Quant Radar UI/UX v2 — UX-1A Evidence

## Status and scope

Status: **UX-1A browser and visual gates passed with the limitations recorded
below**.

UX-1A introduces the approved Calm Decision Cockpit presentation primitives
and adopts them on the bounded target surfaces. Both owned Chromium commands
completed after the last UX-1A production-code change. The manifests, provider
counters, and all 41 final screenshots were reviewed; no pending field is
treated as a pass.

The historical UX-0 evidence remains in
`docs/ui-ux/quant-radar-ui-v2-baseline.json` and
`docs/ui-ux/quant-radar-ui-v2-baseline.md`; UX-1A does not rewrite either file.

## Browser cases

The runner records the browser case separately from the underlying route. The
two interactive cases use Playwright accessibility locators and visible
accessible names; they do not write Streamlit session state or manipulate the
private DOM.

For focused captures at 390px and 320px, the runner first activates
Streamlit's visible sidebar-collapse button by its accessible name. This makes
the component reflow measurable and is recorded as a setup action in each
capture. The unchanged seven-page regression run retains the historical shell
state, so the known expanded-sidebar obstruction remains visible there.

| UX-1A case | Route | Stable interaction | Measured component |
| --- | --- | --- | --- |
| `today-decision` | `/` | none | Today Decision main region |
| `ai-chat-open` | `/` | click button named `AI` | open AI Chat panel |
| `ai-updates` | `/ai-updates` | none | AI Updates main region |
| `schedules` | `/schedules` | none | Schedules main region |
| `institution-portfolio` | `/institutions` | click button named `機構持倉 · 機構 → 它持有什麼` | Institution Portfolio main region |

Each capture manifest records:

- case, page, and route;
- viewport and screenshot path;
- target component bounds, client width, scroll width, and overflow state;
- page-level bounds and overflow;
- console messages, page errors, failed requests, and HTTP errors;
- blocked browser/server network attempts;
- fixture/provider counters and counter quiescence.

## Required automated evidence

### Focused UX-1A matrix

Expected per selected browser: **20 captures** (5 cases × desktop, tablet,
mobile, and 320×844).

| Field | Result |
| --- | --- |
| Run ID / manifest | `focused-20260716-final3` / `.claude/ui_snapshots/ux1a/focused-20260716-final3/manifest.json` |
| Chromium | `supported`; manifest status `passed` |
| Captures passed | `20 / 20` |
| Component / page horizontal overflow | `0 / 20`; `0 / 20` |
| Page / Streamlit exceptions | `0`; `0` |
| Failed / external / server-network requests | `0`; `0`; `0` |
| Provider-counter review | all 20 captures quiescent; no blocked provider/network call |
| Screenshots inspected | `20 / 20` |

Command:

```bash
.venv/bin/python scripts/ui_ux_snapshot_matrix.py \
  --browser chromium \
  --case today-decision \
  --case ai-chat-open \
  --case ai-updates \
  --case schedules \
  --case institution-portfolio \
  --viewport desktop --viewport tablet --viewport mobile --viewport 320x844 \
  --out-dir .claude/ui_snapshots/ux1a/<focused-run-id> --no-prompt
```

### Unchanged UX-0 route regression matrix

Expected per selected browser: **21 captures** (7 historical pages × 3
standard viewports). The invocation deliberately has no `--case` argument.

| Field | Result |
| --- | --- |
| Run ID / manifest | `regression-20260716-final3` / `.claude/ui_snapshots/ux1a/regression-20260716-final3/manifest.json` |
| Chromium | `supported`; manifest status `passed` |
| Captures passed | `21 / 21` |
| Component / page horizontal overflow | `0 / 21`; `0 / 21` |
| Page / Streamlit exceptions | `0`; `0` |
| Compatibility/provider-counter comparison | all 21 fixture-counter maps exactly equal the immutable UX-0 baseline (`0` mismatches); all captures quiescent |
| Screenshots inspected | `21 / 21` |

Both manifests record route-local Streamlit probes as known HTTP/console 404s:
24 entries in the focused run and 36 in the regression run, limited to
`/_stcore/health` and `/_stcore/host-config` below non-root routes. These are
the same class recorded in UX-0; they produced no failed request, page error,
Streamlit exception, external request, or server-network attempt.

Command:

```bash
.venv/bin/python scripts/ui_ux_snapshot_matrix.py \
  --browser chromium \
  --out-dir .claude/ui_snapshots/ux1a/<seven-page-regression-run-id> \
  --no-prompt
```

## Visual-review ledger

All final screenshots are accounted for. Twenty-six final3 PNGs are
byte-identical to the already inspected final2 image at the same case and
viewport; the other fifteen final3 PNGs were reopened at original resolution
and inspected after the final code change.

| Review item | Result |
| --- | --- |
| Intentional StateBanner / SourceMeta differences | `PASS`; fixed safe state/source copy is visible without raw diagnostics |
| Chip contrast and wrapping | `PASS` for scoped UX-1A chips; labels remain legible and wrap at narrow widths |
| AI Chat open-state layout | `PASS`; accessible-name interaction succeeded at all four viewports and panel overflow was zero |
| Institution Portfolio selected state | `PASS`; accessible-name interaction succeeded and the selected portfolio remained visible |
| 320×844 component reflow | `PASS`; all five measured components had zero horizontal overflow |
| Unexpected identity/order/content difference | none observed; fixture identities, ordering, handoffs, and dates remained stable |

The existing mobile shell obstruction remains a known UX-0 issue: the unchanged
default regression run shows the expanded 300px Streamlit sidebar covering most
of all seven 390px captures. Focused mobile/320 setup actions successfully used
the visible accessible collapse control before measuring components; the
manifest's shell metric still flags six focused sidebar overlaps even though
the reviewed screenshots show the sidebar closed, so UX-1A does not claim the
shell issue resolved. The fixed floating AI control can also cover a small
lower-right card/content area on Today Decision, Schedules, and Institution
Portfolio at some widths, including part of Today Decision's progress region at
tablet width; that shell-level placement is deferred to the later redesign.

## Browser and human evidence limitations

| Evidence | Status |
| --- | --- |
| Playwright WebKit | `UNSUPPORTED` in the owned runner environment |
| Real macOS Safari | `NOT_CHECKED` |
| Participant SUS/SEQ/task study | `NOT_RUN` |

Playwright WebKit, when locally supported, is additional automated evidence;
it is not a substitute for real Safari. No synthetic usability score is part
of UX-1A.

## Completion checklist

- [x] focused Chromium manifest passes exactly 20/20 captures;
- [x] unchanged default Chromium manifest passes exactly 21/21 captures;
- [x] every focused and regression screenshot is inspected;
- [x] intentional visual differences and known shell issue are recorded;
- [x] provider counters and candidate identity/order compatibility are checked;
- [x] WebKit capability and Safari status are reported without treating an
  unsupported or unchecked browser as passed.
