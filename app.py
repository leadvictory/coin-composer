import os
import numpy as np
from flask import Flask, render_template, request
from rembg import remove
from PIL import Image, ImageDraw, ImageFont

app = Flask(__name__)

UPLOAD_FOLDER = "static/uploads"
RESULT_FOLDER = "static/results"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(RESULT_FOLDER, exist_ok=True)

BACKGROUND_PATH = "background.jpeg"  # put it next to app.py


def _load_font(size: int):
    """
    Windows-friendly: try common fonts, fallback to PIL default.
    """
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",      # Arial Bold
        "C:/Windows/Fonts/arial.ttf",        # Arial
        "C:/Windows/Fonts/segoeuib.ttf",     # Segoe UI Bold
        "C:/Windows/Fonts/segoeui.ttf",      # Segoe UI
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def center_coin(rgba_img: Image.Image) -> Image.Image:
    """
    Crop to visible alpha pixels and re-center in a square canvas.
    """
    img = np.array(rgba_img.convert("RGBA"))
    alpha = img[:, :, 3]

    coords = np.column_stack(np.where(alpha > 0))
    if coords.size == 0:
        return rgba_img.convert("RGBA")

    ymin, xmin = coords.min(axis=0)
    ymax, xmax = coords.max(axis=0)

    coin = img[ymin:ymax + 1, xmin:xmax + 1]

    h, w = coin.shape[:2]
    size = max(h, w)

    canvas = np.zeros((size, size, 4), dtype=np.uint8)
    y_off = (size - h) // 2
    x_off = (size - w) // 2
    canvas[y_off:y_off + h, x_off:x_off + w] = coin

    return Image.fromarray(canvas, mode="RGBA")


# def create_reflection_no_blur(coin_rgba: Image.Image, height_ratio: float = 0.42) -> Image.Image:
#     """
#     Mirror (flip vertical) and apply a vertical alpha fade.
#     NO blur, keeps same resolution.
#     """
#     coin_rgba = coin_rgba.convert("RGBA")
#     w, h = coin_rgba.size

#     ref_h = max(1, int(h * height_ratio))
#     reflection = coin_rgba.transpose(Image.FLIP_TOP_BOTTOM).crop((0, 0, w, ref_h))

#     ref_arr = np.array(reflection)
#     a = ref_arr[:, :, 3].astype(np.float32)

#     # Fade alpha from strong (top) to zero (bottom)
#     fade = np.linspace(180, 0, ref_h).reshape(ref_h, 1).astype(np.float32)  # 0..255
#     a = np.minimum(a, fade)  # preserve coin cutout + fade
#     ref_arr[:, :, 3] = a.clip(0, 255).astype(np.uint8)

#     return Image.fromarray(ref_arr, mode="RGBA")
def create_reflection_no_blur(coin):

    w, h = coin.size

    reflection = coin.transpose(Image.FLIP_TOP_BOTTOM)

    reflection = reflection.crop((0, 0, w, int(h * 0.40)))

    ref = np.array(reflection)

    fade = np.linspace(180, 0, ref.shape[0]).reshape(ref.shape[0], 1)

    ref[:, :, 3] = np.minimum(ref[:, :, 3], fade)

    return Image.fromarray(ref, "RGBA")

def draw_title_like_example(draw: ImageDraw.ImageDraw, canvas_w: int):
    """
    Draw: 'Coin' (white) + 'Images.' (orange) + 'COM' (gray),
    centered as a whole line.
    """
    # Tune sizes to your background
    font_big = _load_font(64)

    parts = [
        ("Coin", (235, 235, 235, 255)),
        ("Images.", (255, 170, 0, 255)),
        ("COM", (180, 180, 180, 255)),
    ]

    # measure total width
    widths = []
    heights = []
    for text, _ in parts:
        bbox = draw.textbbox((0, 0), text, font=font_big)
        widths.append(bbox[2] - bbox[0])
        heights.append(bbox[3] - bbox[1])

    total_w = sum(widths)
    max_h = max(heights)

    x = (canvas_w - total_w) // 2
    y = 35  # top padding

    for (text, color), w in zip(parts, widths):
        draw.text((x, y), text, fill=color, font=font_big)
        x += w


