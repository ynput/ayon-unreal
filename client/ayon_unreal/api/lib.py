import unreal
from ayon_core.pipeline import (
    get_current_project_name,
    get_representation_path
)
from ayon_unreal.api.pipeline import (
    get_camera_tracks,
    ls
)
from ayon_core.pipeline.context_tools import get_current_folder_entity
import ayon_api
from pathlib import Path



def update_skeletal_mesh(asset_content, sequence):
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    skeletal_mesh_asset = None
    for a in asset_content:
        imported_skeletal_mesh = ar.get_asset_by_object_path(a).get_asset()
        if imported_skeletal_mesh.get_class().get_name() == "SkeletalMesh":
            skeletal_mesh_asset = imported_skeletal_mesh
            break
    if sequence and skeletal_mesh_asset:
        # Get the EditorActorSubsystem instance
        editor_actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

        # Get all level actors
        all_level_actors = editor_actor_subsystem.get_all_level_actors()

        for p in sequence.get_possessables():
            matching_actor = next(
                (actor.get_name() for actor in all_level_actors
                if actor.get_actor_label() == p.get_name()), None)

            actor = unreal.EditorLevelLibrary.get_actor_reference(f"PersistentLevel.{matching_actor}")
            # Ensure the actor is valid
            if actor:
                # Get the skeletal mesh component
                skeletal_mesh_component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
                if skeletal_mesh_component:
                    # Get the skeletal mesh
                    skeletal_mesh = skeletal_mesh_component.skeletal_mesh
                    if skeletal_mesh:
                        skel_mesh_comp = actor.get_editor_property('skeletal_mesh_component')
                        unreal.log("Replacing skeleton mesh component to alembic")
                        unreal.log(skel_mesh_comp)
                        if skel_mesh_comp:
                            if skel_mesh_comp.get_editor_property("skeletal_mesh") != imported_skeletal_mesh:
                                skel_mesh_comp.set_editor_property('skeletal_mesh', skeletal_mesh_asset)


def set_sequence_frame_range(sequence, frameStart, frameEnd):
    display_rate = sequence.get_display_rate()
    fps = float(display_rate.numerator) / float(display_rate.denominator)
    # temp fix on the incorrect frame range
    sequence.set_playback_start(frameStart)
    sequence.set_playback_end(frameEnd + 1)
    sequence.set_work_range_start(float(frameStart / fps))
    sequence.set_work_range_end(float(frameEnd / fps))
    sequence.set_view_range_start(float(frameStart / fps))
    sequence.set_view_range_end(float(frameEnd / fps))


def import_animation_sequence(asset_content, sequence, frameStart, frameEnd):
    bindings = []
    animation = None

    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    for a in asset_content:
        imported_asset_data = ar.get_asset_by_object_path(a).get_asset()
        if imported_asset_data.get_class().get_name() == "AnimSequence":
            animation = imported_asset_data
            break
    if sequence:
        # Add animation to the sequencer
        binding = None
        for p in sequence.get_possessables():
            if p.get_possessed_object_class().get_name() == "SkeletalMeshActor":
                binding = p
                bindings.append(binding)
        anim_section = None
        for binding in bindings:
            tracks = binding.get_tracks()
            track = None
            track = tracks[0] if tracks else binding.add_track(
                unreal.MovieSceneSkeletalAnimationTrack)

            sections = track.get_sections()
            if not sections:
                anim_section = track.add_section()
            else:
                anim_section = sections[0]

            params = unreal.MovieSceneSkeletalAnimationParams()
            params.set_editor_property('Animation', animation)
            anim_section.set_editor_property('Params', params)
            # temp fix on the incorrect frame range
            anim_section.set_range(frameStart, frameEnd + 1)


def get_representation(parent_id, version_id):
    project_name = get_current_project_name()
    return next(
        (repre for repre in ayon_api.get_representations(
            project_name, version_ids={parent_id})
            if repre["id"] == version_id
        ), None)


