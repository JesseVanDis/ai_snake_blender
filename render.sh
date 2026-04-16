#!/bin/bash

if [ "${1}" == "entrypoint" ]; then
  export OUTPUT_FOLDER="/dest"
  export RENDERING_ENABLED=True

  second_latest_frame=$(ls /dest/frame_*.png | sed -E 's/[^0-9]*([0-9]+).*/\1/' | sort -n | uniq | tail -n 2 | head -n 1 | awk '{print $1+0}')
  if [ "${FRAME_START}" -eq "-1" ]; then
    export FRAME_START=${second_latest_frame}
    echo "latest frame: ${FRAME_START}"
  fi

  blender -b ai_presentation.blend -P main.py

  #blender -b your_scene.blend -P your_script.py


else
  color_red="\033[91m"
  color_reset="\033[39m"

  script_filepath=$(basename "$0")
  script_path=$(realpath ${0})
  script_dir=$(realpath "$(dirname "$script_path")")

  scene=0
  num_cpus=0
  start_frame=-1
  for arg in "$@"; do
      if [[ "$arg" == --scene=*    ]];         then scene="${arg#*=}";      fi
      if [[ "$arg" == --num_cpus=*    ]];      then num_cpus="${arg#*=}";   fi
      if [[ "$arg" == --start_frame=*    ]];   then start_frame="${arg#*=}";   fi
  done

  if [ "${scene}" -eq "0" ]; then
    echo "please run with the scene number argument. example: render.sh scene=3"
    exit 1
  fi

  echo "Rendering scene : '${scene}'"
  echo "With num cpus   : '${num_cpus}'"
  echo "start frame     : '${start_frame}'"

  num_cpus_args=""
  if [ "$num_cpus" -gt 0 ]; then
      num_cpus_args="--cpus=${num_cpus}"
  fi

  dest="$(pwd)/output/scene_${scene}"
  if [ ! -d "${dest}" ]; then
    mkdir -p "${dest}"
  fi

  docker build ${docker_build_extra_args} -t "iqip_ia_presentation_render" -f "${script_dir}/Dockerfile" ${script_dir} --progress=plain
  if [ "$?" -ne 0 ]; then
    printf "${color_red}failed to build iqip_ia_presentation_render docker ${color_reset} \n"
    exit 1
  fi

  cd "${script_dir}" || exit 1
  docker run "${num_cpus_args}" -it --rm --entrypoint /bin/bash -u "$(id -u):$(id -g)" -v "${dest}:/dest" -e "ACTIVE_SCENE=scene${scene}" -e "FRAME_START=${start_frame}" iqip_ia_presentation_render -c "/project/render.sh entrypoint"
  if [ "$?" -ne 0 ]; then
    printf "${color_red}failed to run iqip_ia_presentation_render docker ${color_reset} \n"
    exit 1
  fi
fi