import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";

import {
  DirectUploadUnavailable,
  dataUrlToBlob,
  directUpload,
  hasFailedUpload,
  refreshLiveUploads,
  sceneForMime,
  toWireAttachment,
  tryDirectUpload,
  PROFILE_SOURCE_TYPES,
} from "@/lib/media-upload";
import type { AgentAttachment } from "@/lib/types/agent";

/**
 * Two-sided, like every gate in this project: each direct-upload path asserts
 * the success AND the failure that must degrade to `data_url` next to it.
 * A direct-upload client that only proves "the key came back" proves nothing
 * about the case that actually decides user pain — CORS unconfigured, sign
 * 503, offline — where the turn must still go out the old channel.
 *
 * Node environment, no DOM: fetch is stubbed, `atob`/`Blob` are node globals.
 */

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json" },
  });
}

const SIGN_BODY = {
  objectKey: "jc/dev/uploads/usr_a/chat-image/2026/11/18/k22charsxxxxxxxx.jpg",
  upload: {
    method: "PUT",
    url: "https://bucket.test/key?sig=SECRET",
    headers: { "Content-Type": "image/jpeg" },
  },
  limits: { maxBytes: 8 * 1024 * 1024 },
};

const fetchMock = vi.fn();

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("sceneForMime", () => {
  test("accepts whitelisted image and audio types", () => {
    expect(sceneForMime("image/jpeg")).toBe("chat-image");
    expect(sceneForMime("image/webp")).toBe("chat-image");
    expect(sceneForMime("audio/webm;codecs=opus")).toBe("chat-audio");
  });
  test("rejects svg and anything outside the two scenes", () => {
    // svg is the P1-2 shape: an `image/` prefix is not an image scene.
    expect(sceneForMime("image/svg+xml")).toBeNull();
    expect(sceneForMime("application/pdf")).toBeNull();
    expect(sceneForMime(null)).toBeNull();
    expect(sceneForMime(undefined)).toBeNull();
  });
});

describe("directUpload", () => {
  test("signs then PUTs with the signed headers verbatim, returns the key", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(SIGN_BODY))
      .mockResolvedValueOnce(new Response("", { status: 200 }));
    const blob = new Blob([new Uint8Array(1000)], { type: "image/jpeg" });

    const key = await directUpload("chat-image", blob, "image/jpeg");
    expect(key).toBe(SIGN_BODY.objectKey);

    const [signCall, putCall] = fetchMock.mock.calls;
    expect(signCall[0]).toBe("/api/v1/media/sign");
    expect(JSON.parse(String(signCall[1]?.body))).toEqual({
      scene: "chat-image",
      contentType: "image/jpeg",
      sizeBytes: 1000,
    });
    expect(putCall[0]).toBe(SIGN_BODY.upload.url);
    expect(putCall[1]?.method).toBe("PUT");
    // Content-Type is inside the signature: the headers must pass verbatim.
    expect(putCall[1]?.headers).toEqual(SIGN_BODY.upload.headers);
    expect(putCall[1]?.body).toBe(blob);
    // The presigned URL is a bearer secret: the returned value is the key only.
    expect(key).not.toContain("sig=");
  });

  test("a rejected sign raises DirectUploadUnavailable, not a raw ApiError", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ code: "size_over_limit" }, 400));
    await expect(
      directUpload("chat-image", new Blob(["x"], { type: "image/jpeg" }), "image/jpeg"),
    ).rejects.toBeInstanceOf(DirectUploadUnavailable);
    expect(fetchMock).toHaveBeenCalledTimes(1); // never PUTs without a signature
  });

  test("a failed or thrown PUT raises DirectUploadUnavailable", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(SIGN_BODY))
      .mockResolvedValueOnce(new Response("forbidden", { status: 403 }));
    await expect(
      directUpload("chat-image", new Blob(["x"], { type: "image/jpeg" }), "image/jpeg"),
    ).rejects.toBeInstanceOf(DirectUploadUnavailable);

    fetchMock.mockReset();
    fetchMock
      .mockResolvedValueOnce(jsonResponse(SIGN_BODY))
      .mockRejectedValueOnce(new Error("CORS"));
    await expect(
      directUpload("chat-image", new Blob(["x"], { type: "image/jpeg" }), "image/jpeg"),
    ).rejects.toBeInstanceOf(DirectUploadUnavailable);
  });
});

