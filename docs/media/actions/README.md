# Action GIF Library

Every action the pal can perform, rendered from the same keyframe tables,
easing curves, and pose math the live app uses.

Regenerate after changing any action:

```powershell
python scripts\generate_action_gifs.py
```

`full` = complete performance. `body` = body and expression shown, but the
action also uses runtime-only canvas props (paper, hat, cane). `expression`
= the action is carried by eyes, brows, tail, or inner core over an idle body.

## Mood

| Action | Preview | Coverage | Notes |
|---|---|---|---|
| `happy_bounce` | ![happy_bounce](happy_bounce.gif) | full | 轻快弹两下，适合开心、赞同、发现好事。 |
| `dance` | ![dance](dance.gif) | full | 左右跳舞，适合得意、无聊自娱或庆祝。 |
| `celebrate` | ![celebrate](celebrate.gif) | full | 更夸张的小庆祝，适合完成任务或状态变好。 |
| `excited_spin` | ![excited_spin](excited_spin.gif) | full | 原地快速转两圈然后骄傲亮相，适合按捺不住的激动。 |
| `smug_sway` | ![smug_sway](smug_sway.gif) | full | 得意地小幅左右摆，适合毒舌后装无辜。 |
| `sulk` | ![sulk](sulk.gif) | full | 缩下去闷一下，适合小委屈、小嫌弃、小无语。 |
| `hide` | ![hide](hide.gif) | full | 往下躲一躲，适合害羞、心虚、说完冷箭装无辜。 |

## State

| Action | Preview | Coverage | Notes |
|---|---|---|---|
| `thinking_tilt` | ![thinking_tilt](thinking_tilt.gif) | full | 歪着想一想，适合思考和吐槽前的停顿。 |
| `sleepy_sag` | ![sleepy_sag](sleepy_sag.gif) | full | 慢慢塌下去再恢复，适合困、无聊、加载太久。 |
| `flop` | ![flop](flop.gif) | full | 整只纸夹趴下，适合累了、无语、放弃一秒。 |
| `melt` | ![melt](melt.gif) | full | Melt into a low readable puddle, hold for a beat, then recover; use for overload, embarrassment, or complete dramatic collapse. |
| `stretch` | ![stretch](stretch.gif) | full | 伸懒腰，适合从 idle 醒来或准备开工。 |
| `scan` | ![scan](scan.gif) | expression | 眼睛左右扫视，适合监控、找东西、读屏幕状态。 |
| `patrol` | ![patrol](patrol.gif) | full | 左右巡逻，适合等待、监控 Codex 或假装忙。 |
| `curious_lean` | ![curious_lean](curious_lean.gif) | full | 好奇地朝一侧探身拉长凑近看，适合发现新东西或偷看屏幕。 |
| `shiver` | ![shiver](shiver.gif) | full | 缩起来发抖再慢慢平静，适合冷、害怕或看到可怕的代码。 |

## Reactive

