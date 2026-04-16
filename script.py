import bpy
import math
import bmesh
import mathutils
import random
import re
import os
import time
from mathutils import Vector

# https://www.youtube.com/watch?v=jeoJZ8XGJCg

def getenv_int(name, default=0):
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default

def getenv_float(name, default=0.0):
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default

debug_scene="scene9"

_should_render = False
RENDERING_ENABLED = os.getenv("RENDERING_ENABLED", "False") == "False"
OUTPUT_FOLDER = os.getenv("OUTPUT_FOLDER", "//output/")
FRAME_START = getenv_int("FRAME_START", -1)
FRAME_END = getenv_int("FRAME_END", -1)
ACTIVE_SCENE = os.getenv("ACTIVE_SCENE", "")
RENDER_INTERVAL = getenv_int("RENDER_INTERVAL", 0)
SPEED_MULTIPLIER = getenv_float("SPEED_MULTIPLIER", 1.0)
STARTING_GUY_POS = Vector((0.316464, 0, 1.1086))
GUY_POS_STATE_TILE_OFFSET = Vector((-0.2696, 0, 0.32991))
ACTION_TILE_POS_Z = 0.747776

_frames_until_render = 0

EPS = 1e-6
FLIPPER_DIRECTION = 90


class SceneContext:
    def __init__(self, scene, scene_obj, first_spinner_rotations = (), guy_starting_pos: Vector = STARTING_GUY_POS, quality_multiplier = 0.4, quality_bleeds_over = False, chance_table = [(0.5,  "W"), (0.5,  "E")]):
        self.scene_obj = scene_obj
        self.global_scene = scene
        self.frame_current = scene.frame_current - 3 # hacky offset, initialization stuff...
        self.children = scene_obj.children
        self.name = scene_obj.name
        self.first_spinner_rotations = first_spinner_rotations
        self.guy_starting_pos = guy_starting_pos
        self.parent = None
        self.obj_guy = None
        self.quality_multiplier = quality_multiplier # aka. alpha
        self.action_duration_num_frames = 0
        self.quality_bleeds_over = quality_bleeds_over
        self.gamma = 0.8  # max bleedover value perc compared to neighbour
        self.chance_table = chance_table
        self.first_snake_apple_location = [Vector((3, -1.7))]

def render_and_save_current_frame(folder):
    scene = bpy.context.scene
    frame = scene.frame_current
    folder = bpy.path.abspath(folder)
    os.makedirs(folder, exist_ok=True)
    filepath = os.path.join(folder, f"frame_{frame:06d}.png")
    scene.render.filepath = filepath
    bpy.ops.render.render(write_still=True)

_last_frame = None

def handle_frame(scene):
    global _last_frame
    global _should_render
    global _frames_until_render
    frame = scene.frame_current
    if frame == _last_frame:
        return
    _last_frame = frame

    timer_start = time.perf_counter()

    configs_candidates = [
        ("scene1", ((10, 360-40, 160, 40, 80, 170, 40, 100, 190, 10, 210, 100), STARTING_GUY_POS)),
        ("scene2", ()),
        ("scene3", ((180, 180, 180, 180, 180), Vector((STARTING_GUY_POS.x, STARTING_GUY_POS.y - 2, STARTING_GUY_POS.z)))),
        ("scene4", ((0, 0, 0, 0, 0), Vector((STARTING_GUY_POS.x, STARTING_GUY_POS.y + 2, STARTING_GUY_POS.z)), 0.4)),
        ("scene5", ((180, 0, 180, 180, 180, 0, 0, 180, 0, 0, 0), STARTING_GUY_POS, 0.4)),
        ("scene6", ((180), STARTING_GUY_POS)),
        ("scene7", ((180), STARTING_GUY_POS, 0.3)),
        ("scene8", ((), STARTING_GUY_POS, 0.3)),
        ("scene9", ((180), STARTING_GUY_POS, 0.7, True)),
        ("scene10", ((), STARTING_GUY_POS, 0.5, True, [(0.5,  "N"), (0.5,  "E"), (0.5,  "S"), (0.5,  "W")])),
        ("scene11", ((120, 120, 120, 120, 120, 120, 120), Vector((11.2696, 14, 1.07769)), 0.5, True, [(0.5,  "N"), (0.5,  "E"), (0.5,  "S"), (0.5,  "W")])),
    ]

    config = next((cfg for cfg in configs_candidates if cfg[0] == ACTIVE_SCENE), None)
    configs = []
    if config is None:
        if debug_scene is not None:
            debug_config = next((cfg for cfg in configs_candidates if cfg[0] == debug_scene), None)
            configs.append(debug_config)
        else:
            configs = configs_candidates
    else:
        configs.append(config)

    ctxs = []

    for name, extra_args in configs:
        obj = bpy.data.objects[name]
        ctx = SceneContext(scene, obj, *extra_args)
        ctxs.append((name, ctx))

    if scene.frame_current == 0 or scene.frame_current == 1:
        for _, ctx in ctxs:
            init(ctx)

        if len(configs) == 1:
            camera = find_recursive(ctx, ctx, "Camera", False, 2)
            print(f"Assigning '{camera.name}' as render camera")
            bpy.context.scene.camera = camera

        delete_generated_meshes()
        reset_snake(scene)
        delete_trashed_objects(scene)

    if scene.frame_current == 1 or scene.frame_current == 2:
        for name, ctx in ctxs:
            time_function(globals()[f"reset_{name}"], ctx, True)

    if scene.frame_current >= 3:
        for name, ctx in ctxs:
            globals()[f"handle_{name}"](ctx)

        for name, ctx in ctxs:
            if pop_reset_called(ctx):
                globals()[f"reset_{name}"]( ctx, False)

    timer_end = time.perf_counter()
    duration_us = (timer_end - timer_start) * 1_000_000
    #print(f"frame {scene.frame_current} took {duration_us:.1f} µs")
    if _should_render and scene.frame_current > 2:
        if _frames_until_render <= 0:
            print(f"Rendering frame '{scene.frame_current}'...")
            render_and_save_current_frame(OUTPUT_FOLDER)
            _frames_until_render = RENDER_INTERVAL
        _frames_until_render = _frames_until_render - 1

def reset_scene1(context, first_time):
    pass

def handle_scene1(context):
    duration_multiplier = 1.0 * SPEED_MULTIPLIER
    checks = [
        # check function name,                       duration
        ("check_drop_down_spinning_wheel",           5),
        ("check_spin_wheel",                         40),
        ("check_pick_up_spinning_wheel",             5),
        ("check_jump_guy",                           11),
        ("check_reward_or_penalty",                  5),
        ("check_pause",                              10),
        ("check_action_end",                         1)
    ]

    handle_checks(context, checks, duration_multiplier)
    handle(context)


def reset_scene2(context, first_time):
    spinner_tiles = find_recursive_list(context, context, "tile_neutral")
    for tile in spinner_tiles:
        spinning_wheel = get_spinning_wheel_at_tile(context, tile)
        start_drop_down_spinning_wheel_animation(context, spinning_wheel, 0)

def handle_scene2(context):
    duration_multiplier = 0.3 * SPEED_MULTIPLIER
    checks = [
        # check function name,         duration
        ("check_spin_wheel",           40),
        ("check_jump_guy",             11),
        ("check_reward_or_penalty",    5),
        ("check_pause",                10),
        ("check_action_end",           1)
    ]

    handle_checks(context, checks, duration_multiplier)
    handle(context)


def reset_scene3(context, first_time):
    for tile in find_recursive_list(context, context, "tile_neutral"):
        start_drop_down_spinning_wheel_animation(context, get_spinning_wheel_at_tile(context, tile), 0)
        if first_time:
            add_quality_bar_to_spinning_wheel(context, tile)

