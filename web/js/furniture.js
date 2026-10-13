// Mô hình bàn/ghế: khối tham số theo kích thước (mm) hoặc file 3D (GLB) người dùng tải lên.
import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const M = 0.001; // mm → m

function mat(color) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.75, metalness: 0 });
}

function box(w, h, d, x, y, z, material) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), material);
  m.position.set(x, y, z);
  m.castShadow = m.receiveShadow = true;
  return m;
}

/** Bàn: mặt dày 40 mm + 4 chân 50 mm. Gốc ở tâm đáy. */
export function tableModel({ w, d, h }, color) {
  const g = new THREE.Group(), mt = mat(color);
  const W = w * M, D = d * M, H = h * M, top = 0.04, leg = 0.05;
  g.add(box(W, top, D, 0, H - top / 2, 0, mt));
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
    g.add(box(leg, H - top, leg, sx * (W / 2 - leg), (H - top) / 2, sz * (D / 2 - leg), mt));
  }
  return g;
}

/** Ghế: mặt ngồi cao 45% + lưng ở phía sau (−z) → mặt trước nhìn về +z. Gốc ở tâm đáy. */
export function chairModel({ w, d, h }, color) {
  const g = new THREE.Group(), mt = mat(color);
  const W = w * M, D = d * M, H = h * M, seatY = H * 0.55, t = 0.035, leg = 0.035;
  g.add(box(W, t, D, 0, seatY, 0, mt));
  g.add(box(W, H - seatY, t, 0, seatY + (H - seatY) / 2, -D / 2 + t / 2, mt));
  for (const sx of [-1, 1]) for (const sz of [-1, 1]) {
    g.add(box(leg, seatY, leg, sx * (W / 2 - leg), seatY / 2, sz * (D / 2 - leg), mt));
  }
  return g;
}

/** GLB tải lên → scale đúng kích thước (mm), gốc ở tâm đáy, bật bóng đổ. */
export async function modelFromGlb(file, { w, d, h }) {
  const gltf = await new GLTFLoader().parseAsync(await file.arrayBuffer(), '');
  const inner = gltf.scene;
  const box3 = new THREE.Box3().setFromObject(inner);
  const size = box3.getSize(new THREE.Vector3());
  if (!size.x || !size.y || !size.z) throw new Error('File 3D rỗng hoặc phẳng');
  inner.scale.set(w * M / size.x, h * M / size.y, d * M / size.z);
  const b2 = new THREE.Box3().setFromObject(inner), c = b2.getCenter(new THREE.Vector3());
  inner.position.set(-c.x, -b2.min.y, -c.z);
  inner.traverse((o) => {
    if (!o.isMesh) return;
    o.castShadow = o.receiveShadow = true;
    if (!o.geometry.attributes.normal) o.geometry.computeVertexNormals();
  });
  const g = new THREE.Group();
  g.add(inner);
  return g;
}

/** Đổi màu cả cụm (dùng khi chọn màu cho mô hình tham số). */
export function setColor(group, color) {
  group.traverse((o) => { if (o.isMesh && o.material.color && !o.material.map) o.material.color.set(color); });
}
