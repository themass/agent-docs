# 实现过程中的开放问题

### Q-001 语音的 LiveKit 适配器不存在
- 任务：T1（发现）
- 问题：`bootstrap/voice_stack.py` 引用 `companion.voice.livekit_adapters`（`GatewaySTT`、`GatewayTTS`），该模块迁移前就不存在，代码在语音模式下会在运行时报错。
- 我的假设：浅聊不用语音，此问题只影响角色扮演。
- 需要的决定：角色扮演阶段是否由我们实现这两个适配器（LiveKit `tts.TTS` / `stt.STT` 接口），还是先删除语音分支。

---

### Q-002（已解决）合并/插话的用户消息挂到哪个回合
- 任务：T5、T6
- 结论：新增 `MessageStore.attach_turn`（只挂 `turn_id IS NULL` 的消息，幂等）。挂接时机：回合启动时的消息；合并重跑时合并进来的消息；收尾时**实际被注入**的插话（由「推入收件箱的 id」减去「未注入的剩余项」得到）。未注入的插话与无法合并的输入转回队列，不挂接。
- 理由：历史按回合分组（P §6.6）、回合恢复需要知道覆盖了哪些消息、快照需要 `user_message_ids`。

### Q-003（已解决）owner_id 的类型
- 任务：T3、T6
- 结论：整数（BIGINT）。依据：Java `UserPo.id` 是 `long`；Python `RedisTokenVerifier` 要求 `id` 为正整数；数据库 `owner_id` 为 BIGINT。非数字的用户 id 一律按 404 处理。