def handle_scene3(context):
    duration_multiplier = 1.0 * SPEED_MULTIPLIER

    checks = [
        # check function name,         duration
        ("check_spin_wheel",           40),
        ("check_jump_guy",             11),
        ("check_reward_or_penalty",    5),
        ("check_set_quality_by_poke",  10),
        ("check_action_end",           1)
    ]

    handle_checks(context, checks, duration_multiplier)
    handle_jump_guy(context)
    handle_poke_guy(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    handle_spinning_wheels(context)

def reset_scene4(context, first_time):
    for tile in find_recursive_list(context, context, "tile_neutral"):
        start_drop_down_spinning_wheel_animation(context, get_spinning_wheel_at_tile(context, tile), 0)
        if first_time:
            add_quality_bar_to_spinning_wheel(context, tile)

def handle_scene4(context):
    duration_multiplier = 1.0 * SPEED_MULTIPLIER

    checks = [
        # check function name,         duration
        ("check_spin_wheel",           40),
        ("check_jump_guy",             11),
        ("check_reward_or_penalty",    5),
        ("check_set_quality_by_poke",  10),
        ("check_action_end",           1)
    ]

    handle_checks(context, checks, duration_multiplier)
    handle_jump_guy(context)
    handle_poke_guy(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    handle_spinning_wheels(context)

def reset_scene5(context, first_time):
    for tile in find_recursive_list(context, context, "tile_neutral"):
        start_drop_down_spinning_wheel_animation(context, get_spinning_wheel_at_tile(context, tile), 0)
        if first_time:
            add_quality_bar_to_spinning_wheel(context, tile)

def handle_scene5(context):
    duration_multiplier = 1.0 * SPEED_MULTIPLIER

    checks = [
        # check function name,          duration
        ("check_compare_or_spin_wheel", 20),
        ("check_jump_guy",              11),
        ("check_reward_or_penalty",     5),
        ("check_set_quality_by_poke",   10),
        ("check_action_end",            1)
    ]
    handle_checks(context, checks, duration_multiplier)

    handle_jump_guy(context)
    handle_poke_guy(context)
    handle_closely_look_guy(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    handle_spinning_wheels(context)

def reset_scene6(context, first_time):
    for tile in find_recursive_list(context, context, "tile_neutral"):
        start_drop_down_spinning_wheel_animation(context, get_spinning_wheel_at_tile(context, tile), 0)
        if first_time:
            add_quality_bar_to_spinning_wheel(context, tile)

def handle_scene6(context):
    duration_multiplier = 1.0 * SPEED_MULTIPLIER

    checks = [
        # check function name,          duration
        ("check_pause",                 20),
        ("check_compare_or_spin_wheel", 20),
        ("check_jump_guy",              11),
        ("check_reward_or_penalty",     5),
        ("check_set_quality_by_poke",   10),
        ("check_pause",                 20),
        ("check_action_end",            1)
    ]
    handle_checks(context, checks, duration_multiplier)

    handle_jump_guy(context)
    handle_poke_guy(context)
    handle_closely_look_guy(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    handle_spinning_wheels(context)

def reset_scene7(context, first_time):
    for tile in find_recursive_list(context, context, "tile_neutral"):
        start_drop_down_spinning_wheel_animation(context, get_spinning_wheel_at_tile(context, tile), 0)
        if first_time:
            add_quality_bar_to_spinning_wheel(context, tile)

def handle_scene7(context):
    duration_multiplier = 1.0 * SPEED_MULTIPLIER

    checks = [
        # check function name,          duration
        #("check_pause",                 40),
        ("check_dice",                  30),
        ("check_compare_or_spin_wheel", 20),
        ("check_jump_guy",              11),
        ("check_reward_or_penalty",     5),
        ("check_set_quality_by_poke",   10),
        ("check_pause",                 4),
        ("check_action_end",            1)
    ]
    handle_checks(context, checks, duration_multiplier)
    handle_dice(context)
    handle_jump_guy(context)
    handle_poke_guy(context)
    handle_closely_look_guy(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    handle_spinning_wheels(context)

def reset_scene8(context, first_time):
    for tile in find_recursive_list(context, context, "tile_neutral"):
        start_drop_down_spinning_wheel_animation(context, get_spinning_wheel_at_tile(context, tile), 0)
        if first_time:
            add_quality_bar_to_spinning_wheel(context, tile)

def handle_scene8(context):
    duration_multiplier = 1.0 * SPEED_MULTIPLIER

    checks = [
        # check function name,          duration
        #("check_pause",                 40),
        ("check_dice",                  25),
        ("check_compare_or_spin_wheel", 20),
        ("check_jump_guy",              11),
        ("check_reward_or_penalty",     5),
        ("check_set_quality_by_poke",   10),
        ("check_pause",                 4),
        ("check_action_end",            1)
    ]
    handle_checks(context, checks, duration_multiplier)
    handle_dice(context)
    handle_jump_guy(context)
    handle_poke_guy(context)
    handle_closely_look_guy(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    handle_spinning_wheels(context)

def reset_scene9(context, first_time):
    for tile in find_recursive_list(context, context, "tile_neutral"):
        start_drop_down_spinning_wheel_animation(context, get_spinning_wheel_at_tile(context, tile), 0)
        if first_time:
            add_quality_bar_to_spinning_wheel(context, tile)

def handle_scene9(context):
    duration_multiplier = 1.0 * SPEED_MULTIPLIER

    checks = [
        # check function name,          duration
        #("check_pause",                 40),
        ("check_dice",                  25),
        ("check_compare_or_spin_wheel", 20),
        ("check_jump_guy",              11),
        ("check_reward_or_penalty",     5),
        ("check_set_quality_by_poke",   10),
        ("check_pause",                 4),
        ("check_action_end",            1)
    ]
    handle_checks(context, checks, duration_multiplier)
    handle_dice(context)
    handle_jump_guy(context)
    handle_poke_guy(context)
    handle_closely_look_guy(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    handle_spinning_wheels(context)

def reset_scene10(context, first_time):
    for tile in find_recursive_list(context, context, "tile_neutral"):
        start_drop_down_spinning_wheel_animation(context, get_spinning_wheel_at_tile(context, tile), 0)
        if first_time:
            add_quality_bar_to_spinning_wheel(context, tile)

def handle_scene10(context):
    duration_multiplier = 1.0 * SPEED_MULTIPLIER

    checks = [
        # check function name,          duration
        #("check_pause",                 40),
        ("check_dice",                  25),
        ("check_compare_or_spin_wheel", 20),
        ("check_jump_guy",              11),
        ("check_reward_or_penalty",     5),
        ("check_set_quality_by_poke",   10),
        ("check_pause",                 4),
        ("check_action_end",            1)
    ]
    handle_checks(context, checks, duration_multiplier)
    handle_dice(context)
    handle_jump_guy(context)
    handle_poke_guy(context)
    handle_closely_look_guy(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    handle_spinning_wheels(context)

def reset_scene11(context, first_time):
    global GUY_POS_STATE_TILE_OFFSET
    for tile in find_recursive_list(context, context, "tile_state_"):
        start_drop_down_spinning_wheel_animation(context, get_spinning_wheel_at_tile(context, tile), 0)
        if first_time:
            add_quality_bar_to_spinning_wheel(context, tile)
    if first_time:
        #reset_snake(context.global_scene)
        guy = get_guy(context)
        snake_state = get_state_at_snake_head(context)
        #print(f"Snake state walls: {snake_state.walls}, apple dir: {snake_state.apple_dir}")
        tile = find_state_tile(context, snake_state)
        tile_pos = get_world_location(tile)
        set_world_location(guy, tile_pos + GUY_POS_STATE_TILE_OFFSET)
        randomize_snake_apple_position(context)
    reset_snake(context.global_scene)


def handle_scene11(context):
    duration_multiplier = 1.0 * SPEED_MULTIPLIER

    checks = [
        # check function name,          duration
        #("check_pause",                 40),
        ("check_dice",                            25),
        ("check_compare_or_spin_wheel",           20),
        ("check_jump_to_action_guy",              30),
        ("check_snake_action",                    10),
        ("check_reward_or_penalty_as_snake",      10),
        ("check_win_and_move_apple",              5),
        ("check_set_quality_by_poke_from_action", 10),
        ("check_jump_to_state_guy",               40),
        # ("check_set_quality_by_poke",           10),
        ("check_pause",                           4),
        ("check_action_end_snake",                1)
    ]

    handle_checks(context, checks, duration_multiplier)
    handle_dice(context)
    handle_jump_to_action_guy(context)
    handle_snake_action(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    handle_snake_extension(context)
    handle_jump_to_state_guy(context)
    handle_poke_guy(context)
    handle_closely_look_guy(context)
    handle_spinning_wheels(context)

    #new_state = get_state_at_snake_head(context)
    #print(f"Head state: {new_state.state_tile_obj_name()}")


def handle_checks(context, checks, duration_multiplier):
    total_duration = sum((scale_duration(duration, duration_multiplier) + 1) for _, duration in checks) + 2
    context.action_duration_num_frames = total_duration
    start_frame = 1
    for func_name, duration in checks:
        fn = globals()[func_name]
        duration_scaled = scale_duration(duration, duration_multiplier)
        #print(f"calling {func_name}")
        fn(context, total_duration, start_frame, duration_scaled)
        start_frame += (duration_scaled + 1)

def scale_duration(duration_num_frames, duration_multiplier):
    return max(1, int(duration_num_frames * duration_multiplier))

def init(context: SceneContext):
    context.scene_obj.pop("reset_called", None)
    guy = get_guy(context)
    if context.frame_current <= 1:
        generated_objects = list(set(find_generated_objects(context)))
        for obj in generated_objects:
            path = get_object_path(obj)
            if not path.startswith("_ignore") and not path.startswith("_prefabs"):
                # print(f"deleting '{get_object_path(obj)}'")
                try:
                    move_objects_to_trash_recursive(context.global_scene, obj)
                except Exception as e:
                    print(f"move to trash failed: {e}")

        context.scene_obj["spinning_wheels"] = list([])
        print("Cleared list")
        guy.pop("num_actions_done", None)
        guy.pop("num_penalty", None)
        guy.pop("num_reward", None)
        guy.pop("num_losses", None)
        guy.pop("num_wins", None)

        penalty = get_text_penalty(context)
        if penalty is not None:
            penalty.data.body = "0"
        get_text_rewards(context).data.body = "0"
        reset(context)

def handle(context):
    handle_jump_guy(context)
    handle_poke_guy(context)
    handle_win_guy(context)
    handle_lost_guy(context)
    handle_spinning_wheels(context)

def check_set_quality_by_poke(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        if guy_got_reward_or_penalty(context):
            poke_guy_prev_tile(context, check_duration_num_frames)

    if (context.frame_current % total_duration_num_frames) == int(check_frame_index + check_duration_num_frames/2):
        tile_current  = get_tile_at_guy(context)
        tile_previous = get_guy_prev_tile(context)
        penalty_or_reward = get_tile_penalty_or_reward(context, tile_current)
        if penalty_or_reward != 0:
            prev_tile_result = get_spinning_wheel_result(context, get_spinning_wheel_at_tile(context, tile_previous))
            add_quality_at_disk_section(context, get_guy_prev_tile(context), prev_tile_result, penalty_or_reward)

def check_set_quality_by_poke_from_action(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        if guy_got_reward_or_penalty(context):
            poke_guy_prev_tile(context, check_duration_num_frames)

    if (context.frame_current % total_duration_num_frames) == int(check_frame_index + check_duration_num_frames/2):
        tile_current = get_tile_at_snake_head(context)
        tile_previous = get_guy_prev_action_tile(context)
        penalty_or_reward = get_tile_penalty_or_reward(context, tile_current)
        if penalty_or_reward != 0:
            prev_tile_result = get_spinning_wheel_result(context, get_spinning_wheel_at_tile(context, tile_previous))
            add_quality_at_disk_section(context, tile_previous, prev_tile_result, penalty_or_reward)

def check_win_and_move_apple(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        tile = get_tile_at_snake_head(context)
        apple = find_recursive(context, tile, "apple")
        if apple is not None:
            randomize_snake_apple_position(context)

def check_drop_down_spinning_wheel(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        start_drop_down_spinning_wheel_animation(context, get_spinning_wheel_at_guy(context), check_duration_num_frames)

def check_pick_up_spinning_wheel(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        start_pick_up_spinning_wheel_animation(context, get_spinning_wheel_at_guy(context), check_duration_num_frames)

def check_dice(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        if not disk_has_equal_section_qualities(context):
            throw_dice(context, check_duration_num_frames)

def check_pause(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    pass

def disk_has_equal_section_qualities(context):
    tile = get_tile_at_guy(context)
    disk_sections = get_disk_sections(context, tile)
    disk_sections.sort(key=lambda s: s.quality, reverse=True)
    return abs(disk_sections[0].quality - disk_sections[-1].quality) < EPS

def check_compare_or_spin_wheel(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    # disk = get_disk(context, get_tile_at_guy(context))
    # if disk is not None:
    #     result = get_spinning_wheel_result(context, get_tile_at_guy(context))
    #     print(f"current tile disk angle: {math.degrees(disk.rotation_euler.z):.2f} ({(math.degrees(disk.rotation_euler.z) % 360):.2f}). section: {result}")
    #     disk_sections = get_disk_sections(context, get_tile_at_guy(context))
    #     for sec in disk_sections:
    #         print(f"section angle of '{sec.label}': {sec.angle_for_target_start} - {sec.angle_for_target_end}")

    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        should_spin = is_dice_on_spin(context)
        print(f"is dice on spin: {should_spin}")
        if disk_has_equal_section_qualities(context):
            should_spin = True

        if should_spin:
            check_spin_wheel(context, total_duration_num_frames, check_frame_index, check_duration_num_frames)
        else:
            check_compare(context, total_duration_num_frames, check_frame_index, check_duration_num_frames)

def get_target_angle_for_section(context, disk_obj, section_label):
    disk_sections = get_disk_sections(context, disk_obj)
    for section in disk_sections:
        if section.label == section_label:
            return ((section.angle_for_target_start + section.angle_for_target_end) / 2)
    return 0

# random if 2 or more top qualities are equal
def get_top_quality_section(context, disk_obj):
    disk_sections = get_disk_sections(context, disk_obj)
    disk_sections.sort(key=lambda s: s.quality, reverse=True)
    top_quality = disk_sections[0].quality
    top_sections = [s for s in disk_sections if s.quality == top_quality]
    random.seed(context.frame_current * 931)
    return random.choice(top_sections)

def check_compare(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        tile = get_tile_at_guy(context)
        closely_look_guy(context, int((check_duration_num_frames / 4) * 2))
        top_quality_section = get_top_quality_section(context, tile)
        target_angle = get_target_angle_for_section(context, tile, top_quality_section.label)
        print(f"Aiming for: {top_quality_section.label}, at angle: {target_angle}")
        current_section = get_spinning_wheel_result(context, tile)
        #print(f"comparing: {current_section}, {desired_section.label}")
        if current_section is not top_quality_section.label:
            manually_set_spinning_wheel(context, get_spinning_wheel_at_guy(context), target_angle, int((check_duration_num_frames / 4) * 2), int((check_duration_num_frames / 4) * 2))

def check_spin_wheel(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        spin_spinning_wheel(context, get_spinning_wheel_at_guy(context), get_target_rotation(context), check_duration_num_frames)

def check_jump_guy(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        result = get_spinning_wheel_result(context, get_spinning_wheel_at_guy(context))
        #print(f"Spinning Wheel result: {result}")
        if result == "W":
            jump_guy(context, 0, -1, check_duration_num_frames)
        if result == "E":
            jump_guy(context, 0, 1, check_duration_num_frames)
        if result == "N":
            jump_guy(context, -1, 0, check_duration_num_frames)
        if result == "S":
            jump_guy(context, 1, 0, check_duration_num_frames)

def check_jump_to_action_guy(context, total_duration_num_frames, check_frame_index, duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        result = get_spinning_wheel_result(context, get_spinning_wheel_at_guy(context))
        print(f"Spinning Wheel result: {result}")
        jump_to_action_guy(context, result, duration_num_frames)

def check_jump_to_state_guy(context, total_duration_num_frames, check_frame_index, duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        lost_frame = get_property(get_guy(context), "lost_frame", -1)
        if lost_frame < 0: # don't do anything if he lost...
            new_state = get_state_at_snake_head(context)
            jump_to_state_guy(context, new_state, duration_num_frames)

def check_snake_action(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        guy = get_guy(context)
        action = guy["jump_to_action_result"]
        do_snake_action(context, action, check_duration_num_frames)

def get_tile_penalty(context, tile):
    pen_match = re.search(r"_pen(\d+)", tile.name)
    if pen_match:
        return int(pen_match.group(1))
    return 0

def get_tile_reward(context, tile):
    rew_match = re.search(r"_rew(\d+)", tile.name)
    if rew_match:
        return int(rew_match.group(1))

    if context.quality_bleeds_over:
        # bleed_over = True
        # if name_contains_key(tile.name, "lose"):
        #     bleed_over = False
        # if name_contains_key(tile.name, "win"):
        #     bleed_over = False
        # if bleed_over:
        disk = get_disk(context, tile)
        if disk:
            disk_sections = get_disk_sections(context, tile)
            disk_sections.sort(key=lambda s: s.quality, reverse=True)
            best_section = disk_sections[0]
            return best_section.quality * context.gamma

    return 0

def get_tile_penalty_or_reward(context, tile):
    penalty = get_tile_penalty(context, tile)
    reward = get_tile_reward(context, tile)
    return reward - penalty

def check_reward_or_penalty_ext(context, total_duration_num_frames, check_frame_index, check_duration_num_frames, as_snake):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        tile = None
        if as_snake:
            tile = get_tile_at_snake_head(context)
        else:
            tile = get_tile_at_guy(context)
        #print(f"Checking tile {tile.name}")
        penalty = get_tile_penalty(context, tile)
        reward = get_tile_reward(context, tile)
        if penalty > 0:
            penelize_guy(context, penalty)
        if reward > 0:
            reward_guy(context, reward)
        if name_contains_key(tile.name, "lose"):
            lose_guy(context, check_duration_num_frames)
        if name_contains_key(tile.name, "win"):
            win_guy(context, check_duration_num_frames)
            if as_snake:
                extend_snake(context, check_duration_num_frames)

def check_reward_or_penalty(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    check_reward_or_penalty_ext(context, total_duration_num_frames, check_frame_index, check_duration_num_frames, False)

def check_reward_or_penalty_as_snake(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    check_reward_or_penalty_ext(context, total_duration_num_frames, check_frame_index, check_duration_num_frames, True)

def get_num_actions_done(context):
    if context.action_duration_num_frames == 0:
        return 0
    return int(context.frame_current / context.action_duration_num_frames)

def check_action_end(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        print(f"action {get_num_actions_done(context)} done")
        if guy_won(context) or guy_lost(context):
            reset(context)

def check_action_end_snake(context, total_duration_num_frames, check_frame_index, check_duration_num_frames):
    if (context.frame_current % total_duration_num_frames) == check_frame_index:
        print(f"action {get_num_actions_done(context)} done")
        if guy_lost(context):
            reset(context)

def guy_got_reward_or_penalty(context):
    tile = get_tile_at_snake_head(context)
    if tile is None:
        tile = get_tile_at_guy(context)
    return get_tile_penalty_or_reward(context, tile) != 0

def get_target_rotation(context):
    num_actions_done = get_num_actions_done(context)
    target_rotation = -9999

    if isinstance(context.first_spinner_rotations, int):
        if num_actions_done == 0:
            target_rotation = context.first_spinner_rotations
    else:
        if num_actions_done < len(context.first_spinner_rotations):
            target_rotation = context.first_spinner_rotations[num_actions_done]
    return target_rotation

def get_guy_starting_pos(context):
    return context.guy_starting_pos

def reset(context):
    guy = get_guy(context)
    guy.location = get_guy_starting_pos(context)
    guy.scale = (0.1, 0.1, 0.1)
    guy.rotation_euler.x = 0
    guy.rotation_euler.y = 0
    guy.rotation_euler.z = math.radians(0)
    guy.pop("start_jump_frame", None)
    guy.pop("start_poke_frame", None)
    guy.pop("start_jump_to_action_frame", None)
    guy.pop("start_jump_to_state_frame", None)
    guy.pop("jump_direction_x", None)
    guy.pop("jump_direction_y", None)
    guy.pop("lost_frame", None)
    guy.pop("start_closely_look_frame", None)
    guy.pop("win_frame", None)
    guy.pop("start_throw_frame", None)
    reset_guy_arms(context, guy)

    dice_sub_base = find_recursive(context, get_guy(context), "dice_sub_base")
    if dice_sub_base is not None:
        dice = find_recursive(context, get_guy(context), "dice")
        dice.pop("start_throw_frame", None)
        dice_sub_base.scale = (0,0,0)
        dice_sub_base.hide_viewport = False
        dice_sub_base.hide_render = True

    snake_head = get_snake_head(context)
    if snake_head is not None:
        snake_head.pop("action_frame_start", None)

    for spinning_wheel_obj in get_spinning_wheels(context):
        reset_spinning_wheel(context, spinning_wheel_obj)
    for apple in find_recursive_list(context, context, "apple"):
        apple.location = (0,0,0)
    context.scene_obj["reset_called"] = True

def delete_tail(global_scene, starting_tail_obj):
    if starting_tail_obj is None:
        return
    number = get_tail_number(starting_tail_obj.name)
    move_objects_to_trash_recursive(global_scene, starting_tail_obj)
    delete_tail(global_scene, global_scene.objects.get(f"tail_{(number + 1)}"))

def reset_snake(global_scene):
    snake_head = global_scene.objects["snake"]
    snake_head.location.x = -3
    snake_head.location.y = -1
    snake_head.location.z = 1
    snake_head.rotation_euler.z = 0
    tail_1 = global_scene.objects["tail_1"]
    tail_1.location = snake_head.location
    tail_1.location.x = tail_1.location.x + 1
    tail_1.location.y = snake_head.location.y
    tail_1.rotation_euler.z = 0
    tail_2 = global_scene.objects["tail_2"]
    tail_2.location = tail_1.location
    tail_2.location.x = tail_2.location.x + 1
    tail_2.location.y = snake_head.location.y
    tail_2.rotation_euler.z = 0
    delete_tail(global_scene, global_scene.objects.get("tail_3"))

def pop_reset_called(context):
    called = get_property(context.scene_obj, "reset_called", False)
    context.scene_obj.pop("reset_called", None)
    return called

def get_disk(context, spinning_wheel_obj):
    return find_recursive(context, spinning_wheel_obj, "disk")

def get_flipper(context, spinning_wheel_obj):
    return find_recursive(context, spinning_wheel_obj, "flipper")

def get_guy(context):
    return find_recursive(context, context, "guy")

def get_text_penalty(context):
    return find_recursive(context, context, "score_penalty")

def get_text_rewards(context):
    return find_recursive(context, context, "score_rewards")

def get_spinning_wheels(context):
    if "spinning_wheels" in context.scene_obj:
        retval = list(context.scene_obj["spinning_wheels"])
        return retval
    retval = []
    return retval
    #return find_recursive_list(context, context, "spinning_wheel_base", 5)

def reset_guy_arms(context, guy):
    arm_left  = find_recursive(context, guy, "arm_left")
    arm_right = find_recursive(context, guy, "arm_right")
    if arm_left is not None:
        arm_left.rotation_mode = 'XYZ'
        arm_left.rotation_euler = (0,0,0)
        arm_left.scale = (1,1,1)
    if arm_right is not None:
        arm_right.rotation_mode = 'XYZ'
        arm_right.rotation_euler = (0,0,0)
        arm_right.scale = (1,1,1)

def reset_spinning_wheel(context, spinning_wheel_obj):
    disk = get_disk(context, spinning_wheel_obj)
    if "target_angle" in disk:
        disk.rotation_euler.z = math.radians(disk["target_angle"])
    disk.pop("start_spin_frame", None)
    disk.pop("start_manual_frame", None)
    disk.pop("end_spin_frame", None)
    disk.pop("starting_angle", None)
    disk.pop("target_angle", None)
    origin = find_recursive(context, spinning_wheel_obj, "spinning_wheel_origin")
    origin.parent.pop("start_drop_frame", None)
    origin.parent.pop("start_spin_frame", None)
    origin.parent.pop("start_manual_frame", None)
    origin.pop("start_drop_frame", None)
    origin.pop("end_drop_frame", None)
    origin.parent.pop("start_pick_frame", None)
    origin.pop("start_pick_frame", None)
    origin.pop("end_pick_frame", None)
    origin.scale = (0, 0, 0)
    origin.hide_viewport = False
    origin.hide_render = True
    flipper = get_flipper(context, spinning_wheel_obj)
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

    
    # def apply_colors(disk, sections):
    #     mesh = disk.data
    #     bm = bmesh.new()
    #     bm.from_mesh(mesh)
    #     for face in bm.faces:
    #         # Only operate on top faces (normal pointing up)
    #         if not is_disk_face_part_of_section(disk, face):
    #             continue
    #
    #         for sec in sections:
    #             if is_disk_face_part_of_section(disk, face, sec.label):
    #                 sec_index = material_index_from_label_object(disk, sec.label)
    #                 if sec_index < len(mesh.materials):
    #                     face.material_index = sec_index
    #
    #     bm.to_mesh(mesh)
    #     bm.free()
    #     mesh.update()
        
    def add_section_bars(disk, sections):
        template = next((c for c in disk.children if c.name.startswith("bar")), None)
        if template is None:
            print("Bar object not found")
            return
        for sec in sections:
            bar = template.copy()
            bar.name = f"gen_{template.name}"
            bpy.context.collection.objects.link(bar)
            bar.parent = disk
            bar.matrix_parent_inverse.identity()
            bar.location = (0,0,0)
            bar.rotation_euler = (0,0,math.radians(sec.angle_start))
            make_object_and_children_visible_to_renderer(bar)            
            
    def add_section_labels(disk, sections):
        for sec in sections:
            # Find the template child whose name starts with 'choise_{label}'
            template = next((c for c in disk.children if c.name.startswith(f"choise_{sec.label}")), None)
            if template is None:
                print(f"No template found for label {sec.label}")
                continue
            label_obj = duplicate_object_with_children(template, disk)
            make_object_and_children_visible_to_renderer(label_obj)
            label_obj.location = (0, 0, 0)
            label_obj.rotation_euler = (0, 0, math.radians(-90 + ((sec.angle_start + sec.angle_end)/2)))
            
    def generate_sections(chance_table):
        total = sum(ch for ch, _ in chance_table)
        normalized = [(ch / total, label) for ch, label in chance_table]
        sections = []
        start_angle = 0.0

        angles = []
        for prob, label in normalized:
            end_angle = start_angle + prob * 360
            angles.append((start_angle, end_angle, label))
            start_angle = end_angle

        next_index_mirror = 0
        for index in range(len(angles)):
            start_angle = angles[index][0]
            end_angle = angles[index][1]
            start_mirror_angle = angles[next_index_mirror][0]
            end_mirror_angle = angles[next_index_mirror][1]
            label = angles[index][2]
            section = DiskSection(label, start_angle, end_angle, start_mirror_angle, end_mirror_angle, 0)
            sections.append(section)
            next_index_mirror = (next_index_mirror - 1) % len(angles)

        return sections

    sections = generate_sections(chance_table)
    disk = get_disk(context, spinning_wheel_obj)
    disk["sections"] = [
        {"start": sec.angle_start, "end": sec.angle_end, "start_for_target": sec.angle_for_target_start, "end_for_target": sec.angle_for_target_end, "label": sec.label}
        for sec in sections
    ]
    reset_spinning_wheel(context, spinning_wheel_obj)
    # apply_colors(disk, sections)
    add_section_bars(disk, sections)
    add_section_labels(disk, sections)


def add_quality_bar_to_spinning_wheel(context, tile_obj):
    chance_table = get_spinning_wheel_chance_table(context, tile_obj)
    for prob, label in chance_table:
        add_quality_at_disk_section(context, tile_obj, label, 0)

def color_disk_section(context, disk_obj, section_label, color):
    #print(f"Color section of: {disk_obj.data.name}")
    disk = get_disk(context, disk_obj)
    mesh = disk.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    color_layer = bm.verts.layers.float_color.get("col")
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
        r = 1.0 * (1 - t) + 1.0 * t  # 1 -> 0.7
        g = 0.0 * (1 - t) + 1.0 * t  # 0 -> 0.7
        b = 0.0 * (1 - t) + 0.5 * t  # 0 -> 0.7
    else:
        # Interpolate grey -> green
        t = q  # 0 -> 1
        r = 1.0 * (1 - t) + 0.0 * t  # 0.7 -> 0
        g = 1.0 * (1 - t) + 1.0 * t  # 0.7 -> 1
        b = 0.5 * (1 - t) + 0.0 * t  # 0.7 -> 0

    return (r, g, b, 1.0)

def calculate_new_quality(context, current_quality, desired_quality):
    new_quality = current_quality + (desired_quality - current_quality) * context.quality_multiplier
    return new_quality


class SnakeState:
    walls: int
    apple_dir: int

    @classmethod
    def from_state_tile_obj_name(cls, obj_name: str):
        if not obj_name.startswith("tile_state_"):
            return None
        parts = obj_name.split("_")
        w = int(parts[2][1:])  # "w3" -> 3
        a = int(parts[3][1:])  # "a2" -> 2
        return cls(w, a)

    def __init__(self, walls_param: int, apple_dir_param: int):
        self.walls = walls_param
        self.apple_dir = apple_dir_param

    def state_tile_obj_name(self):
        return f"tile_state_w{self.walls}_a{self.apple_dir}"

class DiskSection:
    label: str
    angle_start: float
    angle_end: float
    angle_for_target_start: float
    angle_for_target_end: float
    quality: float

    def __init__(self, label, angle_start, angle_end, angle_for_target_start, angle_for_target_end, quality):
        self.label = label
        self.angle_start = angle_start
        self.angle_end = angle_end
        self.angle_for_target_start = angle_for_target_start
        self.angle_for_target_end = angle_for_target_end
        self.quality = quality

def get_disk_sections(context, tile_obj):
    sections_list = []
    disk = get_disk(context, tile_obj)
    if disk is None or "sections" not in disk:
        return sections_list
    sections = disk["sections"] # list of tuples: (start_angle, end_angle, label)
    for sec in sections:
        label = sec["label"]
        start = sec["start"]
        end = sec["end"]
        start_for_target = sec["start_for_target"]
        end_for_target = sec["end_for_target"]
        section = DiskSection(label, start, end, start_for_target, end_for_target, get_property(disk, f"quality_{label}", 0))
        sections_list.append(section)
    return sections_list

def add_quality_at_disk_section(context, tile_obj, section_label, quality):
    disk = get_disk(context, tile_obj)
    if disk is None or "sections" not in disk:
        return None

    create_colors = False
    if f"quality_{section_label}" not in disk:
        create_colors = True
    current_quality = get_property(disk, f"quality_{section_label}", 0)
    target_quality = quality
    new_quality = calculate_new_quality(context, current_quality, target_quality)
    if new_quality != current_quality:
        create_colors = True

    if create_colors:
        disk[f"quality_{section_label}"] = new_quality
        sections = disk["sections"] # list of tuples: (start_angle, end_angle, label)
        #print(f"Adding quality {quality} to {tile_obj.name}. new quality: {new_quality}")
        for sec in sections:
            label = sec["label"]
            if label == section_label:
                #start = sec["start"]
                #end = sec["end"]
                # quality_bar_obj = find_recursive(context, disk, f"gen_quality_bar_base_{section_label}")
                # if quality_bar_obj is None:
                #     print(f"create for {section_label}")
                #     template = find_recursive(context, disk, "quality_bar_base")
                #     quality_bar_obj = duplicate_object_with_children(template, disk)
                #     quality_bar_obj.name = f"gen_quality_bar_base_{section_label}"
                #     make_object_and_children_visible_to_renderer(quality_bar_obj)
                #     quality_bar_obj["section_label"] = section_label
                #     quality_bar_obj.location = (0, 0, 0)
                #     quality_bar_obj.rotation_euler = (0, 0, math.radians(-90 + ((start+end)/2)))
                color_disk_section(context, disk, label, get_color_from_quality(new_quality))
                break


def handle_spinning_wheel_flipper(context, spinning_wheel_obj, snap_strength=5.0):
    disk = get_disk(context, spinning_wheel_obj)
    flipper = get_flipper(context, spinning_wheel_obj)
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
        
    last_offset_to_bar = flipper["last_offset_to_bar"]
    offset_to_bar = smallest_dist * sign
    flipper["last_offset_to_bar"] = offset_to_bar
    if last_offset_to_bar <= 0 and offset_to_bar > 0:
        flipper["last_hit_frame"] = context.frame_current
    
    frames_since_hit = context.frame_current - flipper["last_hit_frame"]
    flipper_angle = (-math.pow((1/(math.pow((frames_since_hit)*1, 4)+1)), 4)) * 0.7 + math.pi # https://www.desmos.com/calculator/xycbiyqqzs?lang=nl
    flipper.rotation_euler.z = flipper_angle
    
def manually_set_spinning_wheel(context, spinning_wheel_base_obj, target_angle, duration_num_frames=40, start_frame_offset = 0):
    disk = get_disk(context, spinning_wheel_base_obj)
    if disk is None:
        return
    current_angle = math.degrees(disk.rotation_euler.z)
    delta = (target_angle - current_angle + 180) % 360 - 180
    manual_angle = current_angle + delta  # closest equivalent to target_angle
    print(f"Manual set to: {manual_angle} ({manual_angle % 360})")
    disk["start_manual_frame"] = context.frame_current + start_frame_offset
    spinning_wheel_base_obj["start_manual_frame"] = context.frame_current + start_frame_offset # also apply here as its faster to read
    disk["end_manual_frame"] = context.frame_current + start_frame_offset + duration_num_frames
    disk["starting_angle"] = math.degrees(disk.rotation_euler.z)
    disk["manual_angle"] = manual_angle

def is_valid_choice(context, label):
    head = get_snake_head(context)
    if head is None:
        return True
    head_pos = head.location
    tail_pos = context.global_scene.objects["tail_1"].location
    action_dir = Vector(action_to_dir(label))
    tail_diff = tail_pos - head_pos
    tail_l = math.dist(tail_pos, head_pos)
    tail_dir = Vector((tail_diff.x / tail_l, tail_diff.y / tail_l))
    dist = math.dist(action_dir, tail_dir)
    #print(f"checking if label '{label}' is valid: label_dir: {action_dir}, tail_dir: {tail_dir}, dist: {dist}. valid: {dist > 0.2}")
    return dist > 0.2

def spin_spinning_wheel(context, spinning_wheel_base_obj, target_angle=-9999.0, duration_num_frames=40, min_turns=1):
    disk = get_disk(context, spinning_wheel_base_obj)
    if disk is None:
        return
    starting_angle = math.degrees(disk.rotation_euler.z)
    actual_target_angle = target_angle
    if actual_target_angle < -9990:
        random.seed(context.frame_current * 7183)  # deterministic seed
        actual_target_angle = random.uniform(0, 360)
        # print(f"spinner end angle set to: {actual_target_angle}")
    while actual_target_angle < starting_angle:
        actual_target_angle = actual_target_angle + 360
    actual_target_angle = actual_target_angle + min_turns * 360

    sections = disk["sections"] # list of tuples: (start_angle, end_angle,label)
    while not is_valid_choice(context, get_spinning_wheel_label_at_angle(context, sections, math.radians(actual_target_angle))): # HACK: skip invalid choises
        actual_target_angle = actual_target_angle + 10
        print(f"Invalid choice, adding 10 degrees. now target angle: {actual_target_angle}")
    #print(f"target angle: {actual_target_angle}")
    disk["start_spin_frame"] = context.frame_current
    spinning_wheel_base_obj["start_spin_frame"] = context.frame_current # also apply on base, as its faster to read
    disk["end_spin_frame"] = context.frame_current + duration_num_frames
    disk["starting_angle"] = math.degrees(disk.rotation_euler.z)
    disk["target_angle"] = actual_target_angle

def handle_spinning_wheel_origin(context, spinning_wheel_obj):
    if "start_drop_frame" in spinning_wheel_obj:
        origin = find_recursive(context, spinning_wheel_obj, "spinning_wheel_origin", False, 2)
        if origin is not None and "start_drop_frame" in origin:
            start_drop_frame = origin["start_drop_frame"]
            end_drop_frame = origin["end_drop_frame"]
            if start_drop_frame != end_drop_frame:
                anim_perc = min(max((context.frame_current - start_drop_frame) / (end_drop_frame - start_drop_frame), 0), 1)
                origin.scale = (anim_perc, anim_perc, anim_perc)
                if anim_perc >= 1:
                    spinning_wheel_obj.pop("start_drop_frame", None)
                    origin.pop("start_drop_frame", None)
                    origin.pop("end_drop_frame", None)

    if "start_pick_frame" in spinning_wheel_obj:
        origin = find_recursive(context, spinning_wheel_obj, "spinning_wheel_origin", False, 2)
        if origin is not None and "start_pick_frame" in origin:
            start_drop_frame = origin["start_pick_frame"]
            end_drop_frame = origin["end_pick_frame"]
            if start_drop_frame != end_drop_frame:
                anim_perc = min(max((context.frame_current - start_drop_frame) / (end_drop_frame - start_drop_frame), 0), 1)
                origin.scale = (1-anim_perc, 1-anim_perc, 1-anim_perc)
                if anim_perc >= 1:
                    spinning_wheel_obj.pop("start_pick_frame", None)
                    origin.pop("start_pick_frame", None)
                    origin.pop("end_pick_frame", None)
                    origin.hide_render = True

def handle_manual_wheel(context, spinning_wheel_base_obj):
    if "start_manual_frame" in spinning_wheel_base_obj:
        disk = get_disk(context, spinning_wheel_base_obj)
        if disk is None or "start_manual_frame" not in disk:
            return None
        start_frame = disk["start_manual_frame"]
        end_frame = disk["end_manual_frame"]
        start_angle = disk["starting_angle"]
        target_angle = disk["manual_angle"]
        perc = max(0, min((context.frame_current - start_frame) / (end_frame - start_frame), 1), 0)
        disk.rotation_euler.z = math.radians(start_angle + (target_angle - start_angle) * perc)
        disk.location.z = math.sin(perc * math.pi) * 0.2
        if perc >= 1.0:
            disk.pop("start_manual_frame", None)
            spinning_wheel_base_obj.pop("start_manual_frame", None)

def handle_spinning_wheel(context, spinning_wheel_base_obj):
    if "start_spin_frame" in spinning_wheel_base_obj:
        disk = get_disk(context, spinning_wheel_base_obj)
        if disk is None or "start_spin_frame" not in disk:
            return None
        starting_angle = disk["starting_angle"]
        target_angle = disk["target_angle"]
        start_spin_frame = disk["start_spin_frame"]
        end_spin_frame = (disk["end_spin_frame"] - 1)
        if starting_angle == target_angle or start_spin_frame == end_spin_frame:
            return
        if end_spin_frame <= start_spin_frame:
            disk.rotation_euler.z = math.radians(target_angle)
            return
        perc = max(0, min((context.frame_current - start_spin_frame) / (end_spin_frame - start_spin_frame), 1), 0)
        perc_anim = math.sin((perc)*(math.pi/2))
        disk.rotation_euler.z = math.radians(starting_angle + (target_angle - starting_angle) * perc_anim)
        #print(f"setting disk to target angle: {target_angle}. current angle: {math.degrees(disk.rotation_euler.z)}. label: {get_spinning_wheel_result(context, disk)}")
        handle_spinning_wheel_flipper(context, spinning_wheel_base_obj)
        if perc_anim >= 1:
            spinning_wheel_base_obj.pop("start_spin_frame", None)
            disk.pop("start_spin_frame", None)

def handle_spinning_wheels(context):
    spinning_wheels = get_spinning_wheels(context)
    for spinning_wheel_obj in spinning_wheels:
        handle_spinning_wheel_origin(context, spinning_wheel_obj)
        handle_spinning_wheel(context, spinning_wheel_obj)
        handle_manual_wheel(context, spinning_wheel_obj)

def get_spinning_wheel_result(context, tile_obj):
    disk = get_disk(context, tile_obj)
    if disk is None or "sections" not in disk:
        return None
    sections = disk["sections"] # list of tuples: (start_angle, end_angle, label)
    return get_spinning_wheel_label_at_angle(context, sections, disk.rotation_euler.z)

def get_spinning_wheel_label_at_angle(context, sections, angle_rad):
    z_deg = ((math.degrees(-angle_rad) + FLIPPER_DIRECTION) % 360)
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
    return context.chance_table
    # chance_table = [(0.5,  "W"), (0.5,  "E")]
    # return chance_table

def get_spinning_wheel_at_tile(context, tile_obj):
    spinning_wheel = find_recursive(context, tile_obj, "spinning_wheel_base")
    if spinning_wheel is None:
        # create new wheel then
        prefab_source = find_prefab(context, "spinning_wheel_base")
        #print(f"creating from {tile_obj.name}")
        spinning_wheel = duplicate_object_with_children(prefab_source, tile_obj, False)
        #print(f"Generated spinner! {prefab_source} for {tile_obj.name}")
        setup_spinning_wheel(context, spinning_wheel, get_spinning_wheel_chance_table(context, tile_obj))
        wheels = []
        if "spinning_wheels" in context.scene_obj:
            wheels = list(context.scene_obj["spinning_wheels"])
        wheels.append(spinning_wheel)
        context.scene_obj["spinning_wheels"] = wheels

    return spinning_wheel


def start_drop_down_spinning_wheel_animation(context, spinning_wheel_obj, duration_num_frames=5):
    origin = find_recursive(context, spinning_wheel_obj, "spinning_wheel_origin")
    base = find_recursive(context, spinning_wheel_obj, "spinning_wheel_base") # base is quicker to read... so also write the values there
    origin.hide_render = False
    if duration_num_frames > 0:
        origin["start_drop_frame"] = context.frame_current
        origin["end_drop_frame"] = context.frame_current + duration_num_frames
        base["start_drop_frame"] = context.frame_current
    else:
        origin.scale = (1,1,1)

def start_pick_up_spinning_wheel_animation(context, spinning_wheel_obj, duration_num_frames=5):
    origin = find_recursive(context, spinning_wheel_obj, "spinning_wheel_origin")
    base = find_recursive(context, spinning_wheel_obj, "spinning_wheel_base") # base is quicker to read... so also write the values there
    origin["start_pick_frame"] = context.frame_current
    origin["end_pick_frame"] = context.frame_current + duration_num_frames
    base["start_pick_frame"] = context.frame_current
    return context.frame_current + duration_num_frames

def get_dice_from_guy(context, guy, auto_create = True):
    dice = find_recursive(context, guy, "dice", False, 4)
    if dice is None and auto_create:
        prefab_source = find_prefab(context, "dice_base")
        dice_base = duplicate_object_with_children(prefab_source, guy)
        dice_base.rotation_euler.z = math.radians(90)
        dice = find_recursive(context, dice_base, "dice")
        dice_sub_base = find_recursive(context, dice_base, "dice_sub_base")
        dice_base.scale = (10, 10, 10)
        dice_sub_base.scale = (0, 0, 0)
    return dice


def get_dice(context, auto_create = True):
    return get_dice_from_guy(context, get_guy(context), auto_create)

def throw_dice(context, duration_num_frames):
    guy = get_guy(context)
    dice = get_dice_from_guy(context, guy)
    random.seed(context.frame_current * 1523)
    dice["rot_axis_x"] = random.uniform(-180, 180)
    dice["rot_axis_y"] = random.uniform(-180, 180)
    dice["rot_axis_z"] = random.uniform(-180, 180)
    dice["starting_angle"] = random.uniform(0, 360)
    dice["landing_offset_angle"] = random.uniform(-20, 20)
    dice["start_throw_frame"] = context.frame_current
    guy["start_throw_frame"] = context.frame_current # also apply on guy since reading from that is faster
    dice["end_throw_frame"] = context.frame_current + duration_num_frames
    dice["ends_at_spin"] = random.randint(1, 6) == 1

def is_penalty_tile(tile_obj):
    if tile_obj is None:
        return True
    return "_pen" in tile_obj.name

def extend_snake(context, duration_num_frames):
    tail = context.global_scene.objects["tail_1"]
    last_tail = tail
    while tail is not None:
        current_num = get_tail_number(tail.name)
        tail = context.global_scene.objects.get(f"tail_{(current_num+1)}")
        if tail is not None:
            last_tail = tail
    last_tail_num = get_tail_number(last_tail.name)
    new_tail = duplicate_object_with_children(last_tail, last_tail.parent)
    new_tail.name = f"tail_{(last_tail_num+1)}"
    new_tail.location = last_tail.location
    new_tail["start_extend_frame"] = context.frame_current
    new_tail["end_extend_frame"] = context.frame_current + duration_num_frames
    new_tail["extend_start_pos_x"] = last_tail.location.x
    new_tail["extend_start_pos_y"] = last_tail.location.y
    new_tail["extend_end_pos_x"] = last_tail["tail_action_starting_pos_x"]
    new_tail["extend_end_pos_y"] = last_tail["tail_action_starting_pos_y"]
    new_tail.location.x = last_tail.location.x
    new_tail.location.y = last_tail.location.y
    #print(f"placing new tail at: {new_tail.location.x}, {new_tail.location.y}")

def is_tile_blocked_by_snake(context, tile_obj):
    snake_head = get_snake_head(context)
    if not snake_head:
        return None
    play_board = find_recursive(context, context, "play_board")

    next_tail_number = 0
    tail = snake_head
    while tail is not None:
        tile = get_tile_at_pos(context, tail.matrix_world.translation, 2, play_board)
        if tile == tile_obj:
            return True
        next_tail_number = next_tail_number + 1
        tail = context.global_scene.objects.get(f"tail_{next_tail_number}")
    return False

def swap_tiles(context, tile_obj_a, tile_obj_b):
    pos_x = tile_obj_a.location.x
    pos_y = tile_obj_a.location.y
    tile_obj_a.location.x = tile_obj_b.location.x
    tile_obj_a.location.y = tile_obj_b.location.y
    tile_obj_b.location.x = pos_x
    tile_obj_b.location.y = pos_y

def randomize_snake_apple_position(context: SceneContext):
    play_board = find_recursive(context, context, "play_board")
    apple_tile = find_recursive(context, play_board, "apple", False, 3).parent
    tile_candidates = find_recursive_list(context, play_board, "tile_neutral", 3)

    num_actions_done = get_num_actions_done(context)
    next_location = None
    if isinstance(context.first_snake_apple_location, Vector):
        if num_actions_done == 0:
            next_location = context.first_snake_apple_location
    else:
        if num_actions_done < len(context.first_snake_apple_location):
            next_location = context.first_snake_apple_location[num_actions_done]

    if next_location is not None:
        print(f"Setting apple to manually set position: {next_location}")
        tile_candidates.append(apple_tile)
        nearest = min(
            tile_candidates,
            key=lambda obj: (obj.location.xy - next_location).length
        )
        tile_candidates = sorted(tile_candidates, key=lambda obj: obj.name)
        swap_tiles(context, nearest, apple_tile)
    else:
        random.shuffle(tile_candidates)
        ok = False
        for tile in tile_candidates:
            if not is_tile_blocked_by_snake(context, tile):
                swap_tiles(context, tile, apple_tile)
                ok = True
                break

        if not ok:
            print("Error in 'randomize_snake_apple_position'. No available tiles left to place the apple")

    pass

def get_snake_head(context: SceneContext):
    return find_recursive(context, context, "snake")

def get_state_at_snake_head(context: SceneContext):
    snake_head = get_snake_head(context)
    if not snake_head:
        return None
    play_board = find_recursive(context, context, "play_board")
    tile        = get_tile_at_pos(context, snake_head.matrix_world.translation + Vector(( 0,  0, 0)), 2, play_board)
    tile_north  = get_tile_at_pos(context, snake_head.matrix_world.translation + Vector((-1,  0, 0)), 2, play_board)
    tile_south  = get_tile_at_pos(context, snake_head.matrix_world.translation + Vector(( 1,  0, 0)), 2, play_board)
    tile_west   = get_tile_at_pos(context, snake_head.matrix_world.translation + Vector(( 0, -1, 0)), 2, play_board)
    tile_east   = get_tile_at_pos(context, snake_head.matrix_world.translation + Vector(( 0,  1, 0)), 2, play_board)
    apple       = find_recursive(context, play_board, "apple", False, 3)
    snake_head_pos = get_world_location(snake_head)
    apple_tile_pos = get_world_location(apple.parent)

    tile_penalty       = is_penalty_tile(tile)
    tile_north_penalty = is_penalty_tile(tile_north)
    tile_south_penalty = is_penalty_tile(tile_south)
    tile_west_penalty  = is_penalty_tile(tile_west)
    tile_east_penalty  = is_penalty_tile(tile_east)

    walls_state = 0
    if tile_north_penalty:
        walls_state = walls_state + 1
    if tile_east_penalty:
        walls_state = walls_state + 2
    if tile_south_penalty:
        walls_state = walls_state + 4
    if tile_west_penalty:
        walls_state = walls_state + 8

    apple_dir_state = 0
    apple_dist = math.dist(apple_tile_pos, snake_head_pos)
    if apple_dist > 0:
        dir = (apple_tile_pos - snake_head_pos) / apple_dist
        dir_2d = Vector((dir.x, dir.y))

        if dir_2d.x < -0.65:
            apple_dir_state = 0
        if dir_2d.x < -0.35 and dir_2d.y >  0.35:
            apple_dir_state = 1
        if dir_2d.y >  0.65:
            apple_dir_state = 2
        if dir_2d.x >  0.35 and dir_2d.y >  0.35:
            apple_dir_state = 3
        if dir_2d.x >  0.65:
            apple_dir_state = 4
        if dir_2d.x >  0.35 and dir_2d.y < -0.35:
            apple_dir_state = 5
        if dir_2d.y < -0.65:
            apple_dir_state = 6
        if dir_2d.x < -0.35 and dir_2d.y < -0.35:
            apple_dir_state = 7
        #print(f"a{apple_dir_state} | dir: [{dir_2d.x}, {dir_2d.y}] | angle: {round((math.degrees(math.atan2(dir_2d.y, dir_2d.x) / 360)) * 8)}")
    else:
        print("apple_dist should not be 0!")

    return SnakeState(walls_state, apple_dir_state)

def find_state_tile(context, state: SnakeState):
    name = state.state_tile_obj_name()
    return context.global_scene.objects.get(name)

def get_tile_at_pos(context, abs_pos, max_depth = 3, obj = None):
    closest_tile = None
    min_dist = float("inf")
    base_obj = obj
    if base_obj is None:
        base_obj = context
    tiles = find_recursive_list(context, base_obj, "tile_", max_depth)
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
    # floored_pos_x = int(math.floor(guy.matrix_world.translation.x))
    # floored_pos_y = int(math.floor(guy.matrix_world.translation.y))
    # floored_pos_z = int(math.floor(guy.matrix_world.translation.z))
    # property_name = f"tile_at_{floored_pos_x}_{floored_pos_y}_{floored_pos_z}"
    # if property_name in guy:
    #     exact_tile_name = guy[property_name]
    #     return context.global_scene.objects[exact_tile_name]

    max_depth = 3
    base_obj = context
    thinking_board = find_recursive(context, context, "thinking_board", False, 3)
    if thinking_board is not None:
        base_obj = thinking_board
        max_depth = 2

    tile = get_tile_at_pos(context, guy.matrix_world.translation, max_depth, base_obj)
    if tile is None:
        print("ERROR: No tile under 'guy' found")
    #if tile:
    #    guy[property_name] = tile.name
    return tile

def get_tile_at_snake_head(context):
    snake_head = get_snake_head(context)
    play_board = find_recursive(context, context, "play_board")
    if play_board is None:
        return None
    tile = get_tile_at_pos(context, get_world_location(snake_head), 2, play_board)
    return tile

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

def get_guy_prev_tile(context):
    guy = get_guy(context)
    prev_guy_pos = Vector((get_property(guy, "jump_starting_abs_pos_x", guy.location.x), get_property(guy, "jump_starting_abs_pos_y", guy.location.y), get_property(guy, "jump_starting_abs_pos_z", guy.location.z)))
    return get_tile_at_pos(context, prev_guy_pos)

def get_guy_prev_action_tile(context):
    guy = get_guy(context)
    prev_guy_pos = Vector((get_property(guy, "jump_starting_abs_pos_x", guy.location.x), get_property(guy, "jump_starting_abs_pos_y", guy.location.y), get_property(guy, "jump_starting_abs_pos_z", guy.location.z)))
    play_board = find_recursive(context, context, "thinking_board")
    tile = get_tile_at_pos(context, prev_guy_pos, 2, play_board)
    return tile

def poke_guy_prev_tile(context, duration_num_frames):
    guy = get_guy(context)
    guy["start_poke_frame"] = context.frame_current
    guy["end_poke_frame"] = context.frame_current + duration_num_frames
    guy["poke_target_x"] = get_property(guy, "jump_starting_abs_pos_x", guy.location.x) + 0.5
    guy["poke_target_y"] = get_property(guy, "jump_starting_abs_pos_y", guy.location.y)
    guy["poke_target_z"] = get_property(guy, "jump_starting_abs_pos_z", guy.location.z)

def closely_look_guy(context, duration_num_frames = 20):
    guy = get_guy(context)
    guy["start_closely_look_frame"] = context.frame_current
    guy["end_closely_look_frame"] = context.frame_current + duration_num_frames

def jump_guy(context, direction_x, direction_y, duration_num_frames = 11):
    guy = get_guy(context)
    pos_abs = get_world_location(guy)
    guy["start_jump_frame"] = context.frame_current
    guy["end_jump_frame"] = context.frame_current + duration_num_frames
    guy["jump_direction_x"] = direction_x
    guy["jump_direction_y"] = direction_y
    guy["jump_starting_pos_x"] = guy.location.x
    guy["jump_starting_pos_y"] = guy.location.y
    guy["jump_starting_pos_z"] = guy.location.z
    guy["jump_starting_abs_pos_x"] = pos_abs.x
    guy["jump_starting_abs_pos_y"] = pos_abs.y
    guy["jump_starting_abs_pos_z"] = pos_abs.z

def jump_to_action_guy(context, result, duration_num_frames = 11):
    guy = get_guy(context)
    pos_abs = get_world_location(guy)
    guy["start_jump_to_action_frame"] = context.frame_current
    guy["end_jump_to_action_frame"] = context.frame_current + duration_num_frames
    guy["jump_to_action_result"] = result
    guy["jump_to_action_starting_pos_x"] = guy.location.x
    guy["jump_to_action_starting_pos_y"] = guy.location.y
    guy["jump_to_action_starting_pos_z"] = guy.location.z
    guy["jump_starting_abs_pos_x"] = pos_abs.x
    guy["jump_starting_abs_pos_y"] = pos_abs.y
    guy["jump_starting_abs_pos_z"] = pos_abs.z

def jump_to_state_guy(context, new_state, duration_num_frames = 40):
    guy = get_guy(context)
    pos_abs = get_world_location(guy)
    guy["start_jump_to_state_frame"] = context.frame_current
    guy["end_jump_to_state_frame"] = context.frame_current + duration_num_frames
    guy["jump_to_state_state"] = new_state.state_tile_obj_name()
    guy["jump_to_state_starting_pos_x"] = guy.location.x
    guy["jump_to_state_starting_pos_y"] = guy.location.y
    guy["jump_to_state_starting_pos_z"] = guy.location.z
    guy["jump_to_state_starting_abs_pos_x"] = pos_abs.x
    guy["jump_to_state_starting_abs_pos_y"] = pos_abs.y
    guy["jump_to_state_starting_abs_pos_z"] = pos_abs.z

def get_tail_number(name):
    number = int(name.split("_")[-1])
    return number

def do_snake_tail_action(context, source, tail, action, duration_num_frames = 20):
    number = get_tail_number(tail.name)
    next_tail = context.global_scene.objects.get(f"tail_{(number+1)}")
    tail["tail_action_frame_start"] = context.frame_current
    tail["tail_action_frame_end"] = context.frame_current + duration_num_frames
    tail["tail_action_old_starting_pos_x"] = tail["tail_action_starting_pos_x"]
    tail["tail_action_old_starting_pos_y"] = tail["tail_action_starting_pos_y"]
    tail["tail_action_old_starting_pos_z"] = tail["tail_action_starting_pos_z"]
    tail["tail_action_starting_pos_x"] = round(tail.location.x)
    tail["tail_action_starting_pos_y"] = round(tail.location.y)
    tail["tail_action_starting_pos_z"] = round(tail.location.z)
    tail["tail_action_ending_pos_x"] = round(source.location.x)
    tail["tail_action_ending_pos_y"] = round(source.location.y)
    tail["tail_action_ending_pos_z"] = round(source.location.z)
    if next_tail:
        do_snake_tail_action(context, tail, next_tail, action, duration_num_frames)

def do_snake_action(context, action, duration_num_frames = 20):
    snake_head = get_snake_head(context)
    snake_head["action_frame_start"] = context.frame_current
    snake_head["action_frame_end"] = context.frame_current + duration_num_frames
    snake_head["action_starting_pos_x"] = round(snake_head.location.x)
    snake_head["action_starting_pos_y"] = round(snake_head.location.y)
    snake_head["action_starting_pos_z"] = round(snake_head.location.z)
    snake_head["action_starting_rot_z"] = snake_head.rotation_euler.z
    snake_head["action_action"] = action
    do_snake_tail_action(context, snake_head, context.global_scene.objects["tail_1"], action, duration_num_frames)

def lose_guy(context, duration_num_frames = 10):
    guy = get_guy(context)
    guy["lost_frame"] = context.frame_current
    guy["lost_frame_end"] = context.frame_current + duration_num_frames
    guy["num_losses"] = get_property(guy, "num_losses", 0) + 1
    get_text_penalty(context).data.body = str(guy["num_losses"])

def win_guy(context, duration_num_frames = 3):
    guy = get_guy(context)
    guy["win_frame"] = context.frame_current
    guy["win_frame_end"] = context.frame_current + duration_num_frames
    guy["num_wins"] = get_property(guy, "num_wins", 0) + 1
    get_text_rewards(context).data.body = str(guy["num_wins"])

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
        tile = None
        snake_head = get_snake_head(context)
        if snake_head is not None:
            wheel_result = guy["jump_to_action_result"]
            result_tile_name = f"tile_move_{wheel_result}".lower()
            result_tile = context.global_scene.objects.get(result_tile_name)
            if result_tile is None:
                print(f"Failed to find tile of exact name '{result_tile_name}'")
            tile = result_tile
        else:
            tile = get_tile_at_guy(context)
        #print(f"Obtaining aple for '{tile.name}'")
        apple = find_recursive(context, tile, "apple")
        is_hidden_apple = False
        if apple is None:
            apple = find_recursive(context, tile, "hidden_apple")
            is_hidden_apple = True
        guy_pos = get_world_location(guy)
        guy_forward = get_world_forward(guy)
        old_apple_pos = get_world_location(apple.parent)
        target_apple_pos = guy_pos + guy_forward * apple_pos_x + Vector((0, 0, 0.5))
        new_apple_pos = old_apple_pos + (target_apple_pos - old_apple_pos) * anim
        set_world_location(apple, new_apple_pos)
        if is_hidden_apple:
            if anim >= 0.99:
                apple.scale = Vector((0.1, 0.1, 0.1))
            else:
                scale_anim = remap_clamped(anim, 0, 0.1, 0, 1)
                apple.scale = Vector((scale_anim, scale_anim, scale_anim))

def handle_lost_guy(context):
    guy = get_guy(context)
    lost_frame = get_property(guy, "lost_frame", -1)
    lost_frame_end = get_property(guy, "lost_frame_end", -1)
    if lost_frame >= 0:
        anim = max(0, min((context.frame_current - lost_frame) / (lost_frame_end - lost_frame), 1), 0)
        starting_rot_y = get_guy_starting_pos(context).z
        target_rot_y = -90
        new_rot_y = starting_rot_y + (target_rot_y - starting_rot_y) * anim
        guy.rotation_euler.x = math.radians(-new_rot_y)
        guy.location.z = starting_rot_y + math.sin(anim * math.pi * 0.9) * 0.4

def handle_closely_look_guy(context):
    guy = get_guy(context)
    head = find_recursive(context, guy, "head")
    if head is None:
        return
    start_frame = get_property(guy, "start_closely_look_frame", -1)
    end_frame = get_property(guy, "end_closely_look_frame", -1)
    if start_frame >= 0:
        perc = max(0, min((context.frame_current - start_frame) / (end_frame - start_frame), 1), 0)
        head.rotation_euler.y = (math.cos(perc * math.pi * 2) - 1) * 0.3

def handle_poke_guy(context):
    guy = get_guy(context)
    if guy is None or "start_poke_frame" not in guy:
        return None
    start_frame = guy["start_poke_frame"]
    end_frame = guy["end_poke_frame"]
    poke_target = Vector((guy["poke_target_x"], guy["poke_target_y"], guy["poke_target_z"]))
    #print(f"Getting Poke abs location: {poke_target}")
    anim = max(0, min((context.frame_current - start_frame) / (end_frame - start_frame), 1), 0)
    #print(f"Poke anim: {anim}")
    arm_left = find_recursive(context, guy, "arm_left")
    arm_right = find_recursive(context, guy, "arm_right")
    arm_to_use = arm_right
    diff_arm_right = Vector(get_world_location(arm_right) - poke_target)
    diff_arm_left  = Vector(get_world_location(arm_left)  - poke_target)
    distance = diff_arm_right.length
    if diff_arm_left.length < diff_arm_right.length:
        arm_to_use = arm_left
        distance = diff_arm_left.length
    #print(f"distance: {distance}, scale {get_world_scale(arm_to_use).z}")
    point_object_to(poke_target, arm_to_use)
    arm_stretch_dist = distance # fix is probably,  max(distance, 1.0).. but at the same time its kinda funny
    #if abs(guy.rotation_euler.x) > EPS: # if guy is laying down
    #    arm_stretch_dist = 8
    arm_to_use.scale.z = math.sin(anim*math.pi) * arm_stretch_dist * 3.6
    #arm_to_use.scale.z = 1 + ((distance-1) * math.sin(anim*math.pi)) * arm_stretch_dist
    #print(f"given dist: {distance}, scale: {arm_to_use.scale.z}, dist: {arm_stretch_dist}")
    #print(f"z scale: {arm_to_use.scale.z} ({distance}, {arm_stretch_dist})")
    if anim >= 1:
        guy.pop("start_poke_frame", None)
        reset_guy_arms(context, guy)

def handle_jump_guy_to(context, guy, start_frame, end_frame, from_abs_x, from_abs_y, to_abs_x, to_abs_y, jump_height = 10, facing_direction_x = 0, facing_direction_y = 0):
    total_anim = max(0, min((context.frame_current - start_frame) / (end_frame - start_frame), 1), 0)

    facing_direction = 0
    facing_direction_start = 0

    anim_turn          = remap(total_anim,  0, 0.3, 0, 1)
    anim_jump          = remap(total_anim,  0.3, 0.7, 0, 1)
    anim_turn_back     = remap(total_anim,  0.7, 1.0, 0, 1)

    if anim_turn >= 0 and anim_turn <= 1:
        guy.scale = (0.1, 0.1, 0.1 - anim_turn * 0.02)
        guy.rotation_euler.z = math.radians(facing_direction_start + (anim_turn * (facing_direction-facing_direction_start)))
        set_world_location(guy, Vector((from_abs_x, from_abs_y, get_guy_starting_pos(context).z)))
    if anim_jump >= 0 and anim_jump <= 1:
        guy.scale = (0.1, 0.1, 0.1)
        new_pos = Vector((from_abs_x + (to_abs_x - from_abs_x) * anim_jump,
                          from_abs_y + (to_abs_y - from_abs_y) * anim_jump,
                          get_guy_starting_pos(context).z + math.sin(anim_jump * math.pi) * jump_height))
        set_world_location(guy, new_pos)
        guy.rotation_euler.z = math.radians(facing_direction_start + (facing_direction-facing_direction_start))
    if anim_turn_back >= 0 and anim_turn_back <= 1:
        guy.scale = (0.1, 0.1, 0.08 + anim_turn_back * 0.02)
        new_pos = Vector((to_abs_x,
                          to_abs_y,
                          get_guy_starting_pos(context).z))
        set_world_location(guy, new_pos)
        guy.rotation_euler.z = math.radians(facing_direction_start + ((1-anim_turn_back) * (facing_direction-facing_direction_start)))
    if anim_turn_back >= 1:
        new_pos = Vector((to_abs_x,
                          to_abs_y,
                          get_guy_starting_pos(context).z))
        set_world_location(guy, new_pos)
        guy.rotation_euler.z = math.radians(facing_direction_start)
        guy.scale = (0.1, 0.1, 0.1)
        guy.pop("start_jump_to_action_frame", None)
        return True
    return False


def handle_jump_guy(context):
    guy = get_guy(context)
    if guy is None or "start_jump_frame" not in guy:
        return None

    start_frame = guy["start_jump_frame"]
    end_frame = guy["end_jump_frame"]
    direction_x = guy["jump_direction_x"]
    direction_y = guy["jump_direction_y"]
    jump_starting_pos_x = guy["jump_starting_pos_x"]
    jump_starting_pos_y = guy["jump_starting_pos_y"]
    total_anim = max(0, min((context.frame_current - start_frame) / (end_frame - start_frame), 1), 0)

    facing_direction = 0
    if direction_y > 0:
        facing_direction = 90
    if direction_y < 0:
        facing_direction = -90
    facing_direction_start = 0

    anim_turn          = remap(total_anim,  0, 0.3, 0, 1)
    anim_jump          = remap(total_anim,  0.3, 0.7, 0, 1)
    anim_turn_back     = remap(total_anim,  0.7, 1.0, 0, 1)

    target_y = jump_starting_pos_y - direction_y
    target_x = jump_starting_pos_x - direction_x

    if anim_turn >= 0 and anim_turn <= 1:
        guy.scale = (0.1, 0.1, 0.1 - anim_turn * 0.02)
        guy.rotation_euler.z = math.radians(facing_direction_start + (anim_turn * (facing_direction-facing_direction_start)))
    if anim_jump >= 0 and anim_jump <= 1:
        guy.scale = (0.1, 0.1, 0.1)
        guy.location.x = jump_starting_pos_x + (target_x - jump_starting_pos_x) * anim_jump
        guy.location.y = jump_starting_pos_y + (target_y - jump_starting_pos_y) * anim_jump
        guy.location.z = get_guy_starting_pos(context).z + math.sin(anim_jump * math.pi)
        guy.rotation_euler.z = math.radians(facing_direction_start + (facing_direction-facing_direction_start))
    if anim_turn_back >= 0 and anim_turn_back <= 1:
        guy.scale = (0.1, 0.1, 0.08 + anim_turn_back * 0.02)
        guy.location.x = target_x
        guy.location.y = target_y
        guy.location.z = get_guy_starting_pos(context).z
        guy.rotation_euler.z = math.radians(facing_direction_start + ((1-anim_turn_back) * (facing_direction-facing_direction_start)))
    if anim_turn_back >= 1:
        guy.location.x = target_x
        guy.location.y = target_y
        guy.location.z = get_guy_starting_pos(context).z
        guy.rotation_euler.z = math.radians(facing_direction_start)
        guy.scale = (0.1, 0.1, 0.1)
        guy.pop("start_jump_frame", None)
        guy.pop("jump_direction_x", None)
        guy.pop("jump_direction_y", None)

def handle_jump_to_action_guy(context):
    guy = get_guy(context)
    if guy is None or "start_jump_to_action_frame" not in guy:
        return None
    start_frame = guy["start_jump_to_action_frame"]
    end_frame = guy["end_jump_to_action_frame"]
    wheel_result = guy["jump_to_action_result"]
    jump_starting_abs_pos_x = guy["jump_starting_abs_pos_x"]
    jump_starting_abs_pos_y = guy["jump_starting_abs_pos_y"]

    result_tile_name = f"tile_move_{wheel_result}".lower()
    result_tile = context.global_scene.objects.get(result_tile_name)
    if result_tile is None:
        print(f"Failed to find tile of exact name '{result_tile_name}'")

    target_x = get_world_location(result_tile).x
    target_y = get_world_location(result_tile).y

    if handle_jump_guy_to(context, guy, start_frame, end_frame, jump_starting_abs_pos_x, jump_starting_abs_pos_y, target_x, target_y, 10):
        result_tile.location.z = ACTION_TILE_POS_Z
        guy.pop("start_jump_to_action_frame", None)
    else:
        total_anim   = max(0, min((context.frame_current - start_frame) / (end_frame - start_frame), 1), 0)
        landing_anim = remap_clamped(total_anim,  0.7, 1.0, 0, 1)
        boink = -math.sin(landing_anim * math.pi) * 0.5
        result_tile.location.z = ACTION_TILE_POS_Z + boink
        guy.location.z = guy.location.z + boink


def handle_jump_to_state_guy(context):
    global GUY_POS_STATE_TILE_OFFSET
    guy = get_guy(context)
    if guy is None or "start_jump_to_state_frame" not in guy:
        return None

    start_frame = guy["start_jump_to_state_frame"]
    end_frame = guy["end_jump_to_state_frame"]
    state = SnakeState.from_state_tile_obj_name(guy["jump_to_state_state"])
    jump_starting_abs_pos_x = guy["jump_to_state_starting_abs_pos_x"]
    jump_starting_abs_pos_y = guy["jump_to_state_starting_abs_pos_y"]

    tile_name = state.state_tile_obj_name()
    #print(f"Jumping to '{tile_name}'")
    target_tile = context.global_scene.objects.get(tile_name)
    if target_tile is None:
        print(f"Failed to find tile of exact name '{tile_name}'")

    target_y = get_world_location(target_tile).y + GUY_POS_STATE_TILE_OFFSET.y
    target_x = get_world_location(target_tile).x + GUY_POS_STATE_TILE_OFFSET.x

    if handle_jump_guy_to(context, guy, start_frame, end_frame, jump_starting_abs_pos_x, jump_starting_abs_pos_y, target_x, target_y, 10):
        guy.pop("start_jump_to_state_frame", None)

def handle_snake_action_tail(context, tail):
    if "tail_action_frame_start" not in tail:
        return
    number = get_tail_number(tail.name)
    start_frame    = tail["tail_action_frame_start"]
    end_frame      = tail["tail_action_frame_end"]
    starting_pos_x = tail["tail_action_starting_pos_x"]
    starting_pos_y = tail["tail_action_starting_pos_y"]
    ending_pos_x   = tail["tail_action_ending_pos_x"]
    ending_pos_y   = tail["tail_action_ending_pos_y"]
    total_anim = 1
    if end_frame > start_frame:
        end_frame = end_frame-1
    if end_frame > start_frame:
        total_anim = max(0, min((context.frame_current - start_frame) / (end_frame - start_frame), 1), 0)
    new_pos_x = starting_pos_x + (ending_pos_x - starting_pos_x) * total_anim
    new_pos_y = starting_pos_y + (ending_pos_y - starting_pos_y) * total_anim
    #print(f"Setting tail pos of '{tail.name}' to {new_pos_x}, {new_pos_y}")
    tail.location.x = new_pos_x
    tail.location.y = new_pos_y
    next_tail = context.global_scene.objects.get(f"tail_{(number+1)}")
    if next_tail:
        handle_snake_action_tail(context, next_tail)
    if total_anim >= 1:
        tail.pop("tail_action_frame_start", None)

def action_to_dir(action):
    dir_x = 0
    dir_y = 0
    if action.lower() == "w":
        dir_x = 0
        dir_y = 1
    if action.lower() == "e":
        dir_x = 0
        dir_y = -1
    if action.lower() == "n":
        dir_x = 1
        dir_y = 0
    if action.lower() == "s":
        dir_x = -1
        dir_y = 0
    return (dir_x, dir_y)

def handle_snake_action(context):
    snake_head = get_snake_head(context)
    if snake_head is None or "action_frame_start" not in snake_head:
        return None

    start_frame = snake_head["action_frame_start"]
    end_frame = snake_head["action_frame_end"]
    if end_frame > (start_frame+1):
        end_frame = end_frame-1
    starting_pos_x = snake_head["action_starting_pos_x"]
    starting_pos_y = snake_head["action_starting_pos_y"]
    starting_rot_z = snake_head["action_starting_rot_z"]
    action = snake_head["action_action"]

    total_anim = max(0, min((context.frame_current - start_frame) / (end_frame - start_frame), 1), 0)
    rotate_anim = remap_clamped(total_anim, 0, 0.2, 0, 1)
    dir_x, dir_y = action_to_dir(action)

    ending_pos_x = (starting_pos_x + dir_x)
    ending_pos_y = (starting_pos_y + dir_y)

    new_pos_x = starting_pos_x + (ending_pos_x - starting_pos_x) * total_anim
    new_pos_y = starting_pos_y + (ending_pos_y - starting_pos_y) * total_anim

    #print(f"posx: {new_pos_x}, posy: {new_pos_y} | {total_anim} | {starting_pos_x}, {starting_pos_y}")
    snake_head.location.x = new_pos_x
    snake_head.location.y = new_pos_y

    target_rot_z = math.atan2(dir_y, dir_x) + math.pi
    delta = target_rot_z - starting_rot_z
    delta = (delta + math.pi) % (2 * math.pi) - math.pi
    snake_head.rotation_euler.z = starting_rot_z + delta * rotate_anim

    #target_rot_z = math.atan2(dir_y, dir_x) + math.pi
    #snake_head.rotation_euler.z = starting_rot_z + (target_rot_z - starting_rot_z) * rotate_anim

    handle_snake_action_tail(context, context.global_scene.objects["tail_1"])

def handle_snake_extension_ext(context, tail_obj):
    if tail_obj is None:
        return

    tail_number = get_tail_number(tail_obj.name)
    handle_snake_extension_ext(context, context.global_scene.objects.get(f"tail_{(tail_number + 1)}"))
    if "start_extend_frame" not in tail_obj:
        return

    start_frame = tail_obj["start_extend_frame"]
    end_frame = tail_obj["end_extend_frame"]
    total_anim = max(0, min((context.frame_current - start_frame) / (end_frame - start_frame), 1), 0)
    start_pos = Vector((tail_obj["extend_start_pos_x"], tail_obj["extend_start_pos_y"]))
    end_pos = Vector((tail_obj["extend_end_pos_x"], tail_obj["extend_end_pos_y"]))
    tail_obj.location.x = start_pos.x + (end_pos.x - start_pos.x) * total_anim
    tail_obj.location.y = start_pos.y + (end_pos.y - start_pos.y) * total_anim
    if total_anim >= 1:
        tail_obj.pop("start_extend_frame", None)

def handle_snake_extension(context):
    handle_snake_extension_ext(context, context.global_scene.objects["tail_2"])

def is_dice_on_spin(context):
    dice = get_dice(context, False)
    if dice is None:
        return False
    if "result_is_spin" not in dice:
        return False
    on_spin = dice["result_is_spin"]
    #print(f"on stpinnn:: {on_spin}, for : {dice.name}")
    return on_spin
        #dice["result_is_spin"] = side.z > 0.9
    #spin_side_obj = find_recursive(context, dice, "spin_side", False, 2)
    #spin_side_pos = get_world_location(spin_side_obj)
    #side = get_world_up(dice)
    #print(f"side: {side}. pos: ${spin_side_pos}")
    #return spin_side_pos.z > 3.0

def handle_dice(context):
    bounce_height = 1
    guy = get_guy(context)
    start_frame = get_property(guy, "start_throw_frame", -1)
    if start_frame >= 0:
        dice = get_dice_from_guy(context, guy)
        end_frame            = dice["end_throw_frame"]
        ends_at_spin         = dice["ends_at_spin"]
        rot_axis             = Vector((dice["rot_axis_x"], dice["rot_axis_y"], dice["rot_axis_z"]))
        landing_offset_angle = dice["landing_offset_angle"]
        starting_angle       = dice["starting_angle"]

        dice_sub_base = find_recursive(context, guy, "dice_sub_base", False, 3)
        total_anim = max(0, min((context.frame_current - start_frame) / (end_frame - start_frame), 1), 0)

        anim_scale     = remap_clamped(total_anim,  0, 0.1, 0, 1)
        anim_throw     = remap(total_anim,  0.0,   0.6,   0, 1)
        anim_flat      = remap_clamped(total_anim,  0.6, 0.65,   0, 1)
        anim_pickup    = remap(total_anim,  0.9, 1.0,   0, 1)

        ending_angle = starting_angle + 360*1
        if ends_at_spin:
            ending_angle = ending_angle + (360 - (ending_angle % 360))
            ending_angle = ending_angle + landing_offset_angle
        else:
            if ending_angle % 360 < 50 or ending_angle % 360 > (360 - 50):
                ending_angle = ending_angle + 90

        if anim_scale > 0 and anim_throw <= 1:
            dice_sub_base.hide_viewport = False
            dice_sub_base.hide_render = False
            dice_sub_base.scale = (anim_scale,anim_scale,anim_scale)
            set_axis_angle(dice, rot_axis, starting_angle)
        if anim_throw > 0 and anim_throw <= 1:
            dice_sub_base.hide_viewport = False
            dice_sub_base.hide_render = False
            dice.location.z = math.sin(anim_throw * math.pi) * bounce_height
            dice_sub_base.scale = (anim_scale,anim_scale,anim_scale)
            set_axis_angle(dice, rot_axis, starting_angle + (ending_angle - starting_angle) * anim_throw)
        if anim_flat > 0:
            snap_pitch_roll(dice, anim_flat)
        if anim_pickup > 0 and anim_pickup < 1:
            dice_sub_base.hide_viewport = False
            dice_sub_base.hide_render = False
            dice.location.z = 0
            dice_sub_base.scale = (1-anim_pickup, 1-anim_pickup, 1-anim_pickup)
        if anim_pickup >= 1:
            #spin_side_obj = find_recursive(context, dice, "spin_side", False, 2)
            #spin_side_pos = get_world_location(spin_side_obj)
            side = get_world_up(dice)
            #print(f"side: {side}. is spin: {side.z > 0.9}. for: {dice.name}")
            dice["result_is_spin"] = side.z > 0.9
            dice_sub_base.hide_viewport = False
            dice_sub_base.hide_render = True
            dice_sub_base.scale = (0,0,0)
            dice.location.z = 0
            dice.pop("start_throw_frame", None)
            guy.pop("start_throw_frame", None)
    
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
            if not obj.data.name.startswith("gen_"):
                obj.data.name = "gen_" + obj.data.name
            
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

def move_objects_to_trash_recursive(global_scene, obj):
    trash_obj = global_scene.objects["trash"]

    # # First move all children recursively
    children = list(obj.children)
    for child in children:
        move_objects_to_trash_recursive(global_scene, child)
    obj.parent = trash_obj
    obj.name = "remove_me"
    obj.hide_viewport = True
    obj.hide_render = True
    pass

def delete_trashed_objects(global_scene):
    trash_obj = global_scene.objects["trash"]
    names_to_remove = []
    for child in trash_obj.children:
        if child.name.startswith("remove_me"):
            names_to_remove.append(child.name)

    for object_name_to_remove in names_to_remove:
        obj = global_scene.objects[object_name_to_remove]
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
    return obj.matrix_world.to_quaternion() @ Vector((-1, 0, 0))

#def get_world_left(obj):
#    return obj.matrix_world.to_quaternion() @ Vector((1, 0, 0))

def get_world_up(obj):
    return obj.matrix_world.to_quaternion() @ Vector((0, 0, 1))

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

def internal_is_match(obj, name):
    if ((obj.name.startswith(name + ".") or obj.name.startswith("gen_" + name + ".") or obj.name == name or obj.name == ("gen_" + name)) or (obj.name.startswith(name) and name.endswith("_"))):
        return True
    return False

def internal_find_recursive(context, obj, name, allow_prefab = False, max_depth = 10):
    if max_depth < 0:
        return None
    for child in obj.children:
        if internal_is_match(child, name):
            if not should_ignore(obj, allow_prefab):
                return child
    for child in obj.children:
        found = internal_find_recursive(context, child, name, allow_prefab, max_depth-1)
        if found:
            return found
    return None

def check_if_it_is_generator_object(obj):
    check_obj = obj
    while check_obj != None:
        if check_obj.name.startswith("gen_"):
            return True
        check_obj = check_obj.parent
    return False

def find_recursive(context, obj, name, allow_prefab = False, max_depth = 10):
    if obj == None:
        return None

    is_generator_object = check_if_it_is_generator_object(obj)
    if is_generator_object:
        last_find_result_name = get_property(obj, f"last_find_result_of_{name}", "")
        if last_find_result_name != "":
            return context.global_scene.objects.get(last_find_result_name)

    result = None
    if internal_is_match(obj, name):
        if not should_ignore(obj, allow_prefab):
            result = obj
    if result == None:
        result = internal_find_recursive(context, obj, name, allow_prefab, max_depth-1)
    if result and is_generator_object:
        obj[f"last_find_result_of_{name}"] = result.name
    return result

def unique_list(lst):
    seen = set()
    result = []
    for item in lst:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result

def find_prefab(context, name):
    return find_recursive(context, context.global_scene.objects["_prefabs"], name, True, 3)

def find_recursive_list(context, obj, name, max_depth = 10):
    matches = []
    if obj == None or max_depth <= 0:
        return matches
    if isinstance(obj, bpy.types.Scene):
        for real_obj in obj.objects:
            if not should_ignore(real_obj):
                matches.extend(find_recursive_list(context, real_obj, name, max_depth-1))
        return unique_list(matches)
    else:
        if internal_is_match(obj, name):
            matches.append(obj)
        for child in obj.children:
            if not should_ignore(child):
                matches.extend(find_recursive_list(context, child, name, max_depth-1))
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

def delete_generated_meshes():
    for mesh in list(bpy.data.meshes):
        if not mesh.name.startswith("gen_"):
            continue
        if mesh.name.startswith("gen_") and mesh.users == 0:
            bpy.data.meshes.remove(mesh)

def get_object_path(obj):
    parts = []
    while obj is not None:
        parts.append(obj.name)
        obj = obj.parent
    return "/".join(reversed(parts))

def point_object_to_internal(world_pos, obj, track_axis='Z', up_axis='Y', invert = False):
    world_pos = Vector(world_pos)

    # Compute the direction from the object to the target
    obj_world_pos = obj.matrix_world.translation
    direction = world_pos - obj_world_pos

    if invert:
        direction = -direction
    if direction.length == 0:
        return  # Avoid invalid rotation

    # Compute the rotation in world space
    rot_world = direction.normalized().to_track_quat(track_axis, up_axis)

    # Convert world rotation to local rotation if the object has a parent
    if obj.parent:
        parent_inv = obj.parent.matrix_world.to_quaternion().inverted()
        rot_local = parent_inv @ rot_world
    else:
        rot_local = rot_world

    # Preserve existing object rotation offset if needed
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = rot_local

def point_object_to(world_pos, obj, track_axis='Z', up_axis='Y'):
    obj_world_pos = obj.matrix_world.translation
    direction = world_pos - obj_world_pos

    point_object_to_internal(world_pos, obj, track_axis, up_axis, True)
    forward = obj.matrix_world.to_quaternion() @ Vector((0, 0, 1))
    diff = math.dist (direction.normalized(), forward)
    #print(f"forward of {obj.name}: {forward}, diff {diff}")
    #if diff > 1:
    #    flip = mathutils.Quaternion(Vector((0, 1, 0)), math.pi)
    #    obj.rotation_quaternion = obj.rotation_quaternion @ flip

def set_axis_angle(obj, axis, angle_deg):
    axis = Vector(axis).normalized()
    angle_rad = math.radians(angle_deg)

    q = mathutils.Quaternion(axis, angle_rad)

    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = q

def snap_pitch_roll(obj, anim_perc=1.0):
    def snap_90(angle_rad):
        return round(angle_rad / (math.pi / 2)) * (math.pi / 2)
    obj.rotation_mode = 'XYZ'
    e = obj.rotation_euler.copy()
    yaw = e.z
    snapped_x = snap_90(e.x)
    snapped_y = snap_90(e.y)
    target_euler = mathutils.Euler((snapped_x, snapped_y, yaw), 'XYZ')
    q_current = obj.rotation_euler.to_quaternion()
    q_target = target_euler.to_quaternion()
    q_result = q_current.slerp(q_target, anim_perc)
    obj.rotation_mode = 'QUATERNION'
    obj.rotation_quaternion = q_result

def time_function(fn, *args, **kwargs):
    start = time.perf_counter()
    result = fn(*args, **kwargs)
    end = time.perf_counter()

    duration_us = (end - start) * 1_000_000
    print(f"{fn.__name__} took {duration_us:.1f} µs")

    return result

# ========= NO LONGER USED ===========

