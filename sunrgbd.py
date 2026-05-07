import os
import shutil
import random

# paths
image_src = "SUNRGBD/image"
label_src = "SUNRGBD/label"

# output
out_img_train = "dataset/images/train"
out_img_val = "dataset/images/val"
out_lbl_train = "dataset/labels/train"
out_lbl_val = "dataset/labels/val"

os.makedirs(out_img_train, exist_ok=True)
os.makedirs(out_img_val, exist_ok=True)
os.makedirs(out_lbl_train, exist_ok=True)
os.makedirs(out_lbl_val, exist_ok=True)

classes = ["chair", "table", "bed", "sofa"]

def convert_bbox(x, y, w, h, img_w, img_h):
    xc = (x + w/2) / img_w
    yc = (y + h/2) / img_h
    w = w / img_w
    h = h / img_h
    return xc, yc, w, h

# fake example loop (you must adapt based on annotation format)
for file in os.listdir(image_src):

    if not file.endswith(".jpg"):
        continue

    img_path = os.path.join(image_src, file)
    
    # randomly split
    if random.random() < 0.8:
        img_out = out_img_train
        lbl_out = out_lbl_train
    else:
        img_out = out_img_val
        lbl_out = out_lbl_val

    shutil.copy(img_path, img_out)

    # create dummy label (you must replace with real parsing)
    with open(os.path.join(lbl_out, file.replace(".jpg", ".txt")), "w") as f:
        pass