# 07 - Definition of Done

## Ticket
- [ ] Every acceptance-criteria box in `backlog/tickets/<ID>.md` is verified by running something or opening the artifact (not by belief).
- [ ] Deliverable file(s) exist at the stated path.
- [ ] Code has tests where the ticket calls for them; `pytest` and `ruff check .` pass.
- [ ] Any new assumption is added to `docs/assumptions.md` with source or `assumption` tag and a range.
- [ ] Any decision between alternatives is recorded in `docs/decisions/ADR-NNN-*.md`.
- [ ] Time spent is within 1.5x the estimate, or the overrun is noted in the ticket and the plan adjusted.
- [ ] `python tools/backlog.py set <ID> done` run; committed with the ticket ID in the message.

## Sub-epic
- [ ] All P0/P1 tickets done or explicitly cut (status `cut`, reason recorded in the milestone doc).
- [ ] The week's demo-able checkpoint (04_milestone_plan.md) can be shown in < 5 minutes.
- [ ] Exit criterion in 02_epic_breakdown.md met.
- [ ] No orphaned TODOs in the code related to the sub-epic.

## Project
- [ ] `python scripts/run_all.py --quick` from a clean clone reproduces `headline_numbers.json` within documented tolerance.
- [ ] Every number in README, memo, slides and resume bullets equals a value in `results/headline_numbers.json`.
- [ ] All executed plans pass the independent checker (0 violations).
- [ ] Targets in the charter are each reported as met / not met with evidence.
- [ ] Sensitivity and "where it does not help" are published.
- [ ] README has all 6 sections; assumptions and >= 6 limitations documented.
- [ ] Dashboard starts on a clean clone; screenshots committed.
- [ ] No raw data, API tokens or secrets in the repo or history; data licences respected.
- [ ] Portfolio pack finalised; 3 resume bullets, pitch and Q&A match the real results.
