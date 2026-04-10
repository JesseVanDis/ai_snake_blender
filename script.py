import bpy
import math
import bmesh
import mathutils
import random
import re
from mathutils import Vector

# https://www.youtube.com/watch?v=jeoJZ8XGJCg

bpy.app.handlers.frame_change_post.clear()

STARTING_GUY_POS = Vector((0.316464, -2, 1.1086))

EPS = 1e-6
FLIPPER_DIRECTION = 90

class SceneContext:
    def __init__(self, scene, scene_obj, first_spinner_rotations = ()):
        self.scene_obj = scene_obj
        self.global_scene = scene
        self.frame_current = scene.frame_current - 2 # hacky offset, initialization stuff...
        self.children = scene_obj.children
        self.name = scene_obj.name
        self.first_spinner_rotations = first_spinner_rotations
        self.parent = None
                        
def handle_frame(scene):
    ctx_scene1 = SceneContext(scene, bpy.data.objects["scene1"], (10, 360-40, 160, 40, 80,    170, 40, 100, 190, 10, 210, 100))
    ctx_scene2 = SceneContext(scene, bpy.data.objects["scene2"])
    ctx_scene3 = SceneContext(scene, bpy.data.objects["scene3"], (180, 180, 180, 180, 180))

    # 0 is skipped on repeat, so include 1
    if scene.frame_current <= 1:
        init(ctx_scene1)
        init(ctx_scene2)
        init(ctx_scene3)
        init_scene1(ctx_scene1)
        init_scene2(ctx_scene2)
        init_scene3(ctx_scene3)

    if scene.frame_current == 1 or scene.frame_current == 2:
        reset_scene1(ctx_scene1)
        reset_scene2(ctx_scene2)
        reset_scene3(ctx_scene3)

    if scene.frame_current >= 2:
        handle_scene1(ctx_scene1)
        handle_scene2(ctx_scene2)
        handle_scene3(ctx_scene3)

        reset_scene1(ctx_scene1) if pop_reset_called(ctx_scene1) else None
        reset_scene2(ctx_scene2) if pop_reset_called(ctx_scene2) else None
        reset_scene3(ctx_scene3) if pop_reset_called(ctx_scene3) else None

def init_scene1(context):
    pass

def reset_scene1(context):
    pass

def handle_scene1(context):
    duration_multiplier = 1

    drop_spinning_wheel_start     = 1
    drop_spinning_wheel_duration  = max(2, int(5 * duration_multiplier))
    spin_spinning_wheel_start     = (drop_spinning_wheel_start + drop_spinning_wheel_duration) + 0
    spin_spinning_wheel_duration  = max(1, int(40 * duration_multiplier))
    pick_spinning_wheel_start     = (spin_spinning_wheel_start + spin_spinning_wheel_duration) + 5
    pick_spinning_wheel_duration  = max(2, int(5 * duration_multiplier))
    jump_guy_start                = (pick_spinning_wheel_start + pick_spinning_wheel_duration) + 0
    jump_guy_duration             = max(1, int(11 * duration_multiplier))
    winlose_guy_start             = (jump_guy_start + jump_guy_duration) + 1
    winlose_guy_duration          = max(1, int(5 * duration_multiplier))
    winlost_reset_start           = (winlose_guy_start + winlose_guy_duration) + max(1, int(10 * duration_multiplier))
    winlost_reset_duration        = 1
    
    step_duration = (winlost_reset_start + winlost_reset_duration)

    if (context.frame_current % step_duration) == drop_spinning_wheel_start:
        start_drop_down_spinning_wheel_animation(context, get_spinning_wheel_at_guy(context), drop_spinning_wheel_duration)
    
    if (context.frame_current % step_duration) == spin_spinning_wheel_start:
        spin_spinning_wheel(context, get_spinning_wheel_at_guy(context), get_target_rotation(context), spin_spinning_wheel_duration)

    if (context.frame_current % step_duration) == pick_spinning_wheel_start:
        start_pick_up_spinning_wheel_animation(context, get_spinning_wheel_at_guy(context), pick_spinning_wheel_duration)
    
    if (context.frame_current % step_duration) == jump_guy_start:
        check_jump_guy(context, jump_guy_duration)

    if (context.frame_current % step_duration) == winlose_guy_start:
        check_reward_or_penalty(context, winlose_guy_duration)

    if (context.frame_current % step_duration) == winlost_reset_start:
        check_action_end(context)

    handle(context)

def init_scene2(context):
    pass

def reset_scene2(context):
    spinner_tiles = find_recursive_list(context, "tile_neutral")
    for tile in spinner_tiles:
        spinning_wheel = get_spinning_wheel_at_tile(context, tile)
        start_drop_down_spinning_wheel_animation(context, spinning_wheel, 0)

def handle_scene2(context):
    duration_multiplier = 0.3

    spin_spinning_wheel_start     = 1
    spin_spinning_wheel_duration  = max(1, int(40 * duration_multiplier))
    jump_guy_start                = (spin_spinning_wheel_start + spin_spinning_wheel_duration) + 0
    jump_guy_duration             = max(1, int(11 * duration_multiplier))
    winlose_guy_start             = (jump_guy_start + jump_guy_duration) + 1
    winlose_guy_duration          = max(1, int(5 * duration_multiplier))
    winlost_reset_start           = (winlose_guy_start + winlose_guy_duration) + max(1, int(10 * duration_multiplier))
    winlost_reset_duration        = 1

    step_duration = (winlost_reset_start + winlost_reset_duration)

    if (context.frame_current % step_duration) == spin_spinning_wheel_start:
        spin_spinning_wheel(context, get_spinning_wheel_at_guy(context), get_target_rotation(context), spin_spinning_wheel_duration)

    if (context.frame_current % step_duration) == jump_guy_start:
        check_jump_guy(context, jump_guy_duration)

    if (context.frame_current % step_duration) == winlose_guy_start:
        check_reward_or_penalty(context, winlose_guy_duration)

    if (context.frame_current % step_duration) == winlost_reset_start:
        check_action_end(context)

    handle(context)

