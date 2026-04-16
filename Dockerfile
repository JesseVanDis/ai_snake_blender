FROM linuxserver/blender:4.4.3

# Avoid interactive prompts
WORKDIR /
RUN mkdir project

COPY script.py /project/script.py
COPY main.py /project/main.py
COPY render.sh /project/render.sh
COPY ai_presentation.blend /project/ai_presentation.blend
COPY *.png /project/
COPY *.hdr /project/

WORKDIR /project

# Default command
CMD ["/project/render.sh", "entrypoint"]