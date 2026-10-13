// Nối form ↔ cảnh 3D. Mọi kích thước trong state là mm; three.js dùng mét.
import * as THREE from 'three';
import { createStage } from './stage.js';
import { chairModel, modelFromGlb, setColor, tableModel } from './furniture.js';
import { clampInRoom, layoutDining, outsideRoom } from './layout.js';
import { defaultWoodTexture, dominantColor, textureFromFile } from './textures.js';

const M = 0.001;
const $ = (id) => document.getElementById(id);
const num = (id) => Math.max(1, Number($(id).value) || 0);

const stage = createStage($('view'));
const state = { items: [], glb: { table: null, chair: null } }; // item: {kind, x, z, rot, obj}

const room = () => ({ w: num('room-w'), d: num('room-d'), h: num('room-h') });
const dims = (k) => ({ w: num(`${k}-w`), d: num(`${k}-d`), h: num(`${k}-h`) });

function status(text, kind = '') {
  $('status').textContent = text;
  $('status').className = `status ${kind}`;
}

function place(it) {
  it.obj.position.set(it.x * M, 0, it.z * M);
  it.obj.rotation.y = THREE.MathUtils.degToRad(it.rot);
}

async function makeModel(kind) {
  const d = dims(kind), color = $(`${kind}-color`).value;
  if (state.glb[kind]) return modelFromGlb(state.glb[kind], d);
  return kind === 'table' ? tableModel(d, color) : chairModel(d, color);
}

/** Dựng lại toàn bộ bàn ghế theo form, xếp tự động. */
async function rebuild() {
  for (const it of state.items) stage.scene.remove(it.obj);
  state.items = [];
  select(null);
  const n = Math.max(0, Math.min(12, Number($('chair-n').value) || 0));
  const lay = layoutDining(room(), dims('table'), dims('chair'), n);
  try {
    state.items.push({ kind: 'table', ...lay.table, obj: await makeModel('table') });
    for (const c of lay.chairs) state.items.push({ kind: 'chair', ...c, obj: await makeModel('chair') });
  } catch (e) {
    status(`Không đọc được file 3D: ${e.message}`, 'err');
    return;
  }
  state.items.forEach((it, i) => { it.obj.userData.index = i; place(it); stage.scene.add(it.obj); });
  report(lay.unplaced);
}

function report(unplaced = 0) {
  const r = room();
  const out = outsideRoom(r, state.items.map((it) => ({ ...it, ...dims(it.kind) })));
  const chairs = state.items.filter((i) => i.kind === 'chair').length;
  const base = `Phòng ${r.w}×${r.d} mm · 1 bàn · ${chairs} ghế`;
  if (unplaced) status(`${base} · ${unplaced} ghế không đủ chỗ quanh bàn`, 'warn');
  else if (out.length) status(`${base} · ${out.length} món lòi ra ngoài phòng — tăng kích thước phòng hoặc kéo lại`, 'warn');
  else status(base);
}

// ---------------------------------------------------------------- chọn, kéo thả, xoay
const ray = new THREE.Raycaster(), ptr = new THREE.Vector2();
const floorPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
let selected = null, drag = null;

function pick(e) {
  const r = stage.renderer.domElement.getBoundingClientRect();
  ptr.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  ray.setFromCamera(ptr, stage.camera);
}

function itemOf(obj) {
  for (let o = obj; o; o = o.parent) if (o.userData.index !== undefined) return state.items[o.userData.index];
  return null;
}

function glow(it, on) {
  it?.obj.traverse((o) => {
    if (!o.isMesh || !o.material.emissive) return;
    if (!o.userData.ownMat) { o.material = o.material.clone(); o.userData.ownMat = true; }
    o.material.emissive.set(on ? 0x1d3a7a : 0x000000);
  });
}

function select(it) {
  glow(selected, false);
  selected = it;
  glow(selected, true);
  $('sel').hidden = !it;
  if (it) $('sel-name').textContent = it.kind === 'table' ? 'Bàn' : `Ghế ${state.items.indexOf(it)}`;
}