def init_scene3(context):
    spinner_tiles = find_recursive_list(context, "tile_neutral")
    for tile in spinner_tiles:
        spinning_wheel = get_spinning_wheel_at_tile(context, tile)
        start_drop_down_spinning_wheel_animation(context, spinning_wheel, 0)
        add_quality_bar_to_spinning_wheel(context, tile)

def reset_scene3(context):
    spinner_tiles = find_recursive_list(context, "tile_neutral")
    for tile in spinner_tiles:
        spinning_wheel = get_spinning_wheel_at_tile(context, tile)
        start_drop_down_spinning_wheel_animation(context, spinning_wheel, 0)

def handle_scene3(context):
    duration_multiplier = 1.0

    spin_spinning_wheel_start     = 1
    spin_spinning_wheel_duration  = max(1, int(40 * duration_multiplier))
    jump_guy_start                = (spin_spinning_wheel_start + spin_spinning_wheel_duration) + 0
    jump_guy_duration             = max(1, int(11 * duration_multiplier))
    winlose_guy_start             = (jump_guy_start + jump_guy_duration) + 1
    winlose_guy_duration          = max(1, int(5 * duration_multiplier))
    poke_guy_start                = (winlose_guy_start + winlose_guy_duration) + 1
    poke_guy_duration             = max(1, int(10 * duration_multiplier))
    winlost_reset_start           = (poke_guy_start + poke_guy_duration) + max(1, int(10 * duration_multiplier))
    winlost_reset_duration        = 1

    step_duration = (winlost_reset_start + winlost_reset_duration)

    if (context.frame_current % step_duration) == spin_spinning_wheel_start:
        spin_spinning_wheel(context, get_spinning_wheel_at_guy(context), get_target_rotation(context), spin_spinning_wheel_duration)

    if (context.frame_current % step_duration) == jump_guy_start:
        check_jump_guy(context, jump_guy_duration)

    if (context.frame_current % step_duration) == winlose_guy_start:
        check_reward_or_penalty(context, winlose_guy_duration)

    if (context.frame_current % step_duration) == poke_guy_start:
        if guy_got_reward_or_penalty(context):
            poke_guy_prev_tile(context, poke_guy_duration)

    if (context.frame_current % step_duration) == (poke_guy_start + poke_guy_duration/2):
        tile_current  = get_tile_at_guy(context)
        tile_previous = get_guy_prev_tile(context)
        penalty_or_reward = get_tile_penalty_or_reward(tile_current)
        if penalty_or_reward != 0:
            prev_tile_result = get_spinning_wheel_result(get_spinning_wheel_at_tile(context, tile_previous))
            add_quality_at_disk_section(context, get_guy_prev_tile(context), prev_tile_result, penalty_or_reward)

    if (context.frame_current % step_duration) == winlost_reset_start:
        check_action_end(context)

    handle(context)


def init(context):
    context.scene_obj.pop("reset_called", None)
    guy = get_guy(context)
    if context.frame_current <= 1:
        generated_objects = list(set(find_generated_objects(context)))
        for obj in generated_objects:
            path = get_object_path(obj)
            if not path.startswith("_ignore") and not path.startswith("_prefabs"):
                # print(f"deleting '{get_object_path(obj)}'")
                try:
                    delete_object_recursive(obj)
                except Exception as e:
                    print(f"Delete failed: {e}")

        guy.pop("num_actions_done", None)
        guy.pop("num_penalty", None)
        guy.pop("num_reward", None)
        get_text_penalty(context).data.body = "0"
        get_text_rewards(context).data.body = "0"
        reset(context)

