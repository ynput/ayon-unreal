# -*- coding: utf-8 -*-
"""Loader for layouts."""
import json
import collections
from pathlib import Path
import unreal
from unreal import (
    EditorAssetLibrary,
    EditorLevelLibrary,
    EditorLevelUtils,
    MovieSceneLevelVisibilityTrack,
    MovieSceneSubTrack,
    LevelSequenceEditorBlueprintLibrary as LevelSequenceLib,
)
import ayon_api

from ayon_core.pipeline import (
    discover_loader_plugins,
    loaders_from_representation,
    load_container,
    get_representation_path,
    AYON_CONTAINER_ID,
    get_current_project_name,
)
from ayon_core.settings import get_current_project_settings
from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    generate_sequence,
    set_sequence_hierarchy,
    create_container,
    imprint,
    AYON_ROOT_DIR,
    format_asset_directory,
    get_top_hierarchy_folder,
    generate_hierarchy_path,
    remove_map_and_sequence
)
from ayon_unreal.api.lib import (
    remove_loaded_asset,
    import_animation
)
from ayon_core.lib import EnumDef


class LayoutLoader(plugin.Loader):
    """Load Layout from a JSON file"""

    product_types = {"layout"}
    representations = {"json"}

    label = "Load Layout"
    icon = "code-fork"
    color = "orange"
    folder_representation_type = "json"
    force_loaded = False
    loaded_layout_dir = "{folder[path]}/{product[name]}"

    @classmethod
    def apply_settings(cls, project_settings):
        super(LayoutLoader, cls).apply_settings(project_settings)
        unreal_settings =  project_settings.get("unreal", {})
        # Apply import settings
        folder_representation_type = unreal_settings.get(
            "folder_representation_type", {})
        use_force_loaded = unreal_settings.get("force_loaded", {})
        # Apply import settings
        loaded_layout_dir = unreal_settings.get(
            "loaded_layout_dir", cls.loaded_layout_dir)

        if folder_representation_type:
            cls.folder_representation_type = folder_representation_type
        if use_force_loaded:
            cls.force_loaded = use_force_loaded
        if loaded_layout_dir:
            cls.loaded_layout_dir = loaded_layout_dir

    @classmethod
    def get_options(cls, contexts):
        defs = []
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

    @staticmethod
    def _get_fbx_loader(loaders, family):
        name = ""
        if family in ['rig', 'skeletalMesh']:
            name = "SkeletalMeshFBXLoader"
        elif family in ['model', 'staticMesh']:
            name = "StaticMeshFBXLoader"
        elif family == 'camera':
            name = "CameraLoader"

        if name == "":

            return None

        for loader in loaders:
            if loader.__name__ == name:
                return loader

        return None

    @staticmethod
    def _get_abc_loader(loaders, family):
        name = ""
        if family in ['rig', 'skeletalMesh']:
            name = "SkeletalMeshAlembicLoader"
        elif family in ['model', 'staticMesh']:
            name = "StaticMeshAlembicLoader"

        if name == "":
            return None

        for loader in loaders:
            if loader.__name__ == name:
                return loader

        return None

    def _transform_from_basis(self, transform, basis):
        """Transform a transform from a basis to a new basis."""
        # Get the basis matrix
        basis_matrix = unreal.Matrix(
            basis[0],
            basis[1],
            basis[2],
            basis[3]
        )
        transform_matrix = unreal.Matrix(
            transform[0],
            transform[1],
            transform[2],
            transform[3]
        )

        new_transform = (
            basis_matrix.get_inverse() * transform_matrix * basis_matrix)

        return new_transform.transform()

    def _process_family(
        self, assets, class_name, transform, basis, sequence, inst_name=None,
        rotation=None
    ):
        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        actors = []
        bindings = []

        for asset in assets:
            obj = ar.get_asset_by_object_path(asset).get_asset()
            if obj.get_class().get_name() == class_name:
                t = self._transform_from_basis(transform, basis)
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

    def _get_repre_entities_by_version_id(self, data, repre_extension, force_loaded=False):
        version_ids = {
            element.get("version")
            for element in data
            if element.get("representation")
        }
        version_ids.discard(None)
        output = collections.defaultdict(list)
        if not version_ids:
            return output
        # Extract extensions from data with backward compatibility for "ma"
        extensions = {
            element["extension"]
            for element in data
            if element.get("representation")
        }

        # Update extensions based on the force_loaded flag
        updated_extensions = set()

        for ext in extensions:
            if not force_loaded or repre_extension == "json":
                if ext == "ma":
                    updated_extensions.update({"fbx", "abc"})
                else:
                    updated_extensions.add(ext)
            else:
                updated_extensions.update({repre_extension})

        project_name = get_current_project_name()
        repre_entities = ayon_api.get_representations(
            project_name,
            representation_names=updated_extensions,
            version_ids=version_ids,
            fields={"id", "versionId", "name"}
        )
        for repre_entity in repre_entities:
            version_id = repre_entity["versionId"]
            output[version_id].append(repre_entity)
        return output

    def _process(self, lib_path, asset_dir, sequence,
                 repr_loaded=None, loaded_extension=None,
                 force_loaded=False):
        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        with open(lib_path, "r") as fp:
            data = json.load(fp)

        all_loaders = discover_loader_plugins()

        if not repr_loaded:
            repr_loaded = []

        path = Path(lib_path)

        skeleton_dict = {}
        actors_dict = {}
        bindings_dict = {}

        loaded_assets = []

        repre_entities_by_version_id = self._get_repre_entities_by_version_id(
            data, loaded_extension, force_loaded=force_loaded
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
                extension = element.get("extension")
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
                loaders = loaders_from_representation(
                    all_loaders, repre_id)

                loader = None

                if repr_format == 'fbx':
                    loader = self._get_fbx_loader(loaders, product_type)
                elif repr_format == 'abc':
                    loader = self._get_abc_loader(loaders, product_type)

                if not loader:
                    if repr_format == "ma":
                        msg = (
                            f"No valid {product_type} loader found for {repre_id} ({repr_format}), "
                            f"consider using {product_type} loader (fbx/abc) instead."
                        )
                        self.log.warning(msg)
                    else:
                        self.log.error(
                            f"No valid loader found for {repre_id} "
                            f"({repr_format}) "
                            f"{product_type}")
                    continue

                options = {
                    # "asset_dir": asset_dir
                }

                assets = load_container(
                    loader,
                    repre_id,
                    namespace=instance_name,
                    options=options
                )

                container = None

                for asset in assets:
                    obj = ar.get_asset_by_object_path(asset).get_asset()
                    if obj.get_class().get_name() == 'AyonAssetContainer':
                        container = obj
                    if obj.get_class().get_name() == 'Skeleton':
                        skeleton = obj

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

                    actors = []

                    if product_type in ['model', 'staticMesh']:
                        actors, _ = self._process_family(
                            assets, 'StaticMesh', transform, basis,
                            sequence, inst, rotation
                        )
                    elif product_type in ['rig', 'skeletalMesh']:
                        actors, bindings = self._process_family(
                            assets, 'SkeletalMesh', transform, basis,
                            sequence, inst, rotation
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
        create_sequences = data["unreal"]["level_sequences_for_layouts"]

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
        master_level = None
        shot = None
        sequences = []

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_level = f"{asset_dir}/{folder_name}_map.{folder_name}_map"
        if not EditorAssetLibrary.does_asset_exist(asset_level):
            EditorLevelLibrary.new_level(f"{asset_dir}/{folder_name}_map")
        if create_sequences:
            # Create map for the shot, and create hierarchy of map. If the
            # maps already exist, we will use them.
            master_level = f"{hierarchy_dir}/{master_dir_name}_map.{master_dir_name}_map"
            if not EditorAssetLibrary.does_asset_exist(master_level):
                EditorLevelLibrary.new_level(f"{hierarchy_dir}/{master_dir_name}_map")
            if master_level:
                EditorLevelLibrary.load_level(master_level)
                EditorLevelUtils.add_level_to_world(
                    EditorLevelLibrary.get_editor_world(),
                    asset_level,
                    unreal.LevelStreamingDynamic
                )
                EditorLevelLibrary.save_all_dirty_levels()
                EditorLevelLibrary.load_level(asset_level)

            # Get all the sequences in the hierarchy. It will create them, if
            # they don't exist.
            frame_ranges = []
            root_content = EditorAssetLibrary.list_assets(
                hierarchy_dir, recursive=False, include_folder=False)

            existing_sequences = [
                EditorAssetLibrary.find_asset_data(asset)
                for asset in root_content
                if EditorAssetLibrary.find_asset_data(
                    asset).get_class().get_name() == 'LevelSequence'
            ]

            if not existing_sequences:
                sequence, frame_range = generate_sequence(master_dir_name, hierarchy_dir)

                sequences.append(sequence)
                frame_ranges.append(frame_range)
            else:
                for e in existing_sequences:
                    sequences.append(e.get_asset())
                    frame_ranges.append((
                        e.get_asset().get_playback_start(),
                        e.get_asset().get_playback_end()))

            shot_name = f"{asset_dir}/{folder_name}.{folder_name}"
            shot = None
            if not EditorAssetLibrary.does_asset_exist(shot_name):
                shot = tools.create_asset(
                    asset_name=folder_name,
                    package_path=asset_dir,
                    asset_class=unreal.LevelSequence,
                    factory=unreal.LevelSequenceFactoryNew()
                )
            else:
                shot = unreal.load_asset(shot_name)

            # sequences and frame_ranges have the same length
            for i in range(0, len(sequences) - 1):
                set_sequence_hierarchy(
                    sequences[i], sequences[i + 1],
                    frame_ranges[i][1],
                    frame_ranges[i + 1][0], frame_ranges[i + 1][1],
                    [asset_level])

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
        extension = options.get(
            "folder_representation_type", self.folder_representation_type)
        path = self.filepath_from_context(context)
        loaded_assets = self._process(
            path, asset_dir, shot, loaded_extension=extension,
            force_loaded=self.force_loaded)

        for s in sequences:
            EditorAssetLibrary.save_asset(s.get_path_name())

        EditorLevelLibrary.save_current_level()
        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{container_name}"
        ):
            # Create Asset Container
            create_container(
                container=container_name, path=asset_dir)

            data = {
                "schema": "ayon:container-2.0",
                "id": AYON_CONTAINER_ID,
                "asset": folder_name,
                "folder_path": folder_path,
                "namespace": asset_dir,
                "container_name": container_name,
                "asset_name": asset_name,
                "loader": str(self.__class__.__name__),
                "representation": context["representation"]["id"],
                "parent": context["representation"]["versionId"],
                "family": context["product"]["productType"],
                "loaded_assets": loaded_assets,
                "master_directory": hierarchy_dir
            }
            imprint(
                "{}/{}".format(asset_dir, container_name), data)

        save_dir = hierarchy_dir if create_sequences else asset_dir

        asset_content = EditorAssetLibrary.list_assets(
            save_dir, recursive=True, include_folder=False)

        for a in asset_content:
            EditorAssetLibrary.save_asset(a)

        return asset_content

    def update(self, container, context):
        data = get_current_project_settings()
        create_sequences = data["unreal"]["level_sequences_for_layouts"]

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
        if not hierarchy_dir:
            master_dir_name = get_top_hierarchy_folder(asset_dir)
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

        source_path = get_representation_path(repre_entity)

        loaded_assets = self._process(
            source_path, asset_dir, sequence,
            loaded_extension=self.folder_representation_type,
            force_loaded=self.force_loaded)

        data = {
            "representation": repre_entity["id"],
            "parent": repre_entity["versionId"],
            "loaded_assets": loaded_assets,
        }
        imprint(
            "{}/{}".format(asset_dir, container.get('container_name')), data)

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
        """
        Delete the layout. First, check if the assets loaded with the layout
        are used by other layouts. If not, delete the assets.
        """
        data = get_current_project_settings()
        create_sequences = data["unreal"]["level_sequences_for_layouts"]
        remove_loaded_assets = data["unreal"].get("remove_loaded_assets", False)
        if remove_loaded_assets:
            remove_asset_confirmation_dialog = unreal.EditorDialog.show_message(
                "The removal of the loaded assets",
                "The layout will be removed. Do you want to delete all associated assets as well?",
                unreal.AppMsgType.YES_NO)
            if (remove_asset_confirmation_dialog == unreal.AppReturnType.YES):
                remove_loaded_asset(container)

        master_sequence = None
        sequences = []

        if create_sequences:
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
                tracks = s.get_master_tracks()
                subscene_track = None
                visibility_track = None
                for t in tracks:
                    if t.get_class() == MovieSceneSubTrack.static_class():
                        subscene_track = t
                    if (t.get_class() ==
                            MovieSceneLevelVisibilityTrack.static_class()):
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
