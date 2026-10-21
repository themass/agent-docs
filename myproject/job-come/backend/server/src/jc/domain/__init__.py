"""Pure domain knowledge: resume methodology with no I/O.

Nothing in this layer may import `jc.services`, `jc.stores`, `jc.llm`, `jc.mcp` or
`jc.agent`. It holds the product's written-down expertise — role playbooks, structural
rules, scoring heuristics — as data and pure functions, so that both the business
services and the skill composer can depend on it without depending on each other.

That cycle is the reason the layer exists: `jc.skills.composer` needs the role
playbook to compose a prompt, and `jc.services` needs the composer to run a turn. With
the playbook sitting in `jc.services`, those two imported each other.
""" 