def handle(context):
    handle_jump_guy(context)
    handle_poke_guy(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    for spinning_wheel_obj in get_spinning_wheels(context):
        handle_spinning_wheel(context, spinning_wheel_obj)

def check_jump_guy(context, duration_num_frames):
    result = get_spinning_wheel_result(get_spinning_wheel_at_guy(context))
    if result == "L":
        jump_guy(context, -1, duration_num_frames)
    else:
        jump_guy(context, 1, duration_num_frames)

def get_tile_penalty(tile):
    pen_match = re.search(r"_pen(\d+)", tile.name)
    if pen_match:
        return int(pen_match.group(1))
    return 0

def get_tile_reward(tile):
    rew_match = re.search(r"_rew(\d+)", tile.name)
    if rew_match:
        return int(rew_match.group(1))
    return 0

def get_tile_penalty_or_reward(tile):
    penalty = get_tile_penalty(tile)
    reward = get_tile_reward(tile)
    return reward - penalty

def check_reward_or_penalty(context, duration_num_frames):
    tile = get_tile_at_guy(context)
    penalty = get_tile_penalty(tile)
    reward = get_tile_reward(tile)
    if penalty > 0:
        penelize_guy(context, penalty)
    if reward > 0:
        reward_guy(context, reward)
    if name_contains_key(tile.name, "lose"):
        lose_guy(context, duration_num_frames)
    if name_contains_key(tile.name, "win"):
        win_guy(context, duration_num_frames)

def guy_got_reward_or_penalty(context):
    tile = get_tile_at_guy(context)
    return get_tile_penalty_or_reward(tile) != 0


def check_action_end(context):
    guy = get_guy(context)
    num_actions_done = get_property(guy, "num_actions_done", 0)
    guy["num_actions_done"] = (num_actions_done + 1)
    print(f"action {num_actions_done} done")
    if guy_won(context) or guy_lost(context):
        reset(context)

def get_target_rotation(context):
    num_actions_done = get_property(get_guy(context), "num_actions_done", 0)
    target_rotation = -1
    if num_actions_done < len(context.first_spinner_rotations):
        target_rotation = context.first_spinner_rotations[num_actions_done]
    return target_rotation

def reset(context):
    global STARTING_GUY_POS

    guy = get_guy(context)
    guy.location = STARTING_GUY_POS
    guy.scale = (0.1, 0.1, 0.1)
    guy.rotation_euler.x = 0
    guy.rotation_euler.y = 0
    guy.rotation_euler.z = math.radians(90)
    guy.pop("start_jump_frame", None)
    guy.pop("start_poke_frame", None)
    guy.pop("jump_direction_y", None)
    guy.pop("lost_frame", None)
    guy.pop("win_frame", None)
    reset_guy_arms(guy)

    for spinning_wheel_obj in get_spinning_wheels(context):
        reset_spinning_wheel(spinning_wheel_obj)
    for apple in find_recursive_list(context, "apple"):
        apple.location = (0,0,0)
    context.scene_obj["reset_called"] = True

def pop_reset_called(context):
    called = get_property(context.scene_obj, "reset_called", False)
    context.scene_obj.pop("reset_called", None)
    return called

def get_disk(spinning_wheel_obj):
    return find_recursive(spinning_wheel_obj, "disk")

def get_flipper(spinning_wheel_obj):
    return find_recursive(spinning_wheel_obj, "flipper")

def get_guy(context):
    return find_recursive(context, "guy")

def get_text_penalty(context):
    return find_recursive(context, "score_penalty")

def get_text_rewards(context):
    return find_recursive(context, "score_rewards")

def get_spinning_wheels(context):
    return find_recursive_list(context, "spinning_wheel_base")

def reset_guy_arms(guy):
    for arm in find_recursive_list(guy, "arm_left"):
        arm.rotation_mode = 'XYZ'
        arm.rotation_euler = (0,0,0)
        arm.scale = (1,1,1)
    for arm in find_recursive_list(guy, "arm_right"):
        arm.rotation_mode = 'XYZ'
        arm.rotation_euler = (0,0,0)
        arm.scale = (1,1,1)

def reset_spinning_wheel(spinning_wheel_obj):
    disk = get_disk(spinning_wheel_obj)
    # disk.rotation_euler.z = 0
    disk.pop("start_spin_frame", None)
    disk.pop("end_spin_frame", None)
    disk.pop("starting_angle", None)
    disk.pop("target_angle", None)
    origin = find_recursive(spinning_wheel_obj, "spinning_wheel_origin")
    origin.pop("start_drop_frame", None)
    origin.pop("end_drop_frame", None)
    origin.pop("start_pick_frame", None)
    origin.pop("end_pick_frame", None)
    origin.scale = (0, 0, 0)
    origin.hide_viewport = False
    origin.hide_render = True
    flipper = get_flipper(spinning_wheel_obj)
    flipper.pop("last_hit_frame", None)
    flipper.pop("last_offset_to_bar", None)

def is_disk_face_part_of_section(disk, face, section_label = ""):
    def angle(v):
        a = math.degrees(math.atan2(v.co.y, v.co.x))
        if a < 0:
            a += 360
        return a

    if face.normal.z < 0.9:
        return False

    if section_label == "":
        for v in face.verts:
            if abs(v.co.x) < EPS and abs(v.co.y) < EPS:
                return True

    sections = disk["sections"]

    for v in face.verts:
        if abs(v.co.x) < EPS and abs(v.co.y) < EPS:
            center_v = None
            others = []
            for v in face.verts:
                if abs(v.co.x) < EPS and abs(v.co.y) < EPS:
                    center_v = v
                else:
                    others.append(v)
            if center_v is None:
                continue
            p0 = center_v
            p1, p2 = others
            a1 = angle(p1)
            a2 = angle(p2)
            if abs(a1 - a2) > 180:
                mid_angle = ((a1 + a2 + 360) / 2)
            else:
                mid_angle = (a1 + a2) / 2
            mid_angle = mid_angle % 360
            for section in sections:
                sec_label = section["label"]
                start = section["start"]
                end = section["end"]
                if start <= mid_angle < end:
                    if section_label == sec_label:
                        return True
                    break
    return False


def setup_spinning_wheel(context, spinning_wheel_obj, chance_table):
    def angle(v):
        a = math.degrees(math.atan2(v.co.y, v.co.x))
        if a < 0:
            a += 360
        return a
    
    def material_index_from_label_object(disk_obj, label_object_name):
        label_object = next((c for c in disk_obj.children if c.name.startswith(f"choise_{label_object_name}")), None)
        if not label_object.material_slots:
            return 0  # fallback if the label has no materials
        mat_name = label_object.material_slots[0].material.name
        for i, slot in enumerate(disk_obj.material_slots):
            if slot.material and slot.material.name == mat_name:
                return i
        return 0 # fallback if not found

    
    def apply_colors(disk, sections):
        mesh = disk.data
        bm = bmesh.new()
        bm.from_mesh(mesh)
        for face in bm.faces:      
            # Only operate on top faces (normal pointing up)  
            if not is_disk_face_part_of_section(disk, face):
                continue

            for sec_label in sections:
                if is_disk_face_part_of_section(disk, face, sec_label):
                    sec_index = material_index_from_label_object(disk, sec_label)
                    if sec_index < len(mesh.materials):
                        face.material_index = sec_index

            #
            # # Only triangles that contain the center vertex (0,0)
            # center_v = None
            # others = []
            # for v in face.verts:
            #     if abs(v.co.x) < EPS and abs(v.co.y) < EPS:
            #         center_v = v
            #     else:
            #         others.append(v)
            # if center_v is None:
            #     continue
            # p0 = center_v
            # p1, p2 = others
            # a1 = angle(p1)
            # a2 = angle(p2)
            # if abs(a1 - a2) > 180:
            #     mid_angle = ((a1 + a2 + 360) / 2)
            # else:
            #     mid_angle = (a1 + a2) / 2
            # # mid_angle += 10
            # mid_angle = mid_angle % 360
            # mat_index = 0
            # for start, end, sec_label in sections:
            #     sec_index = material_index_from_label_object(disk, sec_label)
            #     if start <= mid_angle < end:
            #         if sec_index < len(mesh.materials):
            #             mat_index = sec_index
            #         break
            # face.material_index = mat_index
        bm.to_mesh(mesh)
        bm.free()
        mesh.update()
        
    def add_section_bars(disk, sections):
        template = next((c for c in disk.children if c.name.startswith("bar")), None)
        if template is None:
            print("Bar object not found")
            return
        for start, end, _ in sections:
            bar = template.copy()
            bar.name = f"gen_{template.name}"
            bpy.context.collection.objects.link(bar)
            bar.parent = disk
            bar.matrix_parent_inverse.identity()
            bar.location = (0,0,0)
            bar.rotation_euler = (0,0,math.radians(start))
            make_object_and_children_visible_to_renderer(bar)            
            
    def add_section_labels(disk, sections):
        for start, end, label in sections:
            # Find the template child whose name starts with 'choise_{label}'
            template = next((c for c in disk.children if c.name.startswith(f"choise_{label}")), None)
            if template is None:
                print(f"No template found for label {label}")
                continue
            label_obj = duplicate_object_with_children(template, disk)
            make_object_and_children_visible_to_renderer(label_obj)
            label_obj.location = (0, 0, 0)
            label_obj.rotation_euler = (0, 0, math.radians(-90 + ((start+end)/2)))
            
    def generate_sections(chance_table):
        total = sum(ch for ch, _ in chance_table)
        normalized = [(ch / total, label) for ch, label in chance_table]
        sections = []
        start_angle = 0.0
        for prob, label in normalized:
            end_angle = start_angle + prob * 360
            sections.append((start_angle, end_angle, label))
            start_angle = end_angle
        return sections

    sections = generate_sections(chance_table)
    disk = get_disk(spinning_wheel_obj)
    disk["sections"] = [
        {"start": start, "end": end, "label": label}
        for start, end, label in sections
    ]
    reset_spinning_wheel(spinning_wheel_obj)
    apply_colors(disk, sections)
    add_section_bars(disk, sections)
    add_section_labels(disk, sections)


def add_quality_bar_to_spinning_wheel(context, tile_obj):
    chance_table = get_spinning_wheel_chance_table(context, tile_obj)
    for prob, label in chance_table:
        add_quality_at_disk_section(context, tile_obj, label, 0)

def color_disk_section(context, disk_obj, section_label, color):
    disk = get_disk(disk_obj)
    mesh = disk.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    color_layer = bm.verts.layers.float_color.get("color")
    if color_layer is None:
        raise Exception("Color attribute 'color' not found") # please add a vertex_color attribute and name it "color"
    for face in bm.faces:
        if not is_disk_face_part_of_section(disk, face, section_label):
            continue
        face.material_index = 1
        for v in face.verts:
            v[color_layer] = color
    bm.to_mesh(mesh)
    bm.free()
    mesh.update()

def get_color_from_quality(quality):
    q = max(-1.0, min(1.0, quality))
    if q < 0:
        # Interpolate red -> grey
        t = q + 1  # map -1 -> 0, 0 -> 1
        r = 1.0 * (1 - t) + 0.7 * t  # 1 -> 0.7
        g = 0.0 * (1 - t) + 0.7 * t  # 0 -> 0.7
        b = 0.0 * (1 - t) + 0.7 * t  # 0 -> 0.7
    else:
        # Interpolate grey -> green
        t = q  # 0 -> 1
        r = 0.7 * (1 - t) + 0.0 * t  # 0.7 -> 0
        g = 0.7 * (1 - t) + 1.0 * t  # 0.7 -> 1
        b = 0.7 * (1 - t) + 0.0 * t  # 0.7 -> 0

    return (r, g, b, 1.0)

def add_quality_at_disk_section(context, tile_obj, section_label, quality):
    disk = get_disk(tile_obj)
    if disk is None or "sections" not in disk:
        return None

    create_colors = False
    if f"quality_{section_label}" not in disk:
        create_colors = True
    current_quality = get_property(disk, f"quality_{section_label}", 0)
    target_quality = quality
    new_quality = current_quality + (target_quality - current_quality) * 0.2
    if new_quality != current_quality:
        create_colors = True

    if create_colors:
        disk[f"quality_{section_label}"] = new_quality
        sections = disk["sections"] # list of tuples: (start_angle, end_angle, label)
        print(f"Adding quality {quality} to {tile_obj.name}. new quality: {new_quality}")
        for sec in sections:
            label = sec["label"]
            if label == section_label:
                start = sec["start"]
                end = sec["end"]
                quality_bar_obj = find_recursive(disk, f"gen_quality_bar_base_{section_label}")
                if quality_bar_obj is None:
                    print(f"create for {section_label}")
                    template = find_recursive(disk, "quality_bar_base")
                    quality_bar_obj = duplicate_object_with_children(template, disk)
                    quality_bar_obj.name = f"gen_quality_bar_base_{section_label}"
                    make_object_and_children_visible_to_renderer(quality_bar_obj)
                    quality_bar_obj["section_label"] = section_label
                    quality_bar_obj.location = (0, 0, 0)
                    quality_bar_obj.rotation_euler = (0, 0, math.radians(-90 + ((start+end)/2)))
                color_disk_section(context, disk, label, get_color_from_quality(new_quality))
                break


def handle_spinning_wheel_flipper(context, spinning_wheel_obj, snap_strength=5.0):
    disk = get_disk(spinning_wheel_obj)
    flipper = get_flipper(spinning_wheel_obj)
    if disk is None or flipper is None:
        return
    # Get all bar angles (Z rotation in degrees)
    fixed_flipper_dir = (1,0)
    smallest_dist = 100
    sign = 1
    
    for bar in disk.children:
        if bar.name.startswith("gen_bar"):
            z = (bar.rotation_euler.z + bar.parent.rotation_euler.z) + (math.pi / 2)
            direction_angle = z % (2 * math.pi)
            direction = (math.cos(direction_angle), math.sin(direction_angle))
            dist = math.dist(direction, fixed_flipper_dir)            
            if dist < smallest_dist:
                smallest_dist = dist
                fixed_vec = mathutils.Vector((fixed_flipper_dir[0], fixed_flipper_dir[1], 0))
                bar_vec   = mathutils.Vector((direction[0], direction[1], 0))
                if fixed_vec.cross(bar_vec).z < 0:
                    sign = -1
                else:
                    sign = 1
                    
    if "last_offset_to_bar" not in flipper:
        flipper["last_offset_to_bar"] = 0
    if "last_hit_frame" not in flipper:
        flipper["last_hit_frame"] = -100
        
    last_offset_to_bar = flipper["last_offset_to_bar"];
    offset_to_bar = smallest_dist * sign
    flipper["last_offset_to_bar"] = offset_to_bar
    if last_offset_to_bar <= 0 and offset_to_bar > 0:
        flipper["last_hit_frame"] = context.frame_current
    
    frames_since_hit = context.frame_current - flipper["last_hit_frame"]
    flipper_angle = (-math.pow((1/(math.pow((frames_since_hit)*1, 4)+1)), 4)) * 0.7 + math.pi # https://www.desmos.com/calculator/xycbiyqqzs?lang=nl
    flipper.rotation_euler.z = flipper_angle
    

def spin_spinning_wheel(context, spinning_wheel_obj, target_angle=-1, duration_num_frames=40, min_turns=1):
    disk = get_disk(spinning_wheel_obj)
    if disk is None:
        return
    starting_angle = math.degrees(disk.rotation_euler.z)
    actual_target_angle = target_angle
    if actual_target_angle < 0:
        random.seed(context.frame_current)  # deterministic seed
        actual_target_angle = random.uniform(0, 360)
        # print(f"spinner end angle set to: {actual_target_angle}")
    while actual_target_angle < starting_angle:
        actual_target_angle = actual_target_angle + 360
    actual_target_angle = actual_target_angle + min_turns * 360
    disk["start_spin_frame"] = context.frame_current
    disk["end_spin_frame"] = context.frame_current + duration_num_frames
    disk["starting_angle"] = math.degrees(disk.rotation_euler.z)
    disk["target_angle"] = actual_target_angle
    return context.frame_current + duration_num_frames

def handle_spinning_wheel_origin(context, spinning_wheel_obj):
    origin = find_recursive(spinning_wheel_obj, "spinning_wheel_origin")
    if origin is not None and "start_drop_frame" in origin:
        start_drop_frame = origin["start_drop_frame"]
        end_drop_frame = origin["end_drop_frame"]
        if start_drop_frame != end_drop_frame:
            anim_perc = min(max((context.frame_current - start_drop_frame) / (end_drop_frame - start_drop_frame), 0), 1)
            origin.scale = (anim_perc, anim_perc, anim_perc)
            if anim_perc >= 1:
                origin.pop("start_drop_frame", None)
                origin.pop("end_drop_frame", None)
    if origin is not None and "start_pick_frame" in origin:
        start_drop_frame = origin["start_pick_frame"]
        end_drop_frame = origin["end_pick_frame"]
        if start_drop_frame != end_drop_frame:
            anim_perc = min(max((context.frame_current - start_drop_frame) / (end_drop_frame - start_drop_frame), 0), 1)
            origin.scale = (1-anim_perc, 1-anim_perc, 1-anim_perc)
            if anim_perc >= 1:
                origin.pop("start_pick_frame", None)
                origin.pop("end_pick_frame", None)
                origin.hide_render = True

def handle_spinning_wheel(context, spinning_wheel_obj):
    handle_spinning_wheel_origin(context, spinning_wheel_obj)
    disk = get_disk(spinning_wheel_obj)
    if disk is None or "starting_angle" not in disk:
        return None
    starting_angle = disk["starting_angle"]
    target_angle = disk["target_angle"]
    start_spin_frame = disk["start_spin_frame"]
    end_spin_frame = disk["end_spin_frame"]
    if starting_angle == target_angle or start_spin_frame == end_spin_frame:
        return
    perc = max(0, min((context.frame_current - start_spin_frame) / (end_spin_frame - start_spin_frame), 1), 0)
    perc_anim = math.sin((perc)*(math.pi/2))
    disk.rotation_euler.z = math.radians(starting_angle + (target_angle - starting_angle) * perc_anim)
    handle_spinning_wheel_flipper(context, spinning_wheel_obj)


def get_spinning_wheel_result(spinning_wheel_name):
    disk = get_disk(spinning_wheel_name)
    if disk is None or "sections" not in disk:
        return None
    sections = disk["sections"] # list of tuples: (start_angle, end_angle, label)
    z_deg = ((math.degrees(disk.rotation_euler.z) + FLIPPER_DIRECTION) % 360)
    for sec in sections:
        start = sec["start"]
        end = sec["end"]
        label = sec["label"]
        if start <= z_deg < end:
            #print(f"{label}, {z_deg}")
            return label
        elif end < start and (z_deg >= start or z_deg < end):
            #print(f"{label}, {z_deg}")
            return label
    return None

def get_spinning_wheel_chance_table(context, tile_obj):
    chance_table = [(0.5,  "L"), (0.5,  "R")]
    return chance_table

def get_spinning_wheel_at_tile(context, tile_obj):
    spinning_wheel = find_recursive(tile_obj, "spinning_wheel_base")
    if spinning_wheel is None:
        # create new wheel then
        prefab_source = find_prefab(context, "spinning_wheel_base")
        spinning_wheel = duplicate_object_with_children(prefab_source, tile_obj, False)
        #print(f"Generated spinner! {prefab_source} for {tile_obj.name}")
        setup_spinning_wheel(context, spinning_wheel, get_spinning_wheel_chance_table(context, tile_obj))

    return spinning_wheel


def start_drop_down_spinning_wheel_animation(context, spinning_wheel_obj, duration_num_frames=5):
    origin = find_recursive(spinning_wheel_obj, "spinning_wheel_origin")
    origin.hide_render = False
    if duration_num_frames > 0:
        origin["start_drop_frame"] = context.frame_current
        origin["end_drop_frame"] = context.frame_current + duration_num_frames
    else:
        origin.scale = (1,1,1)

def start_pick_up_spinning_wheel_animation(context, spinning_wheel_obj, duration_num_frames=5):
    origin = find_recursive(spinning_wheel_obj, "spinning_wheel_origin")    
    origin["start_pick_frame"] = context.frame_current
    origin["end_pick_frame"] = context.frame_current + duration_num_frames
    return context.frame_current + duration_num_frames

def get_tile_at_pos(context, abs_pos):
    closest_tile = None
    min_dist = float("inf")
    tiles = find_recursive_list(context, "tile_")
    for tile in tiles:
        if tile:
            tile_pos = tile.matrix_world.translation
            dx = abs(tile_pos.x - abs_pos.x)
            dy = abs(tile_pos.y - abs_pos.y)
            if dx <= 0.5 and dy <= 0.5:
                dist = math.hypot(dx, dy)
                if dist < min_dist:
                    min_dist = dist
                    closest_tile = tile
    return closest_tile

def get_tile_at_guy(context):
    guy = get_guy(context)
    if not guy:
        return None
    return get_tile_at_pos(context, guy.matrix_world.translation)

def get_spinning_wheel_at_guy(context):
    return get_spinning_wheel_at_tile(context, get_tile_at_guy(context))

def penelize_guy(context, num_penalty):
    guy = get_guy(context)
    new_penalty_count = get_property(guy, "num_penalty", 0) + num_penalty
    guy["num_penalty"] = new_penalty_count
    get_text_penalty(context).data.body = str(new_penalty_count)
    
def reward_guy(context, num_reward):
    guy = get_guy(context)
    new_reward_count = get_property(guy, "num_reward", 0) + num_reward
    guy["num_reward"] = new_reward_count
    get_text_rewards(context).data.body = str(new_reward_count)

def get_guy_prev_tile(context):
    guy = get_guy(context)
    prev_guy_pos = Vector((get_property(guy, "jump_starting_abs_pos_x", guy.location.x), get_property(guy, "jump_starting_abs_pos_y", guy.location.y), get_property(guy, "jump_starting_abs_pos_z", guy.location.z)))
    return get_tile_at_pos(context, prev_guy_pos)

def poke_guy_prev_tile(context, duration_num_frames):
    guy = get_guy(context)
    guy["start_poke_frame"] = context.frame_current
    guy["end_poke_frame"] = context.frame_current + duration_num_frames
    guy["poke_target_x"] = get_property(guy, "jump_starting_abs_pos_x", guy.location.x) + 0.5
    guy["poke_target_y"] = get_property(guy, "jump_starting_abs_pos_y", guy.location.y)
    guy["poke_target_z"] = get_property(guy, "jump_starting_abs_pos_z", guy.location.z)

def jump_guy(context, direction_y, duration_num_frames = 11):
    guy = get_guy(context)
    pos_abs = get_world_location(guy)
    guy["start_jump_frame"] = context.frame_current
    guy["end_jump_frame"] = context.frame_current + duration_num_frames
    guy["jump_direction_y"] = direction_y
    guy["jump_starting_pos_x"] = guy.location.x
    guy["jump_starting_pos_y"] = guy.location.y
    guy["jump_starting_pos_z"] = guy.location.z
    guy["jump_starting_abs_pos_x"] = pos_abs.x
    guy["jump_starting_abs_pos_y"] = pos_abs.y
    guy["jump_starting_abs_pos_z"] = pos_abs.z

def lose_guy(context, duration_num_frames = 10):
    guy = get_guy(context)
    guy["lost_frame"] = context.frame_current
    guy["lost_frame_end"] = context.frame_current + duration_num_frames
    
def win_guy(context, duration_num_frames = 3):
    guy = get_guy(context)
    guy["win_frame"] = context.frame_current
    guy["win_frame_end"] = context.frame_current + duration_num_frames
    
def guy_won(context):
    guy = get_guy(context)
    return get_property(guy, "win_frame", -1) >= 0
    
def guy_lost(context):
    guy = get_guy(context)
    return get_property(guy, "lost_frame", -1) >= 0

def handle_win_guy(context):
    guy = get_guy(context)
    win_frame = get_property(guy, "win_frame", -1)
    win_frame_end = get_property(guy, "win_frame_end", -1)
    if win_frame >= 0:
        anim = max(0, min((context.frame_current - win_frame) / (win_frame_end - win_frame), 1), 0)
        apple_pos_x = 0.3
        frames_since_win = context.frame_current - win_frame
        tile = get_tile_at_guy(context)
        apple = find_recursive(tile, "apple")
        guy_pos = get_world_location(guy)
        guy_forward = get_world_forward(guy)
        old_apple_pos = get_world_location(apple.parent)
        target_apple_pos = guy_pos + guy_forward * apple_pos_x + Vector((0, 0, 0.5));
        new_apple_pos = old_apple_pos + (target_apple_pos - old_apple_pos) * anim
        set_world_location(apple, new_apple_pos)                

def handle_lost_guy(context):
    global STARTING_GUY_POS
    guy = get_guy(context)
    lost_frame = get_property(guy, "lost_frame", -1)
    lost_frame_end = get_property(guy, "lost_frame_end", -1)
    if lost_frame >= 0:
        anim = max(0, min((context.frame_current - lost_frame) / (lost_frame_end - lost_frame), 1), 0)
        starting_rot_y = STARTING_GUY_POS.z
        target_rot_y = -90
        new_rot_y = starting_rot_y + (target_rot_y - starting_rot_y) * anim
        guy.rotation_euler.y = math.radians(new_rot_y)
        guy.location.z = starting_rot_y + math.sin(anim * math.pi * 0.9) * 0.4

def handle_poke_guy(context):
    guy = get_guy(context)
    if guy is None or "start_poke_frame" not in guy:
        return None
    start_frame = guy["start_poke_frame"]
    end_frame = guy["end_poke_frame"]
    poke_target = Vector((guy["poke_target_x"], guy["poke_target_y"], guy["poke_target_z"]))
    anim = max(0, min((context.frame_current - start_frame) / (end_frame - start_frame), 1), 0)
    arm_left = find_recursive(guy, "arm_left")
    arm_right = find_recursive(guy, "arm_right")
    arm_to_use = arm_right
    diff_arm_right = Vector(get_world_location(arm_right) - poke_target)
    diff_arm_left  = Vector(get_world_location(arm_left)  - poke_target)
    distance = diff_arm_right.length
    if diff_arm_left.length < diff_arm_right.length:
        arm_to_use = arm_left
        distance = diff_arm_left.length
    #print(f"distance: {distance}, scale {get_world_scale(arm_to_use).z}")
    point_object_to(poke_target, arm_to_use)
    arm_to_use.scale.z = 1 + ((distance-1) * math.sin(anim*math.pi)) * 25
    if anim >= 1:
        guy.pop("start_poke_frame", None)
        reset_guy_arms(guy)

def handle_jump_guy(context):
    global STARTING_GUY_POS
    guy = get_guy(context)
    if guy is None or "start_jump_frame" not in guy:
        return None

    start_frame = guy["start_jump_frame"]
    end_frame = guy["end_jump_frame"]
    direction_y = guy["jump_direction_y"]
    jump_starting_pos_y = guy["jump_starting_pos_y"]
    total_anim = max(0, min((context.frame_current - start_frame) / (end_frame - start_frame), 1), 0)
        
    facing_direction = 0
    if direction_y > 0:
        facing_direction = 180
    if direction_y < 0:
        facing_direction = 0
    facing_direction_start = 90
    
    anim_turn          = remap(total_anim,  0, 0.3, 0, 1)
    anim_jump          = remap(total_anim,  0.3, 0.7, 0, 1)
    anim_turn_back     = remap(total_anim,  0.7, 1.0, 0, 1)    
    
    target_y = jump_starting_pos_y - direction_y
        
    if anim_turn >= 0 and anim_turn <= 1:
        guy.scale = (0.1, 0.1, 0.1 - anim_turn * 0.02)
        guy.rotation_euler.z = math.radians(facing_direction_start + (anim_turn * (facing_direction-facing_direction_start)))
    if anim_jump >= 0 and anim_jump <= 1:
        guy.scale = (0.1, 0.1, 0.1)
        guy.location.y = jump_starting_pos_y + (target_y - jump_starting_pos_y) * anim_jump
        guy.location.z = STARTING_GUY_POS.z + math.sin(anim_jump * math.pi)
        guy.rotation_euler.z = math.radians(facing_direction_start + (facing_direction-facing_direction_start))
    if anim_turn_back >= 0 and anim_turn_back <= 1:
        guy.scale = (0.1, 0.1, 0.08 + anim_turn_back * 0.02)
        guy.location.y = target_y
        guy.location.z = STARTING_GUY_POS.z
        guy.rotation_euler.z = math.radians(facing_direction_start + ((1-anim_turn_back) * (facing_direction-facing_direction_start)))
    if anim_turn_back >= 1:
        guy.location.y = target_y
        guy.location.z = STARTING_GUY_POS.z
        guy.rotation_euler.z = math.radians(facing_direction_start)
        guy.scale = (0.1, 0.1, 0.1)
        guy.pop("start_jump_frame", None)
        guy.pop("jump_direction_y", None)


# register handler once
if handle_frame not in bpy.app.handlers.frame_change_post:
    bpy.app.handlers.frame_change_post.append(handle_frame)
    
    
# ========= UTIL FUNCTIONS ===========
def duplicate_object_with_children(template, parent, reference = True, is_root = True):
    # Duplicate the template (linked mesh)
    obj = template.copy()
    if is_root and not template.name.startswith("gen_"):
        obj.name = f"gen_{template.name}"
    
    # Copy the object data so it is not linked
    if not reference:
        if obj.data:
            obj.data = template.data.copy()
            
    bpy.context.collection.objects.link(obj)

    # Parent to the provided parent
    obj.parent = parent
    obj.matrix_parent_inverse.identity()

    # Position & rotate
    if is_root:
        obj.location = (0,0,0)
        obj.rotation_euler = (0,0,0)

    # Recursively duplicate children
    for child in template.children:
        duplicate_object_with_children(child, obj, reference, False)

    return obj

def make_object_and_children_visible_to_renderer(obj):
    obj.hide_viewport = False
    obj.hide_render = False
    for child in obj.children:
        make_object_and_children_visible_to_renderer(child)
    
def delete_object_recursive(obj):
    if obj is None:
        return
    # First delete all children recursively
    children = list(obj.children)
    for child in children:
        delete_object_recursive(child)

    # Then unlink and remove this object
    for col in obj.users_collection:
        col.objects.unlink(obj)
    bpy.data.objects.remove(obj)        

def name_contains_key(name, key):
    if ("_" + key + "_") in name:
        return True
    if ("_" + key + ".") in name:
        return True
    if name.endswith("_" + key):
        return True
    return name == key

def get_property(object, name, default_value):
    if name not in object:
        return default_value
    else:
        return object[name]

def set_world_location(obj, world_pos):
    world_pos = Vector(world_pos)
    if obj.parent:
        obj.location = obj.parent.matrix_world.inverted() @ world_pos
    else:
        obj.location = world_pos

def get_world_location(obj):
    return obj.matrix_world.translation.copy()

def get_world_scale(obj):
    return obj.matrix_world.to_scale()

def get_world_forward(obj):
    return obj.matrix_world.to_quaternion() @ Vector((0, 1, 0))

def get_world_left(obj):
    return obj.matrix_world.to_quaternion() @ Vector((1, 0, 0))

def remap(x, in_min, in_max, out_min, out_max):
    return out_min + (x - in_min) * (out_max - out_min) / (in_max - in_min)

def remap_clamped(x, in_min, in_max, out_min, out_max):
    t = max(0.0, min(1.0, (x - in_min) / (in_max - in_min)))
    return out_min + t * (out_max - out_min)

def should_ignore(obj, allow_prefab = False):
    path = get_object_path(obj)
    if path.startswith("_ignore"):
        return True
    elif path.startswith("_prefabs") and not allow_prefab:
        return True
    else:
        return False

def unique_list(lst):
    seen = set()
    result = []
    for item in lst:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

def find_prefab(context, name):
    return find_recursive(context.global_scene.objects["_prefabs"], name, True)

def find_recursive(obj, name, allow_prefab = False):
    if obj == None:
        return None
        
    if not should_ignore(obj, allow_prefab) and (obj.name.startswith(name + ".") or obj.name.startswith("gen_" + name + ".") or obj.name == name or obj.name == ("gen_" + name)):
        return obj
    for child in obj.children:
        if not should_ignore(child, allow_prefab):
            found = find_recursive(child, name, allow_prefab)
            if found:
                return found
    return None

def find_recursive_list(obj, name):
    matches = []
    if obj == None:
        return matches
    if isinstance(obj, bpy.types.Scene):
        for real_obj in obj.objects:
            if not should_ignore(real_obj):
                matches.extend(find_recursive_list(real_obj, name))
        return unique_list(matches)
    else:
        if obj.name.startswith(name + ".") or obj.name == name or obj.name.startswith("gen_" + name + ".") or obj.name == ("gen_" + name) or (obj.name.startswith(name) and name.endswith("_")):
            matches.append(obj)
        for child in obj.children:
            if not should_ignore(child):
                matches.extend(find_recursive_list(child, name))
        return unique_list(matches)
    
def find_generated_objects(obj):
    matches = []
    if obj == None:
        return matches
    if isinstance(obj, bpy.types.Scene):
        for real_obj in obj.objects:
            matches.extend(find_generated_objects(real_obj))
        return unique_list(matches)
    else:
        if obj.name.startswith("gen_"):
            matches.append(obj)
        else:
            for child in obj.children:
                matches.extend(find_generated_objects(child))
        return unique_list(matches)

def get_object_path(obj):
    parts = []
    while obj:
        try:
            parts.append(obj.name)
            obj = obj.parent
        except ReferenceError:
            break
    return "/".join(reversed(parts))

def point_object_to(world_pos, obj, track_axis='Z', up_axis='Y'):
    world_pos = Vector(world_pos)
    obj_world_pos = obj.matrix_world.translation
    direction = obj_world_pos - world_pos
    if direction.length == 0:
        return  # avoid invalid rotation
    rot_world = direction.normalized().to_track_quat(track_axis, up_axis)
    if obj.parent:
        parent_world_rot = obj.parent.matrix_world.to_quaternion()
        rot_local = parent_world_rot.inverted() @ rot_world
    else:
        rot_local = rot_world
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = rot_local

# ========= NO LONGER USED ===========

