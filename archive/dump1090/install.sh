#!/usr/bin/bash
apt update
apt install expect wget udev git make gcc pkg-config usbutils librtlsdr-dev 

wget https://www.sdrplay.com/software/SDRplay_RSP_API-Linux-3.15.2.run
chmod +x SDRplay_RSP_API-Linux-3.15.2.run
chmod +x ./install.exp
./install.exp

git clone https://github.com/SDRplay/dump1090
cd dump1090
SDRPLAY=1 make dump1090
cp ./dump1090 /bin/
