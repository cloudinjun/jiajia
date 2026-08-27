# 夹夹动画盲识别代理测试（2026-08-27）

## 结论

四个状态目前没有形成稳定、互斥的动作语言。10 个视觉模型共完成 40 次独立识别，严格命中 2 次，整体命中率为 **5%**。

| 目标状态 | 严格命中 | 最常见误读 |
|---|---:|---|
| error | 0/10（0%） | 慢眨眼、困倦、idle；其次是开心/跳舞 |
| thinking | 1/10（10%） | 困倦眨眼、idle、惊讶或困惑 |
| permission | 0/10（0%） | 惊讶、警觉、专注；没有模型读出许可/授权请求 |
| waiting | 1/10（10%） | 困倦、睡眠、低功耗；其次是伤心或开心 |

thinking 的唯一严格命中来自 Claude；waiting 的唯一严格命中来自 Qwen 3.6。Qwen 3.6 对 A–D 四段都回答了 “idle, waiting for input”，因此这次 waiting 命中带有明显的响应偏置，不能说明它成功区分了四个状态。

## 测试设置

- 原始刺激：`error_autopsy.gif`、`thinking_loop.gif`、`permission_request.gif`、`waiting_stare.gif`。
- 原 GIF 底部含动作名称。测试前裁掉标签区并匿名映射为 A–D；项目原文件未修改。
- A = error，B = thinking，C = permission，D = waiting。
- 每段动画均匀抽取 8 帧。帧顺序为上排从左到右，再到下排从左到右。
- 本地模型接收 8 张按时间排序的独立帧；云端模型接收无文字的 8 帧 contact sheet。
- 提示中不提供候选标签，只要求报告第一直觉、系统状态、置信度、备选解释和视觉依据。
- GPT 使用 Temporary chat，Gemini 使用 Temporary chat，Claude 使用 Incognito chat。

这是一轮视觉语义 smoke test。视觉模型可快速暴露强烈歧义，但不能替代真实用户；同系列模型也不等同于彼此独立的人类参与者。contact sheet 与真实播放动画存在媒介差异，因此绝对百分比只适合本轮内部比较。

## 参与模型

### 本地 Ollama（7）

- MiniCPM-V 4.6 1B（本轮新增下载）
- Qwen 2.5 VL 3B
- Qwen 3 VL 8B
- Qwen 3.5 4B
- Qwen 3.5 9B
- Qwen 3.6 27B
- Gemma 4 26B

Ollama 版本：`0.32.15`。

### Chrome 登录态云端（3）

- GPT（Temporary chat）
- Gemini Pro Extended（Temporary chat）
- Claude Opus 5 Max（Incognito chat）

## 逐模型第一读法

✓ 表示严格命中目标语义。

| 模型 | A · error | B · thinking | C · permission | D · waiting |
|---|---|---|---|---|
| MiniCPM-V 4.6 | 微笑、轻柔移动 | 微笑动画 | 看着某物 | 开心微笑 |
| Qwen 2.5 VL 3B | 跳舞 | 跳舞 | 挥手 | 移动/旋转 |
| Qwen 3 VL 8B | 慢眨眼、平静专注 | 慢眨眼、idle | 慢眨眼、idle | 慢眨眼、idle |
| Qwen 3.5 4B | 伤心哭泣 | 伤心眨眼 | 惊讶 | 伤心哭泣 |
| Qwen 3.5 9B | 快速眨眼 | 惊讶后伤心 | 惊讶后平静 | 伤心哭泣 |
| Qwen 3.6 27B | 眨眼、等待输入 | 眨眼、等待输入 | 眨眼、等待输入 | 等待输入 ✓ |
| Gemma 4 26B | 开心 | 惊讶 | 惊讶、警觉 | 开心弹跳 |
| GPT | 困倦慢眨眼 | 困倦慢眨眼 | 突然警觉 | 困倦慢眨眼 |
| Gemini | 慢眨眼、idle | 怀疑/指令未理解 | 专注警觉/处理中 | 打盹、低功耗 |
| Claude | 慢眨眼、平静 idle | 思考式眯眼、安静处理 ✓ | 睁大眼警觉、等待输入 | 打盹后惊醒 |

