# Pipe Notes

| Date | Decision | Notes |
| --- | --- | --- |
| 2026-07-03 | Added weekday premarket candidate refresh | Use UTC cron `30 12 * * 1-5` in `Daily US Surge Screener` instead of timezone syntax to match existing workflow style. The job runs deterministic `run_candidate_pipeline.py --mode full_refresh` with money-flow prefetch and no LLM. It commits candidate artifacts and triggers an in-workflow test-server deploy with `RUN_SOURCE_REFRESH=1` so shared money-flow storage updates after GitHub-token report commits. |
