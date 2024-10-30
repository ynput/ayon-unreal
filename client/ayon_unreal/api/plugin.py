# -*- coding: utf-8 -*-
import ast
import collections
import sys
import six
from abc import (
    ABC,
    ABCMeta,
)

import unreal
import ayon_api

from .pipeline import (
    create_publish_instance,
    imprint,
    ls_inst,
    UNREAL_VERSION
)
from ayon_core.lib import (
    BoolDef,
    UILabelDef
)
from ayon_core.pipeline import (
    AutoCreator,
    Creator,
    LoaderPlugin,
    CreatorError,
    CreatedInstance,
    discover_loader_plugins,
    loaders_from_representation,
    load_container,
    AYON_CONTAINER_ID,
    get_current_project_name
)


class UnrealCreateLogic():
    """Universal class for logic that Unreal creators could inherit from."""
    root = "/Game/Ayon/AyonPublishInstances"
    suffix = "_INS"


    @staticmethod
    def get_cached_instances(shared_data):
        """Cache instances for Creators to shared data.

        Create `unreal_cached_subsets` key when needed in shared data and
        fill it with all collected instances from the scene under its
        respective creator identifiers.

        If legacy instances are detected in the scene, create
        `unreal_cached_legacy_subsets` there and fill it with
        all legacy subsets under product_type as a key.

        Args:
            Dict[str, Any]: Shared data.

        Return:
            Dict[str, Any]: Shared data dictionary.

        """
        if shared_data.get("unreal_cached_subsets") is None:
            unreal_cached_subsets = collections.defaultdict(list)
            unreal_cached_legacy_subsets = collections.defaultdict(list)
            for instance in ls_inst():
                creator_id = instance.get("creator_identifier")
                if creator_id:
                    unreal_cached_subsets[creator_id].append(instance)
                else:
                    product_type = instance.get("product_type")
                    unreal_cached_legacy_subsets[product_type].append(instance)

            shared_data["unreal_cached_subsets"] = unreal_cached_subsets
            shared_data["unreal_cached_legacy_subsets"] = (
                unreal_cached_legacy_subsets
            )
        return shared_data

    def _default_collect_instances(self):
        # cache instances if missing
        self.get_cached_instances(self.collection_shared_data)
        for instance in self.collection_shared_data[
                "unreal_cached_subsets"].get(self.identifier, []):
            # Unreal saves metadata as string, so we need to convert it back
            instance['creator_attributes'] = ast.literal_eval(
                instance.get('creator_attributes', '{}'))
            instance['publish_attributes'] = ast.literal_eval(
                instance.get('publish_attributes', '{}'))
            instance['members'] = ast.literal_eval(
                instance.get('members', '[]'))
            instance['families'] = ast.literal_eval(
                instance.get('families', '[]'))
            instance['active'] = ast.literal_eval(
                instance.get('active', ''))
            created_instance = CreatedInstance.from_existing(instance, self)
            self._add_instance_to_context(created_instance)

    def _default_update_instances(self, update_list):
        for created_inst, changes in update_list:
            instance_node = created_inst.get("instance_path", "")

            if not instance_node:
                unreal.log_warning(
                    f"Instance node not found for {created_inst}")
                continue

            new_values = {
                key: changes[key].new_value
                for key in changes.changed_keys
            }
            imprint(
                instance_node,
                new_values
            )

    def _default_remove_instances(self, instances):
        for instance in instances:
            instance_node = instance.data.get("instance_path", "")
            if instance_node:
                unreal.EditorAssetLibrary.delete_asset(instance_node)

            self._remove_instance_from_context(instance)


    def create_unreal(self, product_name, instance_data, pre_create_data):
        try:
            instance_name = f"{product_name}{self.suffix}"
            pub_instance = create_publish_instance(instance_name, self.root)

            instance_data["product_name"] = product_name
            instance_data["instance_path"] = f"{self.root}/{instance_name}"

            instance = CreatedInstance(
                self.product_type,
                product_name,
                instance_data,
                self)
            self._add_instance_to_context(instance)

            pub_instance.set_editor_property('add_external_assets', True)
            assets = pub_instance.get_editor_property('asset_data_external')

            ar = unreal.AssetRegistryHelpers.get_asset_registry()

            for member in pre_create_data.get("members", []):
                obj = ar.get_asset_by_object_path(member).get_asset()
                assets.add(obj)

            imprint(f"{self.root}/{instance_name}",
                    instance.data_to_store())

            return instance

        except Exception as er:
            six.reraise(
                CreatorError,
                CreatorError(f"Creator error: {er}"),
                sys.exc_info()[2])