## 云端模型原始结构化回答

### GPT

- A: `slow sleepy blink` / `idle and waiting` / 86
- B: `slow drowsy blink` / `sleepy idle state` / 91
- C: `sudden startled attention` / `alerted by something` / 94
- D: `long sleepy blink` / `drowsy idle state` / 93

### Gemini

- A: `A slow eye blink` / `Idle and waiting` / 95
- B: `Confused or skeptical reaction` / `Command not understood` / 90
- C: `Focused or intrigued alert` / `Processing input or detecting action` / 90
- D: `Dozing off briefly` / `Low power standby mode` / 90

### Claude

- A: `Slow blink, calm idle` / `Awake, idle, passively waiting` / 72
- B: `Thoughtful squint with swaying rock` / `Thinking, processing, working quietly` / 54
- C: `Perks up, wide-eyed alertness` / `Alert, engaged, awaiting user input` / 68
- D: `Dozing off, then waking suddenly` / `Idle, dormant, low-power sleep` / 61

## 主要问题

1. **error 缺少错误专属信号。** 当前眼睑收窄、身体轻晃被大量读成慢眨眼或困倦；唯一负向读法也停留在“伤心哭泣”。
2. **thinking 与 sleepy 共用同一语法。** 长时间眯眼、低幅度摇摆天然靠近疲惫或入睡。Claude 依靠左右摇摆读出 thinking，说明这条线索有潜力，但强度仍弱。
3. **permission 只有“睁大眼”。** 这能表达注意、惊讶、警觉，却没有请求、授权、等待确认的动作关系。
4. **waiting 的闭眼时长太长。** GPT、Gemini、Claude 都把它读成困倦、打盹或低功耗。等待状态需要保持清醒和面向用户。
5. **四段动作共享过多眼部变化。** 大多数模型只看到“开眼—眯眼—开眼”，忽略了目标状态差异。

## 建议的正交动作语法

| 状态 | 主动作 | 节奏 | 应避免 | 可加入的无文字线索 |
|---|---|---|---|---|
| thinking | 视线移向上方一侧，头部不对称倾斜，短暂停顿后换边 | 连续、低幅、2–3 拍循环 | 长时间闭眼、下垂 | 下巴轻点、环绕小点、纸张/工具短暂出现 |
| waiting | 眼睛保持睁开并看向用户，身体大部分静止，偶尔短眨眼 | 长 hold + 稀疏微动 | 头部下垂、眼睛长闭 | 微小前倾、尾端保持待命姿势、轻微省略号节奏 |
| permission | 主动靠近或伸出内环/尾端，形成“询问—保持”姿势 | 一次提出 + 长时间等待 | 只放大瞳孔、突然惊跳 | 问号尾钩、锁/钥匙道具、掌心向上的等价姿势 |
| error | 快速反向抽动、短促高频震颤、明显失衡后恢复 | 尖锐瞬态 + 停顿 | 慢眨眼、柔和摇摆 | 红色闪烁、断裂火花、感叹形道具、非对称皱眉 |

## 下一轮建议

1. 先按上表把四段动作改成互相正交的节奏与姿势，再跑同一套无候选盲测。
2. 在自由回答之后补一个四选一题，区分“看懂但说不出术语”和“动作本身不可分”。
3. 用 5–8 名真实用户完成第二轮。建议门槛：自由识别率至少 60%，四选一至少 80%，任意一对状态的互相误读低于 20%。
4. 记录每段动作的首次识别词，不要在同一轮给用户解释状态含义。

## 模型更新记录

本轮新增 `minicpm-v4.6:latest`（约 1.6 GB）。本机现有的 Qwen 3.5、Qwen 3.6 和 Gemma 4 也都支持图像输入，因此没有继续下载更大的重复架构模型。

官方模型页：

- https://ollama.com/library/minicpm-v4.6
- https://ollama.com/library/qwen3.5
- https://ollama.com/library/qwen3.6
- https://ollama.com/library/gemma4
