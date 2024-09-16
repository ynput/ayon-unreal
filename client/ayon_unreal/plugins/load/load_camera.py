# -*- coding: utf-8 -*-
"""Load camera from FBX."""
import unreal
from unreal import (
    EditorAssetLibrary,
    EditorLevelLibrary,
    EditorLevelUtils
)
from ayon_core.pipeline import (
    AYON_CONTAINER_ID,
    get_representation_path,
)
from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    generate_sequence,
    set_sequence_hierarchy,
    create_container,
    imprint,
)


class CameraLoader(plugin.Loader):
    """Load Unreal StaticMesh from FBX"""

    product_types = {"camera"}
    label = "Load Camera"
    representations = {"fbx"}
    icon = "cube"
    color = "orange"
    root = "/Game/Ayon"

    def _import_camera(
        self, world, sequence, bindings, import_fbx_settings, import_filename
    ):
        ue_version = unreal.SystemLibrary.get_engine_version().split('.')
        ue_major = int(ue_version[0])
        ue_minor = int(ue_version[1])

        if ue_major == 4 and ue_minor <= 26:
            unreal.SequencerTools.import_fbx(
                world,
                sequence,
                bindings,
                import_fbx_settings,
                import_filename
            )
        elif (ue_major == 4 and ue_minor >= 27) or ue_major == 5:
            unreal.SequencerTools.import_level_sequence_fbx(
                world,
                sequence,
                bindings,
                import_fbx_settings,
                import_filename
            )
        else:
            raise NotImplementedError(
                f"Unreal version {ue_major} not supported")
    def imprint(
        self,
        folder_path,
        asset_dir,
        container_name,
        asset_name,
        representation,
        folder_name,
        product_type):
        data = {
            "schema": "ayon:container-2.0",
            "id": AYON_CONTAINER_ID,
            "folder_path": folder_path,
            "namespace": asset_dir,
            "container_name": container_name,
            "asset_name": asset_name,
            "loader": str(self.__class__.__name__),
            "representation": representation["id"],
            "parent": representation["versionId"],
            "product_type": product_type,
            # TODO these should be probably removed
            "asset": folder_name,
            "family": product_type,
        }
        imprint(f"{asset_dir}/{container_name}", data)
        unreal.log("data")
        unreal.log(data)

    def _create_map_camera(self, context, path, tools, hierarchy_dir_list,
                           hierarchy_dir, hierarchy_parts,
                           asset_dir, asset_name):
        # Create map for the shot, and create hierarchy of map. If the maps
        # already exist, we will use them.
        h_dir = hierarchy_dir_list[0]
        h_asset = hierarchy_dir[0]
        master_level = f"{h_dir}/{h_asset}_map.{h_asset}_map"
        if not EditorAssetLibrary.does_asset_exist(master_level):
            EditorLevelLibrary.new_level(f"{h_dir}/{h_asset}_map")

        level = (
            f"{asset_dir}/{asset_name}_map_camera.{asset_name}_map_camera"
        )
        if not EditorAssetLibrary.does_asset_exist(level):
            EditorLevelLibrary.new_level(
                f"{asset_dir}/{asset_name}_map_camera"
            )

            EditorLevelLibrary.load_level(master_level)
            EditorLevelUtils.add_level_to_world(
                EditorLevelLibrary.get_editor_world(),
                level,
                unreal.LevelStreamingDynamic
            )
        EditorLevelLibrary.save_all_dirty_levels()
        EditorLevelLibrary.load_level(level)

        # Get all the sequences in the hierarchy. It will create them, if
        # they don't exist.
        frame_ranges = []
        sequences = []
        for (h_dir, h) in zip(hierarchy_dir_list, hierarchy_parts):
            root_content = EditorAssetLibrary.list_assets(
                h_dir, recursive=False, include_folder=False)

            existing_sequences = [
                EditorAssetLibrary.find_asset_data(asset)
                for asset in root_content
                if EditorAssetLibrary.find_asset_data(
                    asset).get_class().get_name() == 'LevelSequence'
            ]

            if existing_sequences:
                for seq in existing_sequences:
                    sequences.append(seq.get_asset())
                    frame_ranges.append((
                        seq.get_asset().get_playback_start(),
                        seq.get_asset().get_playback_end()))
            else:
                sequence, frame_range = generate_sequence(h, h_dir)

                sequences.append(sequence)
                frame_ranges.append(frame_range)

        cam_seq = tools.create_asset(
            asset_name=f"{asset_name}_camera",
            package_path=asset_dir,
            asset_class=unreal.LevelSequence,
            factory=unreal.LevelSequenceFactoryNew()
        )

        # Add sequences data to hierarchy
        for i in range(len(sequences) - 1):
            set_sequence_hierarchy(
                sequences[i], sequences[i + 1],
                frame_ranges[i][1],
                frame_ranges[i + 1][0], frame_ranges[i + 1][1],
                [level])

        folder_entity = context["folder"]
        folder_attributes = folder_entity["attrib"]
        clip_in = folder_attributes.get("clipIn")
        clip_out = folder_attributes.get("clipOut")

        cam_seq.set_display_rate(
            unreal.FrameRate(folder_attributes.get("fps"), 1.0))
        cam_seq.set_playback_start(clip_in)
        cam_seq.set_playback_end(clip_out + 1)
        set_sequence_hierarchy(
            sequences[-1], cam_seq,
            frame_ranges[-1][1],
            clip_in, clip_out,
            [level])

        settings = unreal.MovieSceneUserImportFBXSettings()
        settings.set_editor_property('reduce_keys', False)

        if cam_seq:
            self._import_camera(
                EditorLevelLibrary.get_editor_world(),
                cam_seq,
                cam_seq.get_bindings(),
                settings,
                path
            )

        # Set range of all sections
        # Changing the range of the section is not enough. We need to change
        # the frame of all the keys in the section.
        for possessable in cam_seq.get_possessables():
            for tracks in possessable.get_tracks():
                for section in tracks.get_sections():
                    section.set_range(clip_in, clip_out + 1)
                    for channel in section.get_all_channels():
                        for key in channel.get_keys():
                            old_time = key.get_time().get_editor_property(
                                'frame_number')
                            old_time_value = old_time.get_editor_property(
                                'value')
                            new_time = old_time_value + (
                                clip_in - folder_attributes.get('frameStart')
                            )
                            key.set_time(unreal.FrameNumber(value=new_time))
        return master_level

    def load(self, context, name, namespace, data):
        """
        Load and containerise representation into Content Browser.

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
            data (dict): Those would be data to be imprinted. This is not used
                         now, data are imprinted by `containerise()`.

        Returns:
            list(str): list of container content
        """
        # Create directory for asset and Ayon container
        folder_entity = context["folder"]
        folder_path = folder_entity["path"]
        hierarchy_parts = folder_path.split("/")
        # Remove empty string
        hierarchy_parts.pop(0)
        # Pop folder name
        folder_name = hierarchy_parts.pop(-1)

        hierarchy_dir = self.root
        hierarchy_dir_list = []
        for h in hierarchy_parts:
            hierarchy_dir = f"{hierarchy_dir}/{h}"
            hierarchy_dir_list.append(hierarchy_dir)
        suffix = "_CON"
        asset_name = f"{folder_name}_{name}" if folder_name else name
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        version = context["version"]["version"]
        # Check if version is hero version and use different name
        if version < 0:
            name_version = f"{name}_hero"
        else:
            name_version = f"{name}_v{version:03d}"
        asset_dir, container_name = tools.create_unique_asset_name(
            f"{hierarchy_dir}/{folder_name}/{name_version}", suffix="")

        container_name += suffix
        master_level = None
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            EditorAssetLibrary.make_directory(asset_dir)
            path = self.filepath_from_context(context)
            master_level = self._create_map_camera(
                context, path, tools, hierarchy_dir_list,
                hierarchy_dir, hierarchy_parts,
                asset_dir, asset_name
            )

        # Create Asset Container
        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{container_name}"
        ):
            create_container(
                container=container_name, path=asset_dir)

        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            context["representation"],
            folder_name,
            context["product"]["productType"]
        )

        EditorLevelLibrary.save_all_dirty_levels()
        EditorLevelLibrary.load_level(master_level)

        # Save all assets in the hierarchy
        asset_content = EditorAssetLibrary.list_assets(
            hierarchy_dir_list[0], recursive=True, include_folder=False
        )

        for a in asset_content:
            EditorAssetLibrary.save_asset(a)

        return asset_content

    def update(self, container, context):
        # Create directory for asset and Ayon container
        repre_entity = context["representation"]
        folder_entity = context["folder"]
        folder_path = folder_entity["path"]
        product_name = context["product"]["name"]
        hierarchy_parts = folder_path.split("/")
        # Remove empty string
        hierarchy_parts.pop(0)
        # Pop folder name
        folder_name = hierarchy_parts.pop(-1)

        hierarchy_dir = self.root
        hierarchy_dir_list = []
        for h in hierarchy_parts:
            hierarchy_dir = f"{hierarchy_dir}/{h}"
            hierarchy_dir_list.append(hierarchy_dir)
        suffix = "_CON"
        asset_name = f"{folder_name}_{product_name}" if folder_name else product_name
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        version = context["version"]["version"]
        # Check if version is hero version and use different name
        if version < 0:
            name_version = f"{product_name}_hero"
        else:
            name_version = f"{product_name}_v{version:03d}"
        asset_dir, container_name = tools.create_unique_asset_name(
            f"{hierarchy_dir}/{folder_name}/{name_version}", suffix="")

        container_name += suffix
        master_level = None
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            EditorAssetLibrary.make_directory(asset_dir)
            path = get_representation_path(repre_entity)
            master_level = self._create_map_camera(
                context, path, tools, hierarchy_dir_list,
                hierarchy_dir, hierarchy_parts,
                asset_dir, asset_name
            )

        # Create Asset Container
        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{container_name}"
        ):
            create_container(
                container=container_name, path=asset_dir)

        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            context["representation"],
            folder_name,
            context["product"]["productType"]
        )

        EditorLevelLibrary.save_all_dirty_levels()
        EditorLevelLibrary.load_level(master_level)

        # Save all assets in the hierarchy
        asset_content = EditorAssetLibrary.list_assets(
            hierarchy_dir_list[0], recursive=True, include_folder=False
        )

        for a in asset_content:
            EditorAssetLibrary.save_asset(a)

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        asset_dir = container.get('namespace')
        # Create a temporary level to delete the layout level.
        EditorLevelLibrary.save_all_dirty_levels()
        EditorAssetLibrary.make_directory(f"{self.root}/tmp")
        tmp_level = f"{self.root}/tmp/temp_map"
        if not EditorAssetLibrary.does_asset_exist(f"{tmp_level}.temp_map"):
            EditorLevelLibrary.new_level(tmp_level)
        else:
            EditorLevelLibrary.load_level(tmp_level)
        EditorLevelLibrary.save_all_dirty_levels()
        # Delete the camera directory.
        if EditorAssetLibrary.does_directory_exist(asset_dir):
            EditorAssetLibrary.delete_directory(asset_dir)
        # Load the default level
        default_level_path = "/Engine/Maps/Templates/OpenWorld"
        EditorLevelLibrary.load_level(default_level_path)
        EditorAssetLibrary.delete_directory(f"{self.root}/tmp")
