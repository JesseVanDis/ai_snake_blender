#!/usr/bin/env bash

scene="${1}"

src="./${scene}"
dst="./${scene}_filtered"
frame_skip=${2} #2   # 1 = keep all, 2 = every 2nd, 3 = every 3rd, etc.

mkdir -p "$dst"

last_kept=-1
i=0

for f in "$src"/frame_*.png; do
    num=$(basename "$f" | sed -E 's/frame_([0-9]+)\.png/\1/')
    num=$((10#$num))  # force base 10

    # keep if enough "time" has passed
    if (( last_kept < 0 || num - last_kept >= frame_skip )); then
        #printf -v new "frame_%06d.png" "$i"
	filename=$(basename ${f})
	#echo "copying '${f}' to '${dst}/${filename}'"
        cp "$f" "$dst/$filename"
        last_kept=$num
        ((i++))
    fi
done


echo "Done. Kept $i frames in $dst"
