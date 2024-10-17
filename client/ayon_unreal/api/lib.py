import unreal
from ayon_core.pipeline import (
    get_current_project_name,
    get_representation_path
)
from ayon_unreal.api.pipeline import get_camera_tracks
import ayon_api


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
    sequence.set_playback_start(frameStart)
    sequence.set_playback_end(frameEnd)
    sequence.set_work_range_start(frameStart / fps)
    sequence.set_work_range_end(frameEnd / fps)


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
            anim_section.set_range(frameStart, frameEnd)
            set_sequence_frame_range(sequence, frameStart, frameEnd)


def get_representation(parent_id, version_id):
    project_name = get_current_project_name()
    return next(
        (repre for repre in ayon_api.get_representations(
            project_name, version_ids={parent_id})
            if repre["id"] == version_id
        ), None)


def import_camera_to_level_sequence(sequence, parent_id, version_id,
                                    namespace, world, frameStart,
                                    frameEnd):
    # Add a camera cut track to the sequence
    if not get_camera_tracks(sequence):
        sequence.add_master_track(unreal.MovieSceneCameraCutTrack)
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
    tracks = get_camera_tracks(sequence)
    if tracks:
        for track in tracks:
            sections = track.get_sections()
            for section in sections:
                track.remove_section(section)
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

    for binding in sequence.get_bindings():
        if binding.get_display_name() == camera_actor_name:
            camera_binding = sequence.get_binding_id(binding)
            unreal.log("camera_binding: {}".format(camera_binding))
            sections = get_sections(sequence)
            for section in sections:
                section.set_camera_binding_id(camera_binding)

    set_sequence_frame_range(sequence, frameStart, frameEnd)


def get_sections(sequence):
    tracks = get_camera_tracks(sequence)
    sections = [section for track in tracks for section in track.get_sections()] if tracks else []
    return sections
