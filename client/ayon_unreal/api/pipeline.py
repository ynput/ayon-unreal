# -*- coding: utf-8 -*-
import os
import re
import json
import clique
import copy
import logging
from typing import List, Any
from contextlib import contextmanager
import time

import semver
import pyblish.api
import ayon_api

from ayon_core.pipeline import (
    register_loader_plugin_path,
    register_creator_plugin_path,
    register_inventory_action_path,
    deregister_loader_plugin_path,
    deregister_creator_plugin_path,
    deregister_inventory_action_path,
    AYON_CONTAINER_ID,
    get_current_project_name,
)
from ayon_core.lib import StringTemplate
from ayon_core.pipeline.context_tools import (
    get_current_folder_entity
)
from ayon_core.tools.utils import host_tools
from ayon_core.host import HostBase, ILoadHost, IPublishHost
from ayon_unreal import UNREAL_ADDON_ROOT

import unreal  # noqa

# Rename to Ayon once parent module renames
logger = logging.getLogger("ayon_core.hosts.unreal")

AYON_CONTAINERS = "AyonContainers"
AYON_ROOT_DIR = "/Game/Ayon"
AYON_ASSET_DIR = "/Game/Ayon/Assets"
CONTEXT_CONTAINER = "Ayon/context.json"
UNREAL_VERSION = semver.VersionInfo(
    *os.getenv("AYON_UNREAL_VERSION").split(".")
)

PLUGINS_DIR = os.path.join(UNREAL_ADDON_ROOT, "plugins")
PUBLISH_PATH = os.path.join(PLUGINS_DIR, "publish")
LOAD_PATH = os.path.join(PLUGINS_DIR, "load")
CREATE_PATH = os.path.join(PLUGINS_DIR, "create")
INVENTORY_PATH = os.path.join(PLUGINS_DIR, "inventory")


class UnrealHost(HostBase, ILoadHost, IPublishHost):
    """Unreal host implementation.

    For some time this class will re-use functions from module based
    implementation for backwards compatibility of older unreal projects.
    """

    name = "unreal"

    def install(self):
        install()

    def get_containers(self):
        return ls()

    @staticmethod
    def show_tools_popup():
        """Show tools popup with actions leading to show other tools."""
        show_tools_popup()

    @staticmethod
    def show_tools_dialog():
        """Show tools dialog with actions leading to show other tools."""
        show_tools_dialog()

    def update_context_data(self, data, changes):
        content_path = unreal.Paths.project_content_dir()
        op_ctx = content_path + CONTEXT_CONTAINER
        attempts = 3
        for i in range(attempts):
            try:
                with open(op_ctx, "w+") as f:
                    json.dump(data, f)
                break
            except IOError as e:
                if i == attempts - 1:
                    raise Exception(
                        "Failed to write context data. Aborting.") from e
                unreal.log_warning("Failed to write context data. Retrying...")
                i += 1
                time.sleep(3)
                continue

    def get_context_data(self):
        content_path = unreal.Paths.project_content_dir()
        op_ctx = content_path + CONTEXT_CONTAINER
        if not os.path.isfile(op_ctx):
            return {}
        with open(op_ctx, "r") as fp:
            data = json.load(fp)
        return data


def install():
    """Install Unreal configuration for AYON."""
    print("-=" * 40)
    logo = '''.
.
                    ·
                    │
                   ·∙/
                 ·-∙•∙-·
              / \\  /∙·  / \\
             ∙   \\  │  /   ∙
              \\   \\ · /   /
              \\\\   ∙ ∙  //
                \\\\/   \\//
                   ___
                  │   │
                  │   │
                  │   │
                  │___│
                    -·

         ·-─═─-∙ A Y O N ∙-─═─-·
                by  YNPUT
.
'''
    print(logo)
    print("installing Ayon for Unreal ...")
    print("-=" * 40)
    logger.info("installing Ayon for Unreal")
    pyblish.api.register_host("unreal")
    pyblish.api.register_plugin_path(str(PUBLISH_PATH))
    register_loader_plugin_path(str(LOAD_PATH))
    register_creator_plugin_path(str(CREATE_PATH))
    register_inventory_action_path(str(INVENTORY_PATH))
    _register_callbacks()
    _register_events()


def uninstall():
    """Uninstall Unreal configuration for Ayon."""
    pyblish.api.deregister_plugin_path(str(PUBLISH_PATH))
    deregister_loader_plugin_path(str(LOAD_PATH))
    deregister_creator_plugin_path(str(CREATE_PATH))
    deregister_inventory_action_path(str(INVENTORY_PATH))


def _register_callbacks():
    """
    TODO: Implement callbacks if supported by UE
    """
    pass


