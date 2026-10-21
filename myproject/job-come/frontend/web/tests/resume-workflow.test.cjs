const { test } = require("node:test");
const assert = require("node:assert/strict");
const ts = require("typescript");
const fs = require("node:fs");
const path = require("node:path");

const code = ts.transpileModule(
  fs.readFileSync(path.join(__dirname, "../lib/resume-workflow.ts"), "utf8"),
  { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } },
).outputText;
const mod = { exports: {} };
const parseCode = ts.transpileModule(
  fs.readFileSync(path.join(__dirname, "../lib/profile-parse.ts"), "utf8"),
  { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } },
).outputText;
const parseMod = { exports: {} };
new Function("exports", parseCode)(parseMod.exports);
new Function("exports", "require", code)(mod.exports, (name) => {
  assert.equal(name, "@/lib/profile-parse");
  return parseMod.exports;
});
const { profilePastUploadStep, computeWorkflowSteps } = mod.exports;

test("empty created profile is still on upload step", () => {
  const profile = {
    id: "prof_x",
    status: "draft",
    version: 1,
    payload: { contact: { name: null }, summary: null, experiences: [], education: [] },
    sources: [],
  };
  assert.equal(profilePastUploadStep(profile), false);
  const steps = computeWorkflowSteps(profile, {
    hasElevatePreview: false,
    hasExported: false,
    currentStep: "review",
  });
  assert.equal(steps.find((s) => s.id === "upload")?.active, true);
  assert.equal(steps.find((s) => s.id === "upload")?.done, false);
  assert.equal(steps.find((s) => s.id === "review")?.active, false);
});

test("a pending source alone has not finished upload step", () => {
  const profile = {
    id: "prof_y",
    status: "draft",
    version: 1,
    payload: { contact: { name: null }, summary: null, experiences: [], education: [] },
    sources: [{ id: "s1", file_name: "a.pdf", storage_key: "k", parse_status: "pending" }],
  };
  assert.equal(profilePastUploadStep(profile), false);
});

for (const status of ["pending", "processing"]) {
  test(`source ${status} stays on upload and locks later steps`, () => {
    const profile = { status: "confirmed", sources: [{ parse_status: status }], payload: {} };
    const steps = computeWorkflowSteps(profile, {
      hasElevatePreview: true, hasExported: false, currentStep: "export", uploadComplete: true,
    });
    assert.equal(steps.find(s => s.id === "upload").active, true);
    assert.equal(steps.find(s => s.id === "upload").done, false);
    for (const id of ["review", "elevate", "export"]) {
      assert.equal(steps.find(s => s.id === id).disabled, true);
    }
  });
}
test("progress distinguishes local extraction from scan recognition", () => {
  const { parseProgressState } = parseMod.exports;
  assert.match(parseProgressState("inspect_document").currentLabel, /判断/);
  assert.match(parseProgressState("extract_markdown").currentLabel, /本地/);
  assert.match(parseProgressState("llm_vision_pdf").currentLabel, /扫描/);
});

test("parsing studio renders only upload progress, not old facts or preview panels", () => {
  const React = require("react");
  const { renderToStaticMarkup } = require("react-dom/server");
  const studioCode = ts.transpileModule(
    fs.readFileSync(path.join(__dirname, "../components/resume/ResumeStudio.tsx"), "utf8"),
    { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
                         jsx: ts.JsxEmit.ReactJSX } },
  ).outputText;
  const studio = { exports: {} };
  new Function("exports", "require", studioCode)(studio.exports, (name) => {
    if (name === "react" || name === "react/jsx-runtime") return require(name);
    if (name === "@/lib/profile-parse") return parseMod.exports;
    if (name === "@/lib/hooks/useResumeQualityReview") return {
      useResumeQualityReview: (target) => { assert.equal(target.canReview, false); return {}; },
    };
    if (name === "@/components/profile/ProfileUploader") {
      return { ProfileUploader: () => React.createElement("div", null, "上传解析进行中") };
    }
    // Rendering any other panel while parsing is a regression.
    return new Proxy({}, { get: () => () => { throw new Error(`stale panel rendered: ${name}`); } });
  });
  for (const activeStep of ["review", "elevate", "export"]) {
    const html = renderToStaticMarkup(React.createElement(studio.exports.ResumeStudio, {
      profile: { sources: [{ parse_status: "processing" }] },
      isConfirmed: true, activeStep, canExport: true, generateTick: 0,
      onProfileChange: () => {},
    }));
    assert.match(html, /上传解析进行中/);
    assert.doesNotMatch(html, /档案已确认|当前：核对确认/);
  }
});