def draw_bottom_id(draw: ImageDraw.ImageDraw, canvas_w: int, canvas_h: int, coin_id: str, safe_bottom_y: int):
    """
    Place ID and subtitle BELOW coins (no overlap).
    safe_bottom_y is the Y coordinate after the coin/reflection area.
    """
    id_font = _load_font(52)
    sub_font = _load_font(26)

    id_text = coin_id.strip()
    sub_text = "Identification Number"

    # We place them a bit above bottom, but always below safe_bottom_y.
    # Compute desired positions:
    id_bbox = draw.textbbox((0, 0), id_text, font=id_font)
    id_w = id_bbox[2] - id_bbox[0]
    id_h = id_bbox[3] - id_bbox[1]

    sub_bbox = draw.textbbox((0, 0), sub_text, font=sub_font)
    sub_w = sub_bbox[2] - sub_bbox[0]
    sub_h = sub_bbox[3] - sub_bbox[1]

    # bottom padding
    bottom_pad = 30

    # target block height
    block_h = id_h + 10 + sub_h

    # place block as low as possible, but still above bottom padding
    y_block = max(safe_bottom_y + 15, canvas_h - bottom_pad - block_h)

    # center align
    draw.text(((canvas_w - id_w) / 2, y_block), id_text, fill=(235, 235, 235, 255), font=id_font)
    draw.text(((canvas_w - sub_w) / 2, y_block + id_h + 10), sub_text, fill=(200, 200, 200, 255), font=sub_font)


def create_coin_showcase(background_path, front_coin, back_coin, coin_id):

    bg = Image.open(background_path).convert("RGBA")
    W, H = bg.size

    canvas = bg.copy()

    # -------- BIG COINS --------
    coin_size = int(H * 0.62)

    front = front_coin.resize((coin_size, coin_size))
    back = back_coin.resize((coin_size, coin_size))

    # -------- CLOSE GAP --------
    gap = -int(W * 0.01)   # MUCH closer

    total_width = coin_size * 2 + gap

    start_x = (W - total_width) // 2

    coin_y = int(H * 0.18)

    front_x = start_x
    back_x = start_x + coin_size + gap

    canvas.alpha_composite(front, (front_x, coin_y))
    canvas.alpha_composite(back, (back_x, coin_y))

    # -------- REFLECTION --------
    ref_front = create_reflection_no_blur(front)
    ref_back = create_reflection_no_blur(back)

    ref_y = coin_y + coin_size + 10

    canvas.alpha_composite(ref_front, (front_x, ref_y))
    canvas.alpha_composite(ref_back, (back_x, ref_y))

    draw = ImageDraw.Draw(canvas)

    try:
        title_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 64)
        id_font = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 48)
        sub_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 24)
    except:
        title_font = ImageFont.load_default()
        id_font = ImageFont.load_default()
        sub_font = ImageFont.load_default()

    # -------- TITLE --------
    title = "CoinImages.com"

    bbox = draw.textbbox((0, 0), title, font=title_font)

    tw = bbox[2] - bbox[0]

    draw.text(((W - tw) / 2, 40), title, fill="white", font=title_font)

    # -------- IDENTIFICATION NUMBER --------

    id_y = H - 140

    bbox = draw.textbbox((0, 0), coin_id, font=id_font)
    id_w = bbox[2] - bbox[0]

    draw.text(((W - id_w) / 2, id_y), coin_id, fill="white", font=id_font)

    sub = "Identification Number"

    bbox = draw.textbbox((0, 0), sub, font=sub_font)
    sub_w = bbox[2] - bbox[0]

    draw.text(((W - sub_w) / 2, id_y + 50), sub, fill="lightgray", font=sub_font)

    return canvas


@app.route("/", methods=["GET", "POST"])
def index():

    front_original = back_original = None
    front_result = back_result = None
    final_result = None

    if request.method == "POST":

        # get two files from single upload input
        files = request.files.getlist("coins")

        coin_id = request.form.get("coin_id", "").strip()

        # validation
        if len(files) != 2 or coin_id == "":
            return render_template(
                "index.html",
                error="Please upload TWO images and enter an identification number."
            )

        # first file = LEFT coin
        front_file = files[0]

        # second file = RIGHT coin
        back_file = files[1]

        front_path = os.path.join(UPLOAD_FOLDER, "front.png")
        back_path = os.path.join(UPLOAD_FOLDER, "back.png")

        front_file.save(front_path)
        back_file.save(back_path)

        # remove background
        front_img = remove(Image.open(front_path))
        back_img = remove(Image.open(back_path))

        # center coins
        front_img = center_coin(front_img)
        back_img = center_coin(back_img)

        # save extracted
        front_result_path = os.path.join(RESULT_FOLDER, "front_coin.png")
        back_result_path = os.path.join(RESULT_FOLDER, "back_coin.png")

        front_img.save(front_result_path)
        back_img.save(back_result_path)

        # create final image
        final = create_coin_showcase(
            BACKGROUND_PATH,
            front_img,
            back_img,
            coin_id
        )

        final_result_path = os.path.join(RESULT_FOLDER, "final_coin.png")
        final.save(final_result_path)

        front_original = front_path
        back_original = back_path
        front_result = front_result_path
        back_result = back_result_path
        final_result = final_result_path

    return render_template(
        "index.html",
        front_original=front_original,
        back_original=back_original,
        front_result=front_result,
        back_result=back_result,
        final_result=final_result
    )

if __name__ == "__main__":
    # On Windows + Py3.12: avoid socket/reloader issues
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)