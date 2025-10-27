import unreal


def init_ayon_menu():
    print("Menu Init...")
    menus = unreal.ToolMenus.get()
    section_name = "halon_ayon_section"
    command = (
        "from ayon_unreal.api import tools_ui;"
        "tools_ui.show_tools_dialog()"
    )

    level_menu_bar = menus.find_menu(
        "LevelEditor.LevelEditorToolBar.PlayToolBar"
    )
    level_menu_bar.add_section(section_name=section_name, label=section_name)

    entry = unreal.ToolMenuEntry(type=unreal.MultiBlockType.TOOL_BAR_BUTTON)
    entry.set_label("Script Editor")
    entry.set_tool_tip("Unreal Python Script Editor")
    entry.set_icon("EditorStyle", "Symbols.SearchGlass")
    entry.set_string_command(
        type=unreal.ToolMenuStringCommandType.PYTHON,
        custom_type=unreal.Name(""),
        string=command,
    )
    level_menu_bar.add_menu_entry(section_name, entry)
    menus.refresh_all_widgets()
