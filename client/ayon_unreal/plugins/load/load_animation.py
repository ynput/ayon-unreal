# -*- coding: utf-8 -*-
"""Load FBX with animations."""
import json
import os
import ayon_api
import unreal
from ayon_core.pipeline import (AYON_CONTAINER_ID, get_current_project_name,
                                get_representation_path, load_container,
                                discover_loader_plugins,
                                loaders_from_representation)
from ayon_core.pipeline.context_tools import get_current_folder_entity
from ayon_core.pipeline.load import LoadError
from ayon_unreal.api import pipeline as unreal_pipeline
from ayon_unreal.api import plugin
from unreal import (EditorAssetLibrary, MovieSceneSkeletalAnimationSection,
                    MovieSceneSkeletalAnimationTrack)


class AnimationFBXLoader(plugin.Loader):
    """Load Unreal SkeletalMesh from FBX."""

    product_types = {"animation"}
    label = "Import FBX Animation"
    representations = {"fbx"}
    icon = "cube"
    color = "orange"

    root = unreal_pipeline.AYON_ROOT_DIR
    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"
    show_dialog = False

    @classmethod
    def apply_settings(cls, project_settings):
        super(AnimationFBXLoader, cls).apply_settings(project_settings)
        # Apply import settings
        unreal_settings = project_settings["unreal"]["import_settings"]
        cls.loaded_asset_dir = unreal_settings["loaded_asset_dir"]
        cls.show_dialog = unreal_settings["show_dialog"]

    def _import_latest_skeleton(self, version_ids):
        version_ids = set(version_ids)
        project_name = get_current_project_name()
        repre_entities = ayon_api.get_representations(
            project_name,
            representation_names={"fbx"},
            version_ids=version_ids,
            fields={"id"}
        )
        repre_entity = next(
            (repre_entity for repre_entity
             in repre_entities), None)
        if not repre_entity:
            raise LoadError(
                f"No valid representation for version {version_ids}")
        repre_id = repre_entity["id"]

        target_loader = None
        all_loaders = discover_loader_plugins()
        loaders = loaders_from_representation(
            all_loaders, repre_id)
        for loader in loaders:
            if loader.__name__ == "SkeletalMeshFBXLoader":
                target_loader = loader
        assets = load_container(
            target_loader,
            repre_id,
            namespace=None,
            options={}
        )
        return assets


    @classmethod
    def _import_animation(
        cls, path, asset_dir, asset_name,
        skeleton, automated, replace=False,
        loaded_options=None
    ):
        task = unreal.AssetImportTask()
        task.options = unreal.FbxImportUI()

        folder_entity = get_current_folder_entity(fields=["attrib.fps"])

        task.set_editor_property('filename', path)
        task.set_editor_property('destination_path', asset_dir)
        task.set_editor_property('destination_name', asset_name)
        task.set_editor_property('replace_existing', replace)
        task.set_editor_property('automated', not cls.show_dialog)
        task.set_editor_property('save', False)

        # set import options here
        task.options.set_editor_property(
            'automated_import_should_detect_type', True)
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
            unreal.FBXAnimationLengthImportType.FBXALIT_SET_RANGE
        )
        task.options.anim_sequence_import_data.set_editor_property(
            'frame_import_range', unreal.Int32Interval(
                min=loaded_options.get("frameStart"),
                max=loaded_options.get("frameEnd")
        ))
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
        task.options.anim_sequence_import_data.set_editor_property(
            'force_front_x_axis', False)
        task.options.anim_sequence_import_data.set_editor_property(
            'import_rotation', unreal.Rotator(roll=90.0, pitch=0.0, yaw=0.0))

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    def _process(self, path, asset_dir, asset_name,
                 instance_name, loaded_options=None):
        automated = False
        actor = None

        if instance_name:
            automated = True
            # Old method to get the actor
            # actor_name = 'PersistentLevel.' + instance_name
            # actor = unreal.EditorLevelLibrary.get_actor_reference(actor_name)
            actors = unreal.EditorLevelLibrary.get_all_level_actors()
            for a in actors:
                if a.get_class().get_name() != "SkeletalMeshActor":
                    continue
                if a.get_actor_label() == instance_name:
                    actor = a
                    break
            if not actor:
                raise LoadError(f"Could not find actor {instance_name}")
            skeleton = actor.skeletal_mesh_component.skeletal_mesh.skeleton

        if not actor:
            return None

        self._import_animation(
            path, asset_dir, asset_name,
            skeleton, automated, loaded_options=loaded_options)

        asset_content = EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=True
        )

        animation = None

        for a in asset_content:
            imported_asset_data = EditorAssetLibrary.find_asset_data(a)
            imported_asset = unreal.AssetRegistryHelpers.get_asset(
                imported_asset_data)
            if imported_asset.__class__ == unreal.AnimSequence:
                animation = imported_asset
                break

        if animation:
            animation.set_editor_property('enable_root_motion', True)
            actor.skeletal_mesh_component.set_editor_property(
                'animation_mode', unreal.AnimationMode.ANIMATION_SINGLE_NODE)
            actor.skeletal_mesh_component.animation_data.set_editor_property(
                'anim_to_play', animation)

        return animation

    def _load_from_json(
        self, libpath, path, asset_dir, asset_name, hierarchy_dir,
        loaded_options=None
    ):
        with open(libpath, "r") as fp:
            data = json.load(fp)

        instance_name = data.get("instance_name")

        animation = self._process(
            path, asset_dir, asset_name,
            instance_name, loaded_options=loaded_options)

        asset_content = EditorAssetLibrary.list_assets(
            hierarchy_dir, recursive=True, include_folder=False)

        # Get the sequence for the layout, excluding the camera one.
        sequences = [a for a in asset_content
                     if (EditorAssetLibrary.find_asset_data(a).get_class() ==
                         unreal.LevelSequence.static_class() and
                         "_camera" not in a.split("/")[-1])]

        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        for s in sequences:
            sequence = ar.get_asset_by_object_path(s).get_asset()
            possessables = [
                p for p in sequence.get_possessables()
                if p.get_display_name() == instance_name]

            for p in possessables:
                tracks = [
                    t for t in p.get_tracks()
                    if (t.get_class() ==
                        MovieSceneSkeletalAnimationTrack.static_class())]

                for t in tracks:
                    sections = [
                        s for s in t.get_sections()
                        if (s.get_class() ==
                            MovieSceneSkeletalAnimationSection.static_class())]

                    for section in sections:
                        section.params.set_editor_property('animation', animation)

    @staticmethod
    def is_skeleton(asset):
        return asset.get_class() == unreal.Skeleton.static_class()

    def _load_standalone_animation(
        self, path, asset_dir, asset_name,
        version_id, loaded_options=None
    ):
        selection = unreal.EditorUtilityLibrary.get_selected_assets()
        skeleton = None
        if selection:
            skeleton = selection[0]
            if not self.is_skeleton(skeleton):
                self.log.warning(
                    f"Selected asset {skeleton.get_name()} is not "
                    f"a skeleton. It is {skeleton.get_class().get_name()}")
                skeleton = None

        print("Trying to find original rig with links.")
        # If no skeleton is selected, we try to find the skeleton by
        # checking linked rigs.
        project_name = get_current_project_name()
        server = ayon_api.get_server_api_connection()

        v_links = server.get_version_links(
            project_name, version_id=version_id)
        entities = [v_link["entityId"] for v_link in v_links]
        linked_versions = list(server.get_versions(project_name, entities))
        unreal.log("linked_versions")
        unreal.log(linked_versions)
        rigs = [
            version["id"] for version in linked_versions
            if "rig" in version["attrib"]["families"]]

        self.log.debug(f"Found rigs: {rigs}")

        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        containers = unreal_pipeline.ls()
        for container in containers:
            self.log.debug(f"Checking container: {container}")
            if container["parent"] not in rigs:
                unreal.log("{}".format(container["parent"]))
                # we found loaded version of the linked rigs
                if container["loader"] != "SkeletalMeshFBXLoader":
                    continue
                namespace = container["namespace"]

                _filter = unreal.ARFilter(
                    class_names=["Skeleton"],
                    package_paths=[namespace],
                    recursive_paths=False)
                if skeletons := ar.get_assets(_filter):
                    skeleton = skeletons[0].get_asset()
                    break

        if not skeleton:
           ar = unreal.AssetRegistryHelpers.get_asset_registry()
           skeleton_asset = self._import_latest_skeleton(rigs)
           for asset in skeleton_asset:
               obj = ar.get_asset_by_object_path(asset).get_asset()
               if obj.get_class().get_name() == 'Skeleton':
                    skeleton = obj

        if not self.is_skeleton(skeleton):
            raise LoadError("Selected asset is not a skeleton.")

        self.log.info(f"Using skeleton: {skeleton.get_name()}")
        self._import_animation(
            path, asset_dir, asset_name,
            skeleton, True, loaded_options=loaded_options)

    def _import_animation_with_json(self, path, context, hierarchy,
                                    asset_dir, folder_name,
                                    asset_name, asset_path=None,
                                    loaded_options=None):
            libpath = path.replace(".fbx", ".json")

            master_level = None
            if asset_path:
                asset_dir = unreal.Paths.split(asset_path)[0]
            # check if json file exists.
            if os.path.exists(libpath):
                ar = unreal.AssetRegistryHelpers.get_asset_registry()

                _filter = unreal.ARFilter(
                    class_names=["World"],
                    package_paths=[f"{self.root}/{hierarchy[0]}"],
                    recursive_paths=False)
                levels = ar.get_assets(_filter)
                master_level = levels[0].get_asset().get_path_name()

                hierarchy_dir = self.root
                for h in hierarchy:
                    hierarchy_dir = f"{hierarchy_dir}/{h}"
                hierarchy_dir = f"{hierarchy_dir}/{folder_name}"

                _filter = unreal.ARFilter(
                    class_names=["World"],
                    package_paths=[f"{hierarchy_dir}/"],
                    recursive_paths=True)
                levels = ar.get_assets(_filter)
                level = levels[0].get_asset().get_path_name()

                unreal.EditorLevelLibrary.save_all_dirty_levels()
                unreal.EditorLevelLibrary.load_level(level)

                self._load_from_json(
                    libpath, path, asset_dir, asset_name, hierarchy_dir)
            else:
                version_id = context["representation"]["versionId"]
                if not unreal.EditorAssetLibrary.does_asset_exist(
                    f"{asset_dir}/{asset_name}"):
                        self._load_standalone_animation(
                            path, asset_dir, asset_name,
                            version_id, loaded_options=loaded_options)

            return master_level

    def imprint(
        self,
        folder_path,
        asset_dir,
        container_name,
        asset_name,
        representation,
        product_type,
        folder_entity,
        project_name
    ):
        data = {
            "schema": "ayon:container-2.0",
            "id": AYON_CONTAINER_ID,
            "namespace": asset_dir,
            "container_name": container_name,
            "asset_name": asset_name,
            "loader": str(self.__class__.__name__),
            "representation": representation["id"],
            "parent": representation["versionId"],
            "folder_path": folder_path,
            "product_type": product_type,
            # TODO these shold be probably removed
            "asset": folder_path,
            "family": product_type,
            "frameStart": folder_entity["attrib"]["frameStart"],
            "frameEnd": folder_entity["attrib"]["frameEnd"],
            "project_name": project_name
        }
        unreal_pipeline.imprint(f"{asset_dir}/{container_name}", data)

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
        hierarchy = folder_path.lstrip("/").split("/")
        folder_name = hierarchy.pop(-1)
        product_type = context["product"]["productType"]

        suffix = "_CON"

        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")
        asset_root, asset_name = unreal_pipeline.format_asset_directory(context, self.loaded_asset_dir)
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")

        container_name += suffix
        asset_path = unreal_pipeline.has_asset_directory_pattern_matched(asset_name, asset_dir, name)
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            EditorAssetLibrary.make_directory(asset_dir)
        loaded_options = {
            "frameStart": folder_entity["attrib"]["frameStart"],
            "frameEnd": folder_entity["attrib"]["frameEnd"]
        }
        master_level = self._import_animation_with_json(
            path, context, hierarchy,
            asset_dir, folder_name,
            asset_name, asset_path=asset_path,
            loaded_options=loaded_options
        )
        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{container_name}"):
                unreal_pipeline.create_container(
                    container=container_name, path=asset_dir)
        if asset_path:
            unreal.EditorAssetLibrary.rename_asset(
                f"{asset_path}",
                f"{asset_dir}/{asset_name}.{asset_name}"
            )
        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            context["representation"],
            product_type,
            folder_entity,
            context["project"]["name"]
        )

        imported_content = EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=False)

        for asset in imported_content:
            loaded_asset = EditorAssetLibrary.load_asset(asset)
            # Enable root motion for animations so they are oriented correctly
            if loaded_asset.get_class() == unreal.AnimSequence.static_class():
                loaded_asset.set_editor_property("enable_root_motion", True)
                loaded_asset.set_editor_property(
                    "root_motion_root_lock",
                    unreal.RootMotionRootLock.ANIM_FIRST_FRAME)
            EditorAssetLibrary.save_asset(asset)

        if master_level:
            unreal.EditorLevelLibrary.save_current_level()
            unreal.EditorLevelLibrary.load_level(master_level)

    def update(self, container, context):
        # Create directory for folder and Ayon container
        folder_path = context["folder"]["path"]
        hierarchy = folder_path.lstrip("/").split("/")
        folder_name = hierarchy.pop(-1)
        folder_name = context["folder"]["name"]
        product_type = context["product"]["productType"]
        repre_entity = context["representation"]
        folder_entity = context["folder"]

        suffix = "_CON"
        source_path = get_representation_path(repre_entity)
        ext = os.path.splitext(source_path)[-1].lstrip(".")
        asset_root, asset_name = unreal_pipeline.format_asset_directory(context, self.loaded_asset_dir)
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")

        container_name += suffix
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            EditorAssetLibrary.make_directory(asset_dir)

        master_level = self._import_animation_with_json(
            source_path, context, hierarchy,
            asset_dir, folder_name, asset_name
        )
        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{container_name}"):
                # Create Asset Container
                unreal_pipeline.create_container(
                    container=container_name, path=asset_dir
                )
        # update metadata
        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            repre_entity,
            product_type,
            folder_entity,
            context["project"]["name"]
        )

        asset_content = EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=True
        )

        for a in asset_content:
            EditorAssetLibrary.save_asset(a)

        if master_level:
            unreal.EditorLevelLibrary.save_current_level()
            unreal.EditorLevelLibrary.load_level(master_level)

        return asset_content

    def remove(self, container):
        path = container["namespace"]
        if unreal.EditorAssetLibrary.does_directory_exist(path):
            unreal.EditorAssetLibrary.delete_directory(path)
