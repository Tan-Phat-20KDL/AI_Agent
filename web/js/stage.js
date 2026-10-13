// Sân khấu 3D: renderer, camera, đèn, và căn phòng (sàn + 3 tường, mặt trước mở để nhìn vào).
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const M = 0.001;

export function createStage(container) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color('#1c1d21');
  const camera = new THREE.PerspectiveCamera(50, 1, 0.05, 100);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.maxPolarAngle = Math.PI / 2 - 0.05;

  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a7f72, 1.1));
  const sun = new THREE.DirectionalLight(0xffffff, 1.7);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.bias = -0.0004;
  scene.add(sun, sun.target);

  const room = new THREE.Group();
  scene.add(room);
  const floorMat = new THREE.MeshStandardMaterial({ roughness: 0.8 });
  const wallMat = new THREE.MeshStandardMaterial({ color: '#e9e6e0', roughness: 0.95 });
  const backMat = new THREE.MeshStandardMaterial({ color: '#e9e6e0', roughness: 0.95 });
  let dims = { w: 4000, d: 3500, h: 2700 }, tile = { w: 1200, l: 200 };

  function plane(w, h, material) {
    const m = new THREE.Mesh(new THREE.PlaneGeometry(w, h), material);
    m.receiveShadow = true;
    return m;
  }

  function buildRoom() {
    room.clear();
    const W = dims.w * M, D = dims.d * M, H = dims.h * M;
    const floor = plane(W, D, floorMat);
    floor.rotation.x = -Math.PI / 2;
    floor.position.set(W / 2, 0, D / 2);
    floor.name = 'floor';
    const back = plane(W, H, backMat);
    back.position.set(W / 2, H / 2, 0);
    const left = plane(D, H, wallMat);
    left.rotation.y = Math.PI / 2;
    left.position.set(0, H / 2, D / 2);
    const right = plane(D, H, wallMat);
    right.rotation.y = -Math.PI / 2;
    right.position.set(W, H / 2, D / 2);
    room.add(floor, back, left, right);
    applyTile();
    const s = Math.max(W, D);
    sun.position.set(W * 0.75, H * 2.6, D * 1.5);
    sun.target.position.set(W / 2, 0, D / 2);
    Object.assign(sun.shadow.camera, { left: -s, right: s, top: s, bottom: -s, near: 0.1, far: 40 });
    sun.shadow.camera.updateProjectionMatrix();
  }

  function applyTile() {
    if (floorMat.map) floorMat.map.repeat.set(dims.w / tile.w, dims.d / tile.l);
  }

  function frame() {
    const W = dims.w * M, D = dims.d * M, H = dims.h * M;
    controls.target.set(W / 2, 0.5, D / 2);
    camera.position.set(W / 2, H * 0.85, D + Math.max(W, D) * 0.95);
    controls.maxDistance = Math.max(W, D) * 3;
    controls.update();
  }

  function resize() {
    const { clientWidth: w, clientHeight: h } = container;
    renderer.setSize(w, h, false);
    camera.aspect = w / Math.max(h, 1);
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(container);
  resize();
  renderer.setAnimationLoop(() => { controls.update(); renderer.render(scene, camera); });

  return {
    scene, camera, renderer, controls,
    floor: () => room.getObjectByName('floor'),
    setRoom(d) { dims = { ...d }; buildRoom(); },
    setFloorTexture(tex, t) {
      if (tex && floorMat.map !== tex) { floorMat.map = tex; floorMat.color.set('#ffffff'); floorMat.needsUpdate = true; }
      if (t) tile = { ...t };
      applyTile();
    },
    setWallColor(c) { wallMat.color.set(c); if (!backMat.map) backMat.color.set(c); },
    setBackPhoto(tex) {
      backMat.map = tex || null;
      backMat.color.set(tex ? '#ffffff' : wallMat.color);
      backMat.needsUpdate = true;
    },
    frame,
    screenshot(name) {
      const prev = renderer.getPixelRatio(), w = container.clientWidth;
      renderer.setPixelRatio(Math.max(prev, 1920 / w));
      resize();
      renderer.render(scene, camera);
      const a = document.createElement('a');
      a.href = renderer.domElement.toDataURL('image/png');
      a.download = name;
      a.click();
      renderer.setPixelRatio(prev);
      resize();
    },
  };
}
