"""可复用的 Agent 能力：主脑、记忆、工具、提示词、技能、世界书。

这一层不认识「角色扮演产品」：它只提供能力，由 service 组合。
约束（见 .importlinter）：不得 import companion.service / api / bootstrap，
所以换一个产品（job-come 那种招聘 agent）时这一层可以直接拿走。
"""
