# Optimisation model

Code: `src/shelflife/opt/model.py`, `src/shelflife/opt/sequencing.py`. Decision record: ADR-003. Costs: `configs/costs.yaml` (assumptions).

## Sets and parameters
- p in P: SKUs; t = 0..H-1 weeks (H = 13); a = 0..A_p ages in weeks.
- A_p = floor((1 - MSL) * L_p / 7): oldest age that may still ship (ADR-004); L_p is shelf life in days.
- d_pt: forecast demand (cases); r_p: line rate (cases/h); K: available hours per week.
- m_p, M_p: min and max run (cases) = rate x min/max run hours.
- C_ij: changeover hours i -> j (allergen rule, `plant/changeover.py`); C_ii = 0.
- I0_pa: initial stock of age a >= 1; l0: SKU last run before week 0.
- Costs: c_prod, c_hold, c_exp, c_lost, c_co, c_ss.

## Variables
x_pt >= 0 production; y_pt in {0,1} run; s_pat >= 0 shipment from age-a stock.
Sequencing (mode "arc"): z_ijt in {0,1} i directly before j in week t; f_pt, e_pt in {0,1} first/last run of week t; rho_t in {0,1} week has production; L_pt in [0,1] line state (last SKU) after week t; w_ijt in [0,1] carry-over transition; pi_pt in [0,|P|] MTZ position.

## Inventory by age (expressions)
I_p0t = x_pt; I_pat = I_{p,a-1,t-1} - s_{p,a-1,t-1} (a >= 1, t >= 1); I_pa0 = I0_pa.
Shipped S_pt = sum_a s_pat; lost u_pt = d_pt - S_pt; expired E_pt = I_{p,A_p,t} - s_{p,A_p,t}; carried V_pt = sum_{a<A_p} (I_pat - s_pat).

## Constraints
1. s_pat <= I_pat (ship only what exists; this also makes all I_pat >= 0 and E_pt >= 0).
2. S_pt <= d_pt (lost sales, no backorders).
3. m_p y_pt <= x_pt <= M_p y_pt.
4. Capacity: sum_p x_pt / r_p + CO_t <= K.
5. Changeover hours CO_t:
   - "arc": CO_t = sum_{i != j} C_ij (z_ijt + w_ijt), with
     - flow: sum_i z_ipt + f_pt = y_pt; sum_j z_pjt + e_pt = y_pt;
     - sum_p f_pt = sum_p e_pt = rho_t; rho_t >= y_pt; rho_t <= sum_p y_pt;
     - line state: L_pt >= e_pt; L_pt >= L_{p,t-1} - rho_t; sum_p L_pt = 1 (L_{p,-1} = 1 iff p = l0);
     - carry-over: w_ijt >= L_{i,t-1} + f_jt - 1;
     - MTZ: pi_jt >= pi_it + 1 - |P| (1 - z_ijt).
   - "approx" (decomposition): CO_t = sum_p cbar_p y_pt, with cbar_p = mean_{i != p} C_ip; then CP-SAT finds the cheapest order per week given the selected SKUs and the carried line state, and repairs capacity pro rata if needed.
6. Safety stock (T4.3.1, optional, SOFT): g_pt >= SS_pt - V_pt, g_pt >= 0, where V_pt is usable stock at the end of week t
   and g_pt is the **shortfall variable**, penalised at c_ss per case (`safety_stock_shortfall_per_case`, assumption 2.0,
   range 0.5-5 in `configs/costs.yaml`). Because the floor is soft, safety stock can never make the model infeasible.
   Target (`src/shelflife/opt/safety_stock.py`): SS_pt = min( z(alpha) sigma_{p,h=t+2}, sum of forecast_p over weeks
   t+1 .. t+A_p ), with sigma from the validation year (`results/forecast/error_sigma.csv`), alpha a TARGET service
   level (default 0.95, A-24) and A_p the SKU's maximum ship age in weeks. The cap stops the model from holding stock
   that would expire before it could be sold (it binds for slow, short-life SKUs; tested). Caveat: the validation-year
   sigmas under-cover on the test year (forecasting.md, Uncertainty), so realised service will fall short of alpha.

## Objective
min sum_{p,t} [c_prod x_pt + c_lost u_pt + c_exp E_pt + c_hold V_pt + c_ss g_pt] + c_co sum_t CO_t

## Verification
The arc-model objective equals the simulator-evaluated cost of the same plan (`tests/test_opt_consistency.py`); the MIP's run order matches brute force for the chosen SKU set; CP-SAT sequencing matches brute force on random weeks; zero demand gives zero production.

Further checks: a hand-solved 2-SKU x 4-week toy (`tests/test_model_toy.py`; LP file in `tests/fixtures/toy.lp`). My first hand derivation missed the free same-SKU carry-over and overstated the optimum (145,600 vs 145,300); the solver found the cheaper plan, the simulator confirmed it, and the corrected derivation is kept in the test docstring. With all changeover times 0, the arc model equals pure lot sizing. Invalid input returns status `INVALID_INPUT`; demand above capacity returns an optimal plan with lost sales, not an error.

## Plan output schema (`sim.engine.plan_to_frame`, shared by baseline, optimiser, checker, dashboard)
| Column | Meaning |
|---|---|
| week | 0-based week of the plan |
| position | run order within the week (0 = first) |
| sku_id | SKU |
| qty | cases produced in the run |
| changeover_hours_before | hours of the switch into this run (includes carry-over from the previous week's last SKU) |
| clean_type | `none` (same SKU or line start), `routine`, or `allergen` |

Every executed plan is re-validated by `shelflife.checks.plan_checker` (no imports from opt/sim; rules re-derived from `configs/plant.yaml`).

## Per-run changeover estimate (ADR-007)
The decomposition's per-run estimate cbar_p is now chosen on the validation year (`scripts/tune_planner_validation.py`,
`configs/planner.yaml`): 1.0 h for every SKU (the cheapest incoming changeover). It beat the ADR-003 mean-incoming
default, estimates iterated from realised sequences, and the exact arc model on simulator-evaluated cost. The reason is
robustness to forecast error, not accuracy (ADR-007). The true changeover hours are always charged by the sequencer,
the simulator and the independent checker.

## Open improvement
Plan against demand scenarios (stochastic or chance-constrained lot sizing) instead of a point forecast plus safety stock.
That would make the deliberate under-charging of changeovers unnecessary.
