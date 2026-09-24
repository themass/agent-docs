import { deepSpaceById, deepSpacePois } from "../data/deepSpacePois";
import { bodies, bodyById, primaryBodies } from "../data/solarSystem";
import { useSpaceStore } from "../state/useSpaceStore";
import { formatDistanceAu } from "../solar/scale";
import type { ScaleMode } from "../types";
import { MissionHud } from "./MissionHud";

function BodyDetails({ id }: { id: string }) {
  const body = bodyById.get(id);
  if (!body) return null;
  const moons = body.moons?.map((moonId) => bodyById.get(moonId)?.name).filter(Boolean);

  return (
    <section className="target-card">
      <p className="eyebrow">{body.kind === "dwarf-planet" ? "矮行星 / 经典第九行星" : body.kind}</p>
      <h2>{body.name}</h2>
      <p className="english-name">{body.englishName}</p>
      <div className="metric-grid">
        <div>
          <span>半径</span>
          <strong>{body.radiusKm.toLocaleString()} km</strong>
        </div>
        <div>
          <span>轨道半径</span>
          <strong>{formatDistanceAu(body.orbitRadiusAu)}</strong>
        </div>
        <div>
          <span>轨道周期</span>
          <strong>{Math.abs(body.orbitPeriodDays).toLocaleString()} d</strong>
        </div>
        <div>
          <span>自转周期</span>
          <strong>{Math.abs(body.rotationPeriodHours).toLocaleString()} h</strong>
        </div>
      </div>
      {body.id === "pluto" && (
        <p className="truth-note">
          界面保留“经典九大行星”的用户心智；科学分类中冥王星是 dwarf planet。
        </p>
      )}
      <ul className="fact-list">
        {body.facts.map((fact) => (
          <li key={fact}>{fact}</li>
        ))}
      </ul>
      {moons && moons.length > 0 && (
        <p className="moon-list">
          主要卫星：<strong>{moons.join(" · ")}</strong>
        </p>
      )}
      <p className="visual-note">{body.texturePlan}</p>
      <h3>数据来源</h3>
      {body.sources.map((source) => (
        <a key={source.url} className="source-link" href={source.url} target="_blank" rel="noreferrer">
          {source.name} <span>{source.note}</span>
        </a>
      ))}
    </section>
  );
}

function DeepSpaceDetails({ id }: { id: string }) {
  const poi = deepSpaceById.get(id);
  if (!poi) return null;
  return (
    <section className="target-card">
      <p className="eyebrow">{poi.sourceMission}</p>
      <h2>{poi.name}</h2>
      <p className="english-name">{poi.englishName}</p>
      <div className="metric-grid">
        <div>
          <span>类型</span>
          <strong>{poi.kind}</strong>
        </div>
        <div>
          <span>距离</span>
          <strong>{poi.distance}</strong>
        </div>
      </div>
      <p className="coordinates">{poi.coordinates}</p>
      <p>{poi.whyItMatters}</p>
      <h3>观测事实</h3>
      <ul className="fact-list">
        {poi.observationFacts.map((fact) => (
          <li key={fact}>{fact}</li>
        ))}
      </ul>
      <h3>可视化增强</h3>
      <ul className="fact-list warning">
        {poi.artisticEnhancements.map((fact) => (
          <li key={fact}>{fact}</li>
        ))}
      </ul>
      <p className="visual-note">{poi.visualizationPlan}</p>
      <h3>数据来源</h3>
      {poi.archive.map((source) => (
        <a key={source.url + source.name} className="source-link" href={source.url} target="_blank" rel="noreferrer">
          {source.name} <span>{source.note}</span>
        </a>
      ))}
    </section>
  );
}

export function TargetPanel() {
  const selectedTarget = useSpaceStore((state) => state.selectedTarget);
  const selectTarget = useSpaceStore((state) => state.selectTarget);
  const setScaleMode = useSpaceStore((state) => state.setScaleMode);
  const scaleMode = useSpaceStore((state) => state.scaleMode);
  const simulationDay = useSpaceStore((state) => state.simulationDay);
  const setSimulationDay = useSpaceStore((state) => state.setSimulationDay);

  return (
    <aside className="side-panel">
      <header>
        <p className="eyebrow">DeepSpace Field v0.1</p>
        <h1>真实太阳系科学地图</h1>
        <p>
          主场是太阳系：经典九大行星、主要卫星、真实/压缩尺度，以及
          Hubble/Webb 旗舰深空目标。
        </p>
      </header>

      <section className="controls-card">
        <label>
          尺度模式
          <select value={scaleMode} onChange={(event) => setScaleMode(event.target.value as ScaleMode)}>
            <option value="compressed">教学压缩</option>
            <option value="cinematic">电影飞行</option>
            <option value="real">真实比例</option>
          </select>
        </label>
        <label>
          模拟日期偏移（天）
          <input
            type="range"
            min={0}
            max={3650}
            step={1}
            value={simulationDay}
            onChange={(event) => setSimulationDay(Number(event.target.value))}
          />
          <span>{simulationDay} d</span>
        </label>
      </section>

      <section className="catalog-section">
        <h3>太阳系</h3>
        <div className="target-list">
          {primaryBodies.map((body) => (
            <button
              key={body.id}
              className={selectedTarget.type === "body" && selectedTarget.id === body.id ? "active" : ""}
              onClick={() => selectTarget({ type: "body", id: body.id })}
            >
              <span style={{ background: body.color }} />
              {body.name}
            </button>
          ))}
        </div>
      </section>

      <section className="catalog-section">
        <h3>主要卫星</h3>
        <div className="target-list compact">
          {bodies
            .filter((body) => body.kind === "moon")
            .map((body) => (
              <button
                key={body.id}
                className={selectedTarget.type === "body" && selectedTarget.id === body.id ? "active" : ""}
                onClick={() => selectTarget({ type: "body", id: body.id })}
              >
                <span style={{ background: body.color }} />
                {body.name}
              </button>
            ))}
        </div>
      </section>

      <section className="catalog-section">
        <h3>5 个深空旗舰 POI</h3>
        <div className="target-list">
          {deepSpacePois.map((poi) => (
            <button
              key={poi.id}
              className={selectedTarget.type === "deep-space" && selectedTarget.id === poi.id ? "active" : ""}
              onClick={() => selectTarget({ type: "deep-space", id: poi.id })}
            >
              <span style={{ background: poi.color }} />
              {poi.name}
            </button>
          ))}
        </div>
      </section>
    </aside>
  );
}

export function SciencePanel() {
  const selectedTarget = useSpaceStore((state) => state.selectedTarget);
  const showSciencePanel = useSpaceStore((state) => state.showSciencePanel);
  if (!showSciencePanel) return null;
  return (
    <aside className="science-panel">
      <div className="science-panel-content">
        {selectedTarget.type === "body" ? (
          <BodyDetails id={selectedTarget.id} />
        ) : (
          <DeepSpaceDetails id={selectedTarget.id} />
        )}
      </div>
      <MissionHud />
    </aside>
  );
}
