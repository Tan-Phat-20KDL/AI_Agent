"""Giao diện Gradio: 1–3 ảnh + kích thước → cảnh 3D (three.js nhúng trong trang) + ảnh 2D.

    python app/gradio_app.py                 # http://127.0.0.1:7860
    python app/gradio_app.py --share         # link công khai (Colab / RunPod)

Logic nằm trong core/ (core.design, core.room.moge); file này chỉ nối giao diện.
"""

from __future__ import annotations

import argparse
import mimetypes
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Windows lấy MIME từ Registry, nhiều máy khai .js = text/plain → trình duyệt không chạy three.js
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("model/gltf-binary", ".glb")

import gradio as gr  # noqa: E402

from core.design import Design, Item, build_design  # noqa: E402
from core.placement import PlacementError  # noqa: E402
from core.room.moge import MeasureUnavailable, measure_room  # noqa: E402
from core.scene3d import SceneSpecError  # noqa: E402

RUNS = ROOT / "runtime" / "gradio"
RUNS.mkdir(parents=True, exist_ok=True)
gr.set_static_paths([ROOT / "viewer", RUNS])  # viewer three.js + cảnh đã dựng phục vụ trực tiếp

SURFACES = {"Sàn": "floor", "Tường sau": "wall_back", "Tường trái": "wall_left", "Tường phải": "wall_right"}


def viewer_html(scene_rel: str | None) -> str:
    if not scene_rel:
        return "<div style='padding:24px;color:#888'>Bấm <b>Dựng 3D</b> để xem cảnh.</div>"
    src = f"/gradio_api/file={ROOT.as_posix()}/viewer/index.html?scene={scene_rel}&t={int(time.time())}"
    return (f"<iframe src='{src}' style='width:100%;height:600px;border:0;border-radius:8px' "
            "title='Cảnh 3D'></iframe>")


def on_build(rw, rd, rh, tex, tile_w, tile_l, surface, tw, td, th, tcolor, tglb, cw, cd, ch, ccolor, cglb, cqty):
    run_dir = RUNS / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:4]}"
    d = Design(room_mm=(int(rw), int(rd), int(rh)),
               table=Item((int(tw), int(td), int(th)), glb=tglb, color=tcolor),
               chair=Item((int(cw), int(cd), int(ch)), glb=cglb, color=ccolor),
               chair_qty=int(cqty), texture=tex, tile_mm=(int(tile_w), int(tile_l)), surface=SURFACES[surface])
    try:
        meta = build_design(d, ROOT, run_dir)
    except (PlacementError, SceneSpecError, FileNotFoundError, ValueError) as e:
        return viewer_html(None), f"**Không dựng được:** {e}"
    chairs = sum(1 for n in meta["nodes"] if n.startswith("chair#"))
    msg = [f"Phòng {rw}×{rd}×{rh} mm · 1 bàn · {chairs} ghế · lát {surface.lower()} {tile_w}×{tile_l} mm"]
    msg += [f"⚠️ {w}" for w in meta["warnings"]]
    return viewer_html(meta["scene"]), "\n\n".join(msg)


def on_measure(img, known_h):
    if not img:
        return gr.update(), gr.update(), gr.update(), "Chưa tải ảnh phòng."
    try:
        est = measure_room(img, int(known_h) if known_h else None)
    except MeasureUnavailable as e:
        return gr.update(), gr.update(), gr.update(), f"⚠️ {e}. Nhập kích thước tay."
    note = "" if known_h else " — nhập chiều cao trần thật để hiệu chỉnh tỉ lệ"
    return est.width_mm, est.depth_mm, est.height_mm, (
        f"MoGe-2: rộng {est.width_mm} × sâu {est.depth_mm} × cao {est.height_mm} mm "
        f"(camera cao {est.camera_height_mm} mm){note}. Rộng/sâu lấy từ phần sàn nhìn thấy nên có thể nhỏ hơn thật.")


