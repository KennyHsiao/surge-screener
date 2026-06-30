# Tempo Notes

## 2026-07-01 Candidate Outcomes Schedule

- GitHub Actions schedule is UTC-only. The no-LLM candidate outcome job runs on
  weekdays at `35 23 * * 1-5`, after the US close and after the 23:15 UTC
  oversold-lane job.
- The job is stateless and idempotent by `scan_date + ticker`: reruns update the
  same `reports/candidate_outcomes/YYYY-MM-DD.json` rows instead of appending
  duplicates.
- Price fetching is gated by maturity windows. The script records paper rows
  immediately but only fetches prices when 7/14/30/60D horizons are due, keeping
  the daily schedule bounded as history grows.