def import_camera_to_level_sequence(sequence, parent_id, version_id,
                                    namespace, world, frameStart, frameEnd):
    repre_entity = get_representation(parent_id, version_id)
    import_fbx_settings = unreal.MovieSceneUserImportFBXSettings()
    import_fbx_settings.set_editor_property('reduce_keys', False)
    camera_path = get_representation_path(repre_entity)

    camera_actor_name = unreal.Paths.split(namespace)[1]
    for spawned_actor in sequence.get_possessables():
        if spawned_actor.get_display_name() == camera_actor_name:
            spawned_actor.remove()

    sel_actors = unreal.GameplayStatics().get_all_actors_of_class(
        world, unreal.CameraActor)
    if sel_actors:
        for actor in sel_actors:
            unreal.EditorLevelLibrary.destroy_actor(actor)
    unreal.SequencerTools.import_level_sequence_fbx(
            world,
            sequence,
            sequence.get_bindings(),
            import_fbx_settings,
            camera_path
        )
    camera_actors = unreal.GameplayStatics().get_all_actors_of_class(
        world, unreal.CameraActor)
    if namespace:
        unreal.log(f"Spawning camera: {camera_actor_name}")
        for actor in camera_actors:
            actor.set_actor_label(camera_actor_name)
    tracks = get_camera_tracks(sequence)
    for track in tracks:
        sections = track.get_sections()
        for section in sections:
            # temp fix on the incorrect frame range
            section.set_range(frameStart, frameEnd + 1)

    set_sequence_frame_range(sequence, frameStart, frameEnd)


def remove_loaded_asset(container):
    # Check if the assets have been loaded by other layouts, and deletes
    # them if they haven't.
    containers = ls()
    layout_containers = [
        c for c in containers
        if (c.get('asset_name') != container.get('asset_name') and
            c.get('family') == "layout")]

    for asset in eval(container.get('loaded_assets')):
        layouts = [
            lc for lc in layout_containers
            if asset in lc.get('loaded_assets')]

        if not layouts:
            unreal.EditorAssetLibrary.delete_directory(str(Path(asset).parent))

            # Delete the parent folder if there aren't any more
            # layouts in it.
            asset_content = unreal.EditorAssetLibrary.list_assets(
                str(Path(asset).parent.parent), recursive=False,
                include_folder=True
            )

            if len(asset_content) == 0:
                unreal.EditorAssetLibrary.delete_directory(
                    str(Path(asset).parent.parent))


