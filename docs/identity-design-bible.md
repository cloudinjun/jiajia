# Identity Design Bible

Identity design should happen before accessory drawing. Each Paperclip Pal identity needs a readable job, attitude, first-sight silhouette, and visual taboo list. Accessories should clarify that identity, not decorate the character randomly.

## Global rules

- Keep the same paperclip body, eyes, and brows.
- Use one long-lived primary accessory silhouette per identity.
- Use short-lived state/performance accents for effects such as heat, error, cold arrow, sleep, or celebration.
- Use one accent color per identity.
- Do not add mouth, arms, feet, hats, costumes, or animal parts.
- Avoid circular props near the eyes; they read as monocles, extra eyes, or face features at desktop size.

## Identity silhouette map

| Identity | First-sight read | Primary silhouette | Short accents | Avoid |
|---|---|---|---|---|
| `default_pal` | bare mischievous paperclip | none | cold spark, innocent halo, annotation tick | permanent badges |
| `task_auditor` | tiny audit clipboard | vertical checklist with fold corner | green check, red micro-x, audit circle | generic sticky note |
| `agent_supervisor` | terminal monitor / status console | terminal card with prompt and status lamp | cursor blink, waiting dots, reconnect tick | lone green dot |
| `thermal_technician` | heat gauge, not thermometer glasses | side heat bar with tick marks | heat wisps, sweat dot, red level | round bulb near eyes |
| `usage_accountant` | receipt / ledger strip | narrow receipt with percent and balance line | refill tick, reset clock dot | generic progress bar |
| `focus_companion` | quiet low-presence mode | no hard prop; soft lavender aura only | moon dot, soft ring | occupational tools |
| `sleepy_clip` | low-power sleep state | Z cluster plus soft cloud shadow | slow Z drift, tiny sleep puff | sleep hat or pillow limbs |
| `bug_coroner` | bug scene investigator | tilted magnifier plus evidence tag | warning burst, stamp, caution tick | magnifier near eye |
| `critic_clip` | red-pen reviewer | angled red pen | hand-drawn circle, arrow, underline | weapon-like pen |
| `tab_warden` | browser-tab warden | stacked tabs / tiny browser fence | lock dot, block mark, tab wiggle | lock-only icon |
| `gremlin_clip` | mischievous easter-egg state | no hard prop; plum spark language | tiny spark, motion tick, fake halo | devil horns or tail |
| `meltdown_clip` | physical shape compromise | puddle shadow / low collapsed pose | warning bubble, crawl-back ticks | oversized alarm sign |

## Accessory design order

1. Write the identity's job and emotional rule.
2. Pick a large silhouette that reads at 25-40px, before adding detail.
3. Pick one accent color.
4. Decide which details are long-lived and which only appear during a performance.
5. Check the prop at desktop size. If it can be mistaken for an eye, monocle, mouth, hand, or hat, move or redesign it.
6. Only then implement the Tk Canvas shape.

## Thermal technician redesign note

The old thermometer can read as a monocle because it is placed near the upper-left face area and uses a circular bulb. The replacement should be a side heat gauge: a vertical bar with clear tick marks and a red fill level. Heat wisps should appear above the head only during hot states.

## Minimum readability test

For each identity, hide the line text and ask whether the silhouette alone suggests the role:

- audit clipboard means task/audit
- terminal monitor means agent supervision
- side heat gauge means hardware temperature
- receipt strip means budget/usage
- soft aura means focus/quiet
- Z cluster means sleep
- magnifier plus tag means bug investigation
- red pen means design critique
- stacked tabs means tab clutter
- plum spark means gremlin
- puddle shadow means meltdown

If the answer depends on reading the tooltip or knowing the YAML name, the accessory is not distinct enough.