| Action | Preview | Coverage | Notes |
|---|---|---|---|
| `wiggle` | ![wiggle](wiggle.gif) | full | 被戳或欠欠地抖一下，短促。 |
| `blink` | ![blink](blink.gif) | expression | 睁大眼装无辜或轻轻眨眼。 |
| `peek` | ![peek](peek.gif) | expression | 眼睛偷瞄鼠标或屏幕角落，适合观察。 |
| `jump` | ![jump](jump.gif) | full | 明显跳一下，适合开心或突然来劲。 |
| `spin_jump` | ![spin_jump](spin_jump.gif) | full | 跳起并在空中转体一整圈再落地，适合特别兴奋或想炫技。 |
| `twirl` | ![twirl](twirl.gif) | full | 2D 水平翻转转身，适合装酷或一本正经胡说八道。 |
| `shake` | ![shake](shake.gif) | full | 快速左右抖，适合紧张、报错、被吓到。 |
| `sneeze` | ![sneeze](sneeze.gif) | full | 慢慢吸气仰起来，猛地打个喷嚏，再委屈地缓一下，适合灰尘、着凉、突发小事故。 |
| `peekaboo` | ![peekaboo](peekaboo.gif) | full | 迅速躲下去憋一会儿，再猛地弹出来，适合逗用户或装神秘。 |
| `startled_pop` | ![startled_pop](startled_pop.gif) | full | 突然弹高又缩回，适合被戳、提示、意外状态。 |
| `tail_wag` | ![tail_wag](tail_wag.gif) | expression | 把回形针右侧翘起的尾端轻轻甩两下，适合开心、得意、被逗到。 |
| `tail_tip_flick` | ![tail_tip_flick](tail_tip_flick.gif) | expression | Quick tail-tip flick; use for impatience, suspicion, or a tiny opinion leaking out. |
| `tail_guilty_tuck` | ![tail_guilty_tuck](tail_guilty_tuck.gif) | expression | Tail tucks inward; use for fake innocence, guilt, or pretending nothing happened. |
| `tail_alert_snap` | ![tail_alert_snap](tail_alert_snap.gif) | expression | Tail snaps stiff then rebounds; use for warning, surprise, or sudden status changes. |
| `nod` | ![nod](nod.gif) | full | 点头，适合确认、假装懂了、认真附和。 |

## Tail

| Action | Preview | Coverage | Notes |
|---|---|---|---|
| `tail_idle_slow` | ![tail_idle_slow](tail_idle_slow.gif) | expression | Slow, low-intensity tail sway; use for quiet companionship and subtle aliveness. |
| `tail_smug_sway` | ![tail_smug_sway](tail_smug_sway.gif) | expression | Slow smug tail sway; use after a dry roast or when the pal is pleased with itself. |
| `tail_sleepy_droop` | ![tail_sleepy_droop](tail_sleepy_droop.gif) | expression | Tail droops softly; use for sleepy, bored, or waiting-too-long states. |
| `tail_frantic_innocent` | ![tail_frantic_innocent](tail_frantic_innocent.gif) | expression | Short frantic tail betrayal; use when the pal is trying too hard to look innocent. |
| `tail_raise_excited` | ![tail_raise_excited](tail_raise_excited.gif) | expression | 尾巴竖直高举、梢部微颤，适合兴奋、打招呼、发现好事（猫式竖尾）。 |
| `tail_question_hook` | ![tail_question_hook](tail_question_hook.gif) | expression | 尾巴弯成问号钩并保持，适合好奇、玩心起、歪着头研究东西。 |
| `tail_bristle` | ![tail_bristle](tail_bristle.gif) | expression | 尾巴僵直炸起并快速震颤，适合防御、警戒、被吓到但摆出架势。 |

## Inner

| Action | Preview | Coverage | Notes |
|---|---|---|---|
| `inner_cover_oops` | ![inner_cover_oops](inner_cover_oops.gif) | expression | Inner core swings toward the face like a tiny oops/cover-mouth gesture; never open like a mouth. |
| `inner_side_smirk` | ![inner_side_smirk](inner_side_smirk.gif) | expression | Inner core makes a small sideways smirk gesture; ambiguous between mouth-corner and hand. |
| `inner_shy_retract` | ![inner_shy_retract](inner_shy_retract.gif) | expression | Inner core retracts inward like it has decided to stop incriminating itself. |
| `inner_droop` | ![inner_droop](inner_droop.gif) | expression | Inner core droops softly for sleepy, sulky, or low-energy states. |
| `oops_innocent_combo` | ![oops_innocent_combo](oops_innocent_combo.gif) | expression | Signature post-roast act: inner cover-oops, darting innocent eyes, frantic tail betrayal. |

## Costume

