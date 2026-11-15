/**
 * Which waiting indicators a turn produces.
 *
 * The reported defect was two stacked 「舟卡思考中」 pills for one turn. There are three
 * places a waiting indicator can come from, and each is correct on its own:
 *
 *   1. `AgentTurnCard`'s bare row, when a turn is streaming with no answer text yet
 *   2. the step card's header chip, when the same turn has activities to show
 *   3. `AgentConversationThread`'s bottom pill, when `busy` but no turn is streaming
 *
 * They must never overlap. This suite pins the rule at the level where the decision
 * is actually made — the assembled turn — instead of at the JSX, because the JSX is
 * where the duplicate was reported and the turn is where it can be prevented.
 */

import { describe, expect, it } from "vitest";

import type { AgentUiDisplayItem } from "../display-items";
import { buildAgentTurns } from "../turn-model";

const user = (id: string, content: string): AgentUiDisplayItem =>
  ({ kind: "user", id, content }) as AgentUiDisplayItem;

const assistant = (
  id: string,
  content: string,
  streaming: boolean,
): AgentUiDisplayItem => ({ kind: "assistant", id, content, streaming }) as AgentUiDisplayItem;

const skill = (id: string, name: string): AgentUiDisplayItem =>
  ({ kind: "skill", id, name }) as AgentUiDisplayItem;

describe("buildAgentTurns — exactly one turn is streaming", () => {
  it("marks only the last turn streaming while a request is in flight", () => {
    const turns = buildAgentTurns([user("u1", "你好"), skill("s1", "resume-coach")], true);
    expect(turns.filter((t) => t.streaming)).toHaveLength(1);
  });

  it("a finished earlier turn stays non-streaming when a new request starts", () => {
    // This is the shape that produced the duplicate: turn 1 has an answer, turn 2 has
    // only a skill event. Two streaming turns would render two waiting indicators.
    const items = [
      user("u1", "第一句"),
      assistant("a1", "第一句的回复", false),
      user("u2", "第二句"),
      skill("s2", "resume-coach"),
    ];
    const turns = buildAgentTurns(items, true);
    expect(turns).toHaveLength(2);
    expect(turns[0].streaming).toBe(false);
    expect(turns[1].streaming).toBe(true);
    expect(turns.filter((t) => t.streaming)).toHaveLength(1);
  });

  it("no turn streams once the request is no longer busy", () => {
    const items = [user("u1", "你好"), skill("s1", "resume-coach")];
    expect(buildAgentTurns(items, false).some((t) => t.streaming)).toBe(false);
  });

  it("a turn that already produced an answer is not streaming, even while busy", () => {
    // `busy` is the session's request-in-flight flag, and it can be true while the
    // newest turn already has its answer — the gap before a queued follow-up starts.
    // Treating `busy` alone as "this turn is still working" put a second waiting
    // indicator under a reply that had already arrived.
    const items = [user("u1", "你好"), assistant("a1", "已经回复完了", false)];
    const turns = buildAgentTurns(items, true);
    expect(turns[0].assistant?.content).toBe("已经回复完了");
    expect(turns[0].streaming).toBe(false);
  });

  it("an error ends the wait instead of leaving the indicator up", () => {
    // An error is an outcome. A turn that says "still thinking" underneath an error
    // message contradicts itself, which is the same class of defect as the duplicate.
    const items: AgentUiDisplayItem[] = [
      user("u1", "你好"),
      { kind: "error", id: "e1", message: "这次没能完成" } as AgentUiDisplayItem,
    ];
    const turns = buildAgentTurns(items, true);
    expect(turns.some((t) => t.streaming)).toBe(false);
  });
});

describe("buildAgentTurns — turn boundaries", () => {
  it("each user message opens a new turn", () => {
    const turns = buildAgentTurns(
      [user("u1", "a"), assistant("a1", "1", false), user("u2", "b"), assistant("a2", "2", false)],
      false,
    );
    expect(turns).toHaveLength(2);
    expect(turns[0].user?.content).toBe("a");
    expect(turns[1].user?.content).toBe("b");
  });

  it("an assistant reply attaches to the turn its user message opened", () => {
    const turns = buildAgentTurns([user("u1", "问题"), assistant("a1", "回答", false)], false);
    expect(turns).toHaveLength(1);
    expect(turns[0].user?.content).toBe("问题");
    expect(turns[0].assistant?.content).toBe("回答");
  });

  it("usage events never create or split a turn", () => {
    const turns = buildAgentTurns(
      [
        user("u1", "问"),
        { kind: "usage", id: "use1" } as AgentUiDisplayItem,
        assistant("a1", "答", false),
      ],
      false,
    );
    expect(turns).toHaveLength(1);
    expect(turns[0].assistant?.content).toBe("答");
  });
});