def on_compose_2d(room_img, table_img, chair_img, tex_img):
    # Ghép 2D bằng Qwen-Image-Edit-2511 qua ComfyUI — nối ở Phase 0 (cần GPU, xem workflows/README.md)
    have = [n for n, v in (("phòng", room_img), ("bàn", table_img), ("ghế", chair_img), ("vật liệu", tex_img)) if v]
    return None, (f"Đã nhận ảnh: {', '.join(have) or 'chưa có'}. **Ghép 2D bằng AI chưa nối** — cần GPU + ComfyUI "
                  "với Qwen-Image-Edit-2511 (Phase 0 trên RunPod).")


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="Thiết kế phòng 3D") as demo:
        gr.Markdown("## Thiết kế phòng — ghép bàn ghế / lát vật liệu (2D + 3D)")
        with gr.Row():
            with gr.Column(scale=1, min_width=340):
                with gr.Tab("Phòng"):
                    room_img = gr.Image(type="filepath", label="Ảnh phòng thật", height=180)
                    with gr.Row():
                        rw = gr.Number(4200, label="Rộng (mm)", precision=0)
                        rd = gr.Number(3600, label="Sâu (mm)", precision=0)
                        rh = gr.Number(2800, label="Cao (mm)", precision=0)
                    known_h = gr.Number(None, label="Chiều cao trần thật (mm, để hiệu chỉnh — tuỳ chọn)", precision=0)
                    btn_measure = gr.Button("Đo phòng từ ảnh (MoGe-2, cần GPU)")
                with gr.Tab("Vật liệu"):
                    tex = gr.Image(type="filepath", label="Ảnh 1 viên gạch / 1 thanh gỗ", height=140)
                    with gr.Row():
                        tile_w = gr.Number(1200, label="Dài (mm)", precision=0)
                        tile_l = gr.Number(200, label="Rộng (mm)", precision=0)
                    surface = gr.Radio(list(SURFACES), value="Sàn", label="Lát lên")
                with gr.Tab("Bàn"):
                    table_img = gr.Image(type="filepath", label="Ảnh bàn", height=140)
                    with gr.Row():
                        tw = gr.Number(1600, label="Dài", precision=0)
                        td = gr.Number(900, label="Rộng", precision=0)
                        th = gr.Number(750, label="Cao", precision=0)
                    tcolor = gr.ColorPicker("#2e2e30", label="Màu khối tạm")
                    tglb = gr.File(label="File 3D .glb (từ TRELLIS.2)", file_types=[".glb"], type="filepath")
                with gr.Tab("Ghế"):
                    chair_img = gr.Image(type="filepath", label="Ảnh ghế", height=140)
                    with gr.Row():
                        cw = gr.Number(450, label="Rộng", precision=0)
                        cd = gr.Number(520, label="Sâu", precision=0)
                        ch = gr.Number(820, label="Cao", precision=0)
                    cqty = gr.Slider(0, 12, value=4, step=1, label="Số ghế")
                    ccolor = gr.ColorPicker("#7a5232", label="Màu khối tạm")
                    cglb = gr.File(label="File 3D .glb (từ TRELLIS.2)", file_types=[".glb"], type="filepath")
                btn_build = gr.Button("Dựng 3D", variant="primary")
            with gr.Column(scale=2):
                with gr.Tab("3D (three.js)"):
                    view = gr.HTML(viewer_html(None))
                    info = gr.Markdown()
                with gr.Tab("2D (AI)"):
                    btn_2d = gr.Button("Ghép 2D bằng AI")
                    out_2d = gr.Image(label="Ảnh phòng đã ghép", interactive=False)
                    info_2d = gr.Markdown()

        inputs = [rw, rd, rh, tex, tile_w, tile_l, surface, tw, td, th, tcolor, tglb, cw, cd, ch, ccolor, cglb, cqty]
        btn_build.click(on_build, inputs, [view, info])
        demo.load(on_build, inputs, [view, info])  # mở trang là có cảnh mẫu
        btn_measure.click(on_measure, [room_img, known_h], [rw, rd, rh, info])
        btn_2d.click(on_compose_2d, [room_img, table_img, chair_img, tex], [out_2d, info_2d])
    return demo


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--share", action="store_true", help="tạo link công khai (Colab/RunPod)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=7860)
    a = ap.parse_args()
    build_ui().launch(server_name=a.host, server_port=a.port, share=a.share)


if __name__ == "__main__":
    main()
