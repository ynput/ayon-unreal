import semver
import os

from ayon_unreal import UNREAL_ADDON_ROOT

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
