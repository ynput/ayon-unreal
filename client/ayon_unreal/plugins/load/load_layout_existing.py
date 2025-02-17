import json
from pathlib import Path

import unreal
from unreal import EditorLevelLibrary
import ayon_api
from ayon_core.pipeline.load import LoadError
from ayon_unreal.api import plugin
from ayon_unreal.api import pipeline as upipeline


class ExistingLayoutLoader(plugin.LayoutLoader):
    """
    Load Layout for an existing scene, and match the existing assets.
    """

    label = "Load Layout on Existing Scene"
    delete_unmatched_assets = True

    @classmethod
    def apply_settings(cls, project_settings):
        super(ExistingLayoutLoader, cls).apply_settings(
            project_settings
        )
        import_settings = project_settings["unreal"]["import_settings"]
        cls.delete_unmatched_assets = (
            import_settings["delete_unmatched_assets"]
        )
        cls.loaded_asset_dir = import_settings["loaded_asset_dir"]
        cls.loaded_layout_dir = import_settings["loaded_layout_dir"]
        cls.remove_loaded_assets = import_settings["remove_loaded_assets"]
        cls.resolution_priority = import_settings.get(
            "resolution_priority", cls.resolution_priority)

    def _spawn_actor(self, obj, lasset, sequence):
        actor = EditorLevelLibrary.spawn_actor_from_object(
            obj, unreal.Vector(0.0, 0.0, 0.0)
        )

        transform = lasset.get('transform_matrix')
        basis = lasset.get('basis')
        rotation = lasset.get("rotation", {})
        unreal_import = (
            True if "unreal" in lasset.get("host", []) else False
        )

        computed_transform = self._transform_from_basis(
            transform, basis, unreal_import=unreal_import)

        actor.set_actor_transform(computed_transform, False, True)
        if rotation:
            actor_rotation = unreal.Rotator(
                roll=rotation["x"], pitch=rotation["z"],
                yaw=-rotation["y"])
            actor.set_actor_rotation(actor_rotation, False)
        if sequence is not None:
            sequence.add_possessable(actor)
        else:
            self.log.warning(
                "No Level Sequence found for current level. "
                "Skipping to add spawned actor into the sequence."
            )

    def _load_asset(self, project_name, repr_data, instance_name,
                    family, extension, options):
        repre_entity = next((repre_entity for repre_entity in repr_data
                             if repre_entity["name"] == extension), None)
        if not repre_entity or extension == "ma":
            repre_entity = repr_data[0]

        repr_format = repre_entity.get('name')
        representation = repre_entity.get('id')
        assets = self._load_assets(
            project_name, instance_name, representation, family, repr_format, options)
        return assets

    def _process(self, lib_path, project_name, sequence, options):
        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        actors = EditorLevelLibrary.get_all_level_actors()

        with open(lib_path, "r") as fp:
            data = json.load(fp)

        elements = []
        repre_ids = set()
        extensions = []
        # Get all the representations in the JSON from the database.
        for element in data:
            repre_id = element.get('representation')
            extension = element.get("extension", "ma")
            if repre_id:
                repre_ids.add(repre_id)
                elements.append(element)
            if extension == "ma":
                extensions.extend(["fbx", "abc"])
            else:
                extensions.append(extension)

        repre_entities = ayon_api.get_representations(
            project_name, representation_ids=repre_ids
        )
        repre_entities_by_id = {
            repre_entity["id"]: repre_entity
            for repre_entity in repre_entities
        }
        layout_data = []
        version_ids = set()
        for element in elements:
            repre_id = element.get("representation")
            repre_entity = repre_entities_by_id.get(repre_id)
            if not repre_entity:
                raise AssertionError("Representation not found")
            if not (
                repre_entity.get("attrib")
                or repre_entity["attrib"].get("path")
            ):
                raise AssertionError("Representation does not have path")
            if not repre_entity.get('context'):
                raise AssertionError("Representation does not have context")

            layout_data.append((repre_entity, element))
            version_ids.add(repre_entity["versionId"])

        repre_entities_by_version_id = self._get_repre_entities_by_version_id(
            project_name, data, "json"
        )
        containers = []
        actors_matched = []

        for (repre_entity, lasset) in layout_data:
            # For every actor in the scene, check if it has a representation in
            # those we got from the JSON. If so, create a container for it.
            # Otherwise, remove it from the scene.
            found = False
            repre_id = repre_entity["id"]

            for actor in actors:
                if not actor.get_class().get_name() == 'StaticMeshActor':
                    continue
                if actor in actors_matched:
                    continue

                # Get the original path of the file from which the asset has
                # been imported.
                smc = actor.get_editor_property('static_mesh_component')
                mesh = smc.get_editor_property('static_mesh')
                if not mesh:
                    continue
                import_data = mesh.get_editor_property('asset_import_data')
                filename = import_data.get_first_filename()
                path = Path(filename)

                if (not path.name or
                        path.name not in repre_entity["attrib"]["path"]):
                    unreal.log("Path is not found in representation entity")
                    continue
                existing_asset_dir = unreal.Paths.get_path(mesh.get_path_name())
                assets = ar.get_assets_by_path(existing_asset_dir, recursive=False)
                for asset in assets:
                    obj = asset.get_asset()
                    if asset.get_class().get_name() == 'AyonAssetContainer':
                        container = obj
                        containers.append(container.get_path_name())
                # Set the transform for the actor.
                transform = lasset.get('transform_matrix')
                basis = lasset.get('basis')
                rotation = lasset.get("rotation", {})
                unreal_import = (
                    True if "unreal" in lasset.get("host", []) else False
                )

                computed_transform = self._transform_from_basis(
                    transform, basis, unreal_import=unreal_import)
                actor.set_actor_transform(computed_transform, False, True)
                if rotation:
                    actor_rotation = unreal.Rotator(
                        roll=rotation["x"], pitch=rotation["z"],
                        yaw=-rotation["y"])
                    actor.set_actor_rotation(actor_rotation, False)
                actors_matched.append(actor)
                found = True
                break

            # If an actor has not been found for this representation,
            # we check if it has been loaded already by checking all the
            # loaded containers. If so, we add it to the scene. Otherwise,
            # we load it.
            if found:
                continue

            all_containers = upipeline.ls()

            loaded = False

            for container in all_containers:
                repre_id = container.get('representation')

                if not repre_id == repre_entity["id"]:
                    continue

                asset_dir = container.get('namespace')

                arfilter = unreal.ARFilter(
                    class_names=["StaticMesh"],
                    package_paths=[asset_dir],
                    recursive_paths=False)
                assets = ar.get_assets(arfilter)

                for asset in assets:
                    obj = asset.get_asset()
                    self._spawn_actor(obj, lasset, sequence)
                loaded = True
                break

            # If the asset has not been loaded yet, we load it.
            if loaded:
                continue

            version_id = lasset.get('version')
            repre_entities = repre_entities_by_version_id.get(version_id)
            if not repre_entities:
                self.log.error(
                    f"No valid representation found for version"
                    f" {version_id}")
                continue

            product_type = lasset.get("product_type")
            if product_type is None:
                product_type = lasset.get("family")
            extension = lasset.get("extension")
            assets = self._load_asset(
                project_name,
                repre_entities,
                lasset.get('instance_name'),
                product_type,
                extension,
                options
            )
            con = None
            for asset in assets:
                obj = ar.get_asset_by_object_path(asset).get_asset()
                if not obj.get_class().get_name() == 'StaticMesh':
                    continue

                self._spawn_actor(obj, lasset, sequence)
                if obj.get_class().get_name() == 'AyonAssetContainer':
                    con = obj
                    containers.append(con.get_path_name())
                break
        # Check if an actor was not matched to a representation.
        # If so, remove it from the scene.
        for actor in actors:
            if not actor.get_class().get_name() == 'StaticMeshActor':
                continue
            if actor not in actors_matched:
                self.log.warning(f"Actor {actor.get_name()} not matched.")
                if self.delete_unmatched_assets:
                    EditorLevelLibrary.destroy_actor(actor)

        return containers

    def load(self, context, name, namespace, options):
        print("Loading Layout and Match Assets")

        # Create directory for asset and Ayon container
        folder_entity = context["folder"]
        folder_path = folder_entity["path"]

        folder_name = folder_entity["name"]
        asset_root, _ = upipeline.format_asset_directory(
            context, self.loaded_layout_dir)
        suffix = "_CON"
        asset_name = f"{folder_name}_{name}" if folder_name else name

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root,
            suffix="_existing"
        )

        sub_sys = unreal.get_editor_subsystem(unreal.LevelEditorSubsystem)
        curr_level = sub_sys.get_current_level()
        curr_asset_dir = Path(
            curr_level.get_outer().get_path_name()).parent.as_posix()
        if curr_asset_dir == "/Temp":
            curr_asset_dir = asset_dir
        #TODO: make sure asset_dir is not a temp path,
        # create new level for layout level
        level_seq_filter = unreal.ARFilter(
            class_names=["LevelSequence"],
            package_paths=[curr_asset_dir],
            recursive_paths=False)

        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        sequence = next((asset.get_asset() for asset in ar.get_assets(level_seq_filter)), None)
        if not curr_level:
            raise LoadError("Current level not saved")

        project_name = context["project"]["name"]
        path = self.filepath_from_context(context)
        import_options = {
            "resolution_priority": options.get(
                "resolution_priority", self.resolution_priority)
        }

        loaded_assets = self._process(path, project_name, sequence, import_options)

        container_name += suffix
        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{curr_asset_dir}/{container_name}"
        ):
            upipeline.create_container(
                container=container_name, path=curr_asset_dir)
        self.imprint(
            context,
            folder_path,
            folder_name,
            loaded_assets,
            curr_asset_dir,
            asset_name,
            container_name,
            context["project"]["name"]
        )

    def update(self, container, context):
        asset_dir = container.get('namespace')

        project_name = context["project"]["name"]
        repre_entity = context["representation"]
        level_seq_filter = unreal.ARFilter(
            class_names=["LevelSequence"],
            package_paths=[asset_dir],
            recursive_paths=False)

        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        sequence = next((asset for asset in ar.get_assets(level_seq_filter)), None)
        source_path = self.filepath_from_context(context)
        import_options = {
            "resolution_priority": self.resolution_priority
        }
        loaded_assets = self._process(source_path, project_name, sequence, import_options)

        upipeline.update_container(
            container, repre_entity, loaded_assets=loaded_assets)

        unreal.EditorLevelLibrary.save_current_level()

    def remove(self, container):
        parent_path = Path(container["namespace"])
        self._remove_Loaded_asset(container)
        container_name = container["container_name"]
        if unreal.EditorAssetLibrary.does_asset_exist(
            f"{parent_path}/{container_name}"):
                unreal.EditorAssetLibrary.delete_asset(
                    f"{parent_path}/{container_name}")