for (const status of ["draft", "confirmed"]) {
  test(`failed upload with empty ${status} profile cannot confirm or preview`, () => {
    const profile = { status, sources: [{ parse_status: "failed" }], payload: {} };
    const steps = computeWorkflowSteps(profile, {
      uploadComplete: true, currentStep: "elevate", hasElevatePreview: true, hasExported: true,
    });
    assert.equal(steps.find(s => s.id === "upload").active, true);
    for (const id of ["review", "elevate", "export"]) {
      assert.equal(steps.find(s => s.id === id).disabled, true);
      assert.equal(steps.find(s => s.id === id).done, false);
    }
  });
}

test("failed replacement preserves access to the old populated profile", () => {
  const profile = { status: "confirmed", sources: [{ parse_status: "failed" }],
    payload: { contact: { name: "原有姓名" }, experiences: [{ company: "原有公司" }] } };
  assert.equal(parseMod.exports.isProfileParseBlocking(profile), false);
  assert.equal(profilePastUploadStep(profile), true);
  const steps = computeWorkflowSteps(profile, {
    currentStep: "review", hasElevatePreview: false, hasExported: false,
  });
  assert.equal(steps.find(s => s.id === "review").disabled, false);
});

test("failed first upload studio renders upload recovery only", () => {
  const React = require("react");
  const { renderToStaticMarkup } = require("react-dom/server");
  const compiled = ts.transpileModule(
    fs.readFileSync(path.join(__dirname, "../components/resume/ResumeStudio.tsx"), "utf8"),
    { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX } },
  ).outputText;
  const studio = { exports: {} };
  new Function("exports", "require", compiled)(studio.exports, (name) => {
    if (name === "react" || name === "react/jsx-runtime") return require(name);
    if (name === "@/lib/profile-parse") return parseMod.exports;
    if (name === "@/lib/hooks/useResumeQualityReview") return {
      useResumeQualityReview: (target) => { assert.equal(target.canReview, false); return {}; },
    };
    if (name === "@/components/profile/ProfileUploader") {
      return { ProfileUploader: () => React.createElement("div", null, "解析失败恢复入口") };
    }
    return new Proxy({}, { get: () => () => { throw new Error(`unexpected panel: ${name}`); } });
  });
  const html = renderToStaticMarkup(React.createElement(studio.exports.ResumeStudio, {
    profile: { sources: [{ parse_status: "failed" }], payload: {} },
    isConfirmed: false, activeStep: "review", canExport: false, generateTick: 0,
    onProfileChange: () => {},
  }));
  assert.match(html, /解析失败恢复入口/);
  assert.doesNotMatch(html, /核对确认|档案已确认/);
});

test("failed upload card exposes the actual safe error and preserved-profile notice", () => {
  const React = require("react");
  const { renderToStaticMarkup } = require("react-dom/server");
  const compiled = ts.transpileModule(
    fs.readFileSync(path.join(__dirname, "../components/profile/ProfileUploader.tsx"), "utf8"),
    { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
      jsx: ts.JsxEmit.ReactJSX } },
  ).outputText;
  const uploader = { exports: {} };
  new Function("exports", "require", compiled)(uploader.exports, (name) => {
    if (name === "react" || name === "react/jsx-runtime") return require(name);
    if (name === "@/lib/profile-parse") return parseMod.exports;
    if (name === "@/lib/hooks/useResumeQualityReview") return {
      useResumeQualityReview: (target) => { assert.equal(target.canReview, false); return {}; },
    };
    return {};
  });
  for (const hasOldFacts of [false, true]) {
    const html = renderToStaticMarkup(React.createElement(uploader.exports.ProfileUploader, {
      hasProfile: true, onUploaded: () => {},
      profile: { sources: [{ parse_status: "failed", parse_error: "模型服务响应超时" }],
        payload: hasOldFacts ? { contact: { name: "原有姓名" } } : {} },
    }));
    assert.match(html, /简历解析未完成/);
    assert.match(html, /模型服务响应超时/);
    assert.match(html, hasOldFacts ? /原有档案未被覆盖/ : /没有生成可确认的档案/);
  }
});
