// Texture: vân gỗ mặc định (vẽ bằng canvas), ảnh người dùng tải lên, màu chủ đạo của ảnh sản phẩm.
import * as THREE from 'three';

function finish(tex) {
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 8;
  return tex;
}

/** 1 thanh gỗ (ngang = chiều dài thanh) vẽ bằng canvas — dùng khi chưa tải ảnh vật liệu. */
export function defaultWoodTexture() {
  const c = document.createElement('canvas');
  c.width = 1024; c.height = 170;
  const g = c.getContext('2d');
  for (let y = 0; y < c.height; y++) {
    for (let x = 0; x < c.width; x += 4) {
      const grain = 0.5 + 0.25 * Math.sin(2 * Math.PI * (y / c.height * 9 + 0.15 * Math.sin(x / c.width * 6 * Math.PI)));
      const n = (Math.sin(x * 12.9898 + y * 78.233) * 43758.5453) % 1 * 0.08;
      const v = grain + n;
      g.fillStyle = `rgb(${150 + 60 * v | 0},${105 + 45 * v | 0},${65 + 30 * v | 0})`;
      g.fillRect(x, y, 4, 1);
    }
  }
  g.fillStyle = 'rgba(40,25,15,0.55)';
  g.fillRect(0, 0, c.width, 3); g.fillRect(0, c.height - 3, c.width, 3); g.fillRect(0, 0, 3, c.height);
  return finish(new THREE.CanvasTexture(c));
}

export async function textureFromFile(file) {
  const url = URL.createObjectURL(file);
  try {
    return finish(await new THREE.TextureLoader().loadAsync(url));
  } finally {
    setTimeout(() => URL.revokeObjectURL(url), 5000);
  }
}

/** Màu chủ đạo (trung bình, bỏ điểm gần trắng = nền ảnh sản phẩm) → '#rrggbb'. */
export async function dominantColor(file) {
  const bmp = await createImageBitmap(file);
  const c = document.createElement('canvas');
  c.width = 64; c.height = 64;
  const g = c.getContext('2d', { willReadFrequently: true });
  g.drawImage(bmp, 0, 0, 64, 64);
  const px = g.getImageData(0, 0, 64, 64).data;
  let r = 0, gg = 0, b = 0, n = 0;
  for (let i = 0; i < px.length; i += 4) {
    if (px[i + 3] < 128 || (px[i] > 235 && px[i + 1] > 235 && px[i + 2] > 235)) continue;
    r += px[i]; gg += px[i + 1]; b += px[i + 2]; n++;
  }
  if (!n) return '#888888';
  const hex = (v) => Math.round(v / n).toString(16).padStart(2, '0');
  return `#${hex(r)}${hex(gg)}${hex(b)}`;
}