def _register_events():
    """
    TODO: Implement callbacks if supported by UE
    """
    pass


def ls():
    """List all containers.

    List all found in *Content Manager* of Unreal and return
    metadata from them. Adding `objectName` to set.

    """
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    # UE 5.1 changed how class name is specified
    class_name = ["/Script/Ayon", "AyonAssetContainer"] if UNREAL_VERSION.major == 5 and UNREAL_VERSION.minor > 0 else "AyonAssetContainer"  # noqa
    ayon_containers = ar.get_assets_by_class(class_name, True)

    # get_asset_by_class returns AssetData. To get all metadata we need to
    # load asset. get_tag_values() work only on metadata registered in
    # Asset Registry Project settings (and there is no way to set it with
    # python short of editing ini configuration file).
    for asset_data in ayon_containers:
        asset = asset_data.get_asset()
        data = unreal.EditorAssetLibrary.get_metadata_tag_values(asset)
        data["objectName"] = asset_data.asset_name
        yield cast_map_to_str_dict(data)


def ls_inst():
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    # UE 5.1 changed how class name is specified
    class_name = [
        "/Script/Ayon",
        "AyonPublishInstance"
    ] if (
            UNREAL_VERSION.major == 5
            and UNREAL_VERSION.minor > 0
    ) else "AyonPublishInstance"  # noqa
    instances = ar.get_assets_by_class(class_name, True)

    # get_asset_by_class returns AssetData. To get all metadata we need to
    # load asset. get_tag_values() work only on metadata registered in
    # Asset Registry Project settings (and there is no way to set it with
    # python short of editing ini configuration file).
    for asset_data in instances:
        asset = asset_data.get_asset()
        data = unreal.EditorAssetLibrary.get_metadata_tag_values(asset)
        data["objectName"] = asset_data.asset_name
        yield cast_map_to_str_dict(data)


def parse_container(container):
    """To get data from container, AyonAssetContainer must be loaded.

    Args:
        container(str): path to container

    Returns:
        dict: metadata stored on container
    """
    asset = unreal.EditorAssetLibrary.load_asset(container)
    data = unreal.EditorAssetLibrary.get_metadata_tag_values(asset)
    data["objectName"] = asset.get_name()
    data = cast_map_to_str_dict(data)

    return data


def publish():
    """Shorthand to publish from within host."""
    import pyblish.util

    return pyblish.util.publish()


def containerise(name, namespace, nodes, context, loader=None, suffix="_CON"):
    """Bundles *nodes* (assets) into a *container* and add metadata to it.

    Unreal doesn't support *groups* of assets that you can add metadata to.
    But it does support folders that helps to organize asset. Unfortunately
    those folders are just that - you cannot add any additional information
    to them. Ayon Integration Plugin is providing way out - Implementing
    `AssetContainer` Blueprint class. This class when added to folder can
    handle metadata on it using standard
    :func:`unreal.EditorAssetLibrary.set_metadata_tag()` and
    :func:`unreal.EditorAssetLibrary.get_metadata_tag_values()`. It also
    stores and monitor all changes in assets in path where it resides. List of
    those assets is available as `assets` property.

    This is list of strings starting with asset type and ending with its path:
    `Material /Game/Ayon/Test/TestMaterial.TestMaterial`

    """
    # 1 - create directory for container
    root = "/Game"
    container_name = f"{name}{suffix}"
    new_name = move_assets_to_path(root, container_name, nodes)

    # 2 - create Asset Container there
    path = f"{root}/{new_name}"
    create_container(container=container_name, path=path)

    namespace = path

    data = {
        "schema": "ayon:container-2.0",
        "id": AYON_CONTAINER_ID,
        "name": new_name,
        "namespace": namespace,
        "loader": str(loader),
        "representation": context["representation"]["id"],
    }
    # 3 - imprint data
    imprint(f"{path}/{container_name}", data)
    return path


def instantiate(root, name, data, assets=None, suffix="_INS"):
    """Bundles *nodes* into *container*.

    Marking it with metadata as publishable instance. If assets are provided,
    they are moved to new path where `AyonPublishInstance` class asset is
    created and imprinted with metadata.

    This can then be collected for publishing by Pyblish for example.

    Args:
        root (str): root path where to create instance container
        name (str): name of the container
        data (dict): data to imprint on container
        assets (list of str): list of asset paths to include in publish
                              instance
        suffix (str): suffix string to append to instance name

    """
    container_name = f"{name}{suffix}"

    # if we specify assets, create new folder and move them there. If not,
    # just create empty folder
    if assets:
        new_name = move_assets_to_path(root, container_name, assets)
    else:
        new_name = create_folder(root, name)

    path = f"{root}/{new_name}"
    create_publish_instance(instance=container_name, path=path)

    imprint(f"{path}/{container_name}", data)


