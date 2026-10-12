"""Download AWS Terrarium elevation tiles (open data, no key) and mosaic them for the Kanto box."""
import math, urllib.request, io, numpy as np, os
from PIL import Image
Z = 10
LON0, LON1, LAT0, LAT1 = 138.95, 140.60, 35.10, 36.35
def tx(lon): return (lon + 180) / 360 * 2**Z
def ty(lat):
    r = math.radians(lat); return (1 - math.log(math.tan(r) + 1/math.cos(r)) / math.pi) / 2 * 2**Z
x0, x1 = int(tx(LON0)), int(tx(LON1)); y0, y1 = int(ty(LAT1)), int(ty(LAT0))
print("tiles x", x0, x1, "y", y0, y1)
os.makedirs("data/tiles", exist_ok=True)
rows = []
for y in range(y0, y1 + 1):
    row = []
    for x in range(x0, x1 + 1):
        p = f"data/tiles/{Z}_{x}_{y}.png"
        if not os.path.exists(p):
            urllib.request.urlretrieve(f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{x}/{y}.png", p)
        a = np.asarray(Image.open(p).convert("RGB")).astype(np.float64)
        row.append(a[..., 0] * 256 + a[..., 1] + a[..., 2] / 256 - 32768)
    rows.append(np.hstack(row))
elev = np.vstack(rows)
# pixel-center lon/lat arrays (Web Mercator)
n = 2**Z
px = (np.arange(elev.shape[1]) + 0.5) / 256 + x0
py = (np.arange(elev.shape[0]) + 0.5) / 256 + y0
lons = px / n * 360 - 180
lats = np.degrees(np.arctan(np.sinh(np.pi * (1 - 2 * py / n))))
np.savez_compressed("data/elev.npz", elev=elev.astype(np.float32), lons=lons, lats=lats)
print(elev.shape, float(elev.min()), float(elev.max()))
