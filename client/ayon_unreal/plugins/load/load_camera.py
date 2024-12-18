# -*- coding: utf-8 -*-
"""Load camera from FBX."""
import unreal
from unreal import (
    EditorAssetLibrary,
    EditorLevelLibrary
)
from ayon_core.pipeline import AYON_CONTAINER_ID
from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    generate_master_level_sequence,
    set_sequence_hierarchy,
    create_container,
    imprint,
    format_asset_directory,
    AYON_ROOT_DIR,
    get_top_hierarchy_folder,
    generate_hierarchy_path,
    remove_map_and_sequence
)


class CameraLoader(plugin.Loader):
    """Load Unreal StaticMesh from FBX"""

    product_types = {"camera"}
    label = "Load Camera"
    representations = {"fbx"}
    icon = "cube"
    color = "orange"
    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"

    @classmethod
    def apply_settings(cls, project_settings):
        super(CameraLoader, cls).apply_settings(
            project_settings
        )
        cls.loaded_asset_dir = (
            project_settings["unreal"]
                            ["import_settings"]
                            ["loaded_asset_dir"]
        )

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
        product_type,
        folder_entity,
        project_name
    ):
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
            "frameStart": folder_entity["attrib"]["frameStart"],
            "frameEnd": folder_entity["attrib"]["frameEnd"],
            "project_name": project_name
        }
        imprint(f"{asset_dir}/{container_name}", data)

    def _create_map_camera(self, context, path, tools, hierarchy_dir,
                           master_dir_name, asset_dir, asset_name):
        cam_seq, master_level, level, sequences, frame_ranges = (
            generate_master_level_sequence(
                tools, asset_dir, asset_name,
                hierarchy_dir, master_dir_name,
                suffix="camera")
        )
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
            camera_actors = unreal.GameplayStatics().get_all_actors_of_class(
            EditorLevelLibrary.get_editor_world(), unreal.CameraActor)
            unreal.log(f"Spawning camera: {asset_name}")
            for actor in camera_actors:
                actor.set_actor_label(asset_name)

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

    def load(self, context, name, namespace, options):
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
        folder_name = folder_entity["name"]
        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir)
        master_dir_name = get_top_hierarchy_folder(asset_root)
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, hierarchy_dir, container_name, _ = (
            generate_hierarchy_path(
                name, folder_name, asset_root, master_dir_name
            )
        )
        path = self.filepath_from_context(context)
        master_level = self._create_map_camera(
            context, path, tools, hierarchy_dir,
            master_dir_name, asset_dir, asset_name
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
            context["product"]["productType"],
            folder_entity,
            context["project"]["name"]
        )

        EditorLevelLibrary.save_all_dirty_levels()
        EditorLevelLibrary.load_level(master_level)

        # Save all assets in the hierarchy
        asset_content = EditorAssetLibrary.list_assets(
            hierarchy_dir, recursive=True, include_folder=False
        )

        for a in asset_content:
            EditorAssetLibrary.save_asset(a)

        return asset_content

    def update(self, container, context):
        # Create directory for asset and Ayon container
        repre_entity = context["representation"]
        folder_entity = context["folder"]
        folder_path = folder_entity["path"]
        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir)
        master_dir_name = get_top_hierarchy_folder(asset_root)
        hierarchy_dir = f"{AYON_ROOT_DIR}/{master_dir_name}"
        suffix = "_CON"
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix="")

        container_name += suffix
        master_level = None
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            EditorAssetLibrary.make_directory(asset_dir)
            path = self.filepath_from_context(context)
            master_level = self._create_map_camera(
                context, path, tools, hierarchy_dir,
                master_dir_name, asset_dir, asset_name
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
            folder_entity["name"],
            context["product"]["productType"],
            folder_entity,
            context["project"]["name"]
        )

        EditorLevelLibrary.save_all_dirty_levels()
        EditorLevelLibrary.load_level(master_level)

        # Save all assets in the hierarchy
        asset_content = EditorAssetLibrary.list_assets(
            hierarchy_dir, recursive=True, include_folder=False
        )

        for a in asset_content:
            EditorAssetLibrary.save_asset(a)

    def switch(self, container, context):
        self.update(container, context)

    def remove(self, container):
        remove_map_and_sequence(container)
