// Xếp đồ (mm, cùng quy ước với core/placement): gốc ở góc phòng, x theo chiều rộng, z theo chiều sâu.
// rotation 0° = mặt trước nhìn về +z; 90° = nhìn về +x (giống three.js rotation.y).

export const GAP_MM = 50;

export function footprint(w, d, rot) {
  const r = ((Math.round(rot / 90) % 4) + 4) % 4;
  return r % 2 ? [d, w] : [w, d];
}

/** Bàn giữa phòng; n ghế chia đều 2 cạnh dài trước, thiếu chỗ mới sang 2 cạnh ngắn, quay mặt vào bàn. */
export function layoutDining(room, table, chair, n) {
  const t = { x: room.w / 2, z: room.d / 2, rot: table.w >= table.d ? 0 : 90 };
  const [tw, td] = footprint(table.w, table.d, t.rot);
  const sides = [
    { name: 'south', len: tw, rot: 180 }, { name: 'north', len: tw, rot: 0 },
    { name: 'east', len: td, rot: 270 }, { name: 'west', len: td, rot: 90 },
  ];
  const cap = (len) => Math.max(0, Math.floor((len + GAP_MM) / (chair.w + GAP_MM)));
  const count = Object.fromEntries(sides.map((s) => [s.name, 0]));
  let left = n;
  for (const group of [sides.slice(0, 2), sides.slice(2)]) {
    while (left > 0 && group.some((s) => count[s.name] < cap(s.len))) {
      for (const s of group) if (left > 0 && count[s.name] < cap(s.len)) { count[s.name]++; left--; }
    }
  }
  const chairs = [];
  for (const s of sides) {
    const k = count[s.name];
    for (let i = 0; i < k; i++) {
      const off = -s.len / 2 + (i + 0.5) * s.len / k;
      const out = GAP_MM + chair.d / 2;
      if (s.name === 'south') chairs.push({ x: t.x + off, z: t.z + td / 2 + out, rot: s.rot });
      if (s.name === 'north') chairs.push({ x: t.x + off, z: t.z - td / 2 - out, rot: s.rot });
      if (s.name === 'east') chairs.push({ x: t.x + tw / 2 + out, z: t.z + off, rot: s.rot });
      if (s.name === 'west') chairs.push({ x: t.x - tw / 2 - out, z: t.z + off, rot: s.rot });
    }
  }
  return { table: t, chairs, unplaced: left };
}

/** Món nằm ngoài phòng (để cảnh báo). items: [{x, z, rot, w, d}] */
export function outsideRoom(room, items) {
  return items.filter((it) => {
    const [fw, fd] = footprint(it.w, it.d, it.rot);
    return it.x - fw / 2 < 0 || it.z - fd / 2 < 0 || it.x + fw / 2 > room.w || it.z + fd / 2 > room.d;
  });
}

/** Giữ món trong phòng khi kéo thả. */
export function clampInRoom(room, it) {
  const [fw, fd] = footprint(it.w, it.d, it.rot);
  return {
    x: Math.min(Math.max(it.x, fw / 2), room.w - fw / 2),
    z: Math.min(Math.max(it.z, fd / 2), room.d - fd / 2),
  };
}
