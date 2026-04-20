#!/bin/bash
scene="$1"
echo "${scene}"
ffmpeg -framerate 30 -pattern_type glob -i "./${scene}/frame_*.png" -f lavfi -i color=c=white:s=1280x720 -filter_complex "[1][0]overlay=shortest=1,split[a][b];[a]palettegen[p];[b][p]paletteuse" ${scene}.gif
