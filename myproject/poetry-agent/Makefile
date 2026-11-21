SHELL := /bin/bash

# 入口只转发到 scripts/ 下对应项目的脚本；Makefile 本身不放逻辑。
.PHONY: help content-bootstrap content-up content-down content-logs content-ps content-smoke \
        content-profile-check deerflow-bootstrap migrate-agent-domain migrate-agent-orchestration \
        student-dev student-verify check-copies check-layout build-images lint test-all

help:
	@echo "内容生产 (content-agent): content-bootstrap content-up content-down content-logs content-smoke content-profile-check"
	@echo "C 端 (student-app):       student-dev student-verify"
	@echo "数据库迁移 (需要授权):     migrate-agent-domain migrate-agent-orchestration"
	@echo "维护:                      check-copies check-layout build-images lint deerflow-bootstrap test-all"
	@echo "本地离线演示 (content-agent): content-dev-offline content-dev-offline-down content-dev-offline-status content-env-sync content-llm-check"

content-bootstrap:
	./scripts/content-agent/bootstrap.sh
content-up:
	./scripts/content-agent/up.sh
content-down:
	./scripts/content-agent/down.sh
content-logs:
	./scripts/content-agent/logs.sh
content-ps:
	source scripts/lib.sh && ensure_content_env && content_compose ps
content-smoke:
	./scripts/content-agent/smoke.sh
content-profile-check:
	./scripts/content-agent/profile-check.sh

deerflow-bootstrap:
	./scripts/deerflow/bootstrap-deerflow-runtime.sh

migrate-agent-domain:
	./scripts/db/migrate-agent-domain.sh
migrate-agent-orchestration:
	./scripts/db/migrate-agent-orchestration-v008.sh

student-dev:
	./scripts/student-app/dev.sh
student-verify:
	./scripts/student-app/verify.sh

check-copies:
	./scripts/maintenance/check-copies.sh
check-layout:
	./scripts/maintenance/check-layout.sh
build-images:
	./scripts/deploy/build-images.sh

lint:
	uv run ruff check content-agent/agent

# 统一测试入口：开发期间不跑，留到最后一次性运行。不连数据库、不启动容器。
test-all:
	./scripts/maintenance/test-all.sh

# ---- 素材任务体系(任务 C,追加)----
.PHONY: production-gen production-report production-check production-regen-placeholders
production-gen:
	./scripts/student-app-production/prod.sh gen chun-wang
production-report:
	./scripts/student-app-production/prod.sh report chun-wang
production-check:
	./scripts/student-app-production/prod.sh registry-check
production-regen-placeholders:
	./scripts/student-app-production/regen-placeholders.sh

# ---- 本地离线演示 / 环境同步 / 网关检查(任务 A 子任务 S2,追加)----
# content-dev-offline 加 Studio: make content-dev-offline ARGS=--studio
.PHONY: content-dev-offline content-dev-offline-down content-dev-offline-status content-env-sync content-llm-check
content-dev-offline:
	./scripts/content-agent/dev-offline.sh $(ARGS)
content-dev-offline-down:
	./scripts/content-agent/dev-offline-down.sh
content-dev-offline-status:
	./scripts/content-agent/dev-offline-status.sh
content-env-sync:
	./scripts/content-agent/env-sync.sh
content-llm-check:
	./scripts/content-agent/llm-check.sh

# ---- 学生端(任务 B,追加)----
# student-web: 组装可直接托管 / 交给 Capacitor 作 webDir 的静态目录 student-app/frontend/dist/web
# student-eval: 离线评测 runner(脚本路径,不联网);按约定开发期间不跑,最后统一执行
.PHONY: student-web student-eval
student-web:
	cd student-app/frontend && node build.mjs --web
student-eval:
	cd student-app/agent && PYTHONPATH=src ../../.venv/bin/python -m student_agent.evalrun

# ---- 移动壳 Capacitor(任务 F,追加)----
# student-shell-check: 壳静态检查(不构建原生、不跑测试);student-shell-env: 只读探测 SDK/Xcode/CocoaPods
# student-shell-sync-android: make student-web → 写运行时配置 → cap sync android(需先 npx cap add android)
.PHONY: student-shell-check student-shell-env student-shell-sync-android student-shell-sync-ios
student-shell-check:
	./scripts/student-app-shell/shell.sh check
student-shell-env:
	./scripts/student-app-shell/shell.sh env
student-shell-sync-android:
	./scripts/student-app-shell/shell.sh sync-android
student-shell-sync-ios:
	./scripts/student-app-shell/shell.sh sync-ios

# ---- 学生端 agent 的 mock 大模型网关(任务 B 第二阶段,追加)----
# student-agent-mock-llm: 本地 mock OpenAI 兼容网关 + LLM 模式 agent;MODE=ok|leak|garbage|empty|5xx|timeout。不调用真实网关。
.PHONY: student-agent-mock-llm
student-agent-mock-llm:
	./scripts/student-app/mock-llm.sh
