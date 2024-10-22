import json
from pathlib import Path

import unreal
import collections
from unreal import EditorLevelLibrary
import ayon_api

from ayon_core.pipeline import (
    discover_loader_plugins,
    loaders_from_representation,
    load_container,
    get_representation_path,
    AYON_CONTAINER_ID,
)
from ayon_unreal.api import plugin
from ayon_unreal.api import pipeline as upipeline


class ExistingLayoutLoader(plugin.Loader):
    """
    Load Layout for an existing scene, and match the existing assets.
    """

    product_types = {"layout"}
    representations = {"json"}

    label = "Load Layout on Existing Scene"
    icon = "code-fork"
    color = "orange"
    ASSET_ROOT = "/Game/Ayon"

    delete_unmatched_assets = True
    loaded_layout_dir = "{folder[path]}/{product[name]}"
    master_dir = "{project[name]}"

    @classmethod
    def apply_settings(cls, project_settings):
        super(ExistingLayoutLoader, cls).apply_settings(
            project_settings
        )
        cls.delete_unmatched_assets = (
            project_settings["unreal"]["delete_unmatched_assets"]
        )

    @staticmethod
    def _get_current_level():
        ue_version = unreal.SystemLibrary.get_engine_version().split('.')
        ue_major = ue_version[0]

        if ue_major == '4':
            return EditorLevelLibrary.get_editor_world()
        elif ue_major == '5':
            return unreal.LevelEditorSubsystem().get_current_level()

        raise NotImplementedError(
            f"Unreal version {ue_major} not supported")

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

    def _spawn_actor(self, obj, lasset, sequence):
        actor = EditorLevelLibrary.spawn_actor_from_object(
            obj, unreal.Vector(0.0, 0.0, 0.0)
        )

        transform = lasset.get('transform_matrix')
        basis = lasset.get('basis')
        rotation = lasset.get("rotation", {})

        computed_transform = self._transform_from_basis(transform, basis)

        actor.set_actor_transform(computed_transform, False, True)
        if rotation:
            actor_rotation = unreal.Rotator(
                roll=rotation["x"], pitch=rotation["z"],
                yaw=-rotation["y"])
            actor.set_actor_rotation(actor_rotation, False)
        sequence.add_possessable(actor)

    @staticmethod
    def _get_fbx_loader(loaders, family):
        name = ""
        if family == 'rig':
            name = "SkeletalMeshFBXLoader"
        elif family == 'model' or family == 'staticMesh':
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
        if family == 'rig':
            name = "SkeletalMeshAlembicLoader"
        elif family == 'model' or family == 'staticMesh':
            name = "StaticMeshAlembicLoader"

        if name == "":
            return None

        for loader in loaders:
            if loader.__name__ == name:
                return loader

        return None

    def _load_asset(self, repr_data, instance_name, family, extension):
        repre_entity = next((repre_entity for repre_entity in repr_data
                             if repre_entity["name"] == extension), None)
        if not repre_entity or extension == "ma":
            repre_entity = repr_data[0]

        repr_format = repre_entity.get('name')
        representation = repre_entity.get('id')
        all_loaders = discover_loader_plugins()
        loaders = loaders_from_representation(
            all_loaders, representation)

        loader = None

        if repr_format == 'fbx':
            loader = self._get_fbx_loader(loaders, family)
        elif repr_format == 'abc':
            loader = self._get_abc_loader(loaders, family)

        if not loader:
            if repr_format == "ma":
                msg = (
                    f"No valid {family} loader found for {representation} ({repr_format}), "
                    f"consider using {family} loader (fbx/abc) instead."
                )
                self.log.warning(msg)
            else:
                self.log.error(
                    f"No valid loader found for {representation} "
                    f"({repr_format}) "
                    f"{family}")
            return []

        # This option is necessary to avoid importing the assets with a
        # different conversion compared to the other assets. For ABC files,
        # it is in fact impossible to access the conversion settings. So,
        # we must assume that the Maya conversion settings have been applied.
        options = {
            "default_conversion": True
        }

        assets = load_container(
            loader,
            representation,
            namespace=instance_name,
            options=options
        )

        return assets

    def _get_repre_entities_by_version_id(self, project_name, data):
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
            if ext == "ma":
                updated_extensions.update({"fbx", "abc"})
            else:
                updated_extensions.add(ext)

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

    def _process(self, lib_path, project_name, sequence):
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
            extension = element.get("extension")
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
            project_name, data
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
                computed_transform = self._transform_from_basis(
                    transform, basis)
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
                repre_entities,
                lasset.get('instance_name'),
                product_type,
                extension
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
        product_type = context["product"]["productType"]
        asset_root, _ = upipeline.format_asset_directory(
            context, self.loaded_layout_dir)
        suffix = "_CON"
        asset_name = f"{folder_name}_{name}" if folder_name else name

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root,
            suffix="_existing"
        )

        curr_level = self._get_current_level()
        curr_level_path = Path(
            curr_level.get_outer().get_path_name()).parent.as_posix()
        if curr_level_path == "/Temp":
            curr_level_path = asset_dir
        #TODO: make sure curr_level_path is not a temp path,
        # create new level for layout level
        level_seq_filter = unreal.ARFilter(
            class_names=["LevelSequence"],
            package_paths=[curr_level_path],
            recursive_paths=False)

        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        sequence = next((asset.get_asset() for asset in ar.get_assets(level_seq_filter)), None)
        if not curr_level:
            raise AssertionError("Current level not saved")

        project_name = context["project"]["name"]
        path = self.filepath_from_context(context)
        containers = self._process(path, project_name, sequence)
        container_name += suffix
        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{curr_level_path}/{container_name}"
        ):
            upipeline.create_container(
                container=container_name, path=curr_level_path)

        data = {
            "schema": "ayon:container-2.0",
            "id": AYON_CONTAINER_ID,
            "folder_path": folder_path,
            "namespace": curr_level_path,
            "container_name": container_name,
            "asset_name": asset_name,
            "loader": str(self.__class__.__name__),
            "representation": context["representation"]["id"],
            "parent": context["representation"]["versionId"],
            "product_type": product_type,
            "loaded_assets": containers,
            # TODO these shold be probably removed
            "asset": folder_path,
            "family": product_type,
        }
        upipeline.imprint(f"{curr_level_path}/{container_name}", data)

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
        source_path = get_representation_path(repre_entity)
        containers = self._process(source_path, project_name, sequence)

        data = {
            "representation": repre_entity["id"],
            "loaded_assets": containers,
            "parent": repre_entity["versionId"],
        }
        upipeline.imprint(
            "{}/{}".format(asset_dir, container.get('container_name')), data)

    def remove(self, container):
        parent_path = Path(container["namespace"])
        container_name = container["container_name"]
        if unreal.EditorAssetLibrary.does_asset_exist(
            f"{parent_path}/{container_name}"):
                unreal.EditorAssetLibrary.delete_asset(
                    f"{parent_path}/{container_name}")
