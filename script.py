import bpy
import math
import bmesh
import mathutils
import random
import re
from mathutils import Vector

bpy.app.handlers.frame_change_post.clear()

TARGET_OBJECT = "guy"
SPINNING_WHEEL_NAME = "spinning_wheel_base"

starting_guy_pos = Vector((0.316464, 0, 1.1086))
first_spinner_rotations = (10, 360-40, 160, 40, 80,    170, 40, 100, 190, 10, 210, 100)
#first_spinner_rotations = (10, 360-40, 40, 80)

EPS = 1e-6
FLIPPER_DIRECTION = 90

class SceneContext:
    def __init__(self, scene, scene_obj):
        self.scene_obj = scene_obj
        self.global_scene = scene
        self.frame_current = scene.frame_current
        self.children = scene_obj.children
        self.name = scene_obj.name
                        
def handle_frame(scene):
    handle_scene(SceneContext(scene, bpy.data.objects["scene1"]))


def handle_scene(context):
    guy = get_guy(context)
    num_actions_done = get_property(guy, "num_actions_done", 0)

    # 0 is skipped on repeat, so include 1
    if context.frame_current <= 1:
        guy.pop("num_actions_done", None)
        guy.pop("num_penalty", None)
        guy.pop("num_reward", None)
        get_text_penalty(context).data.body = "0"
        get_text_rewards(context).data.body = "0"

        reset(context)
        #chance_table = [(0.5,  "L"), (0.5,  "R")]
        #for spinning_wheel_obj in find_recursive_list(context, SPINNING_WHEEL_NAME):
        #    setup_spinning_wheel(context, spinning_wheel_obj, chance_table)
        
    duration_multiplier = 1
        
    drop_spinning_wheel_start     = 1
    if context.frame_current < 5:
        drop_spinning_wheel_start = 2
    
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
        target_rotation = -1
        if num_actions_done < len(first_spinner_rotations):
            target_rotation = first_spinner_rotations[num_actions_done]
        #print(f"{num_actions_done}, {target_rotation}")
        spin_spinning_wheel(context, get_spinning_wheel_at_guy(context), target_rotation, spin_spinning_wheel_duration)

    if (context.frame_current % step_duration) == pick_spinning_wheel_start:
        start_pick_up_spinning_wheel_animation(context, get_spinning_wheel_at_guy(context), pick_spinning_wheel_duration)
    
    if (context.frame_current % step_duration) == jump_guy_start:
        result = get_spinning_wheel_result(get_spinning_wheel_at_guy(context))
        if result == "L":
            jump_guy(context, -1, jump_guy_duration)
        else:
            jump_guy(context, 1, jump_guy_duration)

    if (context.frame_current % step_duration) == winlose_guy_start:
        tile = get_tile_at_guy(context)
        pen_match = re.search(r"_pen(\d+)", tile.name)
        rew_match = re.search(r"_rew(\d+)", tile.name)
        if pen_match:
            penelize_guy(context, int(pen_match.group(1)))
        if rew_match:
            reward_guy(context, int(rew_match.group(1)))
        if "_lose_" in tile.name:
            lose_guy(context, winlose_guy_duration)
        if "_win_" in tile.name:
            win_guy(context, winlose_guy_duration)

    if (context.frame_current % step_duration) == winlost_reset_start:
        guy["num_actions_done"] = (num_actions_done + 1)
        print(f"action {num_actions_done} done")
        if guy_won(context) or guy_lost(context):
            reset(context)
                    
    handle_jump_guy(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    for spinning_wheel_obj in find_recursive_list(context, SPINNING_WHEEL_NAME):
        handle_spinning_wheel(context, spinning_wheel_obj)
    

def handle(context):
    handle_jump_guy(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    for spinning_wheel_obj in find_recursive_list(context, SPINNING_WHEEL_NAME):
        handle_spinning_wheel(context, spinning_wheel_obj)

def reset(context):
    global starting_guy_pos
    generated_objects = list(set(find_generated_objects(context)))
    for obj in generated_objects:
        path = get_object_path(obj)
        if not path.startswith("_ignore") and not path.startswith("_prefabs"):
            # print(f"deleting '{get_object_path(obj)}'")
            try:
                delete_object_recursive(obj)
            except Exception as e:
                print(f"Delete failed: {e}")
    
    guy = get_guy(context)
    guy.location = starting_guy_pos
    guy.scale = (0.1, 0.1, 0.1)
    guy.rotation_euler.x = 0
    guy.rotation_euler.y = 0
    guy.rotation_euler.z = math.radians(90)
    guy.pop("start_jump_frame", None)
    guy.pop("jump_direction_y", None)
    guy.pop("lost_frame", None)
    guy.pop("win_frame", None)
    for spinning_wheel_obj in find_recursive_list(context, SPINNING_WHEEL_NAME):
        reset_spinning_wheel(spinning_wheel_obj)
    for apple in find_recursive_list(context, "apple"):
        apple.location = (0,0,0)

def get_disk(spinning_wheel_obj):
    return find_recursive(spinning_wheel_obj, "disk")

def get_flipper(spinning_wheel_obj):
    return find_recursive(spinning_wheel_obj, "flipper")

def get_guy(context):
    guy = bpy.data.objects[TARGET_OBJECT]
    return guy

def get_text_penalty(context):
    return bpy.data.objects["score_penalty"]

def get_text_rewards(context):
    return bpy.data.objects["score_rewards"]

def reset_spinning_wheel(spinning_wheel_obj):
    disk = get_disk(spinning_wheel_obj)
    disk.rotation_euler.z = 0
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

def setup_spinning_wheel(context, spinning_wheel_obj, chance_table):
    disk = get_disk(spinning_wheel_obj)
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
            if face.normal.z < 0.9:
                continue
            # Only triangles that contain the center vertex (0,0)
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
            # mid_angle += 10
            mid_angle = mid_angle % 360
            mat_index = 0
            for start, end, sec_label in sections:
                sec_index = material_index_from_label_object(disk, sec_label)
                if start <= mid_angle < end:
                    if sec_index < len(mesh.materials):
                        mat_index = sec_index
                    break
            face.material_index = mat_index
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

    disk = get_disk(spinning_wheel_obj)        
    reset_spinning_wheel(spinning_wheel_obj)
    sections = generate_sections(chance_table)
    apply_colors(disk, sections)
    add_section_bars(disk, sections)
    add_section_labels(disk, sections)
    disk["sections"] = [
        {"start": start, "end": end, "label": label}
        for start, end, label in sections
    ]


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

def get_spinning_wheel_at_tile(context, tile_obj):
    spinning_wheel = find_recursive(tile_obj, SPINNING_WHEEL_NAME)
    if spinning_wheel is None:
        # create new wheel then
        prefab_source = find_prefab(context, SPINNING_WHEEL_NAME)
        spinning_wheel = duplicate_object_with_children(prefab_source, tile_obj, False)
        #print(f"Generated spinner! {prefab_source} for {tile_obj.name}")
        chance_table = [(0.5,  "L"), (0.5,  "R")]
        setup_spinning_wheel(context, spinning_wheel, chance_table)

    return spinning_wheel


def start_drop_down_spinning_wheel_animation(context, spinning_wheel_obj, duration_num_frames=5):
    origin = find_recursive(spinning_wheel_obj, "spinning_wheel_origin")    
    origin["start_drop_frame"] = context.frame_current
    origin["end_drop_frame"] = context.frame_current + duration_num_frames
    origin.hide_render = False
    return context.frame_current + duration_num_frames

def start_pick_up_spinning_wheel_animation(context, spinning_wheel_obj, duration_num_frames=5):
    origin = find_recursive(spinning_wheel_obj, "spinning_wheel_origin")    
    origin["start_pick_frame"] = context.frame_current
    origin["end_pick_frame"] = context.frame_current + duration_num_frames
    return context.frame_current + duration_num_frames

def get_tile_at_guy(context):
    guy = bpy.data.objects[TARGET_OBJECT]
    if not guy:
        return None

    closest_tile = None
    min_dist = float("inf")    
    tiles = find_recursive_list(context, "tile_")
    guy_pos = guy.matrix_world.translation
    for tile in tiles:
        if tile:
            tile_pos = tile.matrix_world.translation
            dx = abs(tile_pos.x - guy_pos.x)
            dy = abs(tile_pos.y - guy_pos.y)
            if dx <= 0.5 and dy <= 0.5:
                dist = math.hypot(dx, dy)
                if dist < min_dist:
                    min_dist = dist
                    closest_tile = tile
    return closest_tile

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

def jump_guy(context, direction_y, duration_num_frames = 11):
    guy = get_guy(context)
    guy["start_jump_frame"] = context.frame_current
    guy["end_jump_frame"] = context.frame_current + duration_num_frames
    guy["jump_direction_y"] = direction_y
    guy["jump_starting_y"] = guy.location.y

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
    global starting_guy_pos    
    guy = get_guy(context)
    lost_frame = get_property(guy, "lost_frame", -1)
    lost_frame_end = get_property(guy, "lost_frame_end", -1)
    if lost_frame >= 0:
        anim = max(0, min((context.frame_current - lost_frame) / (lost_frame_end - lost_frame), 1), 0)
        starting_rot_y = starting_guy_pos.z
        target_rot_y = -90
        new_rot_y = starting_rot_y + (target_rot_y - starting_rot_y) * anim
        guy.rotation_euler.y = math.radians(new_rot_y)
        guy.location.z = starting_rot_y + math.sin(anim * math.pi * 0.9) * 0.4

def handle_jump_guy(context):
    global starting_guy_pos    
    guy = get_guy(context)
    frame = context.frame_current
    if guy is None or "start_jump_frame" not in guy:
        return None

    start_frame = guy["start_jump_frame"]
    end_frame = guy["end_jump_frame"]
    direction_y = guy["jump_direction_y"]
    jump_starting_y = guy["jump_starting_y"]
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
    
    target_y = jump_starting_y - direction_y
        
    if anim_turn >= 0 and anim_turn <= 1:
        guy.scale = (0.1, 0.1, 0.1 - anim_turn * 0.02)
        guy.rotation_euler.z = math.radians(facing_direction_start + (anim_turn * (facing_direction-facing_direction_start)))
    if anim_jump >= 0 and anim_jump <= 1:
        guy.scale = (0.1, 0.1, 0.1)
        guy.location.y = jump_starting_y + (target_y - jump_starting_y) * anim_jump
        guy.location.z = starting_guy_pos.z + math.sin(anim_jump * math.pi)
        guy.rotation_euler.z = math.radians(facing_direction_start + (facing_direction-facing_direction_start))
    if anim_turn_back >= 0 and anim_turn_back <= 1:
        guy.scale = (0.1, 0.1, 0.08 + anim_turn_back * 0.02)
        guy.location.y = target_y
        guy.location.z = starting_guy_pos.z
        guy.rotation_euler.z = math.radians(facing_direction_start + ((1-anim_turn_back) * (facing_direction-facing_direction_start)))
    if anim_turn_back >= 1:
        guy.location.y = target_y
        guy.location.z = starting_guy_pos.z
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

def get_property(object, name, default_value = 0):
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

# ========= NO LONGER USED ===========

