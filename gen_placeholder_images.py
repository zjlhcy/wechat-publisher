# -*- coding: utf-8 -*-
"""Generate placeholder images for CI pipeline"""
import os
from PIL import Image

img_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "images")
os.makedirs(img_dir, exist_ok=True)

for i in range(1, 7):
    img = Image.new("RGB", (900, 500), color=(40 + i * 30, 80 + i * 20, 160 + i * 15))
    path = os.path.join(img_dir, "placeholder_{}.png".format(i))
    img.save(path)
    print("Created: {}".format(path))

print("All placeholder images generated.")
