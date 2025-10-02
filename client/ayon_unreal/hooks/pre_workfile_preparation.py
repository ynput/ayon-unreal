# -*- coding: utf-8 -*-
"""Hook to launch Unreal and prepare projects."""
import logging
import os
import pathlib
import sys
import copy
import shutil
import tempfile
import platform
import json
from pathlib import Path

from qtpy import QtCore, QtWidgets

from ayon_core import resources
from ayon_applications import (
    PreLaunchHook,
    ApplicationLaunchFailed,
    LaunchTypes,
)
from ayon_core.pipeline.anatomy.anatomy import Anatomy
from ayon_core.pipeline.anatomy.templates import AnatomyStringTemplate
from ayon_core.pipeline.template_data import get_template_data
from ayon_core.settings import get_project_settings
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
    order = 0

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
        if not QtWidgets.QApplication.instance():
            QtWidgets.QApplication(sys.argv)
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
        if not QtWidgets.QApplication.instance():
            QtWidgets.QApplication(sys.argv)

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
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.log.handlers[0].setFormatter(formatter)
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

        from pprint import pformat
        # self.log.info(pformat(self.launch_context.data))
        current_project = self.launch_context.data['project_entity']['name']
        unreal_settings = get_project_settings(current_project).get("unreal")
        use_plugin = unreal_settings['project_setup']['use_plugin']

        self.log.info(f"Project Settings {pformat(unreal_settings)}")
        self.log.info(f"Project Name {current_project}")
        self.log.info(f"Use Plugin = {use_plugin}")

        if use_plugin:
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
                self.launch_context.env['AYON_PLUGIN_ENABLED'] = "1"
        else:
            self.launch_context.env['AYON_PLUGIN_ENABLED'] = "0"

        use_exact_path = unreal_settings['project_setup']['use_exact_path']

        if use_exact_path:
            project_template_str = unreal_settings['project_setup']['existing_uproject_directory']
            anatomy = Anatomy(current_project)
            project_template = AnatomyStringTemplate(anatomy.templates_obj, project_template_str)
            launch_context = self.launch_context.data
            template_data = get_template_data(
                project_entity=launch_context["project_entity"],
                folder_entity=launch_context["folder_entity"],
                task_entity=launch_context["task_entity"],
            )
            template_data.update({
                'root': anatomy.roots
            })

            self.log.debug(pformat(self.launch_context.data))
            project_file = pathlib.Path(project_template.format_strict(template_data))
            project_path = project_file.parent
            self.log.info(f"New Project File {project_file}")
            if not project_file.is_file():
                raise RuntimeError("Invalid Project Path")
        else:
            project_file = project_path / unreal_project_filename

        self.launch_context.env["AYON_UNREAL_VERSION"] = engine_version

        self.log.info(f"Project File {project_file}")
        if not project_file.is_file():

            # Get project settings -> allow project creation
            current_project = self.launch_context.data['project_entity']['name']
            unreal_settings = get_project_settings(current_project).get("unreal")
            allow_project_creation = unreal_settings["project_setup"].get(
            "allow_project_creation")
            # add the project template options
            # add the custom path for the existing project
            if allow_project_creation:
                existing_uproject_directory = Path(
                    unreal_settings["project_setup"].get(
                        "existing_uproject_directory")
                )
                self.log.info(existing_uproject_directory)
                uproject_files = list(existing_uproject_directory.glob("*.uproject"))
                if (
                    existing_uproject_directory.exists() and
                    uproject_files
                ):
                    self.copy_project(existing_uproject_directory, project_path)
                    # rename the project folder copied from existing_uproject directory
                    new_project_path = project_path.parent / unreal_project_name
                    project_path.rename(new_project_path)

                    # find the copied uproject file in the new project directory
                    copied_uproject_files = list(new_project_path.glob("*.uproject"))
                    if len(copied_uproject_files) != 1:
                        raise ApplicationLaunchFailed(
                            f"{self.signature} Expected exactly one .uproject file in "
                            f"{new_project_path}, but found {len(copied_uproject_files)}. "
                            "Please check the project directory."
                        )
                    copied_uproject_file = copied_uproject_files[0]
                    # set the correct engine version on the copied file
                    self.set_engine_version(copied_uproject_file, engine_version)

                    # rename the copied uproject file to match the expected filename
                    copied_uproject_file.rename(new_project_path / unreal_project_filename)
                    self.log.info((
                        f"{self.signature} Renamed {copied_uproject_file.name} to "
                        f"{unreal_project_filename}"
                    ))
                else:
                    with tempfile.TemporaryDirectory() as temp_dir:
                        self.exec_ue_project_gen(engine_version,
                                                 unreal_project_name,
                                                 engine_path,
                                                 Path(temp_dir))
                        self.copy_project(Path(temp_dir), project_path)

            # if the template path has been found with unreal project
            # copy that existing project to ayon work directory
            elif unreal_settings["project_setup"].get(
                    "force_existing_project"):
                msg = (
                    "Could not open project; Project file not found.\n\n"
                    f"'{project_path.as_posix()}' \n\n"
                    "Please contact administrator.\n"
                    "Make sure the project is in the correct folder. "
                    "Or enable 'allow project creation' in studio "
                    "settings."
                )
                raise ApplicationLaunchFailed(msg)
            else:
                return

        self.launch_context.env['AYON_UNREAL_PROJECT_PATH'] = project_path.as_posix()
        # Append the project file to launch arguments
        self.launch_context.launch_args.append(
            f"\"{project_file.as_posix()}\"")

    def set_engine_version(self, uproject_path: Path, new_version: str):
        """Set the engine version in a Unreal project file.

        Args:
            uproject_path (Path): The path to the .uproject file.
            new_version (str): The new engine version to set.

        Raises:
            FileNotFoundError: If the .uproject file does not exist.
        """
        if not uproject_path.is_file():
            raise FileNotFoundError(f"File not found: {uproject_path}")

        try:
            data = json.loads(uproject_path.read_text(encoding="utf-8"))

        except json.JSONDecodeError as e:
            raise ApplicationLaunchFailed(
                f"{self.signature} Malformed .uproject file at {uproject_path}: {e}"
            ) from e

        # Set the new engine version
        data["EngineAssociation"] = new_version

        uproject_path.write_text(json.dumps(data, indent=4), encoding="utf-8")

        self.log.info(
            f"Engine version set to '{new_version}' for {uproject_path}"
        )

    def copy_project(self, source: Path, destination: Path):
        """Copy an Unreal project directory.

        Args:
            source (Path): The source project directory.
            destination (Path): The destination directory.
        """
        try:
            self.log.info((
                f"Moving from {source.as_posix()} to "
                f"{destination.as_posix()}"
            ))
            shutil.copytree(
                source, destination, dirs_exist_ok=True)

        except shutil.Error as e:
            msg = (
                f"{self.signature} Cannot copy directory {source.as_posix()} "
                f"to {destination.as_posix()} - {e}"
            )
            raise ApplicationLaunchFailed(msg) from e
