# 实现过程中的开放问题

### Q-001 语音的 LiveKit 适配器不存在
- 任务：T1（发现）
- 问题：`bootstrap/voice_stack.py` 引用 `companion.voice.livekit_adapters`（`GatewaySTT`、`GatewayTTS`），该模块迁移前就不存在，代码在语音模式下会在运行时报错。
- 我的假设：浅聊不用语音，此问题只影响角色扮演。
- 需要的决定：角色扮演阶段是否由我们实现这两个适配器（LiveKit `tts.TTS` / `stt.STT` 接口），还是先删除语音分支。
