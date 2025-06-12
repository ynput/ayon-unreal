import os
import subprocess
from platform import system
from ayon_applications import PreLaunchHook, LaunchTypes


class InstallOtioToUnreal(PreLaunchHook):
    """Install Qt binding to Unreal's python packages.

    Prelaunch hook does 2 things:
    1.) Unreal's python packages are pushed to the beginning of PYTHONPATH.
    2.) Check if Unreal has installed otio and will try to install if not.

    For pipeline implementation is required to have Qt binding installed in
    Unreal's python packages.
    """

    app_groups = {"unreal"}
    launch_types = {LaunchTypes.local}

    def execute(self):
        # Prelaunch hook is not crucial
        try:
            self.inner_execute()
        except Exception:
            self.log.warning(
                "Processing of {} crashed.".format(self.__class__.__name__),
                exc_info=True
            )

    def inner_execute(self):
        platform = system().lower()
        executable = self.launch_context.executable.executable_path
        expected_executable = "UnrealEditor"
        if platform == "windows":
            expected_executable += ".exe"

        if os.path.basename(executable) != expected_executable:
            self.log.info((
                f"Executable does not lead to {expected_executable} file."
                "Can't determine Unreal's python to check/install"
                " otio binding."
            ))
            return

        versions_dir = self.find_parent_directory(executable)
        otio_binding = "opentimelineio"
        otio_binding_version = None

        python_dir = os.path.join(versions_dir, "ThirdParty", "Python3", "Win64")
        python_version = "python"

        if platform == "windows":
            python_executable = os.path.join(python_dir, "python.exe")
        else:
            python_executable = os.path.join(python_dir, python_version)
            # Check for python with enabled 'pymalloc'
            if not os.path.exists(python_executable):
                python_executable += "m"

        if not os.path.exists(python_executable):
            self.log.warning(
                "Couldn't find python executable for Unreal. {}".format(
                    executable
                )
            )
            return

        # Check if otio is installed and skip if yes
        if self.is_otio_installed(python_executable, otio_binding):
            self.log.debug("Unreal has already installed otio.")
            return

        # Install otio in Unreal's python
        if platform == "windows":
            result = self.install_otio_windows(
                python_executable,
                otio_binding,
                otio_binding_version
            )
        else:
            result = self.install_otio(
                python_executable,
                otio_binding,
                otio_binding_version
            )

        if result:
            self.log.info(
                f"Successfully installed {otio_binding} module to Unreal."
            )
        else:
            self.log.warning(
                f"Failed to install {otio_binding} module to Unreal."
            )

    def install_otio_windows(
        self,
        python_executable,
        otio_binding,
        otio_binding_version
    ):
        """Install otio python module to Unreal's python.

        Installation requires administration rights that's why it is required
        to use "pywin32" module which can execute command's and ask for
        administration rights.
        """
        try:
            import win32con
            import win32process
            import win32event
            import pywintypes
            from win32comext.shell.shell import ShellExecuteEx
            from win32comext.shell import shellcon
        except Exception:
            self.log.warning("Couldn't import \"pywin32\" modules")
            return


        otio_binding = f"{otio_binding}==0.16.0"

        try:
            # Parameters
            # - use "-m pip" as module pip to install otio and argument
            #   "--ignore-installed" is to force install module to Unreal's
            #   site-packages and make sure it is binary compatible
            fake_exe = "fake.exe"
            args = [
                fake_exe,
                "-m",
                "pip",
                "install",
                "--ignore-installed",
                otio_binding,
            ]

            parameters = (
                subprocess.list2cmdline(args)
                .lstrip(fake_exe)
                .lstrip(" ")
            )

            # Execute command and ask for administrator's rights
            process_info = ShellExecuteEx(
                nShow=win32con.SW_SHOWNORMAL,
                fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
                lpVerb="runas",
                lpFile=python_executable,
                lpParameters=parameters,
                lpDirectory=os.path.dirname(python_executable)
            )
            process_handle = process_info["hProcess"]
            win32event.WaitForSingleObject(process_handle, win32event.INFINITE)
            returncode = win32process.GetExitCodeProcess(process_handle)
            return returncode == 0
        except pywintypes.error:
            pass

    def install_otio(
        self,
        python_executable,
        otio_binding,
        otio_binding_version,
    ):
        """Install Qt binding python module to Unreal's python."""
        if otio_binding_version:
            otio_binding = f"{otio_binding}=={otio_binding_version}"
        try:
            # Parameters
            # - use "-m pip" as module pip to install qt binding and argument
            #   "--ignore-installed" is to force install module to Unreal's
            #   site-packages and make sure it is binary compatible
            # TODO find out if Unreal 4.x on linux/darwin does install
            #   qt binding to correct place.
            args = [
                python_executable,
                "-m",
                "pip",
                "install",
                "--ignore-installed",
                otio_binding,
            ]
            process = subprocess.Popen(
                args, stdout=subprocess.PIPE, universal_newlines=True
            )
            process.communicate()
            return process.returncode == 0
        except PermissionError:
            self.log.warning(
                "Permission denied with command:"
                "\"{}\".".format(" ".join(args))
            )
        except OSError as error:
            self.log.warning(f"OS error has occurred: \"{error}\".")
        except subprocess.SubprocessError:
            pass

    def is_otio_installed(self, python_executable, otio_binding):
        """Check if OTIO module is in Unreal's pip list.

        Check that otio is installed directly in Unreal's site-packages.
        It is possible that it is installed in user's site-packages but that
        may be incompatible with Unreal's python.
        """

        otio_binding_low = otio_binding.lower()
        # Get pip list from Unreal's python executable
        args = [python_executable, "-m", "pip", "list"]
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
            package_name = line[0:package_len].strip()
            if package_name.lower() == otio_binding_low:
                return True
        return False

    def find_parent_directory(self, file_path, target_dir="Binaries"):
        # Split the path into components
        path_components = file_path.split(os.sep)

        # Traverse the path components to find the target directory
        for i in range(len(path_components) - 1, -1, -1):
            if path_components[i] == target_dir:
                # Join the components to form the target directory path
                return os.sep.join(path_components[:i + 1])
        return None
