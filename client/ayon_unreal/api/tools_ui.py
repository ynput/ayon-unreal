import sys

import ayon_api
import unreal
from ayon_core import resources, style
from ayon_core.pipeline import get_current_folder_path, get_current_task_name
from ayon_core.pipeline.context_tools import change_current_context
from ayon_core.tools import context_dialog
from ayon_core.tools.utils import host_tools
from ayon_core.tools.utils.lib import qt_app_context
from ayon_unreal.api import hierarchy, rendering
from qtpy import QtCore, QtGui, QtWidgets


class ToolsBtnsWidget(QtWidgets.QWidget):
    """Widget containing buttons which are clickable."""

    tool_required = QtCore.Signal(str)

    def __init__(self, parent=None):
        super(ToolsBtnsWidget, self).__init__(parent)

        current_context_string = (
            f"Context: {get_current_task_name()} - {get_current_folder_path()}"
        )
        self.context_btn = QtWidgets.QPushButton(current_context_string, self)
        self.context_btn.setToolTip(
            "Open context dialog to set up current project, task and folder."
        )
        load_btn = QtWidgets.QPushButton("Load...", self)
        publish_btn = QtWidgets.QPushButton("Publish...", self)
        manage_btn = QtWidgets.QPushButton("Manage...", self)
        render_btn = QtWidgets.QPushButton("Render...", self)
        sequence_btn = QtWidgets.QPushButton("Build sequence hierarchy...", self)
        experimental_tools_btn = QtWidgets.QPushButton("Experimental tools...", self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.context_btn, 0)
        layout.addSpacing(4)
        layout.addWidget(load_btn, 0)
        layout.addWidget(manage_btn, 0)
        layout.addWidget(render_btn, 0)
        layout.addWidget(publish_btn, 0)
        layout.addWidget(sequence_btn, 0)
        layout.addWidget(experimental_tools_btn, 0)
        layout.addStretch(1)

        load_btn.clicked.connect(self._on_load)
        manage_btn.clicked.connect(self._on_manage)
        render_btn.clicked.connect(self._on_render)
        publish_btn.clicked.connect(self._on_publish)
        sequence_btn.clicked.connect(self._on_sequence)
        experimental_tools_btn.clicked.connect(self._on_experimental)
        self.context_btn.clicked.connect(self._on_context_change)

    def _on_create(self):
        self.tool_required.emit("creator")

    def _on_load(self):
        self.tool_required.emit("loader")

    def _on_publish(self):
        self.tool_required.emit("publisher")

    def _on_manage(self):
        self.tool_required.emit("sceneinventory")

    def _on_render(self):
        rendering.start_rendering()

    def _on_sequence(self):
        hierarchy.build_sequence_hierarchy()

    def _on_experimental(self):
        self.tool_required.emit("experimental_tools")

    def _on_context_change(self):
        """Open a context dialog to change the current context."""
        context = context_dialog.ask_for_context(strict=False)

        if context is None:
            return

        folder_entity = ayon_api.get_folder_by_id(
            context["project_name"], folder_id=context["folder_id"]
        )
        task_entity = ayon_api.get_task_by_id(
            context["project_name"], task_id=context["task_id"]
        )
        new_context = change_current_context(
            folder_entity=folder_entity,
            task_entity=task_entity,
        )

        unreal.log(f"Context changed to: {new_context}")
        self.context_btn.setText(
            f"Context: {new_context['task_name']} - " f"{new_context['folder_path']}"
        )


class ToolsDialog(QtWidgets.QDialog):
    """Dialog with tool buttons that will stay opened until user close it."""

    def __init__(self, *args, **kwargs):
        super(ToolsDialog, self).__init__(*args, **kwargs)

        self.setWindowTitle("Ayon tools")
        icon = QtGui.QIcon(resources.get_ayon_icon_filepath())
        self.setWindowIcon(icon)

        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)

        tools_widget = ToolsBtnsWidget(self)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(tools_widget)

        tools_widget.tool_required.connect(self._on_tool_require)
        self._tools_widget = tools_widget

        self._first_show = True

    def sizeHint(self):
        result = super(ToolsDialog, self).sizeHint()
        result.setWidth(result.width() * 2)
        return result

    def showEvent(self, event):
        super(ToolsDialog, self).showEvent(event)
        if self._first_show:
            self.setStyleSheet(style.load_stylesheet())
            self._first_show = False

    def _on_tool_require(self, tool_name):
        host_tools.show_tool_by_name(tool_name, parent=self)


class ToolsPopup(ToolsDialog):
    """Popup with tool buttons that will close when loose focus."""

    def __init__(self, *args, **kwargs):
        super(ToolsPopup, self).__init__(*args, **kwargs)

        self.setWindowFlags(QtCore.Qt.FramelessWindowHint | QtCore.Qt.Popup)

    def showEvent(self, event):
        super(ToolsPopup, self).showEvent(event)
        app = QtWidgets.QApplication.instance()
        app.processEvents()
        pos = QtGui.QCursor.pos()
        self.move(pos)


class WindowCache:
    """Cached objects and methods to be used in global scope."""

    _dialog = None
    _popup = None
    _first_show = True

    @classmethod
    def _before_show(cls):
        """Create QApplication if does not exists yet."""
        if not cls._first_show:
            return

        cls._first_show = False
        if not QtWidgets.QApplication.instance():
            QtWidgets.QApplication(sys.argv)

    @classmethod
    def show_popup(cls):
        cls._before_show()
        with qt_app_context():
            if cls._popup is None:
                cls._popup = ToolsPopup()

            cls._popup.show()

    @classmethod
    def show_dialog(cls):
        cls._before_show()
        with qt_app_context():
            if cls._dialog is None:
                cls._dialog = ToolsDialog()

            cls._dialog.show()
            cls._dialog.raise_()
            cls._dialog.activateWindow()


def show_tools_popup():
    WindowCache.show_popup()


def show_tools_dialog():
    WindowCache.show_dialog()
