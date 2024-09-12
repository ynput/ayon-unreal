import unreal


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
                break
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
                anim_section = track.add_section()
                anim_section = sections[-1]

        params = unreal.MovieSceneSkeletalAnimationParams()
        params.set_editor_property('Animation', animation)
        anim_section.set_editor_property('Params', params)
        anim_section.set_range(frameStart, frameEnd)
        set_sequence_frame_range(sequence, frameStart, frameEnd)