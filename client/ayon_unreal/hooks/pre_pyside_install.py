"""Install PySide2 python module to unreal's python.

If unreal doesn't have PySide module installed, it will try to install
it.

Note:
    This needs to be changed in the future so the UI is decoupled from the
    host application.

"""
from __future__ import annotations

import os
import site
import contextlib
import subprocess
from pathlib import Path
from platform import system
from typing import Union
from ayon_applications import LaunchTypes, PreLaunchHook

python_versions = {7, 8, 9, 10, 11, 12, 13}
MAX_PYSIDE2_PYTHON_VERSION = 10


class InstallQtBinding(PreLaunchHook):
    """Install Qt binding to unreal's python packages."""

    app_groups = ("unreal")
    launch_types = (LaunchTypes.local)

    def execute(self) -> None:
        """Entry point for the hook."""
        try:
            self._execute()
        except Exception:  # noqa: BLE001
            self.log.warning(
                "Processing of %s crashed.",
                self.__class__.__name__, exc_info=True
            )

    @staticmethod
    def _find_python_executable(
            path_str: str) -> tuple[Union[Path, None], Union[int, None]]:
        """Find python executable in unreal's directory.

        Args:
            path_str (str): Python Directory.

        Returns:
            valid_path (Path): Path to python executable.

        """
        for version in python_versions:
            matching_python_dll_files = [
                dll_file for dll_file in os.listdir(path_str)
                if dll_file.endswith(f"{version}.dll")
            ]
            python_dir = Path(path_str)
            if python_dir.exists() and matching_python_dll_files:
                return python_dir, version
        return None, None

    def _execute(self) -> None:  # noqa: PLR0912, C901
        """Execute the hook.

        Todo:
            * This method is too complex (PLR0912). It should be refactored
              to smaller methods.

        """
        platform = system().lower()
        executable = self.launch_context.executable.executable_path
        expected_executable = "UnrealEditor"
        if platform == "windows":
            expected_executable += ".exe"

        if os.path.basename(executable) != expected_executable:
            self.log.info((
                f"Executable does not lead to {expected_executable} file."
                "Can't determine Unreal's python to check/install"
                " Qt binding."
            ))
            return
        versions_dir = self.find_parent_directory(executable)
        unreal_python_dir = None
        if platform == "windows":
            unreal_python_dir = os.path.join(versions_dir, "ThirdParty", "Python3", "Win64")
        elif platform == "darwin":
            unreal_python_dir = os.path.join(versions_dir, "ThirdParty", "Python3", "Mac", "bin", "python3")
        else:
            unreal_python_dir = os.path.join(versions_dir, "ThirdParty", "Python3", "Linux", "bin")
        python_dir, py_version = self._find_python_executable(unreal_python_dir)

        if not python_dir:
            self.log.warning(
                "Couldn't find python executable "
                "for unreal in %s", unreal_python_dir)
            return

        if platform == "windows":
            python_executable = Path(python_dir) / "python.exe"
        else:
            python_executable = Path(python_dir) / "python"
            # Check for python with enabled 'pymalloc'
            if not python_executable.exists():
                python_executable = Path(python_dir) / f"python3.{py_version}m"

        unreal_settings = self.data["project_settings"]["unreal"]
        prelaunch_settings = unreal_settings["prelaunch_settings"]
        python_executable = self.use_venv_for_installation(python_executable, prelaunch_settings, platform)
        if not python_executable.exists():
            self.log.warning(
                "Couldn't find python executable "
                "for unreal %s", python_executable.as_posix())

            return

        pyside_name = "PySide6"
        if py_version <= MAX_PYSIDE2_PYTHON_VERSION:
            pyside_name = "PySide2"

        # Check if PySide2 is installed and skip if yes
        if self.is_pyside_installed(python_executable, pyside_name):
            self.log.debug(
                "unreal has already installed %s.", pyside_name)
            return

        # Install PySide2/PySide6 in unreal's python
        if platform == "windows":
            result = self.install_pyside_windows(
                python_executable, pyside_name, prelaunch_settings)
        else:
            result = self.install_pyside(
                python_executable, pyside_name, prelaunch_settings)

        if result:
            self.log.info(
                "Successfully installed %s module to unreal.", pyside_name)
        else:
            self.log.warning(
                "Failed to install %s module to unreal.", pyside_name)

    def install_pyside_windows(
            self, python_executable: Path, pyside_name: str, settings: dict) -> Union[None, int]:
        """Install PySide2 python module to unreal's python.

        Installation requires administration rights that's why it is required
        to use "pywin32" module which can execute command's and ask for
        administration rights.

        Note:
            This is asking for administrative right always, no matter if
            it is actually needed or not. Unfortunately getting
            correct permissions for directory on Windows isn't that trivial.
            You can either use `win32security` module or run `icacls` command
            in subprocess and parse its output.

        """
        args = [
            "-m",
            "pip",
            "install",
            "--ignore-installed",
            pyside_name
        ]
        if not settings["use_venv"] or not settings["venv_name"]:
            site_package_path = os.path.join(os.path.dirname(python_executable), "Lib")
            args += ["--target", f"{site_package_path}"]

        args = self.use_dependency_path(args, settings)
        parameters = (
            subprocess.list2cmdline(args)
            .lstrip(" ")
        )
        return_code = self.pip_install_for_window(python_executable, parameters)

        return return_code

    def install_pyside(
            self, python_executable: Path, pyside_name: str, settings: dict) -> int:
        """Install PySide2 python module to unreal's python."""
        args = [
            python_executable.as_posix(),
            "-m",
            "pip",
            "install",
            "--ignore-installed",
            pyside_name
        ]
        args = self.use_dependency_path(args, settings)
        return_code = self.pip_install(args)
        return return_code

    @staticmethod
    def is_pyside_installed(python_executable: Path, pyside_name: str) -> bool:
        """Check if PySide2/6 module is in unreal python env.

        Args:
            python_executable (Path): Path to python executable.
            pyside_name (str): Name of pyside (to distinguish between PySide2
                and PySide6).

        Returns:
            bool: True if PySide2 is installed, False otherwise.

        """
        # Get pip list from unreal's python executable
        args = [python_executable.as_posix(), "-m", "pip", "list"]
        process = subprocess.Popen(args, stdout=subprocess.PIPE)
        stdout, _ = process.communicate()
        lines = stdout.decode().split(os.linesep)
        # Second line contain dashes that define maximum length of module name.
        #   Second column of dashes define maximum length of module version.
        package_dashes, *_ = lines[1].split(" ")
        package_len = len(package_dashes)

        # Got through printed lines starting at line 3
        for idx in range(2, len(lines)):
            line = lines[idx]
            if not line:
                continue
            package_name = line[:package_len].strip()
            if package_name.lower() == pyside_name.lower():
                return True
        return False

    def find_parent_directory(self, file_path: str, target_dir="Binaries") -> str:
        # Split the path into components
        path_components = file_path.split(os.sep)

        # Traverse the path components to find the target directory
        for i in range(len(path_components) - 1, -1, -1):
            if path_components[i] == target_dir:
                # Join the components to form the target directory path
                return os.sep.join(path_components[:i + 1])
        return None

    def use_dependency_path(self, commands: list, settings: dict) -> list:
        if settings.get("use_dependency"):
            dependency_path = settings.get("dependency_path")
            if dependency_path:
                commands.extend(
                    [
                        "--no-index",
                        f"--find-links={dependency_path}"
                    ]
                )
            else:
                self.log.warning(
                    "Skipping to install Pyside with dependency."
                    " No dependency path filled in the setting")

        return commands

    def use_venv_for_installation(self, python_executable: Path,
                                  settings: dict, platform: str) -> Path:
        """Get python executable from virtual environment.

        Args:
            python_executable (Path): python_executable
            settings (dict): unreal settings
            platform (str): system platform

        Returns:
            Path: path for python executable
        """
        if not settings.get("use_venv"):
            return python_executable

        venv_name = settings.get("venv_name")
        if not venv_name:
            return python_executable
        venv_dir = Path(os.getenv("AYON_LAUNCHER_LOCAL_DIR")) / venv_name
        args = [python_executable.as_posix(), '-m', 'venv', venv_dir]
        _ = self.pip_install(args)

        if platform == "windows":
            venv_python = os.path.join(venv_dir, "Scripts", "python.exe")
        else:
            venv_python = os.path.join(venv_dir, "bin", "python")

        args = [
            venv_python, "-c",
            (
                "import site;print(next((path for path "
                "in site.getsitepackages() "
                'if path.endswith("site-packages")), None))')
        ]
        process = subprocess.Popen(
            args, stdout=subprocess.PIPE, universal_newlines=True
        )
        stdout, _ = process.communicate()
        venv_sitepackages = stdout.strip()
        if venv_sitepackages:
            site.addsitedir(venv_sitepackages)

        ue_pythonpath = self.launch_context.env.get("UE_PYTHONPATH")
        if ue_pythonpath:
            ue_pythonpath = os.pathsep.join(
                [ue_pythonpath, venv_sitepackages])
        else:
            ue_pythonpath = venv_sitepackages

        self.launch_context.env["UE_PYTHONPATH"] = ue_pythonpath

        return Path(venv_python)

    def pip_install_for_window(self, python_executable: Path, parameters: list):
        try:
            import pywintypes
            import win32con
            import win32event
            import win32process
            from win32comext.shell import shellcon
            from win32comext.shell.shell import ShellExecuteEx
        except Exception:  # noqa: BLE001
            self.log.warning(
                "Couldn't import 'pywin32' modules", exc_info=True)
            return None
        with contextlib.suppress(pywintypes.error):
            # Parameters
            # - use "-m pip" as module pip to install PySide2 and argument
            #   "--ignore-installed" is to force install module to unreal's
            #   site-packages and make sure it is binary compatible
            # Execute command and ask for administrator's rights
            process_info = ShellExecuteEx(
                nShow=win32con.SW_SHOWNORMAL,
                fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
                lpVerb="runas",
                lpFile=python_executable.as_posix(),
                lpParameters=parameters,
                lpDirectory=python_executable.parent.as_posix()
            )
            process_handle = process_info["hProcess"]
            win32event.WaitForSingleObject(
                process_handle, win32event.INFINITE)
            return_code = win32process.GetExitCodeProcess(process_handle)
            return return_code == 0

    def pip_install(self, args: list):
        try:
            # Parameters
            # - use "-m pip" as module pip to install PySide2/6 and argument
            #   "--ignore-installed" is to force install module to unreal
            #   site-packages and make sure it is binary compatible

            process = subprocess.Popen(
                args, stdout=subprocess.PIPE, universal_newlines=True
            )
            process.communicate()

        except PermissionError:
            self.log.warning(
                'Permission denied with command: "%s".', " ".join(args),
                exc_info=True)
        except OSError as error:
            self.log.warning(
                'OS error has occurred: "%s".', error, exc_info=True)
        except subprocess.SubprocessError:
            pass
        else:
            return process.returncode == 0
