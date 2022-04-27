#!/bin/bash

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

if [ "$(uname)" == "Darwin" ]; then
  pyinstaller allegro.py --onefile --distpath ./dist/macos
elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
  pyinstaller allegro.py --onefile --distpath ./dist/debian
fi