# Identity Prop Icon Candidates

This is the first curated vendor reference set for Jiajia identity props.
The SVGs live under `jiajia/assets/vendor/`, with source licenses preserved.

## Selection Criteria

- Mature open source libraries only.
- SVG only, no random PNGs.
- Simple 24x24 outline icons with round joins and readable silhouettes.
- MIT or ISC license.
- Useful as reference for redrawing, not pasted as final runtime decoration.

## Candidate Mapping

| Identity | Candidate SVGs | Why It Helps | Redraw Direction |
| --- | --- | --- | --- |
| `task_auditor` | `tabler-icons/selected/clipboard-check.svg`, `tabler-icons/selected/list-check.svg` | Reads immediately as audit, checklist, review. | Convert into a tiny off-white clipboard slip with dark brown ticks. |
| `agent_supervisor` | `tabler-icons/selected/terminal.svg`, `lucide/selected/terminal.svg` | Strong Codex/Claude monitoring signal without adding a human role. | Make a small terminal badge with one status dot. |
| `thermal_technician` | `tabler-icons/selected/temperature.svg`, `lucide/selected/thermometer.svg`, `lucide/selected/gauge.svg` | Heat and load are clearer as gauges than red circles. | Use a side-mounted gauge or tiny heat tick, not a traditional monocle shape. |
| `usage_accountant` | `tabler-icons/selected/receipt.svg`, `lucide/selected/receipt-text.svg`, `lucide/selected/badge-percent.svg` | Usage and billing need ledger/receipt language. | Redraw as a tiny receipt ledger or percent tag near the body. |
| `bug_coroner` | `tabler-icons/selected/bug.svg`, `lucide/selected/bug.svg`, `lucide/selected/search.svg` | Bug plus search makes the identity legible. | Redraw as evidence tag plus magnifier, keep small and flat. |
| `tab_warden` | `tabler-icons/selected/browser.svg`, `lucide/selected/panels-top-left.svg` | Stacked tabs/browser panel are clearer than a lock alone. | Use two or three overlapping tab cards. |

## Style Normalization Notes

- Replace `currentColor` with project palette during redraw.
- Favor 2.5 to 3.5 px apparent stroke at Jiajia scale.
- Use filled paper shapes sparingly; avoid complex interior text.
- Keep props outside the eyes and brows unless intentionally layered below brows.
- Do not let props cover the body silhouette enough to read as a costume.