def imprint(node, data):
    loaded_asset = unreal.EditorAssetLibrary.load_asset(node)
    for key, value in data.items():
        # Support values evaluated at imprint
        if callable(value):
            value = value()
        # Unreal doesn't support NoneType in metadata values
        if value is None:
            value = ""
        unreal.EditorAssetLibrary.set_metadata_tag(
            loaded_asset, key, str(value)
        )

    with unreal.ScopedEditorTransaction("Ayon containerising"):
        unreal.EditorAssetLibrary.save_asset(node)


def show_tools_popup():
    """Show popup with tools.

    Popup will disappear on click or losing focus.
    """
    from ayon_unreal.api import tools_ui

    tools_ui.show_tools_popup()


def show_tools_dialog():
    """Show dialog with tools.

    Dialog will stay visible.
    """
    from ayon_unreal.api import tools_ui

    tools_ui.show_tools_dialog()


def show_creator():
    host_tools.show_creator()


def show_loader():
    host_tools.show_loader(use_context=True)


def show_publisher():
    host_tools.show_publish()


def show_manager():
    host_tools.show_scene_inventory()


def show_experimental_tools():
    host_tools.show_experimental_tools_dialog()


def create_folder(root: str, name: str) -> str:
    """Create new folder.

    If folder exists, append number at the end and try again, incrementing
    if needed.

    Args:
        root (str): path root
        name (str): folder name

    Returns:
        str: folder name

    Example:
        >>> create_folder("/Game/Foo")
        /Game/Foo
        >>> create_folder("/Game/Foo")
        /Game/Foo1

    """
    eal = unreal.EditorAssetLibrary
    index = 1
    while True:
        if eal.does_directory_exist(f"{root}/{name}"):
            name = f"{name}{index}"
            index += 1
        else:
            eal.make_directory(f"{root}/{name}")
            break

    return name


def move_assets_to_path(root: str, name: str, assets: List[str]) -> str:
    """Moving (renaming) list of asset paths to new destination.

    Args:
        root (str): root of the path (eg. `/Game`)
        name (str): name of destination directory (eg. `Foo` )
        assets (list of str): list of asset paths

    Returns:
        str: folder name

    Example:
        This will get paths of all assets under `/Game/Test` and move them
        to `/Game/NewTest`. If `/Game/NewTest` already exists, then resulting
        path will be `/Game/NewTest1`

        >>> assets = unreal.EditorAssetLibrary.list_assets("/Game/Test")
        >>> move_assets_to_path("/Game", "NewTest", assets)
        NewTest

    """
    eal = unreal.EditorAssetLibrary
    name = create_folder(root, name)

    unreal.log(assets)
    for asset in assets:
        loaded = eal.load_asset(asset)
        eal.rename_asset(asset, f"{root}/{name}/{loaded.get_name()}")

    return name


def create_container(container: str, path: str) -> unreal.Object:
    """Helper function to create Asset Container class on given path.

    This Asset Class helps to mark given path as Container
    and enable asset version control on it.

    Args:
        container (str): Asset Container name
        path (str): Path where to create Asset Container. This path should
            point into container folder

    Returns:
        :class:`unreal.Object`: instance of created asset

    Example:

        create_container(
            "/Game/modelingFooCharacter_CON",
            "modelingFooCharacter_CON"
        )

    """
    factory = unreal.AyonAssetContainerFactory()
    tools = unreal.AssetToolsHelpers().get_asset_tools()

    return tools.create_asset(container, path, None, factory)


def create_publish_instance(instance: str, path: str) -> unreal.Object:
    """Helper function to create Ayon Publish Instance on given path.

    This behaves similarly as :func:`create_ayon_container`.

    Args:
        path (str): Path where to create Publish Instance.
            This path should point into container folder
        instance (str): Publish Instance name

    Returns:
        :class:`unreal.Object`: instance of created asset

    Example:

        create_publish_instance(
            "/Game/modelingFooCharacter_INST",
            "modelingFooCharacter_INST"
        )

    """
    factory = unreal.AyonPublishInstanceFactory()
    tools = unreal.AssetToolsHelpers().get_asset_tools()
    return tools.create_asset(instance, path, None, factory)


def cast_map_to_str_dict(umap) -> dict:
    """Cast Unreal Map to dict.

    Helper function to cast Unreal Map object to plain old python
    dict. This will also cast values and keys to str. Useful for
    metadata dicts.

    Args:
        umap: Unreal Map object

    Returns:
        dict

    """
    return {str(key): str(value) for (key, value) in umap.items()}


