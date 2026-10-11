// Viewer three.js cho scene.glb do core/scene/assemble.py xuất ra (FR-10, FR-14).
// URL: viewer/?scene=<đường dẫn scene.glb>   (meta đọc từ cùng chỗ: scene.meta.json)
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const params = new URLSearchParams(location.search);
const sceneUrl = '../' + (params.get('scene') || 'runtime/out/s_demo/v2/scene.glb').replace(/^\/+/, '');
const metaUrl = sceneUrl.replace(/\.glb$/, '.meta.json');

const el = (id) => document.getElementById(id);
const fmt = new Intl.NumberFormat('vi-VN');

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
// Phòng dựng từ 1 ảnh chỉ đúng quanh góc chụp → giới hạn góc xoay (SPEC mục 5, chế độ A)
controls.maxPolarAngle = Math.PI / 2 - 0.05;
controls.minAzimuthAngle = -1.2;
controls.maxAzimuthAngle = 1.2;

scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7f72, 1.2));
const sun = new THREE.DirectionalLight(0xffffff, 1.6);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.bias = -0.0005;
scene.add(sun);

let meta = { nodes: {}, room: { width_mm: 4000, depth_mm: 4000, height_mm: 2700 } };
let home = null;

function frameRoom() {
  const W = meta.room.width_mm / 1000, D = meta.room.depth_mm / 1000, H = meta.room.height_mm / 1000;
  const target = new THREE.Vector3(W / 2, 0.6, D / 2);
  camera.position.set(W / 2, H * 0.75, D + Math.max(W, D) * 0.9);  // đứng ở phía tường mở
  controls.target.copy(target);
  controls.minDistance = 1;
  controls.maxDistance = Math.max(W, D) * 3;
  sun.position.set(W * 0.8, H * 2.5, D * 1.4);
  sun.target.position.copy(target);
  scene.add(sun.target);
  const s = Math.max(W, D);
  Object.assign(sun.shadow.camera, { left: -s, right: s, top: s, bottom: -s, near: 0.1, far: 30 });
  sun.shadow.camera.updateProjectionMatrix();
  controls.update();
  home = { pos: camera.position.clone(), target: target.clone() };
}

function nodeOf(obj) {
  for (let o = obj; o; o = o.parent) if (/#\d+$/.test(o.name) && meta.nodes[o.name]) return o;
  return null;
}

async function load() {
  try {
    const r = await fetch(metaUrl);
    if (r.ok) meta = await r.json();
  } catch { /* chạy được cả khi thiếu meta */ }
  const gltf = await new GLTFLoader().loadAsync(sceneUrl);
  gltf.scene.traverse((o) => {
    if (!o.isMesh) return;
    o.material = o.material.clone();  // mesh dùng chung giữa các instance → tách vật liệu để highlight riêng
    const isRoom = o.name.startsWith('room') || (o.parent && o.parent.name.startsWith('room'));
    o.castShadow = !isRoom;
    o.receiveShadow = true;
    if (isRoom && o.material) o.material.side = THREE.FrontSide;  // tường quay mặt vào trong
  });
  scene.add(gltf.scene);
  frameRoom();
  const n = Object.keys(meta.nodes).length;
  el('info').innerHTML = `<h1>${meta.scene_id ?? 'scene'} · v${meta.version ?? '?'}</h1>
    <div class="muted">${n} món · phòng ${meta.room.width_mm}×${meta.room.depth_mm} mm · bấm vào đồ để xem SKU/giá</div>`;
}

const ray = new THREE.Raycaster();
const ptr = new THREE.Vector2();
let picked = null;
renderer.domElement.addEventListener('click', (e) => {
  ptr.set((e.clientX / innerWidth) * 2 - 1, -(e.clientY / innerHeight) * 2 + 1);
  ray.setFromCamera(ptr, camera);
  const hit = ray.intersectObjects(scene.children, true).map((h) => nodeOf(h.object)).find(Boolean);
  if (picked) picked.traverse((o) => o.isMesh && o.material.emissive && o.material.emissive.setHex(0x000000));
  picked = hit || null;
  const box = el('pick');
  if (!picked) { box.style.display = 'none'; return; }
  picked.traverse((o) => o.isMesh && o.material.emissive && o.material.emissive.setHex(0x223355));
  const m = meta.nodes[picked.name];
  box.style.display = 'block';
  box.innerHTML = `<h1>${m.name}</h1>
    <div>${m.variant_id} · ${m.color}${m.tinted ? ' <span class="muted">(màu minh hoạ)</span>' : ''}</div>
    <div>${fmt.format(m.price_vnd)} VND</div>
    <div class="muted">object: ${m.object_id} · node: ${picked.name}</div>`;
});

el('shot').onclick = () => {
  // FR-14: ảnh ≥ 1920 px chiều ngang
  const prev = renderer.getPixelRatio();
  renderer.setPixelRatio(Math.max(prev, 1920 / innerWidth));
  renderer.setSize(innerWidth, innerHeight);
  renderer.render(scene, camera);
  const a = document.createElement('a');
  a.href = renderer.domElement.toDataURL('image/png');
  a.download = `${meta.scene_id ?? 'scene'}_v${meta.version ?? ''}.png`;
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
    <div class="muted">Chạy <code>python tools/demo_local.py</code> rồi <code>python -m http.server 8080</code> ở thư mục gốc.</div>`;
});
