# Content Studio 视频 TTS 配置

视频流水线会读取私有配置：

```bash
~/.hermes/profiles/content-studio/config/tts-providers.yaml
```

第一次使用时，复制模板：

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"
cp "$HERMES_HOME/skills/content-studio/video-pipeline/assets/tts-providers.example.yaml" \
  "$HERMES_HOME/config/tts-providers.yaml"
```

然后在 `tts-providers.yaml` 中填写真实密钥，并调整 `enabled` 顺序。视频生成会按 `enabled` 从上到下尝试，一个失败就切换到下一个。

默认顺序建议：

```yaml
enabled:
  - BYTE_LLM
  - BYTE_DEF
  - MINIMAX_CH
  - MINIMAX_Q
  - ALI_DEF
  - edge-tts
```

## 音频优先级

1. `CONTENT_STUDIO_VIDEO_AUDIO_FILE` 指定的固定音频。
2. `config/tts-providers.yaml` 中配置的 TTS provider。
3. 兼容旧环境变量的火山 TTS。
4. `edge-tts`。
5. 只有没有 TTS 配置时，才使用 `audio_cache/github-video-placeholder.mp3` 占位音频。

## 常用命令

运行今日视频流水线：

```bash
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes/profiles/content-studio}"
"$HERMES_HOME/scripts/content-studio.sh" video-pipeline
```

指定日期：

```bash
"$HERMES_HOME/scripts/content-studio.sh" video-pipeline 2026-06-03
```

临时强制占位音频：

```bash
CONTENT_STUDIO_FORCE_PLACEHOLDER_AUDIO=1 \
  "$HERMES_HOME/scripts/content-studio.sh" video-pipeline
```

指定配置文件：

```bash
CONTENT_STUDIO_TTS_CONFIG=/path/to/tts-providers.yaml \
  "$HERMES_HOME/scripts/content-studio.sh" video-pipeline
```
