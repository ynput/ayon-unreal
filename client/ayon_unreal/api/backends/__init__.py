
import os

from ayon_unreal.api.backends.ayon_plugin import AyonPluginBackend
from ayon_unreal.api.backends.native_unreal import NativeUnrealBackend


def get_backend_class():
    use_plugin = os.getenv('AYON_PLUGIN_ENABLED') == '1'
    if use_plugin:
        return AyonPluginBackend
    return NativeUnrealBackend
