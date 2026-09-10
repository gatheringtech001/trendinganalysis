import React, { useEffect, useRef, useState } from "react";
import DigitalHumanWardrobe from "./DigitalHumanWardrobe";
import { ACCESSORIES, DEFAULT_LOOK, JOINTS, OUTFITS, POSES, SCENES } from "./digitalHuman.js";
import { createStudio } from "./digitalHumanRenderer.js";
import "./digitalHuman.css";

function Choices({ options, value, onChange, label }) {
  return <div className="dh-choices" role="group" aria-label={label}>
    {Object.entries(options).map(([key, text]) => <button key={key} aria-pressed={value === key} onClick={() => onChange(key)}>{text}</button>)}
  </div>;
}

function Range({ label, value, min, max, onChange }) {
  return <label className="dh-range"><span>{label}<output>{value}°</output></span>
    <input type="range" aria-label={label} min={min} max={max} value={value} onChange={(event) => onChange(Number(event.target.value))} />
  </label>;
}

function useStudio(look) {
  const host = useRef(null);
  const studio = useRef(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const fail = (reason) => {
      if (active) { setError(reason.message); setStatus("error"); }
    };
    try {
      studio.current = createStudio(host.current, fail);
      studio.current.ready.then(() => { if (active) setStatus("ready"); }).catch(fail);
    } catch (reason) { fail(reason); }
    return () => { active = false; studio.current?.dispose(); studio.current = null; };
  }, []);
  useEffect(() => { if (status === "ready") studio.current?.update(look); }, [look, status]);
  return { host, studio, status, error };
}

