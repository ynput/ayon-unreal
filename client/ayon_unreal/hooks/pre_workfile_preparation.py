# -*- coding: utf-8 -*-
"""Hook to launch Unreal and prepare projects."""
import os
import copy
import shutil
import tempfile
import platform
from pathlib import Path

from qtpy import QtCore

from ayon_core import resources
from ayon_applications import (
    PreLaunchHook,
    ApplicationLaunchFailed,
    LaunchTypes,
)
from ayon_core.settings import get_project_settings
from ayon_core.pipeline import get_current_project_name
from ayon_core.pipeline.workfile import get_workfile_template_key
import ayon_unreal.lib as unreal_lib
from ayon_unreal.ue_workers import (
    UEProjectGenerationWorker,
    UEPluginInstallWorker
)
from ayon_unreal.ui import SplashScreen


class UnrealPrelaunchHook(PreLaunchHook):
    """Hook to handle launching Unreal.

    This hook will check if current workfile path has Unreal
    project inside. IF not, it initializes it, and finally it pass
    path to the project by environment variable to Unreal launcher
    shell script.

    """
    app_groups = {"unreal"}
    launch_types = {LaunchTypes.local}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.signature = f"( {self.__class__.__name__} )"

    def _get_work_filename(self):
        # Use last workfile if was found
        if self.data.get("last_workfile_path"):
            last_workfile = Path(self.data.get("last_workfile_path"))
            if last_workfile and last_workfile.exists():
                return last_workfile.name

        # Prepare data for fill data and for getting workfile template key
        anatomy = self.data["anatomy"]
        project_entity = self.data["project_entity"]

        # Use already prepared workdir data
        workdir_data = copy.deepcopy(self.data["workdir_data"])
        task_type = workdir_data.get("task", {}).get("type")

        # QUESTION raise exception if version is part of filename template?
        workdir_data["version"] = 1
        workdir_data["ext"] = "uproject"

        # Get workfile template key for current context
        workfile_template_key = get_workfile_template_key(
            project_entity["name"],
            task_type,
            self.host_name,
        )
        # Fill templates
        template_obj = anatomy.get_template_item(
            "work", workfile_template_key, "file"
        )

        # Return filename
        return template_obj.format_strict(workdir_data)

    def exec_plugin_install(self, engine_path: Path, env: dict = None):
        # set up the QThread and worker with necessary signals
        env = env or os.environ
        q_thread = QtCore.QThread()
        ue_plugin_worker = UEPluginInstallWorker()

        q_thread.started.connect(ue_plugin_worker.run)
        ue_plugin_worker.setup(engine_path, env)
        ue_plugin_worker.moveToThread(q_thread)

        splash_screen = SplashScreen(
            "Installing plugin",
            resources.get_resource("app_icons", "ue4.png")
        )

        # set up the splash screen with necessary triggers
        ue_plugin_worker.installing.connect(
            splash_screen.update_top_label_text
        )
        ue_plugin_worker.progress.connect(splash_screen.update_progress)
        ue_plugin_worker.log.connect(splash_screen.append_log)
        ue_plugin_worker.finished.connect(splash_screen.quit_and_close)
        ue_plugin_worker.failed.connect(splash_screen.fail)

        splash_screen.start_thread(q_thread)
        splash_screen.show_ui()

        if not splash_screen.was_proc_successful():
            raise ApplicationLaunchFailed("Couldn't run the application! "
                                          "Plugin failed to install!")

    def exec_ue_project_gen(self,
                            engine_version: str,
                            unreal_project_name: str,
                            engine_path: Path,
                            project_dir: Path):
        self.log.info((
            f"{self.signature} Creating unreal "
            f"project [ {unreal_project_name} ]"
        ))

        q_thread = QtCore.QThread()
        ue_project_worker = UEProjectGenerationWorker()
        ue_project_worker.setup(
            engine_version,
            self.data["project_name"],
            unreal_project_name,
            engine_path,
            project_dir
        )
        ue_project_worker.moveToThread(q_thread)
        q_thread.started.connect(ue_project_worker.run)

        splash_screen = SplashScreen(
            "Initializing UE project",
            resources.get_resource("app_icons", "ue4.png")
        )

        ue_project_worker.stage_begin.connect(
            splash_screen.update_top_label_text
        )
        ue_project_worker.progress.connect(splash_screen.update_progress)
        ue_project_worker.log.connect(splash_screen.append_log)
        ue_project_worker.finished.connect(splash_screen.quit_and_close)
        ue_project_worker.failed.connect(splash_screen.fail)

        splash_screen.start_thread(q_thread)
        splash_screen.show_ui()

        if not splash_screen.was_proc_successful():
            raise ApplicationLaunchFailed("Couldn't run the application! "
                                          "Failed to generate the project!")

    def execute(self):
        """Hook entry method."""
        workdir = self.launch_context.env["AYON_WORKDIR"]
        executable = str(self.launch_context.executable)
        engine_version = self.app_name.split("/")[-1].replace("-", ".")
        try:
            if int(engine_version.split(".")[0]) < 4 and \
                    int(engine_version.split(".")[1]) < 26:
                raise ApplicationLaunchFailed((
                    f"{self.signature} Old unsupported version of UE "
                    f"detected - {engine_version}"))
        except ValueError:
            # there can be string in minor version and in that case
            # int cast is failing. This probably happens only with
            # early access versions and is of no concert for this check
            # so let's keep it quiet.
            ...

        unreal_project_filename = self._get_work_filename()
        unreal_project_name = os.path.splitext(unreal_project_filename)[0]
        # Unreal is sensitive about project names longer then 20 chars
        if len(unreal_project_name) > 20:
            raise ApplicationLaunchFailed(
                f"Project name exceeds 20 characters ({unreal_project_name})!"
            )

        # Unreal doesn't accept non alphabet characters at the start
        # of the project name. This is because project name is then used
        # in various places inside c++ code and there variable names cannot
        # start with non-alpha. We append 'P' before project name to solve it.
        # 😱
        if not unreal_project_name[:1].isalpha():
            self.log.warning((
                "Project name doesn't start with alphabet "
                f"character ({unreal_project_name}). Appending 'P'"
            ))
            unreal_project_name = f"P{unreal_project_name}"
            unreal_project_filename = f'{unreal_project_name}.uproject'

        last_workfile_path = self.data.get("last_workfile_path")
        if last_workfile_path and os.path.exists(last_workfile_path):
            project_path = Path(os.path.dirname(last_workfile_path))
            unreal_project_filename = Path(os.path.basename(last_workfile_path))
        else:
            project_path = Path(os.path.join(workdir, unreal_project_name))
            project_path.mkdir(parents=True, exist_ok=True)

        self.log.info((
            f"{self.signature} requested UE version: "
            f"[ {engine_version} ]"
        ))

        # engine_path points to the specific Unreal Engine root
        # so, we are going up from the executable itself 3 levels.
        # on macOS it's 6 levels up as the executable lives under
        # ./UnrealEditor.app/Contents/MacOS/UnrealEditor
        if platform.system().lower() == "darwin":
            engine_path: Path = Path(executable).parents[6]
        else:
            engine_path: Path = Path(executable).parents[3]

        # Check if new env variable exists, and if it does, if the path
        # actually contains the plugin. If not, install it.

        built_plugin_path = self.launch_context.env.get(
            "AYON_BUILT_UNREAL_PLUGIN", None)

        if unreal_lib.check_built_plugin_existance(built_plugin_path):
            self.log.info((
                f"{self.signature} using existing built Ayon plugin from "
                f"{built_plugin_path}"
            ))
            unreal_lib.copy_built_plugin(engine_path, Path(built_plugin_path))
        else:
            # Set "AYON_UNREAL_PLUGIN" to current process environment for
            # execution of `create_unreal_project`
            env_key = "AYON_UNREAL_PLUGIN"
            if self.launch_context.env.get(env_key):
                self.log.info((
                    f"{self.signature} using Ayon plugin from "
                    f"{self.launch_context.env.get(env_key)}"
                ))
            if self.launch_context.env.get(env_key):
                os.environ[env_key] = self.launch_context.env[env_key]

            if not unreal_lib.check_plugin_existence(engine_path):
                self.exec_plugin_install(engine_path)

        project_file = project_path / unreal_project_filename

        if not project_file.is_file():

            #Get project settings -> allow project creation
            current_project = get_current_project_name()
            unreal_settings = get_project_settings(current_project).get("unreal")
            allow_project_creation = unreal_settings["project_setup"].get(
            "allow_project_creation")
            if allow_project_creation:
                with tempfile.TemporaryDirectory() as temp_dir:
                    self.exec_ue_project_gen(engine_version,
                                             unreal_project_name,
                                             engine_path,
                                             Path(temp_dir))
                    try:
                        self.log.info((
                            f"Moving from {temp_dir} to "
                            f"{project_path.as_posix()}"
                        ))
                        shutil.copytree(
                            temp_dir, project_path, dirs_exist_ok=True)

                    except shutil.Error as e:
                        raise ApplicationLaunchFailed((
                            f"{self.signature} Cannot copy directory {temp_dir} "
                            f"to {project_path.as_posix()} - {e}"
                        )) from e
            else:
                raise ApplicationLaunchFailed(
                    f"Could not open project; Project file not found.\n\n"
                    f"'{project_path.as_posix()}' \n\n"
                    f"Please contact administrator.\n"
                    f"Make sure the project is in the correct folder. Or enable 'allow project creation' in studio settings"
                )

        self.launch_context.env["AYON_UNREAL_VERSION"] = engine_version
        # Append project file to launch arguments
        self.launch_context.launch_args.append(
            f"\"{project_file.as_posix()}\"")
