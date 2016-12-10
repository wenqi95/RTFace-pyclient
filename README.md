#Overview
This is the python client for RTFace, a framework that selectively blurs a person's face based on his identity in real-time to protect user's privacy.
It leverages object tracking to achieve real-time while running face detection using [dlib](http://dlib.net), and face recognition using [OpenFace](https://cmusatyalab.github.io/openface)

#Installation
## Dependency
* OpenCV (>=2.4)
* pyQt4

```
sudo apt-get install libopencv-dev python-opencv python-qt4
```

#Run
1. modify following fields in config.py to point to correct RTFace server
  * GABRIEL_IP: RTFace Server IP
  * VIDEO_STREAM_PORT: 9098 unless you change the port when running RTFace server
  * RESULT_RECEIVING_PORT: 9101 unless you change the port when running RTFace server
2. ./ui.py