export default function DigitalHuman({ store }) {
  const [look, setLook] = useState(() => ({ ...DEFAULT_LOOK }));
  const [product, setProduct] = useState(null);
  const [notice, setNotice] = useState("");
  const [exporting, setExporting] = useState(false);
  const { host, studio, status, error } = useStudio(look);
  const change = (key, value) => setLook((current) => ({ ...current, [key]: value }));
  useEffect(() => { setProduct(null); setNotice(""); }, [store]);
  const selectProduct = (value, outfit) => {
    setProduct(value);
    if (outfit) change("outfit", outfit);
    setNotice(outfit ? `已关联商品，使用${OUTFITS[outfit]}示意模板；未重建该商品的真实版型或印花。` : "已关联商品参考；该商品没有对应 3D 模板，服装保持当前选择。");
  };
  const toggleAccessory = (value) => setLook((current) => ({ ...current,
    accessories: current.accessories.includes(value) ? current.accessories.filter((key) => key !== value) : [...current.accessories, value],
  }));
  const exportLook = async (type) => {
    setExporting(true);
    setNotice("");
    try {
      if (type === "image") await studio.current.exportImage();
      else await studio.current.exportScene(look, product);
      setNotice(type === "image" ? "搭配图片已导出。" : "GLB 已导出，可在 Blender 中通过「文件 → 导入 → glTF 2.0」继续编辑。光照效果可能因渲染器而异。");
    } catch (reason) { setNotice(`导出失败：${reason.message}`); }
    finally { setExporting(false); }
  };
  const ready = status === "ready";
  return <div className="dh-studio">
    <div className="dh-intro"><div><span className="dh-eyebrow">FASHION SCOPE / VIRTUAL STUDIO</span>
      <h2>让搭配进入三维空间<span>花花 · 骨骼数字人</span></h2>
      <p>沿用三花项目中的角色形象，探索服装、场景与模特姿态。</p></div>
      <a href={`${import.meta.env.BASE_URL}digital-human/mannequin.blend`} download>下载 Blender 源模型 ↗</a>
    </div>
    <div className="dh-workspace">
      <aside className="dh-panel dh-wardrobe">
        <div className="dh-section-title"><h3>01 / 造型衣橱</h3><span>原款 / 示意款</span></div>
        <Choices label="服装模板" options={OUTFITS} value={look.outfit} onChange={(value) => change("outfit", value)} />
        <div className="dh-colors"><label>主服装色<input aria-label="主服装色" type="color" value={look.color} onChange={(event) => change("color", event.target.value)} /></label>
          {look.outfit !== "dress" && <label>下装颜色<input aria-label="下装颜色" type="color" value={look.bottomColor} onChange={(event) => change("bottomColor", event.target.value)} /></label>}</div>
        <DigitalHumanWardrobe key={store} store={store} selected={product ? `${product.store_id}:${product.product_id}` : ""} onSelect={selectProduct} />
      </aside>
      <section className="dh-viewport" aria-label="数字人场景预览">
        <div className="dh-viewport-top"><span><i /> {SCENES[look.scene]}</span><span>实时 3D</span></div>
        <div ref={host} className="dh-canvas" data-status={status} />
        {status === "loading" && <div className="dh-canvas-message" role="status">正在载入 Blender 数字人…</div>}
        {error && <div className="dh-canvas-message dh-error" role="alert">无法加载 3D 画布：{error}</div>}
        <div className="dh-canvas-caption"><strong>{OUTFITS[look.outfit]}</strong><span>{look.pose === "custom" ? "自定义姿势" : POSES[look.pose].label} / {look.accessories.length} 件配饰</span></div>
        <div className="dh-viewport-bottom"><span>拖动旋转 · 滚轮缩放 · 右键平移</span><button disabled={!ready} onClick={() => studio.current.resetCamera()}>重置视角</button></div>
      </section>
      <aside className="dh-panel dh-controls">
        <section><div className="dh-section-title"><h3>02 / 拍摄场景</h3><span>ENVIRONMENT</span></div>
          <Choices label="拍摄场景" options={SCENES} value={look.scene} onChange={(value) => change("scene", value)} /></section>
        <section><div className="dh-section-title"><h3>03 / 配饰搭配</h3><span>ACCESSORIES</span></div>
          <div className="dh-accessories">{Object.entries(ACCESSORIES).map(([key, text]) => <label key={key}><input type="checkbox" checked={look.accessories.includes(key)} onChange={() => toggleAccessory(key)} />{text}</label>)}</div></section>
        <section><div className="dh-section-title"><h3>04 / 模特姿势</h3><span>POSE</span></div>
          <Choices label="模特姿势" options={Object.fromEntries(Object.entries(POSES).map(([key, pose]) => [key, pose.label]))} value={look.pose}
            onChange={(value) => setLook((current) => ({ ...current, pose: value, ...POSES[value].values }))} />
          <Range label="模特朝向" min={-180} max={180} value={look.turn} onChange={(value) => change("turn", value)} />
          <details className="dh-joints"><summary>精调关节</summary>{Object.entries(JOINTS).map(([key, joint]) => <Range key={key} {...joint} value={look[key]}
            onChange={(value) => setLook((current) => ({ ...current, pose: "custom", [key]: value }))} />)}</details>
        </section>
        <div className="dh-export"><button className="primary-button" disabled={!ready || exporting} onClick={() => exportLook("image")}>{exporting ? "正在导出…" : "导出搭配图片"}</button>
          <button disabled={!ready || exporting} onClick={() => exportLook("glb")}>导出 3D 场景 · GLB</button></div>
      </aside>
    </div>
    <div className="dh-reference"><span>当前商品参考</span><strong>{product?.title || "未选择 · 可从左侧店铺灵感库关联商品"}</strong>{product && <button onClick={() => { setProduct(null); setNotice(""); }}>清除关联</button>}</div>
    {notice && <p role="status" className="dh-notice">{notice}</p>}
    <p className="dh-boundary">角色来自你在三花项目中提供的 Hi3D 卡通商务女性，保留原贴图与 20 骨骼蒙皮；商务套装为原款，长裙为新建示意款。原款调色叠加于原贴图。店铺商品仅作参考，尚未完成商品服装重建、布料仿真与碰撞检测，部分姿势可能穿模。</p>
  </div>;
}