class UnrealBaseAutoCreator(AutoCreator, UnrealCreateLogic):
    """Base class for Unreal auto creator plugins."""

    def collect_instances(self):
        return self._default_collect_instances()

    def update_instances(self, update_list):
        return self._default_update_instances(update_list)

    def remove_instances(self, instances):
        return self._default_remove_instances(instances)


class UnrealBaseCreator(UnrealCreateLogic, Creator):
    """Base class for Unreal creator plugins."""

    def create(self, subset_name, instance_data, pre_create_data):
        self.create_unreal(subset_name, instance_data, pre_create_data)

    def collect_instances(self):
        return self._default_collect_instances()

    def update_instances(self, update_list):
        return self._default_update_instances(update_list)

    def remove_instances(self, instances):
        return self._default_remove_instances(instances)


class UnrealAssetCreator(UnrealBaseCreator):
    """Base class for Unreal creator plugins based on assets."""

    def create(self, product_name, instance_data, pre_create_data):
        """Create instance of the asset.

        Args:
            product_name (str): Name of the product.
            instance_data (dict): Data for the instance.
            pre_create_data (dict): Data for the instance.

        Returns:
            CreatedInstance: Created instance.
        """
        try:
            # Check if instance data has members, filled by the plugin.
            # If not, use selection.
            if not pre_create_data.get("members"):
                pre_create_data["members"] = []

                if pre_create_data.get("use_selection"):
                    utilib = unreal.EditorUtilityLibrary
                    sel_objects = utilib.get_selected_assets()
                    pre_create_data["members"] = [
                        a.get_path_name() for a in sel_objects]

            super(UnrealAssetCreator, self).create(
                product_name,
                instance_data,
                pre_create_data)

        except Exception as er:
            six.reraise(
                CreatorError,
                CreatorError(f"Creator error: {er}"),
                sys.exc_info()[2])

    def get_pre_create_attr_defs(self):
        return [
            BoolDef("use_selection", label="Use selection", default=True)
        ]


@six.add_metaclass(ABCMeta)
class UnrealActorCreator(UnrealBaseCreator):
    """Base class for Unreal creator plugins based on actors."""

    def create(self, product_name, instance_data, pre_create_data):
        """Create instance of the asset.

        Args:
            product_name (str): Name of the product.
            instance_data (dict): Data for the instance.
            pre_create_data (dict): Data for the instance.

        Returns:
            CreatedInstance: Created instance.
        """
        try:
            if UNREAL_VERSION.major == 5:
                world = unreal.UnrealEditorSubsystem().get_editor_world()
            else:
                world = unreal.EditorLevelLibrary.get_editor_world()

            # Check if the level is saved
            if world.get_path_name().startswith("/Temp/"):
                raise CreatorError(
                    "Level must be saved before creating instances.")

            # Check if instance data has members, filled by the plugin.
            # If not, use selection.
            if not instance_data.get("members"):
                actor_subsystem = unreal.EditorActorSubsystem()
                sel_actors = actor_subsystem.get_selected_level_actors()
                selection = [a.get_path_name() for a in sel_actors]

                instance_data["members"] = selection
            instance_data["level"] = world.get_path_name()

            super(UnrealActorCreator, self).create(
                product_name,
                instance_data,
                pre_create_data)

        except Exception as er:
            six.reraise(
                CreatorError,
                CreatorError(f"Creator error: {er}"),
                sys.exc_info()[2])

    def get_pre_create_attr_defs(self):
        return [
            UILabelDef("Select actors to create instance from them."),
        ]


class Loader(LoaderPlugin, ABC):
    """This serves as skeleton for future Ayon specific functionality"""
    pass


class LayoutLoader(Loader):
    """Load Layout from a JSON file"""

    product_types = {"layout"}
    representations = {"json"}

    label = "Load Layout"
    icon = "code-fork"
    color = "orange"

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

    def _get_repre_entities_by_version_id(self, project_name, data, repre_extension, force_loaded=False):
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

    def imprint(
        self,
        context,
        folder_path,
        folder_name,
        loaded_assets,
        asset_dir,
        asset_name,
        container_name,
        hierarchy_dir=None
    ):
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
        }
        if hierarchy_dir is not None:
            data["master_directory"] = hierarchy_dir
        imprint(
            "{}/{}".format(asset_dir, container_name), data)

    def _load_assets(self, instance_name, repre_id, product_type, repr_format):
        all_loaders = discover_loader_plugins()
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
            return

        options = {
            # "asset_dir": asset_dir
        }

        assets = load_container(
            loader,
            repre_id,
            namespace=instance_name,
            options=options
        )
        return assets