def import_animation(
    asset_dir, path, instance_name, skeleton, actors_dict,
    animation_file, bindings_dict, sequence
    ):
    anim_file = Path(animation_file)
    anim_file_name = anim_file.with_suffix('')

    anim_path = f"{asset_dir}/Animations/{anim_file_name}"

    folder_entity = get_current_folder_entity()
    # Import animation
    task = unreal.AssetImportTask()
    task.options = unreal.FbxImportUI()

    task.set_editor_property(
        'filename', str(path.with_suffix(f".{animation_file}")))
    task.set_editor_property('destination_path', anim_path)
    task.set_editor_property(
        'destination_name', f"{instance_name}_animation")
    task.set_editor_property('replace_existing', False)
    task.set_editor_property('automated', True)
    task.set_editor_property('save', False)

    # set import options here
    task.options.set_editor_property(
        'automated_import_should_detect_type', False)
    task.options.set_editor_property(
        'original_import_type', unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    task.options.set_editor_property(
        'mesh_type_to_import', unreal.FBXImportType.FBXIT_ANIMATION)
    task.options.set_editor_property('import_mesh', False)
    task.options.set_editor_property('import_animations', True)
    task.options.set_editor_property('override_full_name', True)
    task.options.set_editor_property('skeleton', skeleton)

    task.options.anim_sequence_import_data.set_editor_property(
        'animation_length',
        unreal.FBXAnimationLengthImportType.FBXALIT_EXPORTED_TIME
    )
    task.options.anim_sequence_import_data.set_editor_property(
        'import_meshes_in_bone_hierarchy', False)
    task.options.anim_sequence_import_data.set_editor_property(
        'use_default_sample_rate', False)
    task.options.anim_sequence_import_data.set_editor_property(
        'custom_sample_rate', folder_entity.get("attrib", {}).get("fps"))
    task.options.anim_sequence_import_data.set_editor_property(
        'import_custom_attribute', True)
    task.options.anim_sequence_import_data.set_editor_property(
        'import_bone_tracks', True)
    task.options.anim_sequence_import_data.set_editor_property(
        'remove_redundant_keys', False)
    task.options.anim_sequence_import_data.set_editor_property(
        'convert_scene', True)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    asset_content = unreal.EditorAssetLibrary.list_assets(
        anim_path, recursive=False, include_folder=False
    )

    animation = None

    for a in asset_content:
        unreal.EditorAssetLibrary.save_asset(a)
        imported_asset_data = unreal.EditorAssetLibrary.find_asset_data(a)
        imported_asset = unreal.AssetRegistryHelpers.get_asset(
            imported_asset_data)
        if imported_asset.__class__ == unreal.AnimSequence:
            animation = imported_asset
            break

    if animation:
        actor = None
        if actors_dict.get(instance_name):
            for a in actors_dict.get(instance_name):
                if a.get_class().get_name() == 'SkeletalMeshActor':
                    actor = a
                    break

        animation.set_editor_property('enable_root_motion', True)
        actor.skeletal_mesh_component.set_editor_property(
            'animation_mode', unreal.AnimationMode.ANIMATION_SINGLE_NODE)
        actor.skeletal_mesh_component.animation_data.set_editor_property(
            'anim_to_play', animation)

        if sequence:
            # Add animation to the sequencer
            bindings = bindings_dict.get(instance_name)

            ar = unreal.AssetRegistryHelpers.get_asset_registry()

            for binding in bindings:
                tracks = binding.get_tracks()
                track = None
                track = tracks[0] if tracks else binding.add_track(
                    unreal.MovieSceneSkeletalAnimationTrack)

                sections = track.get_sections()
                section = None
                if not sections:
                    section = track.add_section()
                else:
                    section = sections[0]

                    sec_params = section.get_editor_property('params')
                    curr_anim = sec_params.get_editor_property('animation')

                    if curr_anim:
                        # Checks if the animation path has a container.
                        # If it does, it means that the animation is
                        # already in the sequencer.
                        anim_path = str(Path(
                            curr_anim.get_path_name()).parent
                        ).replace('\\', '/')

                        _filter = unreal.ARFilter(
                            class_names=["AyonAssetContainer"],
                            package_paths=[anim_path],
                            recursive_paths=False)
                        containers = ar.get_assets(_filter)

                        if len(containers) > 0:
                            return

                section.set_range(
                    sequence.get_playback_start(),
                    sequence.get_playback_end())
                sec_params = section.get_editor_property('params')
                sec_params.set_editor_property('animation', animation)


def get_shot_track_names(sel_objects=None, get_name=True):
    selection = [
        a for a in sel_objects
        if a.get_class().get_name() == "LevelSequence"
    ]

    sub_sequence_tracks = [
        track for sel in selection for track in
        sel.find_master_tracks_by_type(unreal.MovieSceneSubTrack)
    ]

    movie_shot_tracks = [track for track in sub_sequence_tracks
                         if isinstance(track, unreal.MovieSceneCinematicShotTrack)]
    if get_name:
        return [section.get_shot_display_name() for shot_tracks in
                movie_shot_tracks for section in shot_tracks.get_sections()]
    else:
        return [section for shot_tracks in
                movie_shot_tracks for section in shot_tracks.get_sections()]


def get_shot_tracks(members):
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    selected_sequences = [
        ar.get_asset_by_object_path(member).get_asset() for member in members
    ]
    return get_shot_track_names(selected_sequences, get_name=False)
