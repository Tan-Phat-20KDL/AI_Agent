// Viewer three.js cho scene.glb do core/scene3d.py xuất ra.
// URL: viewer/?scene=<đường dẫn scene.glb tính từ gốc repo>   (meta: cùng chỗ, đuôi .meta.json)
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const params = new URLSearchParams(location.search);
const fromRoot = (p) => '../' + p.replace(/^\/+/, '');
const sceneUrl = fromRoot(params.get('scene') || 'runtime/out/demo/scene.glb');
const metaUrl = sceneUrl.replace(/\.glb$/, '.meta.json');
const el = (id) => document.getElementById(id);

const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.setSize(innerWidth, innerHeight);
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
renderer.outputColorSpace = THREE.SRGBColorSpace;
el('app').appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() || '#f4f2ee');
const camera = new THREE.PerspectiveCamera(50, innerWidth / innerHeight, 0.05, 100);
const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
// Phòng dựng từ 1 ảnh chỉ đúng quanh góc chụp → giới hạn góc xoay
controls.maxPolarAngle = Math.PI / 2 - 0.05;
controls.minAzimuthAngle = -1.2;
controls.maxAzimuthAngle = 1.2;

scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7f72, 1.2));
const sun = new THREE.DirectionalLight(0xffffff, 1.6);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.bias = -0.0005;
scene.add(sun, sun.target);

let meta = { nodes: {}, surfaces: {}, room: { width_mm: 4000, depth_mm: 4000, height_mm: 2700 } };
let home = null;

function frameRoom() {
  const W = meta.room.width_mm / 1000, D = meta.room.depth_mm / 1000, H = meta.room.height_mm / 1000;
  const target = new THREE.Vector3(W / 2, 0.6, D / 2);
  camera.position.set(W / 2, H * 0.75, D + Math.max(W, D) * 0.9);   // đứng phía tường mở
  controls.target.copy(target);
  controls.maxDistance = Math.max(W, D) * 3;
  sun.position.set(W * 0.8, H * 2.5, D * 1.4);
  sun.target.position.copy(target);
  const s = Math.max(W, D);
  Object.assign(sun.shadow.camera, { left: -s, right: s, top: s, bottom: -s, near: 0.1, far: 30 });
  sun.shadow.camera.updateProjectionMatrix();
  controls.update();
  home = { pos: camera.position.clone(), target: target.clone() };
}

// Lát ảnh vật liệu lên 1 mặt phòng: UV tính theo mét nên 1 lần lặp texture = 1 viên thật (tile_mm).
const AXES = { floor: ['x', 'z'], wall_back: ['x', 'y'], wall_left: ['z', 'y'], wall_right: ['z', 'y'] };
async function applySurface(root, name, surf) {
  const mesh = root.getObjectByName(`room_${name}`);
  if (!mesh || !mesh.isMesh) return console.warn('không thấy mặt', name);
  const [a, b] = AXES[name];
  const pos = mesh.geometry.attributes.position, v = new THREE.Vector3(), uv = [];
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i).applyMatrix4(mesh.matrixWorld);
    uv.push(v[a], v[b]);
  }
  mesh.geometry.setAttribute('uv', new THREE.Float32BufferAttribute(uv, 2));
  if (!mesh.geometry.attributes.normal) mesh.geometry.computeVertexNormals();
  const tex = await new THREE.TextureLoader().loadAsync(fromRoot(surf.texture));
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.repeat.set(1000 / surf.tile_mm[0], 1000 / surf.tile_mm[1]);
  tex.anisotropy = renderer.capabilities.getMaxAnisotropy();
  mesh.material = new THREE.MeshStandardMaterial({ map: tex, roughness: 0.8 });
}

function nodeOf(obj) {
  for (let o = obj; o; o = o.parent) if (meta.nodes[o.name]) return o;
  return null;
}

async function load() {
  try { const r = await fetch(metaUrl); if (r.ok) meta = await r.json(); } catch { /* chạy được khi thiếu meta */ }
  const gltf = await new GLTFLoader().loadAsync(sceneUrl);
  scene.add(gltf.scene);
  gltf.scene.updateMatrixWorld(true);
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    o.material = o.material.clone();   // mesh dùng chung giữa các ghế → tách vật liệu để highlight riêng
    // GLB thiếu pháp tuyến / vật liệu (glTF mặc định metallic = 1 → gần như đen) → bù cho đúng
    if (!o.geometry.attributes.normal) o.geometry.computeVertexNormals();
    if (o.material.metalness === 1 && !o.material.metalnessMap) { o.material.metalness = 0; o.material.roughness = 0.85; }
    o.material.flatShading = false;
    o.material.needsUpdate = true;
    const isRoom = o.name.startsWith('room_');
    o.castShadow = !isRoom;
    o.receiveShadow = true;
  });
  for (const [name, surf] of Object.entries(meta.surfaces || {})) {
    await applySurface(gltf.scene, name, surf).catch((e) => console.warn('texture lỗi', name, e));
  }
  frameRoom();
  const counts = {};
  for (const n of Object.values(meta.nodes)) counts[n.object_id] = (counts[n.object_id] || 0) + 1;
  el('info').innerHTML = `<h1>${meta.scene_id ?? 'scene'}</h1>
    <div class="muted">${Object.entries(counts).map(([k, v]) => `${v} ${k}`).join(' · ')} ·
    phòng ${meta.room.width_mm}×${meta.room.depth_mm} mm${Object.keys(meta.surfaces || {}).length ? ' · có lát vật liệu' : ''}</div>`;
}

const ray = new THREE.Raycaster(), ptr = new THREE.Vector2();
let picked = null;
renderer.domElement.addEventListener('click', (e) => {
  ptr.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
  ray.setFromCamera(ptr, camera);
  const hit = ray.intersectObjects(scene.children, true).map((h) => nodeOf(h.object)).find(Boolean);
  const glow = (o, hex) => o && o.traverse((m) => m.isMesh && m.material.emissive && m.material.emissive.setHex(hex));
  glow(picked, 0x000000);
  picked = hit || null;
  glow(picked, 0x223355);
  const box = el('pick');
  if (!picked) { box.style.display = 'none'; return; }
  const m = meta.nodes[picked.name];
  box.style.display = 'block';
  box.innerHTML = `<h1>${m.object_id}</h1><div class="muted">${picked.name} · vị trí ${m.position_mm.join(', ')} mm · quay ${m.rotation_deg}°</div>`;
});

el('shot').onclick = () => {   // ảnh 2D ≥ 1920 px chụp từ cảnh 3D
  const prev = renderer.getPixelRatio();
  renderer.setPixelRatio(Math.max(prev, 1920 / innerWidth));
  renderer.setSize(innerWidth, innerHeight);
  renderer.render(scene, camera);
  const a = document.createElement('a');
  a.href = renderer.domElement.toDataURL('image/png');
  a.download = `${meta.scene_id ?? 'scene'}.png`;
  a.click();
  renderer.setPixelRatio(prev);
  renderer.setSize(innerWidth, innerHeight);
};
el('reset').onclick = () => { if (home) { camera.position.copy(home.pos); controls.target.copy(home.target); } };
addEventListener('resize', () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});

renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });
load().catch((err) => {
  el('info').innerHTML = `<h1 class="err">Không tải được cảnh</h1><div class="muted">${sceneUrl}<br>${err}</div>
    <div class="muted">Chạy <code>python tools/demo_local.py</code> rồi <code>python tools/serve.py</code> ở gốc repo.</div>`;
});