def get_subsequences(sequence: unreal.LevelSequence):
    """Get list of subsequences from sequence.

    Args:
        sequence (unreal.LevelSequence): Sequence

    Returns:
        list(unreal.LevelSequence): List of subsequences

    """
    tracks = get_tracks(sequence)
    subscene_track = next(
        (
            t
            for t in tracks
            if t.get_class() == unreal.MovieSceneSubTrack.static_class()
        ),
        None,
    )
    if subscene_track is not None and subscene_track.get_sections():
        return subscene_track.get_sections()
    return []


def set_sequence_hierarchy(
    seq_i, seq_j, max_frame_i, min_frame_j, max_frame_j, map_paths
):
    # Get existing sequencer tracks or create them if they don't exist
    tracks = get_tracks(seq_i)
    subscene_track = None
    visibility_track = None
    for t in tracks:
        if t.get_class() == unreal.MovieSceneSubTrack.static_class():
            subscene_track = t
        if (t.get_class() ==
                unreal.MovieSceneLevelVisibilityTrack.static_class()):
            visibility_track = t
    if not subscene_track:
        subscene_track = add_track(seq_i, unreal.MovieSceneSubTrack)
    if not visibility_track:
        visibility_track = add_track(
            seq_i, unreal.MovieSceneLevelVisibilityTrack)

    # Create the sub-scene section
    subscenes = subscene_track.get_sections()
    subscene = None
    for s in subscenes:
        if s.get_editor_property('sub_sequence') == seq_j:
            subscene = s
            break
    if not subscene:
        subscene = subscene_track.add_section()
        subscene.set_row_index(len(subscene_track.get_sections()))
        subscene.set_editor_property('sub_sequence', seq_j)
        subscene.set_range(
            min_frame_j,
            max_frame_j + 1)

    # Create the visibility section
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    maps = []
    for m in map_paths:
        # Unreal requires to load the level to get the map name
        unreal.EditorLevelLibrary.save_all_dirty_levels()
        unreal.EditorLevelLibrary.load_level(m)
        maps.append(str(ar.get_asset_by_object_path(m).asset_name))

    vis_section = visibility_track.add_section()
    index = len(visibility_track.get_sections())

    vis_section.set_range(
        min_frame_j,
        max_frame_j + 1)
    vis_section.set_visibility(unreal.LevelVisibility.VISIBLE)
    vis_section.set_row_index(index)
    vis_section.set_level_names(maps)

    if min_frame_j > 1:
        hid_section = visibility_track.add_section()
        hid_section.set_range(
            1,
            min_frame_j)
        hid_section.set_visibility(unreal.LevelVisibility.HIDDEN)
        hid_section.set_row_index(index)
        hid_section.set_level_names(maps)
    if max_frame_j < max_frame_i:
        hid_section = visibility_track.add_section()
        hid_section.set_range(
            max_frame_j + 1,
            max_frame_i + 1)
        hid_section.set_visibility(unreal.LevelVisibility.HIDDEN)
        hid_section.set_row_index(index)
        hid_section.set_level_names(maps)


def generate_sequence(h, h_dir):
    tools = unreal.AssetToolsHelpers().get_asset_tools()

    sequence = tools.create_asset(
        asset_name=h,
        package_path=h_dir,
        asset_class=unreal.LevelSequence,
        factory=unreal.LevelSequenceFactoryNew()
    )

    project_name = get_current_project_name()
    filtered_dir = "/Game/Ayon/"
    folder_path = h_dir.replace(filtered_dir, "")
    folder_entity = ayon_api.get_folder_by_path(
        project_name,
        folder_path,
        fields={
            "id",
            "attrib.fps",
            "attrib.clipIn",
            "attrib.clipOut"
        }
    )
    # unreal default frame range value
    fps = 60.0
    min_frame = sequence.get_playback_start()
    max_frame = sequence.get_playback_end()
    if folder_entity:
        min_frame = folder_entity["attrib"]["clipIn"]
        max_frame = folder_entity["attrib"]["clipOut"]
        fps = folder_entity["attrib"]["fps"]
    else:
        unreal.log_warning(
            "Folder Entity not found. Using default Unreal frame range value."
        )

    sequence.set_display_rate(
        unreal.FrameRate(fps, 1.0))
    sequence.set_playback_start(min_frame)
    sequence.set_playback_end(max_frame)

    sequence.set_work_range_start(min_frame / fps)
    sequence.set_work_range_end(max_frame / fps)
    sequence.set_view_range_start(min_frame / fps)
    sequence.set_view_range_end(max_frame / fps)

    tracks = get_tracks(sequence)
    track = None
    for t in tracks:
        if (t.get_class() ==
                unreal.MovieSceneCameraCutTrack.static_class()):
            track = t
            break
    if not track:
        track = add_track(sequence, unreal.MovieSceneCameraCutTrack)

    return sequence, (min_frame, max_frame)


