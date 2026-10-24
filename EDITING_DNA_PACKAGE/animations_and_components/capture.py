"""Capture component frames with headless Microsoft Edge (verified on this PC) -> PNG.
Usage: python capture.py  (renders the comparison set into ../annotated_comparisons/)"""
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlencode

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"


def capture(params, out, size=(848, 480)):
    url = (HERE / "components.html").as_uri() + "?" + urlencode(params)
    subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--allow-file-access-from-files",
                    "--virtual-time-budget=4000", f"--window-size={size[0]},{size[1]}", f"--screenshot={out}", url],
                   check=True, capture_output=True, timeout=60)
    return out


def side_by_side(ref, rec, out, label_ref, label_rec, note):
    a, b = cv2.imread(str(ref)), cv2.imread(str(rec))
    b = cv2.resize(b, (a.shape[1], a.shape[0]))
    bar = lambda w, txt, col: cv2.putText(np.full((34, w, 3), col, np.uint8), txt, (8, 23), 0, 0.6, (255, 255, 255), 1)
    top = np.hstack([bar(a.shape[1], label_ref, (40, 40, 40)), bar(b.shape[1], label_rec, (20, 60, 160))])
    img = np.vstack([top, np.hstack([a, b])])
    foot = np.full((30, img.shape[1], 3), 20, np.uint8)
    cv2.putText(foot, note, (8, 20), 0, 0.5, (200, 200, 200), 1)
    cv2.imwrite(str(out), np.vstack([img, foot]))


RF = "../reference_frames/"
SETS = [
    ("title_slam_HUARAZ", "R17_1.20s_ref.png",
     {"c": "title_slam", "text": "HUARAZ", "width": "0.958", "height": "0.739", "plate": RF + "R17_0.60s_plate.png"},
     "Anton stretched to 95.8% w x 73.9% h, #E70002. Plate = different shot (no clean plate exists)."),
    ("title_slam_BUENOS_AIRES", "R02_0.90s_ref.png",
     {"c": "title_slam", "text": "BUENOS AIRES", "width": "0.73", "font": "grotesque", "color": "#AC0A22", "plate": RF + "R02_0.40s_plate.png"},
     "Archivo wght900 wdth88 tracking -4.5%. Colour #AC0A22 sampled."),
    ("side_labels_MARRAKECH", "R05_0.90s_ref.png",
     {"c": "side_labels", "text": "04 DAYS IN", "text2": "MARRAKECH", "plate": RF + "R05_2.40s_plate.png"},
     "Archivo wdth125 wght900, 3.7% frame height, x margin 4.5%, mid-height. '++' = arrow glyph approximation."),
    ("white_card_series", "RA_9.60s_ref.png",
     {"c": "white_card", "plate": RF + "RA_13.50s_plate.png"},
     "Inset 69% x 92% centred on #FDFCFD (measured RA 7.5/9.6/16.2 s). Plate = different shot."),
]

if __name__ == "__main__":
    outdir = PKG / "annotated_comparisons"
    outdir.mkdir(exist_ok=True)
    for name, ref, params, note in SETS:
        rec = outdir / f"{name}_reconstruction.png"
        capture(params, str(rec))
        side_by_side(PKG / "reference_frames" / ref, rec, outdir / f"{name}_compare.jpg",
                     f"REFERENCE {ref}", "SYNTHETIC RECONSTRUCTION (HTML)", note)
        print("ok", name)
