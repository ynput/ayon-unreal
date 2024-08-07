import unreal
import json
from ayon_api import get_representation_by_id

from ayon_core.pipeline import (
    InventoryAction,
    get_current_project_name,
    get_representation_path
)


def read_representation_data(lib_path):
    representation_ids = []

    with open(lib_path, "r") as fp:
        data = json.load(fp)
    for element in data:
        representation_ids.append(element["representation"])
    return representation_ids


class SwitchAnimatedAssets(InventoryAction):
    """Switch Animated Assets from the static ones.
    """

    label = "Switch animated assets"
    icon = "arrow-up"
    color = "red"
    order = 1

    def process(self, containers):
        allowed_families = ["animation", "layout", "pointcache"]
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        container_dir = None
        for container in containers:
            container_dir = container.get("namespace")
            if container.get("family") not in allowed_families:
                unreal.log_warning(
                    f"Container {container_dir} is not supported.")
                continue
            sa_containers = []
            if container.get("family") == "layout":
                project_name = get_current_project_name()
                repre_entity = get_representation_by_id(
                    project_name, container["representation"])
                path = get_representation_path(repre_entity)
                representation_ids = read_representation_data(path)
                for repre_id in representation_ids:
                    model_repre_entity = get_representation_by_id(
                        project_name, repre_id)
                    folder_name = model_repre_entity["context"]["folder"]["name"]
                    subset_name = model_repre_entity["context"]["subset"]
                    # find name of asset_modelMain
                    repre_entity_folder = f"{folder_name}_{subset_name}"
                    sa_containers.append(repre_entity_folder)
            transform_list = []
            actorsList = unreal.EditorLevelLibrary.get_all_level_actors()
            for name in sa_containers:
                for actor in actorsList:
                    if name in actor.get_actor_label():
                        transform_list.append({"transform": actor.get_actor_location()})

        asset_content = unreal.EditorAssetLibrary.list_assets(
            container_dir, recursive=True, include_folder=False
        )
        for asset in asset_content:
            obj = ar.get_asset_by_object_path(asset).get_asset()
            if obj.get_class().get_name() == "SkeletalMesh":
                for transform_dict in transform_list:
                    t = transform_dict["transform"]
                    actor = unreal.EditorLevelLibrary.spawn_actor_from_object(
                        obj, t.translation
                    )
                    actor.set_actor_rotation(t.rotation.rotator(), False)
                    actor.set_actor_scale3d(t.scale3d)
                    skm_comp = actor.get_editor_property(
                        'skeletal_mesh_component')
                    skm_comp.set_bounds_scale(10.0)

            unreal.EditorLevelLibrary.save_current_level()
