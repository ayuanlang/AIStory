
import sys, os
from PIL import Image, ImageFilter
import imageio

def make_thumb(filepath):
    thumb_path = filepath + ".thumb.jpg"
    try:
        if filepath.lower().endswith(".mp4"):
            reader = imageio.get_reader(filepath)
            frame = reader.get_data(0)
            img = Image.fromarray(frame)
        else:
            img = Image.open(filepath)
            
        img.thumbnail((64, 64))
        img.convert("RGB").save(thumb_path, format="JPEG", optimize=True, quality=30)
        print("Success:", thumb_path)
    except Exception as e:
        print("Error:", e)

