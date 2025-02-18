# -*- coding: utf-8 -*-
"""Loader for layouts."""
import json
from pathlib import Path
import unreal
from unreal import (
    EditorAssetLibrary,
    EditorLevelLibrary,
    LevelSequenceEditorBlueprintLibrary as LevelSequenceLib,
)
import ayon_api

from ayon_core.pipeline import get_current_project_name
from ayon_core.settings import get_current_project_settings
from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    generate_master_level_sequence,
    set_sequence_hierarchy,
    create_container,
    AYON_ROOT_DIR,
    format_asset_directory,
    get_top_hierarchy_folder,
    generate_hierarchy_path,
    update_container,
    remove_map_and_sequence,
    get_tracks
)
from ayon_unreal.api.lib import (
    import_animation
)
from ayon_core.lib import EnumDef


class LayoutLoader(plugin.LayoutLoader):
    """Load Layout from a JSON file"""

    label = "Load Layout"
    force_loaded = False
    folder_representation_type = "json"
    level_sequences_for_layouts = True

    @classmethod
    def apply_settings(cls, project_settings):
        super(LayoutLoader, cls).apply_settings(project_settings)
        # Apply import settings
        import_settings = project_settings["unreal"]["import_settings"]
        cls.force_loaded = import_settings["force_loaded"]
        cls.folder_representation_type = (
            import_settings["folder_representation_type"]
        )
        cls.level_sequences_for_layouts = (
            import_settings["level_sequences_for_layouts"]
        )
        cls.loaded_layout_dir = import_settings["loaded_layout_dir"]
        cls.remove_loaded_assets = import_settings["remove_loaded_assets"]
        cls.resolution_priority = import_settings.get(
            "resolution_priority", cls.resolution_priority)
        cls.loaded_asset_dir = import_settings.get(
            "loaded_asset_dir", cls.loaded_asset_dir)

    @classmethod
    def get_options(cls, contexts):
        defs = super().get_options(contexts)
        if cls.force_loaded:
            defs.append(
                EnumDef(
                    "folder_representation_type",
                    label="Override layout representation by",
                    items={
                        "json": "json",
                        "fbx": "fbx",
                        "abc": "abc"
                    },
                    default=cls.folder_representation_type
                )
            )
        return defs

    def _process_family(
        self, assets, class_name, transform, basis, sequence, inst_name=None,
        rotation=None, unreal_import=False
    ):
        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        actors = []
        bindings = []

        for asset in assets:
            obj = ar.get_asset_by_object_path(asset).get_asset()
            if obj.get_class().get_name() == class_name:
                t = self._transform_from_basis(
                    transform, basis, unreal_import=unreal_import)
                actor = EditorLevelLibrary.spawn_actor_from_object(
                    obj, t.translation
                )
                actor_rotation = t.rotation.rotator()
                if rotation:
                    actor_rotation = unreal.Rotator(
                        roll=rotation["x"], pitch=rotation["z"],
                        yaw=-rotation["y"])
                actor.set_actor_rotation(actor_rotation, False)
                actor.set_actor_scale3d(t.scale3d)

                if class_name == 'SkeletalMesh':
                    skm_comp = actor.get_editor_property(
                        'skeletal_mesh_component')
                    skm_comp.set_bounds_scale(10.0)

                actors.append(actor)

                if sequence:
                    binding = None
                    for p in sequence.get_possessables():
                        if p.get_name() == actor.get_name():
                            binding = p
                            break

                    if not binding:
                        binding = sequence.add_possessable(actor)

                    bindings.append(binding)

        return actors, bindings

    def _process(self, lib_path, project_name, asset_dir, sequence,
                 repr_loaded=None, loaded_extension=None,
                 force_loaded=False, options={}):
        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        with open(lib_path, "r") as fp:
            data = json.load(fp)


        if not repr_loaded:
            repr_loaded = []

        path = Path(lib_path)

        skeleton_dict = {}
        actors_dict = {}
        bindings_dict = {}

        loaded_assets = []

        repre_entities_by_version_id = self._get_repre_entities_by_version_id(
            project_name, data, loaded_extension, force_loaded=force_loaded
        )
        for element in data:
            repre_id = None
            repr_format = None
            if element.get('representation'):
                version_id = element.get("version")
                repre_entities = repre_entities_by_version_id[version_id]
                if not repre_entities:
                    self.log.error(
                        f"No valid representation found for version"
                        f" {version_id}")
                    continue
                extension = element.get("extension", "ma")
                repre_entity = None
                if not force_loaded or loaded_extension == "json":
                    repre_entity = next((repre_entity for repre_entity in repre_entities
                                         if repre_entity["name"] == extension), None)
                    if not repre_entity or extension == "ma":
                        repre_entity = repre_entities[0]
                else:
                    # use the prioritized representation
                    # to load the assets
                    repre_entity = repre_entities[0]
                repre_id = repre_entity["id"]
                repr_format = repre_entity["name"]

            # If reference is None, this element is skipped, as it cannot be
            # imported in Unreal
            if not repr_format:
                self.log.warning(f"Representation name not defined for element: {element}")
                continue

            instance_name = element.get('instance_name')

            skeleton = None

            if repre_id not in repr_loaded:
                repr_loaded.append(repre_id)

                product_type = element.get("product_type")
                if product_type is None:
                    product_type = element.get("family")

                assets = self._load_assets(
                    instance_name, repre_id,
                    product_type, repr_format, options)

                container = None

                for asset in assets:
                    obj = ar.get_asset_by_object_path(asset).get_asset()
                    if obj.get_class().get_name() == 'AyonAssetContainer':
                        container = obj
                    if obj.get_class().get_name() == 'Skeleton':
                        skeleton = obj
                    if container is not None:
                        loaded_assets.append(container.get_path_name())

                instances = [
                    item for item in data
                    if ((item.get('version') and
                        item.get('version') == element.get('version'))
                        )]

                for instance in instances:
                    transform = instance.get('transform_matrix')
                    rotation = instance.get('rotation', {})
                    basis = instance.get('basis')
                    inst = instance.get('instance_name')
                    unreal_import = (
                        True if "unreal" in instance.get("host", []) else False
                    )

                    actors = []

                    if product_type in ['model', 'staticMesh']:
                        actors, _ = self._process_family(
                            assets, 'StaticMesh', transform, basis,
                            sequence, inst, rotation, unreal_import=unreal_import
                        )
                    elif product_type in ['rig', 'skeletalMesh']:
                        actors, bindings = self._process_family(
                            assets, 'SkeletalMesh', transform, basis,
                            sequence, inst, rotation, unreal_import=unreal_import
                        )
                        actors_dict[inst] = actors
                        bindings_dict[inst] = bindings

                if skeleton:
                    skeleton_dict[repre_id] = skeleton
            else:
                skeleton = skeleton_dict.get(repre_id)

            animation_file = element.get('animation')

            if animation_file and skeleton:
                import_animation(
                    asset_dir, path, instance_name, skeleton, actors_dict,
                    animation_file, bindings_dict, sequence
                )

        return loaded_assets

    def load(self, context, name, namespace, options):
        """Load and containerise representation into Content Browser.

        This is two step process. First, import FBX to temporary path and
        then call `containerise()` on it - this moves all content to new
        directory and then it will create AssetContainer there and imprint it
        with metadata. This will mark this path as container.

        Args:
            context (dict): application context
            name (str): Product name
            namespace (str): in Unreal this is basically path to container.
                             This is not passed here, so namespace is set
                             by `containerise()` because only then we know
                             real path.
            options (dict): Those would be data to be imprinted. This is not
                used now, data are imprinted by `containerise()`.

        Returns:
            list(str): list of container content
        """
        data = get_current_project_settings()
        create_sequences = (
            data["unreal"]["import_settings"]["level_sequences_for_layouts"]
        )
        # Create directory for asset and Ayon container
        folder_entity = context["folder"]
        folder_path = folder_entity["path"]
        folder_name = folder_entity["name"]
        asset_root, _ = format_asset_directory(context, self.loaded_layout_dir)
        master_dir_name = get_top_hierarchy_folder(asset_root)
        asset_dir, hierarchy_dir, container_name, asset_name = (
            generate_hierarchy_path(
                name, folder_name, asset_root, master_dir_name
            )
        )

        tools = unreal.AssetToolsHelpers().get_asset_tools()

        asset_level = f"{asset_dir}/{folder_name}_map.{folder_name}_map"
        if not EditorAssetLibrary.does_asset_exist(asset_level):
            EditorLevelLibrary.new_level(f"{asset_dir}/{folder_name}_map")

        shot = None
        sequences = []
        if create_sequences:
            shot, _, asset_level, sequences, frame_ranges = (
                generate_master_level_sequence(
                    tools, asset_dir, folder_name,
                    hierarchy_dir, master_dir_name
                )
            )

            project_name = get_current_project_name()
            folder_attributes = (
                ayon_api.get_folder_by_path(project_name, folder_path)["attrib"]
            )
            shot.set_display_rate(
                unreal.FrameRate(folder_attributes.get("fps"), 1.0))
            shot.set_playback_start(0)
            shot.set_playback_end(
                folder_attributes.get('clipOut')
                - folder_attributes.get('clipIn')
                + 1
            )
            if sequences:
                min_frame = 0 if frame_ranges[-1][1] == 0 else folder_attributes.get('clipIn')
                max_frame = folder_attributes.get('clipOut')
                max_frame = min_frame + 1 if max_frame < min_frame else max_frame
                set_sequence_hierarchy(
                    sequences[-1],
                    shot,
                    frame_ranges[-1][1],
                    min_frame,
                    max_frame,
                    [asset_level])

            EditorLevelLibrary.load_level(asset_level)
        project_name = get_current_project_name()
        extension = options.get(
            "folder_representation_type", self.folder_representation_type)
        import_options = {
            "resolution_priority": options.get(
                "resolution_priority", self.resolution_priority)
        }

        path = self.filepath_from_context(context)
        loaded_assets = self._process(
            path, project_name, asset_dir, shot,
            loaded_extension=extension,
            force_loaded=self.force_loaded,
            options=import_options
        )

        for s in sequences:
            EditorAssetLibrary.save_asset(s.get_path_name())

        EditorLevelLibrary.save_current_level()
        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{container_name}"
        ):
            # Create Asset Container
            create_container(container=container_name, path=asset_dir)
        self.imprint(
            context,
            folder_path,
            folder_name,
            loaded_assets,
            asset_dir,
            asset_name,
            container_name,
            context["project"]["name"],
            hierarchy_dir=hierarchy_dir
        )
        save_dir = hierarchy_dir if create_sequences else asset_dir

        asset_content = EditorAssetLibrary.list_assets(
            save_dir, recursive=True, include_folder=False)

        for a in asset_content:
            EditorAssetLibrary.save_asset(a)

        return asset_content

    def update(self, container, context):
        project_name = context["project"]["name"]
        data = get_current_project_settings()
        create_sequences = (
            data["unreal"]["import_settings"]["level_sequences_for_layouts"]
        )
        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        curr_level_sequence = LevelSequenceLib.get_current_level_sequence()
        curr_time = LevelSequenceLib.get_current_time()
        is_cam_lock = LevelSequenceLib.is_camera_cut_locked_to_viewport()

        editor_subsystem = unreal.UnrealEditorSubsystem()
        vp_loc, vp_rot = editor_subsystem.get_level_viewport_camera_info()

        asset_dir = container.get('namespace')
        repre_entity = context["representation"]
        sequence = None
        master_level = None
        hierarchy_dir = container.get("master_directory", "")
        master_dir_name = get_top_hierarchy_folder(asset_dir)
        if not hierarchy_dir:
            hierarchy_dir = f"{AYON_ROOT_DIR}/{master_dir_name}"
        if create_sequences:
            master_level = f"{hierarchy_dir}/{master_dir_name}_map.{master_dir_name}_map"
            filter = unreal.ARFilter(
                class_names=["LevelSequence"],
                package_paths=[asset_dir],
                recursive_paths=False)
            sequences = ar.get_assets(filter)
            sequence = sequences[0].get_asset()

        prev_level = None

        if not master_level:
            curr_level = unreal.LevelEditorSubsystem().get_current_level()
            curr_level_path = curr_level.get_outer().get_path_name()
            # If the level path does not start with "/Game/", the current
            # level is a temporary, unsaved level.
            if curr_level_path.startswith("/Game/"):
                prev_level = curr_level_path

        # Get layout level
        filter = unreal.ARFilter(
            class_names=["World"],
            package_paths=[asset_dir],
            recursive_paths=False)
        levels = ar.get_assets(filter)

        layout_level = levels[0].get_asset().get_path_name()

        EditorLevelLibrary.save_all_dirty_levels()
        EditorLevelLibrary.load_level(layout_level)

        # Delete all the actors in the level
        actors = unreal.EditorLevelLibrary.get_all_level_actors()
        for actor in actors:
            unreal.EditorLevelLibrary.destroy_actor(actor)

        if create_sequences:
            EditorLevelLibrary.save_current_level()
        source_path = self.filepath_from_context(context)

        import_options = {
            "resolution_priority": self.resolution_priority
        }
        loaded_assets = self._process(
            source_path, project_name, asset_dir, sequence,
            loaded_extension=self.folder_representation_type,
            force_loaded=self.force_loaded,
            options=import_options
        )

        update_container(container, project_name, repre_entity, loaded_assets=loaded_assets)

        EditorLevelLibrary.save_current_level()

        save_dir = hierarchy_dir if create_sequences else asset_dir

        asset_content = EditorAssetLibrary.list_assets(
            save_dir, recursive=True, include_folder=False)

        for a in asset_content:
            EditorAssetLibrary.save_asset(a)

        if master_level:
            EditorLevelLibrary.load_level(master_level)
        elif prev_level:
            EditorLevelLibrary.load_level(prev_level)

        if curr_level_sequence:
            LevelSequenceLib.open_level_sequence(curr_level_sequence)
            LevelSequenceLib.set_current_time(curr_time)
            LevelSequenceLib.set_lock_camera_cut_to_viewport(is_cam_lock)

        editor_subsystem.set_level_viewport_camera_info(vp_loc, vp_rot)

    def remove(self, container):
        self._remove_Loaded_asset(container)
        master_sequence = None
        sequences = []
        if self.level_sequences_for_layouts:
            # Remove the Level Sequence from the parent.
            # We need to traverse the hierarchy from the master sequence to
            # find the level sequence.
            master_directory = container.get("master_directory", "")
            if not master_directory:
                namespace = container.get('namespace').replace(f"{AYON_ROOT_DIR}/", "")
                ms_asset = namespace.split('/')[0]
                master_directory = f"{AYON_ROOT_DIR}/{ms_asset}"
            ar = unreal.AssetRegistryHelpers.get_asset_registry()
            _filter = unreal.ARFilter(
                class_names=["LevelSequence"],
                package_paths=[master_directory],
                recursive_paths=False)
            sequences = ar.get_assets(_filter)
            master_sequence = sequences[0].get_asset()
            sequences = [master_sequence]

            parent = None
            for s in sequences:
                tracks = get_tracks(s)
                subscene_track = None
                visibility_track = None
                for t in tracks:
                    if t.get_class() == unreal.MovieSceneSubTrack.static_class():
                        subscene_track = t
                    if (t.get_class() ==
                            unreal.MovieSceneLevelVisibilityTrack.static_class()):
                        visibility_track = t
                if subscene_track:
                    sections = subscene_track.get_sections()
                    for ss in sections:
                        try:
                            if (ss.get_sequence().get_name() ==
                                    container.get('asset')):
                                parent = s
                                subscene_track.remove_section(ss)
                                break
                            sequences.append(ss.get_sequence())
                        except AttributeError:
                            unreal.log("Cannot get the level sequences")
                    # Update subscenes indexes.
                    i = 0
                    for ss in sections:
                        ss.set_row_index(i)
                        i += 1

                if visibility_track:
                    sections = visibility_track.get_sections()
                    for ss in sections:
                        if (unreal.Name(f"{container.get('asset')}_map")
                                in ss.get_level_names()):
                            visibility_track.remove_section(ss)
                    # Update visibility sections indexes.
                    i = -1
                    prev_name = []
                    for ss in sections:
                        if prev_name != ss.get_level_names():
                            i += 1
                        ss.set_row_index(i)
                        prev_name = ss.get_level_names()
                if parent:
                    break

            assert parent, "Could not find the parent sequence"

        remove_map_and_sequence(container)
