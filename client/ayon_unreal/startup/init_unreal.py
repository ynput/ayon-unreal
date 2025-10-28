# Copyright (c) 2024 Ynput s.r.o.
import unreal
try:
    import qtpy
    from qtpy import QtWidgets
except ImportError as exc:
    # this is because `QtBingingsNotFoundError` exception is risen
    # directly from `import qtpy`
    if exc.__class__.__name__ != "QtBindingsNotFoundError":
        raise exc
    message = "PySide 2 is missing, please visit to https://ayon.ynput.io/docs/addon_unreal_admin for more installation info"
    title = "Notification"
    message_type = unreal.AppMsgType.OK
    default_value = unreal.AppReturnType.NO

    # Show the message dialog
    unreal.EditorDialog.show_message(title, message, message_type, default_value)

ayon_detected = True
try:
    # AYON support (both ayon-core and ayon-unreal addon locations)
    from ayon_core.pipeline import install_host

    try:
        from ayon_unreal.api import UnrealHost
    except ImportError:
        from ayon_core.hosts.unreal.api import UnrealHost

    ayon_host = UnrealHost()
except ImportError as exc:
    ayon_host = None
    ayon_detected = False
    unreal.log_error(f"Ayon: cannot load Ayon integration [ {exc} ]")

if ayon_detected:
    install_host(ayon_host)