describe("tryDirectUpload", () => {
  test("returns null for a non-whitelisted mime WITHOUT touching the network", async () => {
    const svg = new Blob(["<svg/>"], { type: "image/svg+xml" });
    expect(await tryDirectUpload(svg, "image/svg+xml")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("returns null when the direct channel is down (sign 503) — degrade to data_url", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ code: "direct_upload_disabled" }, 503));
    expect(await tryDirectUpload(new Blob(["x"], { type: "image/jpeg" }), "image/jpeg")).toBeNull();
  });

  test("returns the key on the happy path", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(SIGN_BODY))
      .mockResolvedValueOnce(new Response("", { status: 200 }));
    const key = await tryDirectUpload(new Blob(["x"], { type: "image/jpeg" }), "image/jpeg");
    expect(key).toBe(SIGN_BODY.objectKey);
  });
});

describe("dataUrlToBlob", () => {
  test("decodes a real PNG header", async () => {
    const blob = dataUrlToBlob("data:image/png;base64,iVBORw0KGgo=");
    expect(blob).not.toBeNull();
    expect(blob!.type).toBe("image/png");
    const buf = await blob!.arrayBuffer();
    expect(new Uint8Array(buf)).toEqual(
      new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    );
  });
  test("returns null on malformed input instead of throwing", () => {
    expect(dataUrlToBlob("not-a-data-url")).toBeNull();
    expect(dataUrlToBlob("data:image/jpeg;charset=utf-8,no-base64-flag")).toBeNull();
    expect(dataUrlToBlob("no-comma-at-all")).toBeNull();
  });
});

describe("toWireAttachment", () => {
  const base: AgentAttachment = {
    kind: "image",
    name: "p.jpg",
    mime_type: "image/jpeg",
    data_url: "data:image/jpeg;base64,AAAA",
  };
  test("with a key: only the key travels — no data_url, no signed URL", () => {
    const wire = toWireAttachment({ ...base, object_key: "jc/dev/uploads/usr_a/x.jpg" });
    expect(wire.object_key).toBe("jc/dev/uploads/usr_a/x.jpg");
    // The schema 422s on both channels at once; the wire projection cannot.
    expect("data_url" in wire).toBe(false);
  });
  test("without a key: byte-for-byte the same object (the old channel unchanged)", () => {
    expect(toWireAttachment(base)).toBe(base);
  });
});

describe("refreshLiveUploads", () => {
  const image: AgentAttachment = {
    kind: "image",
    name: "p.jpg",
    mime_type: "image/jpeg",
    data_url: "data:image/jpeg;base64,/9j/4AAQSkZJRg==",
  };

  test("mints a fresh key per uploadable item and KEEPS data_url for retry", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(SIGN_BODY))
      .mockResolvedValueOnce(new Response("", { status: 200 }));
    const [out] = await refreshLiveUploads([image]);
    expect(out!.object_key).toBe(SIGN_BODY.objectKey);
    // The preview/retry source survives the key — this is what makes the
    // retry path (fresh key per attempt) possible at all.
    expect(out!.data_url).toBe(image.data_url);
  });

  test("an item that fails to upload keeps data_url and gets NO key (degrades)", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ code: "rate_limited" }, 429));
    const [out] = await refreshLiveUploads([image]);
    expect(out!.object_key ?? null).toBeNull();
    expect(out!.data_url).toBe(image.data_url);
  });

  test("file attachments and history stubs never touch the network", async () => {
    const file: AgentAttachment = { kind: "file", name: "a.pdf", text_preview: "x" };
    // A replayed history row: server-side keys, no staged bytes.
    const history: AgentAttachment = {
      kind: "image",
      name: "old.jpg",
      download_url: "https://cdn/x",
    };
    const out = await refreshLiveUploads([file, history]);
    expect(out[0]).toBe(file);
    expect(out[1]).toBe(history);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  test("each item in one message gets its own sign call (keys are not shared)", async () => {
    // Uploads run CONCURRENTLY (Promise.all), so both signs are issued before
    // any PUT resolves: the mock dispatches by URL and mints a distinct key
    // per sign call, rather than assuming a per-item sequence.
    const second: AgentAttachment = { ...image, name: "q.jpg" };
    let signs = 0;
    fetchMock.mockImplementation((url: unknown, init?: RequestInit) => {
      if (String(url).endsWith("/media/sign")) {
        signs += 1;
        return Promise.resolve(
          jsonResponse({
            ...SIGN_BODY,
            objectKey: `${SIGN_BODY.objectKey}#${signs}`,
          }),
        );
      }
      return Promise.resolve(new Response("", { status: 200 }));
    });
    const out = await refreshLiveUploads([image, second]);
    expect(out[0]!.object_key).toContain("#");
    expect(out[1]!.object_key).toContain("#");
    expect(out[0]!.object_key).not.toBe(out[1]!.object_key);
    expect(fetchMock).toHaveBeenCalledTimes(4); // two signs + two PUTs
  });
});