def find_common_name(asset_name):
    # Find the common prefix
    prefix_match = re.match(r"^(.*?)(\d+)(.*?)$", asset_name)
    if not prefix_match:
        return
    name, _, ext = prefix_match.groups()
    return f"{name}_{ext}"


def _get_comps_and_assets(
    component_class, asset_class, old_assets, new_assets, selected
):
    eas = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)

    components = []
    if selected:
        sel_actors = eas.get_selected_level_actors()
        for actor in sel_actors:
            comps = actor.get_components_by_class(component_class)
            components.extend(comps)
    else:
        comps = eas.get_all_level_actors_components()
        components = [
            c for c in comps if isinstance(c, component_class)
        ]

    # Get all the static meshes among the old assets in a dictionary with
    # the name as key
    selected_old_assets = {}
    for a in old_assets:
        asset = unreal.EditorAssetLibrary.load_asset(a)
        if isinstance(asset, asset_class):
            asset_name = find_common_name(asset.get_name())
            selected_old_assets[asset_name] = asset

    # Get all the static meshes among the new assets in a dictionary with
    # the name as key
    selected_new_assets = {}
    for a in new_assets:
        asset = unreal.EditorAssetLibrary.load_asset(a)
        if isinstance(asset, asset_class):
            asset_name = find_common_name(asset.get_name())
            selected_new_assets[asset_name] = asset

    return components, selected_old_assets, selected_new_assets


def replace_static_mesh_actors(old_assets, new_assets, selected):
    smes = unreal.get_editor_subsystem(unreal.StaticMeshEditorSubsystem)

    static_mesh_comps, old_meshes, new_meshes = _get_comps_and_assets(
        unreal.StaticMeshComponent,
        unreal.StaticMesh,
        old_assets,
        new_assets,
        selected
    )

    for old_name, old_mesh in old_meshes.items():
        new_mesh = new_meshes.get(old_name)

        if not new_mesh:
            continue

        smes.replace_mesh_components_meshes(
            static_mesh_comps, old_mesh, new_mesh)


def replace_skeletal_mesh_actors(old_assets, new_assets, selected):
    skeletal_mesh_comps, old_meshes, new_meshes = _get_comps_and_assets(
        unreal.SkeletalMeshComponent,
        unreal.SkeletalMesh,
        old_assets,
        new_assets,
        selected
    )

    for old_name, old_mesh in old_meshes.items():
        new_mesh = new_meshes.get(old_name)

        if not new_mesh:
            continue

        for comp in skeletal_mesh_comps:
            if comp.get_skeletal_mesh_asset() == old_mesh:
                comp.set_skeletal_mesh_asset(new_mesh)


def replace_geometry_cache_actors(old_assets, new_assets, selected):
    geometry_cache_comps, old_caches, new_caches = _get_comps_and_assets(
        unreal.GeometryCacheComponent,
        unreal.GeometryCache,
        old_assets,
        new_assets,
        selected
    )

    for old_name, old_mesh in old_caches.items():
        new_mesh = new_caches.get(old_name)

        if not new_mesh:
            continue

        for comp in geometry_cache_comps:
            if comp.get_editor_property("geometry_cache") == old_mesh:
                comp.set_geometry_cache(new_mesh)


def delete_asset_if_unused(container, asset_content):
    ar = unreal.AssetRegistryHelpers.get_asset_registry()

    references = set()

    for asset_path in asset_content:
        asset = ar.get_asset_by_object_path(asset_path)
        refs = ar.get_referencers(
            asset.package_name,
            unreal.AssetRegistryDependencyOptions(
                include_soft_package_references=False,
                include_hard_package_references=True,
                include_searchable_names=False,
                include_soft_management_references=False,
                include_hard_management_references=False
            ))
        if not refs:
            continue
        references = references.union(set(refs))

    # Filter out references that are in the Temp folder
    cleaned_references = {
        ref for ref in references if not str(ref).startswith("/Temp/")}

    # Check which of the references are Levels
    for ref in cleaned_references:
        loaded_asset = unreal.EditorAssetLibrary.load_asset(ref)
        if isinstance(loaded_asset, unreal.World):
            # If there is at least a level, we can stop, we don't want to
            # delete the container
            return

    unreal.log("Previous version unused, deleting...")

    # No levels, delete the asset
    unreal.EditorAssetLibrary.delete_directory(container["namespace"])


@contextmanager
def maintained_selection():
    """Stub to be either implemented or replaced.

    This is needed for old publisher implementation, but
    it is not supported (yet) in UE.
    """
    try:
        yield
    finally:
        pass


