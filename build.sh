#!/bin/bash

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install pyinstaller

if [ "$(uname)" == "Darwin" ]; then
  $DIST_PATH = "./dist/macos"
elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
  $DIST_PATH = "./dist/debian"
fi

pyinstaller allegro.py --onefile --distpath $DIST_PATH