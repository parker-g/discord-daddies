#!/usr/bin/env sh
# on linux, run this script with root permissions: `sudo bash setup.sh`

# provides a setup which can be used from an ssh context without x-11 forwarding
system=$(uname)
python config/venv-setup.py # creates venv, installs pip dependencies
source .venv/Scripts/activate
python config/external-dep-setup.py # determines OS, checks for installation of FFMPEG, downloads FFMPEG. downloads NSSM and installs ParkBot as a Windows service if OS is Windows
if [ ${system} = "Linux" ]; then
    python config/linux-service-manager.py
fi 