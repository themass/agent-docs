# GitHub Analyst 视频 TTS 配置

视频流水线会读取私有配置：

```bash
~/.hermes/profiles/github/config/tts-providers.yaml
```

第一次使用时，复制模板：

```bash
cp ~/.hermes/profiles/github/config/tts-providers.example.yaml \
  ~/.hermes/profiles/github/config/tts-providers.yaml
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

1. `GITHUB_ANALYST_VIDEO_AUDIO_FILE` 指定的固定音频。
2. `config/tts-providers.yaml` 中配置的 TTS provider。
3. 兼容旧环境变量的火山 TTS。
4. `edge-tts`。
5. 只有没有 TTS 配置时，才使用 `audio_cache/github-video-placeholder.mp3` 占位音频。

## 常用命令

运行今日视频流水线：

```bash
~/.hermes/profiles/github/scripts/github-analyst.sh video-pipeline
```

指定日期：

```bash
~/.hermes/profiles/github/scripts/github-analyst.sh video-pipeline 2026-06-03
```

临时强制占位音频：

```bash
GITHUB_ANALYST_FORCE_PLACEHOLDER_AUDIO=1 \
  ~/.hermes/profiles/github/scripts/github-analyst.sh video-pipeline
```

指定配置文件：

```bash
GITHUB_ANALYST_TTS_CONFIG=/path/to/tts-providers.yaml \
  ~/.hermes/profiles/github/scripts/github-analyst.sh video-pipeline
```