@contextmanager
def select_camera(sequence):
    """Select camera during context
    Args:
        sequence (Objects): Level Sequence Object
    """
    camera_actors = find_camera_actors_in_camera_tracks(sequence)
    actor_subsys = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    selected_actors = actor_subsys.get_selected_level_actors()
    actor_subsys.select_nothing()
    for actor in camera_actors:
        actor_subsys.set_actor_selection_state(actor, True)
    try:
        yield
    finally:
        for actor in camera_actors:
            if actor in selected_actors:
                actor_subsys.set_actor_selection_state(actor, True)
            else:
                actor_subsys.set_actor_selection_state(actor, False)


def format_asset_directory(context, directory_template):
    """Setting up the asset directory path and name.
    Args:
        context (dict): context
        directory_template (str): directory template path

    Returns:
        tuple[str, str]: asset directory, asset name
    """

    data = copy.deepcopy(context)
    if "{product[type]}" in directory_template:
        unreal.warning(
            "Deprecated settings: AYON is using settings "
            "that won't work in future releases. "
            "Details: {product[type]} in the template should "
            "be replaced with {product[productType]}."
        )
        directory_template = directory_template.replace(
            "{product[type]}", "{product[productType]}")

    if "{folder[type]}" in directory_template:
        unreal.warning(
            "Deprecated settings: AYON is using settings "
            "that won't work in future releases. "
            "Details: {folder[type]} in the template should "
            "be replaced with {folder[folderType]}."
        )
        directory_template = directory_template.replace(
            "{folder[type]}", "{folder[folderType]}")

    version = data["version"]["version"]

    # if user set {version[version]},
    # the copied data from data["version"]["version"] convert
    # to set the version of the exclusive version folder
    if version < 0:
        data["version"]["version"] = "hero"
    else:
        data["version"]["version"] = f"v{version:03d}"
    asset_name_with_version = set_asset_name(data)
    asset_dir = StringTemplate(directory_template).format_strict(data)

    return f"{AYON_ROOT_DIR}/{asset_dir}", asset_name_with_version


def set_asset_name(data):
    """Set the name of the asset during loading

    Args:
        folder_name (str): folder name
        name (str): instance name
        extension (str): extension

    Returns:
        str: asset name
    """
    asset_name = None,
    name = data["product"]["name"]
    version = data["version"]["version"]
    folder_name = data["folder"]["name"]
    extension = data["representation"]["name"]
    if not extension:
        asset_name = name
    elif folder_name:
        asset_name = "{}_{}_{}_{}".format(
            folder_name, name, version, extension)
    else:
        asset_name = "{}_{}_{}".format(name, version, extension)
    return asset_name


def show_audit_dialog(missing_asset):
    """
    Show a dialog to inform the user about missing assets.
    """
    message = "The following asset was missing in the content plugin:\n"
    message += f"{missing_asset}.\n"
    message += "Loading the asset into Game Content instead."
    unreal.EditorDialog.show_message(
        "Missing Assets", message, unreal.AppMsgType.OK
    )


def get_sequence(files):
    """Get sequence from filename.

    This will only return files if they exist on disk as it tries
    to collect the sequence using the filename pattern and searching
    for them on disk.

    Supports negative frame ranges like -001, 0000, 0001 and -0001,
    0000, 0001.

    Arguments:
        files (str): List of files

    Returns:
        Optional[list[str]]: file sequence.

    """
    collections, _remainder = clique.assemble(
        files,
        patterns=[clique.PATTERNS["frames"]],
        minimum_items=1)

    if len(collections) > 1:
        raise ValueError(
            f"Multiple collections found for {collections}. "
            "This is a bug.")

    return [os.path.basename(filename) for filename in collections[0]]


def find_camera_actors_in_camera_tracks(sequence) -> list[Any]:
    """Find the camera actors in the tracks from the Level Sequence

    Args:
        tracks (Object): Level Seqence Asset

    Returns:
        Object: Camera Actor
    """
    camera_tracks = []
    camera_objects = []
    camera_tracks = get_camera_tracks(sequence)
    if camera_tracks:
        for camera_track in camera_tracks:
            sections = camera_track.get_sections()
            for section in sections:
                binding_id = section.get_camera_binding_id()
                bound_objects = unreal.LevelSequenceEditorBlueprintLibrary.get_bound_objects(
                    binding_id)
                for camera_object in bound_objects:
                    camera_objects.append(camera_object.get_path_name())
    world =  unreal.EditorLevelLibrary.get_editor_world()
    sel_actors = unreal.GameplayStatics().get_all_actors_of_class(
        world, unreal.CameraActor)
    actors = [a for a in sel_actors if a.get_path_name() in camera_objects]
    return actors


