# student-app/agent

学生端的讲诗 agent(Python 3.12 / FastAPI,包 `student_agent`)。**不是内容生产 agent**:没有任何写底座的能力,不读 DRAFT,只消费已发布的 bundle 与诗文包。

设计:`../design/agent-design.md`。要点:

- 流程由程序推进(`machine.py`),模型最多 `suggest_step`;
- 脚本驱动优先(`service.py`):每个动作都有可直接播放的脚本答案;模型只做措辞改写,输入里没有学生原话;
- 上下文按角色裁剪(`lesson.py`):诗人只读本诗的诗人台词;
- 审校(`reviewer.py`)与评估(`evaluator.py`)全用规则,评估只指出缺哪一点,不打分;
- 降级链:主模型 → 备用模型 → 预写脚本 → 前端文字。没有网关/密钥时是脚本模式,服务照常启动。

```bash
make student-dev                       # 与前端一起起
cd student-app/agent && PYTHONPATH=src ../../.venv/bin/python -c 'from student_agent.main import run; run()'
```

配置只读 `POETRY_LLM_API_BASE/KEY/MODEL_PRIMARY/MODEL_FALLBACK`(被 git 忽略的 `.env` 或进程环境)与 `STUDENT_*`(见 `config.py`)。`/agent/v1/health` 不返回地址、密钥、模型名。日志只记元数据,不记学生输入和提示词。

目录:`src/student_agent/`(代码与 `souls/`)、`data/lessons/`(课程旁路文件:要点、问答触发词、向导措辞;不含史实)、`data/eval/`(评测集)、`tests/`。

测试与评测:按约定开发期间不跑,最后统一执行(`pytest student-app/agent/tests`、`make student-eval`)。
