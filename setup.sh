#!/usr/bin/env sh

python config/venv-setup.py # creates venv, installs pip dependencies
source .venv/Scripts/activate
python config/external-dep-setup.py # determines OS, checks for installation of FFMPEG, downloads FFMPEG
#TODO 2. download FFMPEG, nssm