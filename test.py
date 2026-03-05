from rembg import remove
from PIL import Image
import numpy as np

input_path = "back.jpeg"
output_path = "coin_centered.png"

# remove background
input_image = Image.open(input_path)
output_image = remove(input_image)

# convert to numpy
img = np.array(output_image)

# get alpha channel
alpha = img[:, :, 3]

# find coin bounding box
coords = np.column_stack(np.where(alpha > 0))
ymin, xmin = coords.min(axis=0)
ymax, xmax = coords.max(axis=0)

coin = img[ymin:ymax, xmin:xmax]

# make square canvas
h, w = coin.shape[:2]
size = max(h, w)

canvas = np.zeros((size, size, 4), dtype=np.uint8)

# compute center offsets
y_offset = (size - h) // 2
x_offset = (size - w) // 2

canvas[y_offset:y_offset+h, x_offset:x_offset+w] = coin

# save result
Image.fromarray(canvas).save(output_path)

print("Saved:", output_path)