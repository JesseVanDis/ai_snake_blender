#!/bin/bash

if [ "${1}" == "entrypoint" ]; then
  export OUTPUT_FOLDER="/dest"
  export RENDERING_ENABLED=True

#  if [ ! -z "$(ls /dest | grep frame | grep png)" ]; then
#    second_latest_frame=$(ls /dest/frame_*.png | sed -E 's/[^0-9]*([0-9]+).*/\1/' | sort -n | uniq | tail -n 2 | head -n 1 | awk '{print $1+0}')
#    if [ "${FRAME_START}" -eq "-1" ]; then
#      export FRAME_START=${second_latest_frame}
#      echo "latest frame: ${FRAME_START}"
#    fi
#  fi

  blender -b ai_presentation.blend -P main.py


else
  color_red="\033[91m"
  color_reset="\033[39m"

  script_filepath=$(basename "$0")
  script_path=$(realpath ${0})
  script_dir=$(realpath "$(dirname "$script_path")")
  cd "${script_dir}"

  scene=0
  num_cpus=0
  start_frame=-1
  end_frame=-1
  render_interval=0
  speed_multiplier=1
  server=""
  camera_name=""
  for arg in "$@"; do
      if [[ "$arg" == --scene=*    ]];         then scene="${arg#*=}";       fi
      if [[ "$arg" == --num_cpus=*    ]];      then num_cpus="${arg#*=}";    fi
      if [[ "$arg" == --start_frame=*    ]];   then start_frame="${arg#*=}"; fi
      if [[ "$arg" == --end_frame=*    ]];     then end_frame="${arg#*=}";   fi
      if [[ "$arg" == --render_interval=*  ]]; then render_interval="${arg#*=}";   fi
      if [[ "$arg" == --speed_multiplier=* ]]; then speed_multiplier="${arg#*=}";   fi
      if [[ "$arg" == --camera=*    ]];        then camera_name="${arg#*=}";       fi
      if [[ "$arg" == --server=*    ]];        then server="${arg#*=}";      fi
  done

  dest="$(pwd)/output/scene_${scene}"
  if [ ! -z "${camera_name}" ]; then
    dest="${dest}_${camera_name}"
  fi
  if [ ! -d "${dest}" ]; then
    mkdir -p "${dest}"
  fi

  if [ "${start_frame}" -lt 0 ]; then
    start_frame=0
    if [ ! -z "$(ls "${dest}" | grep frame | grep png)" ]; then
      cd "${dest}"
      start_frame=$(ls frame_*.png | sed -E 's/[^0-9]*([0-9]+).*/\1/' | sort -n | uniq | tail -n 2 | head -n 1 | awk '{print $1+0}')
      echo "starting from frame '${start_frame}'"
      cd "${script_dir}"
    fi
  fi

  if [ ! -z "${server}" ]; then
    tar --exclude='./output' --exclude='./__pycache__' --exclude='.git' --exclude='*.blend1' -czvf /tmp/archive.tar.gz .
    scp /tmp/archive.tar.gz "${server}":/tmp/

    ssh "${server}" "rm -rdf /tmp/temp_render 2>/dev/null"
    ssh "${server}" "mkdir -p /tmp/temp_render"
    ssh "${server}" "tar -xzf /tmp/archive.tar.gz -C /tmp/temp_render"
    cmd="/tmp/temp_render/render.sh --scene=${scene} --num_cpus=${num_cpus} --start_frame=${start_frame} --end_frame=${end_frame} --render_interval=${render_interval} --speed_multiplier=${speed_multiplier}"

    echo "server: ${server}"
    echo "cmd   : ${cmd}"

    touch /tmp/render_running
    (
      while test -f /tmp/render_running; do
          rsync -av --remove-source-files --ignore-existing "${server}":/tmp/temp_render/output/scene_${scene}/ ./output/scene_${scene}
          sleep 120
      done
    ) &

    ssh -t "${server}" "${cmd}"
    #rsync -av --ignore-existing "${server}":/tmp/temp_render/output/scene_${scene} ./output/
    echo "Exitting"
    rm -f /tmp/render_running
    exit 0
  fi


  if [ "${scene}" -eq "0" ]; then
    echo "please run with the scene number argument. example: render.sh --scene=3"
    echo "options examples:"
    echo "  --scene=3"
    echo "  --num_cpus=4"
    echo "  --start_frame=40"
    echo "  --end_frame=60"
    echo "  --render_interval=5"
    echo "  --speed_multiplier=0.5"
    echo "  --camera=camera_closeup"
    exit 1
  fi

  echo "Rendering scene : '${scene}'"
  echo "With num cpus   : '${num_cpus}'"
  echo "start frame     : '${start_frame}'"

  num_cpus_args=""
  if [ "$num_cpus" -gt 0 ]; then
      num_cpus_args="--cpus=${num_cpus}"
  fi

  docker build ${docker_build_extra_args} -t "iqip_ia_presentation_render" -f "${script_dir}/Dockerfile" ${script_dir} --progress=plain
  if [ "$?" -ne 0 ]; then
    printf "${color_red}failed to build iqip_ia_presentation_render docker ${color_reset} \n"
    exit 1
  fi

  cd "${script_dir}" || exit 1
  docker run "${num_cpus_args}" -it --rm --entrypoint /bin/bash -u "$(id -u):$(id -g)" -v "${dest}:/dest" -e "ACTIVE_SCENE=scene${scene}" -e "RENDER_INTERVAL=${render_interval}" -e "SPEED_MULTIPLIER=${speed_multiplier}" -e "FRAME_START=${start_frame}" -e "FRAME_END=${end_frame}" -e "CAMERA_NAME=${camera_name}" iqip_ia_presentation_render -c "/project/render.sh entrypoint"
  if [ "$?" -ne 0 ]; then
    printf "${color_red}failed to run iqip_ia_presentation_render docker ${color_reset} \n"
    exit 1
  fi
fi