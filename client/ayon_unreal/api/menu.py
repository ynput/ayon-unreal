import unreal
from ayon_core.tools import context_dialog
from ayon_core.tools.utils import host_tools
from ayon_unreal.api import hierarchy, rendering


@unreal.uclass()
class AyonPythonMenuTool(unreal.ToolMenuEntryScript):
    name = ""
    display_name = ""
    tool_tip = ""

    def __init__(self, menu_object, section_name=""):
        super().__init__()
        self.init_entry(
            owner_name="ayon_manager_id",
            menu=menu_object.menu_name,
            section=section_name,
            name=self.name,
            label=self.display_name,
        )
        menu_object.add_menu_entry_object(self)

    @unreal.ufunction(override=True)
    def execute(self, context):
        print(f"Context {context}")


@unreal.uclass()
class AyonToolsMenuTool(AyonPythonMenuTool):
    name = "ayon_tools_menu"
    display_name = "Ayon Tools"
    tool_tip = "Launches the Ayon tools menu."

    @unreal.ufunction(override=True)
    def execute(self, context):
        from ayon_unreal.api import tools_ui

        tools_ui.show_tools_dialog()


@unreal.uclass()
class AyonPublishMenuItem(AyonPythonMenuTool):
    name = "ayon_publish"
    display_name = "Publish..."
    tool_tip = "Opens the Ayon Publisher"

    @unreal.ufunction(override=True)
    def execute(self, context):
        host_tools.show_tool_by_name("publisher", parent=None)


@unreal.uclass()
class AyonLoadMenuItem(AyonPythonMenuTool):
    name = "ayon_loader"
    display_name = "Loader"
    tool_tip = "Opens the Ayon Loader"

    @unreal.ufunction(override=True)
    def execute(self, context):
        host_tools.show_tool_by_name("loader", parent=None)


@unreal.uclass()
class AyonSceneInventoryMenuItem(AyonPythonMenuTool):
    name = "ayon_scene_inventory"
    display_name = "Manage..."
    tool_tip = "Opens the Ayon Scene Inventroy"

    @unreal.ufunction(override=True)
    def execute(self, context):
        host_tools.show_tool_by_name("sceneinventory", parent=None)


@unreal.uclass()
class AyonContextMenuItem(AyonPythonMenuTool):
    name = "ayon_context"
    display_name = "Set Context..."
    tool_tip = "Open context dialog to set up current project, task and folder."

    @unreal.ufunction(override=True)
    def execute(self, context):
        context_dialog.ask_for_context()


@unreal.uclass()
class AyonRenderMenuItem(AyonPythonMenuTool):
    name = "ayon_render"
    display_name = "Render..."
    tool_tip = "Starts render from Publish Instance selection."

    @unreal.ufunction(override=True)
    def execute(self, context):
        rendering.start_rendering()


@unreal.uclass()
class AyonSequenceItem(AyonPythonMenuTool):
    name = "ayon_build_hierarchy"
    display_name = "Build sequence hierarchy..."
    tool_tip = ""

    @unreal.ufunction(override=True)
    def execute(self, context):
        hierarchy.build_sequence_hierarchy()


@unreal.uclass()
class AyonExperimentalItem(AyonPythonMenuTool):
    name = "ayon_experimental"
    display_name = "Experimental tools..."
    tool_tip = ""

    @unreal.ufunction(override=True)
    def execute(self, context):
        self.tool_required.emit("experimental_tools")


def init_ayon_menu():
    menus = unreal.ToolMenus.get()
    main_menu = menus.find_menu("LevelEditor.MainMenu")
    ayon_menu = main_menu.add_sub_menu(
        owner="ayon_manager_id",
        section_name="",
        name="ayon_tools",
        label="Ayon",
    )
    menu_items = [AyonToolsMenuTool]

    for item in menu_items:
        item(ayon_menu)
