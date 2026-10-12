#!/bin/sh
# Inputs not stored in the repo (sizes as of 2026-10-12). Run from this folder.
set -e
mkdir -p data/n02
for f in ne_10m_land ne_10m_lakes; do
  curl -sSL -o data/$f.geojson https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/$f.geojson
done
curl -sSL -o /tmp/N02-23.zip https://nlftp.mlit.go.jp/ksj/gml/data/N02/N02-23/N02-23_GML.zip
python3 -I -c "import zipfile; z=zipfile.ZipFile('/tmp/N02-23.zip'); [open('data/n02/'+n.split('/')[-1],'wb').write(z.read(n)) for n in ('UTF-8/N02-23_RailroadSection.geojson','UTF-8/N02-23_Station.geojson')]"
python3 terrain.py   # AWS Terrarium tiles, zoom 10, into data/elev.npz