const canvas = stage.renderer.domElement;
canvas.addEventListener('pointerdown', (e) => {
  pick(e);
  const hit = ray.intersectObjects(state.items.map((i) => i.obj), true)[0];
  const it = hit && itemOf(hit.object);
  select(it || null);
  if (!it) return;
  const p = ray.ray.intersectPlane(floorPlane, new THREE.Vector3());
  if (!p) return;
  drag = { it, dx: it.x - p.x / M, dz: it.z - p.z / M };
  stage.controls.enabled = false;
  canvas.setPointerCapture(e.pointerId);
});
canvas.addEventListener('pointermove', (e) => {
  if (!drag) return;
  pick(e);
  const p = ray.ray.intersectPlane(floorPlane, new THREE.Vector3());
  if (!p) return;
  const it = drag.it;
  const pos = clampInRoom(room(), { ...it, ...dims(it.kind), x: p.x / M + drag.dx, z: p.z / M + drag.dz });
  it.x = Math.round(pos.x / 10) * 10;
  it.z = Math.round(pos.z / 10) * 10;
  place(it);
});
const endDrag = () => { if (drag) { drag = null; stage.controls.enabled = true; report(); } };
canvas.addEventListener('pointerup', endDrag);
canvas.addEventListener('pointercancel', endDrag);

$('btn-rot').onclick = () => {
  if (!selected) return;
  selected.rot = (selected.rot + 90) % 360;
  Object.assign(selected, clampInRoom(room(), { ...selected, ...dims(selected.kind) }));
  place(selected);
  report();
};
addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') return;
  if (e.key === 'r' || e.key === 'R') $('btn-rot').click();
  if (e.key === 'Escape') select(null);
});

// ---------------------------------------------------------------- form
const debounce = (fn, ms = 250) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
const rebuildSoon = debounce(rebuild);

function applyRoom() {
  stage.setRoom(room());
  stage.setFloorTexture(null, { w: num('tile-w'), l: num('tile-l') });
}

for (const id of ['room-w', 'room-d', 'room-h']) $(id).addEventListener('input', debounce(() => { applyRoom(); stage.frame(); rebuild(); }));
for (const id of ['tile-w', 'tile-l']) $(id).addEventListener('input', () => stage.setFloorTexture(null, { w: num('tile-w'), l: num('tile-l') }));
for (const k of ['table', 'chair']) for (const s of ['w', 'd', 'h']) $(`${k}-${s}`).addEventListener('input', rebuildSoon);
$('chair-n').addEventListener('input', rebuildSoon);
$('wall-color').addEventListener('input', (e) => stage.setWallColor(e.target.value));

for (const k of ['table', 'chair']) {
  $(`${k}-color`).addEventListener('input', (e) => {
    for (const it of state.items) if (it.kind === k) setColor(it.obj, e.target.value);
  });
  $(`${k}-img`).addEventListener('change', async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    $(`${k}-color`).value = await dominantColor(f);
    $(`${k}-color`).dispatchEvent(new Event('input'));
  });
  $(`${k}-glb`).addEventListener('change', (e) => { state.glb[k] = e.target.files[0] || null; rebuild(); });
}

$('floor-img').addEventListener('change', async (e) => {
  const f = e.target.files[0];
  if (f) stage.setFloorTexture(await textureFromFile(f), { w: num('tile-w'), l: num('tile-l') });
});
$('room-photo').addEventListener('change', async (e) => {
  const f = e.target.files[0];
  stage.setBackPhoto(f ? await textureFromFile(f) : null);
});

$('btn-layout').onclick = rebuild;
$('btn-view').onclick = () => stage.frame();
$('btn-shot').onclick = () => stage.screenshot('thiet-ke-phong.png');
$('btn-json').onclick = () => {
  // cùng dạng spec với core/scene3d.py → đưa sang pipeline Python/ComfyUI được
  const spec = {
    scene_id: 'web',
    room: { width_mm: num('room-w'), depth_mm: num('room-d'), height_mm: num('room-h') },
    surfaces: { floor: { texture: $('floor-img').files[0]?.name || 'default-wood', tile_mm: [num('tile-w'), num('tile-l')] } },
    objects: ['table', 'chair'].map((k) => {
      const its = state.items.filter((i) => i.kind === k), d = dims(k);
      return { id: k, glb: state.glb[k]?.name || '', dims_mm: [d.w, d.d, d.h], qty: its.length,
        placement: k === 'table' ? 'center' : 'around:table',
        instances: its.map((i) => ({ position_mm: [i.x, i.z], rotation_deg: i.rot })) };
    }).filter((o) => o.qty > 0),
  };
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([JSON.stringify(spec, null, 2)], { type: 'application/json' }));
  a.download = 'scene-spec.json';
  a.click();
};

// ---------------------------------------------------------------- khởi động
applyRoom();
stage.setFloorTexture(defaultWoodTexture(), { w: num('tile-w'), l: num('tile-l') });
stage.frame();
rebuild();