def get_frame_range(sequence):
    """Get the Clip in/out value from the camera tracks located inside
    the level sequence

    Args:
        sequence (Object): Level Sequence

    Returns:
        int32, int32 : Start Frame, End Frame
    """
    camera_tracks = get_camera_tracks(sequence)
    if not camera_tracks:
        return sequence.get_playback_start(), sequence.get_playback_end()
    for camera_track in camera_tracks:
        sections = camera_track.get_sections()
        for section in sections:
            return section.get_start_frame(), section.get_end_frame()


def get_camera_tracks(sequence):
    """Get the list of movie scene camera cut tracks in the level sequence

    Args:
        sequence (Object): Level Sequence

    Returns:
        list: list of movie scene camera cut tracks
    """
    camera_tracks = []
    tracks = get_tracks(sequence)
    for track in tracks:
        if str(track).count("MovieSceneCameraCutTrack"):
            camera_tracks.append(track)
    return camera_tracks


def get_frame_range_from_folder_attributes(folder_entity=None):
    """Get the current clip In/Out value
    Args:
        folder_entity (dict): folder Entity.

    Returns:
        int, int: clipIn, clipOut.
    """
    if folder_entity is None:
        folder_entity = get_current_folder_entity(fields={"attrib"})
    folder_attributes = folder_entity["attrib"]
    frame_start = (
        int(folder_attributes.get("frameStart"))
        if folder_attributes.get("frameStart") else 1
    )
    frame_end = (
        int(folder_attributes.get("frameEnd"))
        if folder_attributes.get("frameEnd") else 1
    )
    return frame_start, frame_end


def find_existing_asset(asset_name, search_dir=None,
                        pattern_regex=None, show_dialog=False):
    """
    Search for an existing asset in a specified directory or default directories.


    Args:
        asset_name (str): The name of the asset to search for.
        search_dir (str, optional): The directory to search (e.g., "/Game/Characters").
                                    If None, defaults to ["/Game", "/Plugins"].
        pattern_regex (dict, optional): A dictionary of regex patterns to filter assets.
                                        Keys are attribute names, and values are regex patterns.
        show_dialog (bool, optional): show audit dialogs to warn the users about the failure of
                                      asset loading.

    Returns:
        str: The full path of the asset if found, otherwise None.
    """
    # List all assets in the project content folder
    asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()

    # Get all assets
    asset_list = asset_registry.get_all_assets()
    # Search for the asset by name
    if pattern_regex:
        name = pattern_regex["name"]
        extension = pattern_regex["extension"]
        pattern = rf"{name}_\d{{3}}"
        if extension:
            pattern = rf"{name}_v\d{{3}}_{extension}"
        version_folder = search_dir.split("/")[-1]
        is_version_folder_matched = re.match(pattern, version_folder)

        if is_version_folder_matched:
            # Get all target assets
            target_asset_path = find_content_plugin_asset(pattern)
            if target_asset_path:
                return target_asset_path
        else:
            if show_dialog:
                show_audit_dialog(asset_name)

    else:
        for package in asset_list:
            if asset_name in str(package.asset_name):
                return unreal.Paths.split(package.package_path)[0]

    return None


def find_content_plugin_asset(pattern):
    # List all assets in the project content folder
    asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
    # Get all target assets
    target_assets = {
        unreal.Paths.split(package.package_path)[0]
        for package in
        asset_registry.get_all_assets()
        if re.match(pattern, str(package.asset_name))
    }
    # asset in game content
    game_content = {
        unreal.Paths.split(game_asset.get_asset().get_path_name())[0]
        for game_asset in
        asset_registry.get_assets_by_path('/Game', recursive=True)
        if game_asset.get_asset().get_name() == re.match(
            pattern, game_asset.get_asset().get_name())
    }
    target_assets = target_assets.difference(game_content)
    if target_assets:
        return list(target_assets)[-1]

    return None


def get_top_hierarchy_folder(path):
    """Get top hierarchy of the path

    Args:
        path (str): path

    Returns:
        str: top hierarchy directory
    """
    # Split the path by the directory separator '/'
    path = path.replace(f"{AYON_ROOT_DIR}/", "")
    # Return the first part
    parts = [part for part in path.split('/') if part]
    return parts[0]


def generate_hierarchy_path(name, folder_name, asset_root, master_dir_name, suffix=""):
    asset_name = f"{folder_name}_{name}" if folder_name else name
    hierarchy_dir = f"{AYON_ROOT_DIR}/{master_dir_name}"
    tools = unreal.AssetToolsHelpers().get_asset_tools()
    asset_dir, container_name = tools.create_unique_asset_name(asset_root, suffix=suffix)
    suffix = "_CON"
    container_name += suffix
    if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
        unreal.EditorAssetLibrary.make_directory(asset_dir)

    return asset_dir, hierarchy_dir, container_name, asset_name


