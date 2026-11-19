# 03 - Stories and Tickets

The backlog is generated from one source file so IDs, dependencies and hours stay consistent.

| Need | File |
|---|---|
| Read everything (stories + tickets in the required format) | `backlog/BACKLOG.md` |
| One ticket per file, with YAML frontmatter (agents) | `backlog/tickets/T<n>.<m>.<k>.md` |
| Import to Jira / Linear / Notion / GitHub Projects | `backlog/backlog.csv` (columns: ID, Type, Parent, Title, Description, Acceptance Criteria, Priority, Estimate, Size, Week, Dependencies, Labels, Status, Deliverable) |
| Edit the plan | `backlog/source/tickets.py`, then `python tools/backlog.py build` |
| Track progress | `python tools/backlog.py set <ID> <todo|in_progress|blocked|done|cut>` (stored in `backlog/status.json`) |
| What is next | `python tools/backlog.py next` |
| Validate plan (deps, 1-6 h rule, weekly load <= 10 h, cycles) | `python tools/backlog.py check` |

ID scheme: `EPIC-1` > `SEn` (sub-epic) > `Sn.m` (story) > `Tn.m.k` (ticket). 33 tickets, 16 stories, 7 sub-epics. Sizes: S <= 2 h, M 2.5-4 h, L 4.5-6 h.