| Action | Preview | Coverage | Notes |
|---|---|---|---|
| `britclip_enter` | ![britclip_enter](britclip_enter.gif) | body | Genderless British-inspired costume: tail produces a hat, bow tie, and cane, then holds the Britclip pose. |
| `britclip_exit` | ![britclip_exit](britclip_exit.gif) | body | Reverse the Britclip costume: cane away, bow tie folded, hat removed, then ordinary paperclip posture. |
| `tip_hat` | ![tip_hat](tip_hat.gif) | body | Tail-assisted hat tip for a polite oops or restrained English-mode acknowledgement. |
| `bow_tie_check` | ![bow_tie_check](bow_tie_check.gif) | body | Tiny costume-aware bow-tie adjustment; formal, neutral, and a little self-important. |
| `cane_tap` | ![cane_tap](cane_tap.gif) | body | Small cane tap for punctuation; restrained status or dry English-mode emphasis. |
| `polite_bow` | ![polite_bow](polite_bow.gif) | full | A tiny formal bow; courtesy without gendered body language. |
| `hat_tip_oops` | ![hat_tip_oops](hat_tip_oops.gif) | body | Tail-assisted hat tip/removal for an oops beat; use after a polite roast in English mode. |

## Paper Props

| Action | Preview | Coverage | Notes |
|---|---|---|---|
| `paper_blanket` | ![paper_blanket](paper_blanket.gif) | body | Draft-paper blanket; use for sleepy, low-energy, or long-idle states. |
| `paper_surfboard` | ![paper_surfboard](paper_surfboard.gif) | body | Draft-paper surfboard; use for browser surfing, lively idle, or playful movement. |
| `paper_peek_curtain` | ![paper_peek_curtain](paper_peek_curtain.gif) | body | Draft-paper curtain with only the eyes showing; use for spying, waiting, or fake innocence. |
| `paper_fan` | ![paper_fan](paper_fan.gif) | body | Folded draft-paper fan; use for heat, stress, or dramatic unimpressed cooling. |
| `paper_whisper_fan` | ![paper_whisper_fan](paper_whisper_fan.gif) | body | Open draft-paper fan in front of the mouth/inner core; use for the sharpest spoken roast, like polite gossip after a lethal sentence. |
| `paper_oops_cover` | ![paper_oops_cover](paper_oops_cover.gif) | body | Draft paper held in front of the face; use after a roast or when pretending not to have said anything. |
| `paper_tent` | ![paper_tent](paper_tent.gif) | body | Folded draft-paper tent; use for hiding, focus retreat, or dramatic avoidance. |
| `paper_pillow` | ![paper_pillow](paper_pillow.gif) | body | Draft-paper pillow; use for sleepy or floppy low-energy beats. |
| `paper_stage` | ![paper_stage](paper_stage.gif) | body | Draft-paper stage mat; use for dance, celebration, or tiny performance moments. |

## Movement

| Action | Preview | Coverage | Notes |
|---|---|---|---|
| `twist_scoot` | ![twist_scoot](twist_scoot.gif) | full | Small twist plus 10-20px scoot; frequent tiny reposition with attitude. |
| `mini_hop_shift` | ![mini_hop_shift](mini_hop_shift.gif) | full | Small hop shift of 20-50px with squash, arc, and rebound. |
| `relocate_hop` | ![relocate_hop](relocate_hop.gif) | full | Medium hop relocation with anticipation, landing squash, and rebound. |
| `zoomies` | ![zoomies](zoomies.gif) | full | 像猫发疯一样左右冲刺几趟带急刹，适合精力过剩。 |
| `moonwalk` | ![moonwalk](moonwalk.gif) | full | 面朝一边却往另一边滑走，滑到位再帅气转回来，适合得意退场。 |
| `pounce` | ![pounce](pounce.gif) | full | 压低身子扭两下蓄力，然后向前扑出一小段，适合盯上了什么东西。 |
| `roast_and_scoot` | ![roast_and_scoot](roast_and_scoot.gif) | full | Scoot away after a roast, then snap into fake innocence. |
| `retreat_to_corner` | ![retreat_to_corner](retreat_to_corner.gif) | full | Retreat toward a screen corner for quiet or self-restraint mode. |
| `drop_in` | ![drop_in](drop_in.gif) | full | Drop into the current station from above with a flat landing squash. |