def remove_map_and_sequence(container):
    asset_dir = container.get('namespace')
    # Create a temporary level to delete the layout level.
    unreal.EditorLevelLibrary.save_all_dirty_levels()
    unreal.EditorAssetLibrary.make_directory(f"{AYON_ROOT_DIR}/tmp")
    tmp_level = f"{AYON_ROOT_DIR}/tmp/temp_map"
    if not unreal.EditorAssetLibrary.does_asset_exist(f"{tmp_level}.temp_map"):
        unreal.EditorLevelLibrary.new_level(tmp_level)
    else:
        unreal.EditorLevelLibrary.load_level(tmp_level)
    unreal.EditorLevelLibrary.save_all_dirty_levels()
    # Delete the camera directory.
    if unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
        unreal.EditorAssetLibrary.delete_directory(asset_dir)
    # Load the default level
    default_level_path = "/Engine/Maps/Templates/OpenWorld"
    unreal.EditorLevelLibrary.load_level(default_level_path)
    unreal.EditorAssetLibrary.delete_directory(f"{AYON_ROOT_DIR}/tmp")


def update_container(container, project_name, repre_entity, loaded_assets=None):
    asset_dir = container.get('namespace')
    data = {
        "representation": repre_entity["id"],
        "parent": repre_entity["versionId"],
        "project_name": project_name
    }
    if loaded_assets is not None:
        data["loaded_assets"] = loaded_assets
    imprint(
        "{}/{}".format(
            asset_dir,
            container.get('container_name')),
            data
    )


def generate_master_level_sequence(tools, asset_dir, asset_name,
                                   hierarchy_dir, master_dir_name,
                                   suffix=""):
    # Create map for the shot, and create hierarchy of map. If the maps
    # already exist, we will use them.
    master_level = f"{hierarchy_dir}/{master_dir_name}_map.{master_dir_name}_map"
    if not unreal.EditorAssetLibrary.does_asset_exist(master_level):
        unreal.EditorLevelLibrary.new_level(f"{hierarchy_dir}/{master_dir_name}_map")

    asset_level = f"{asset_dir}/{asset_name}_map.{asset_name}_map"
    if suffix:
        asset_level = (
            f"{asset_dir}/{asset_name}_map_{suffix}.{asset_name}_map_{suffix}"
        )

    unreal.log(f"asset_level: {asset_level}")
    if not unreal.EditorAssetLibrary.does_asset_exist(asset_level):
        unreal.EditorLevelLibrary.new_level(asset_level)
        unreal.EditorLevelLibrary.load_level(master_level)
        unreal.EditorLevelUtils.add_level_to_world(
            unreal.EditorLevelLibrary.get_editor_world(),
            asset_level,
            unreal.LevelStreamingDynamic
        )
    sequences = []
    frame_ranges = []
    root_content = unreal.EditorAssetLibrary.list_assets(
        hierarchy_dir, recursive=False, include_folder=False)

    existing_sequences = [
        unreal.EditorAssetLibrary.find_asset_data(asset)
        for asset in root_content
        if unreal.EditorAssetLibrary.find_asset_data(
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

    shot_name = f"{asset_dir}/{asset_name}.{asset_name}"
    if suffix:
        shot_name = (
            f"{asset_dir}/{asset_name}_{suffix}.{asset_name}_{suffix}"
        )

    shot = None
    if not unreal.EditorAssetLibrary.does_asset_exist(shot_name):
        shot = tools.create_asset(
            asset_name=asset_name if not suffix else f"{asset_name}_{suffix}",
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

    return shot, master_level, asset_level, sequences, frame_ranges


def get_tracks(sequence):
    """Backward compatibility for deprecated function of get_master_tracks() in UE 5.5

    Args:
        sequence (unreal.LevelSequence): Level Sequence

    Returns:
        Array(MovieSceneTracks): Movie scene tracks
    """
    if (
        UNREAL_VERSION.major == 5
        and UNREAL_VERSION.minor > 4
    ):
        return sequence.get_tracks()
    else:
        return sequence.get_master_tracks()


def add_track(sequence, track):
    """Backward compatibility for deprecated function of add_master_track() in UE 5.5

    Args:
        sequence (unreal.LevelSequence): Level Sequence

    Returns:
        MovieSceneTrack: Any tracks inherited from unreal.MovieSceneTrack
    """
    if (
        UNREAL_VERSION.major == 5
        and UNREAL_VERSION.minor > 4
    ):
        return sequence.add_track(track)
    else:
        return sequence.add_master_track(track)
