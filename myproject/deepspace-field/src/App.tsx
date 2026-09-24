import { deepSpaceById } from "./data/deepSpacePois";
import { SolarSystemScene } from "./solar/SolarSystemScene";
import { useSpaceStore } from "./state/useSpaceStore";
import { SciencePanel, TargetPanel } from "./ui/TargetPanel";
import "./styles.css";

function DeepSpaceBanner() {
  const selectedTarget = useSpaceStore((state) => state.selectedTarget);
  if (selectedTarget.type !== "deep-space") return null;
  const poi = deepSpaceById.get(selectedTarget.id);
  if (!poi) return null;
  return (
    <div className="deep-space-banner" style={{ borderColor: poi.color }}>
      <p>深空旗舰 POI</p>
      <strong>{poi.name}</strong>
      <span>
        当前 MVP 先以太阳系为主；该目标已接入真实来源元数据，Phase 2 会进入
        Hubble/Webb 观测图像飞行场景。
      </span>
    </div>
  );
}

export default function App() {
  return (
    <main className="app-shell">
      <TargetPanel />
      <section className="viewport">
        <SolarSystemScene />
        <DeepSpaceBanner />
        <div className="truth-ribbon">
          Visualization mode: real ephemeris pipeline planned · current scaffold uses simplified baked
          orbital parameters.
        </div>
      </section>
      <SciencePanel />
    </main>
  );
}
