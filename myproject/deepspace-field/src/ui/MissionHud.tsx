import { deepSpaceById } from "../data/deepSpacePois";
import { bodyById } from "../data/solarSystem";
import { useSpaceStore } from "../state/useSpaceStore";

export function MissionHud() {
  const selectedTarget = useSpaceStore((state) => state.selectedTarget);
  const flightState = useSpaceStore((state) => state.flightState);
  const viewMode = useSpaceStore((state) => state.viewMode);
  const focusIsolation = useSpaceStore((state) => state.focusIsolation);
  const closeUpLevel = useSpaceStore((state) => state.closeUpLevel);
  const setViewMode = useSpaceStore((state) => state.setViewMode);
  const toggleFocusIsolation = useSpaceStore((state) => state.toggleFocusIsolation);
  const requestCloseUp = useSpaceStore((state) => state.requestCloseUp);
  const toggleSciencePanel = useSpaceStore((state) => state.toggleSciencePanel);

  const target =
    selectedTarget.type === "body"
      ? bodyById.get(selectedTarget.id)
      : deepSpaceById.get(selectedTarget.id);

  const isBody = selectedTarget.type === "body";

  return (
    <section className="mission-hud">
      <div>
        <span>目标</span>
        <strong>{target?.name ?? "未选择"}</strong>
      </div>
      <div>
        <span>状态</span>
        <strong>
          {flightState === "traveling"
            ? "自动前往"
            : closeUpLevel === "surface"
              ? "近距检视"
              : "环绕观测"}
        </strong>
      </div>
      <div>
        <span>模式</span>
        <strong>{viewMode === "inspect" ? "检视（拖转天体）" : "导航（拖转视角）"}</strong>
      </div>
      <div className="hud-actions">
        <button
          className={viewMode === "navigate" ? "active" : ""}
          onClick={() => setViewMode("navigate")}
        >
          导航
        </button>
        <button
          className={viewMode === "inspect" ? "active" : ""}
          onClick={() => setViewMode("inspect")}
        >
          检视
        </button>
        <button onClick={requestCloseUp}>拉近</button>
        {isBody && (
          <button
            className={focusIsolation ? "active" : ""}
            onClick={toggleFocusIsolation}
          >
            {focusIsolation ? "目标视角" : "系统视角"}
          </button>
        )}
        <button onClick={toggleSciencePanel}>科学面板</button>
      </div>
      <span className="nav-hint">
        双击天体快速拉近 · {viewMode === "inspect" ? "拖拽旋转当前天体" : "拖拽旋转相机"} · 滚轮缩放
        {isBody && focusIsolation ? " · 已隐藏其他天体避免遮挡" : ""}
      </span>
    </section>
  );
}
