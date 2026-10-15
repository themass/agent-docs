# JC

JC 是面向互联网行业全部知识工作岗位、服务**主动跳槽与职业提升**的 Web 产品。它帮助用户完成档案核对、简历优化与导出、JD 匹配、模拟面试和真实面试复盘；不提供自动投递能力。

## Quick start

```bash
cd /Users/gqli/work/deepagents/docs/myproject/job-come
./scripts/setup-venv.sh
cp backend/server/.env.example backend/server/.env
./scripts/dev.sh
```

- Web：`http://127.0.0.1:3000`
- API：`http://127.0.0.1:8000/api/v1`
- Agent：内嵌于 API Python 进程

提交前的本地检查：

```bash
./scripts/test-local.sh
```

脚本说明：[`scripts/README.md`](scripts/README.md)。

## Project layout

```text
frontend/web/       # Next.js 前端
backend/server/     # FastAPI、数据库迁移、测试
backend/agent/      # DeerFlow、Skill、Prompt、LLM 配置
backend/infra/      # 基础设施集成
scripts/            # 开发、测试、部署脚本
docs/               # 产品、架构、运维、决策与验收证据
```

线上地址为 `http://jc.sspacee.com`；Nginx 将 `/api/v1` 同域转发给 FastAPI。

## Documentation

完整的软件文档导航与规范：[`docs/README.md`](docs/README.md)。
