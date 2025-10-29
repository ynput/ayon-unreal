import unreal

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
            label=self.display_name
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

def init_ayon_menu():
    menus = unreal.ToolMenus.get()
    main_menu = menus.find_menu("LevelEditor.MainMenu")
    ayon_menu = main_menu.add_sub_menu(
        owner="ayon_manager_id",
        section_name='',
        name="ayon_tools",
        label="Ayon"
    )
    AyonToolsMenuTool(ayon_menu)