describe("PROFILE_SOURCE_TYPES (ADR-011 §6-D resume uploads)", () => {
  test("accepts photo resumes and documents, both sides of the whitelist", () => {
    expect(PROFILE_SOURCE_TYPES.has("application/pdf")).toBe(true);
    expect(PROFILE_SOURCE_TYPES.has("image/jpeg")).toBe(true);
    expect(
      PROFILE_SOURCE_TYPES.has(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      ),
    ).toBe(true);
  });
  test("excludes svg and audio: a resume is neither a voice clip nor markup", () => {
    expect(PROFILE_SOURCE_TYPES.has("image/svg+xml")).toBe(false);
    expect(PROFILE_SOURCE_TYPES.has("audio/webm")).toBe(false);
  });
});

describe("directUpload with the profile-source scene", () => {
  test("signs the scene verbatim and PUTs a PDF, returning only the key", async () => {
    const pdf = new Blob(["%PDF-1.4 test bytes"], { type: "application/pdf" });
    fetchMock.mockImplementation(async (url: string, init?: RequestInit) => {
      if (url.endsWith("/media/sign")) {
        const body = JSON.parse(String(init?.body));
        expect(body.scene).toBe("profile-source");
        expect(body.contentType).toBe("application/pdf");
        return jsonResponse({
          objectKey: "jc/prod/uploads/usr_a/profile-source/2026/11/18/k22charsxxxxxxxx.pdf",
          upload: {
            method: "PUT",
            url: "https://bucket.test/key?sig=SECRET",
            headers: { "Content-Type": "application/pdf" },
          },
          limits: { maxBytes: 15 * 1024 * 1024 },
        });
      }
      // the PUT itself
      expect(init?.method).toBe("PUT");
      return new Response(null, { status: 200 });
    });
    const key = await directUpload("profile-source", pdf, "application/pdf");
    expect(key).toBe("jc/prod/uploads/usr_a/profile-source/2026/11/18/k22charsxxxxxxxx.pdf");
    expect(key).not.toContain("sig="); // the bearer secret never rides onward
  });

  test("a refused sign on a profile upload still throws the typed degrade error", async () => {
    fetchMock.mockImplementation(async (url: string) => {
      if (url.endsWith("/media/sign")) {
        return jsonResponse({ code: "direct_upload_disabled", message: "关闭" }, 503);
      }
      throw new Error("must not PUT after a failed sign");
    });
    await expect(
      directUpload("profile-source", new Blob(["x"], { type: "application/pdf" }), "application/pdf"),
    ).rejects.toBeInstanceOf(DirectUploadUnavailable);
    // exactly one network call happened: the failed sign, no PUT
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});

// ---- R2 P1-3 (E5/E6): two upload failures wearing the same message. ----
// E6 = TOS unreachable from the start (sign never handed out a URL): the
// sanctioned observation-period degradation, send inline, no marker.
// E5 = the PUT was attempted and died: mark it, block the send, never relay
// half-written bytes as a "normal" image.
describe("R2 E5/E6 split in refreshLiveUploads", () => {
  const image: AgentAttachment = {
    kind: "image",
    name: "p.jpg",
    mime_type: "image/jpeg",
    data_url: "data:image/jpeg;base64,/9j/4AAQSkZJRg==",
  };

  test("E6: sign-leg failure keeps data_url, NO key, NO marker — relay stays legal", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ code: "direct_upload_disabled" }, 503));
    const [out] = await refreshLiveUploads([image]);
    expect(out!.object_key ?? null).toBeNull();
    // The absence of the marker is the whole seam: no marker means the
    // sanctioned inline relay, and the send gate must NOT fire on it.
    expect(out!.upload_failed ?? false).toBe(false);
    expect(out!.data_url).toBe(image.data_url);
  });

  test("E5 thrown PUT: upload_failed=true, NO key, data_url kept for retry", async () => {
    // sign 200 (TOS was reachable) → fetch itself dies mid-transfer.
    fetchMock
      .mockResolvedValueOnce(jsonResponse(SIGN_BODY))
      .mockRejectedValueOnce(new Error("net::ERR_INTERNET_DISCONNECTED"));
    const [out] = await refreshLiveUploads([image]);
    expect(out!.upload_failed).toBe(true);
    expect(out!.object_key ?? null).toBeNull();
    // The bytes R2 saw relay as a normal image now carry the marker the
    // send gate keys on.
    expect(out!.data_url).toBe(image.data_url);
  });

  test("a successful re-upload CLEARS the marker — the gate cannot outlive the failure", async () => {
    // Retry sends the same staged bytes with a fresh key. If success only
    // added the key without clearing the old marker, an upload that just
    // healed would stay blocked forever: the gate becomes a second defect.
    const failed: AgentAttachment = { ...image, upload_failed: true };
    fetchMock
      .mockResolvedValueOnce(jsonResponse(SIGN_BODY))
      .mockResolvedValueOnce(new Response("", { status: 200 }));
    const [out] = await refreshLiveUploads([failed]);
    expect(out!.object_key).toBe(SIGN_BODY.objectKey);
    expect(out!.upload_failed).toBe(false);
  });
});

