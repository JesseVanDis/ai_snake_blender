import bpy
import math
import bmesh
import mathutils
import os
import sys
import time

project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_dir)

import script

if script.FRAME_START >= 0:
    scene = bpy.context.scene
    frame_index=0
    did_render = False
    while frame_index < scene.frame_end:
        scene.frame_set(frame_index)
        script._should_render = frame_index > script.FRAME_START
        if not did_render and script._should_render:
            print(f"Render now activated at frame {frame_index}")
            did_render = True
        print(f"Handling frame '{frame_index}'")
        script.handle_frame(scene)
        frame_index = frame_index + 1
else:
    # register handler once
    if script.handle_frame not in bpy.app.handlers.frame_change_post:
        bpy.app.handlers.frame_change_post.append(script.handle_frame)
