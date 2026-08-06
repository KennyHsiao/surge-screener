# Pipe Notes

| Date | Decision | Notes |
| --- | --- | --- |
| 2026-07-03 | Added weekday premarket candidate refresh | Use UTC cron `30 12 * * 1-5` in `Daily US Surge Screener` instead of timezone syntax to match existing workflow style. The job runs deterministic `run_candidate_pipeline.py --mode full_refresh` with money-flow prefetch and no LLM. It commits candidate artifacts and triggers an in-workflow test-server deploy with `RUN_SOURCE_REFRESH=1` so shared money-flow storage updates after GitHub-token report commits. |
| 2026-08-07 | Bound Phase 7E freeze to all deployment lanes | An uninterrupted evidence window must gate the normal main/manual deployment and both candidate post-commit deployment jobs while leaving producer schedules active. Deploy the guard with the variable unset, drain active deploys, then set `PHASE7E_DEPLOY_FREEZE` to literal `true`; unset it and explicitly deploy the latest main after the evidence boundary. |