describe("hasFailedUpload — the composer's send gate", () => {
  const staged: AgentAttachment = {
    kind: "image",
    name: "p.jpg",
    mime_type: "image/jpeg",
    data_url: "data:image/jpeg;base64,/9j/4AAQSkZJRg==",
  };
  test("false on clean uploads — the gate must not eat legitimate sends", () => {
    expect(hasFailedUpload([])).toBe(false);
    expect(hasFailedUpload([{ ...staged, object_key: "jc/dev/x.jpg" }])).toBe(false);
    // E6 shape: no key, no marker — inline relay stays allowed during the
    // observation window (ADR-011 E step).
    expect(hasFailedUpload([staged])).toBe(false);
  });
  test("true on one marked item among clean ones", () => {
    const ok: AgentAttachment = { ...staged, object_key: "jc/dev/ok.jpg", upload_failed: false };
    expect(hasFailedUpload([ok, { ...staged, upload_failed: true }])).toBe(true);
  });});

describe("DirectUploadUnavailable.attemptStarted", () => {
  test("sign-leg failures are NOT attemptStarted (E6 side)", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse({ code: "rate_limited" }, 429));
    const error = await directUpload(
      "chat-image",
      new Blob(["x"], { type: "image/jpeg" }),
      "image/jpeg",
    ).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(DirectUploadUnavailable);
    expect((error as DirectUploadUnavailable).attemptStarted).toBe(false);
  });
  test("PUT-leg failures ARE attemptStarted (E5 side); the signed URL never leaks", async () => {
    fetchMock
      .mockResolvedValueOnce(jsonResponse(SIGN_BODY))
      .mockResolvedValueOnce(new Response("", { status: 500 }));
    const error = await directUpload(
      "chat-image",
      new Blob(["x"], { type: "image/jpeg" }),
      "image/jpeg",
    ).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(DirectUploadUnavailable);
    expect((error as DirectUploadUnavailable).attemptStarted).toBe(true);
    // ADR-011 §7.4: a presigned URL is a bearer secret; it must never ride
    // into a message the UI renders or a logger keeps.
    expect(String((error as Error).message)).not.toContain("sig=");
    expect(String((error as Error).message)).not.toContain("bucket.test");
  });
});
