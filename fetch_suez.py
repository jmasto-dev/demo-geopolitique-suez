"""Fetch real AWS Terrain Tiles (terrarium) & EOX Sentinel-2 Cloudless 2016 (CC BY 4.0) for Suez Canal."""
import os, io, json, math, time, datetime, urllib.request
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, 'raw'); os.makedirs(RAW, exist_ok=True)
ASSETS = os.path.join(HERE, 'assets'); os.makedirs(ASSETS, exist_ok=True)
UA = {'User-Agent': 'lemo-opuscar-suez/1.0'}
LOG = open(os.path.join(RAW, 'manifest.jsonl'), 'a')

# Suez Canal bounding box: Port Said (31.26N, 32.31E) to Suez (29.96N, 32.55E)
W, S, E, N = 31.55, 29.45, 33.35, 31.55

def tile_xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n
    return x, y

def tile_lonlat(tx, ty, z):
    n = 2 ** z
    lon = tx / n * 360 - 180
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * ty / n))))
    return lon, lat

def get(url):
    for k in range(5):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=60) as r:
                b = r.read()
            LOG.write(json.dumps({'url': url, 'bytes': len(b), 'date': datetime.date.today().isoformat()}) + '\n')
            return b
        except Exception:
            if k == 4: raise
            time.sleep(1.5 * (k + 1))

def mosaic(tmpl, z, w, s, e, n, out_size=None):
    x0, y0 = tile_xy(w, n, z); x1, y1 = tile_xy(e, s, z)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    jobs = [(x, y) for y in range(ty0, ty1 + 1) for x in range(tx0, tx1 + 1)]
    im = Image.new('RGB', ((tx1 - tx0 + 1) * 256, (ty1 - ty0 + 1) * 256))
    with ThreadPoolExecutor(8) as ex:
        for (x, y), b in ex.map(lambda j: (j, get(tmpl.format(z=z, x=j[0], y=j[1]))), jobs):
            im.paste(Image.open(io.BytesIO(b)).convert('RGB'), ((x - tx0) * 256, (y - ty0) * 256))
    if out_size:
        im = im.resize(out_size, Image.BILINEAR)
    lon0, lat0 = tile_lonlat(tx0, ty0, z)
    lon1, lat1 = tile_lonlat(tx1 + 1, ty1 + 1, z)
    return im, [lon0, lat1, lon1, lat0]

print('Fetching Suez terrain (AWS Terrarium z=9)...')
ter_im, bbox = mosaic('https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png', 9, W, S, E, N, (512, 512))
arr = np.asarray(ter_im, dtype=np.float32)
# Terrarium decoding: (R * 256 + G + B / 256) - 32768
h_m = (arr[:, :, 0] * 256.0 + arr[:, :, 1] + arr[:, :, 2] / 256.0) - 32768.0
h_m.astype(np.float32).tofile(os.path.join(ASSETS, 'height.bin'))

print('Fetching Suez Sentinel-2 (EOX CC BY 4.0 z=10)...')
s2_im, _ = mosaic('https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg', 10, W, S, E, N, (1024, 1024))
s2_im.save(os.path.join(ASSETS, 's2.jpg'), quality=90)

# Bake low-sun shadow map (sun from WSW at ~20 deg elevation)
GY, GX = 512, 512
dx_m = 180000.0 / GX
dz_m = 230000.0 / GY
sun_step_x, sun_step_y, sun_dz = -1.0, 0.35, 0.38 * dx_m * 3.0  # 3x relief exaggeration
shadow = np.ones((GY, GX), dtype=np.float32)
for step in range(1, 55):
    sx = np.clip(np.arange(GX)[None, :] + int(round(step * sun_step_x)), 0, GX - 1)
    sy = np.clip(np.arange(GY)[:, None] + int(round(step * sun_step_y)), 0, GY - 1)
    occ = h_m[sy, sx] - step * sun_dz
    shadow = np.minimum(shadow, np.where(occ > h_m + 8.0, 0.42, 1.0))
Image.fromarray((shadow * 255).astype(np.uint8)).save(os.path.join(ASSETS, 'shadow.png'))

print('Fetching Globe Sentinel-2 (z=2)...')
glob_im = Image.new('RGB', (4 * 256, 4 * 256))
with ThreadPoolExecutor(8) as ex:
    jobs = [(x, y) for y in range(4) for x in range(4)]
    for (x, y), b in ex.map(lambda j: (j, get(f'https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/2/{j[1]}/{j[0]}.jpg')), jobs):
        glob_im.paste(Image.open(io.BytesIO(b)).convert('RGB'), (x * 256, y * 256))
glob_im.save(os.path.join(ASSETS, 'world.jpg'), quality=88)

json.dump({'bbox': bbox, 'w': GX, 'h': GY, 'h_min': float(h_m.min()), 'h_max': float(h_m.max())},
          open(os.path.join(ASSETS, 'meta.json'), 'w'), indent=1)
print('Done:', bbox, 'h_min=', h_m.min(), 'h_max=', h_m.max())
