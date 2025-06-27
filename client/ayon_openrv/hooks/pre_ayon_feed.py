from logging import Logger
import os
import shutil
import tempfile
from pathlib import Path
import platform
import subprocess

from ayon_openrv.constants import OPENRV_ROOT_DIR
from ayon_applications import PreLaunchHook
from ayon_core.lib.execute import run_subprocess
from ayon_core.lib import is_dev_mode_enabled


FRONTEND_CLIENT_SUBFOLDERS = [
    ("AYON_FEED", "client/ayon_openrv/startup/pkgs_source/ayon_feed"),
]

class PreAYONFeed(PreLaunchHook):
    """Pre-hook for openrv AYON Feed panel"""
    app_groups = ["openrv"]

    def execute(self):
        executable = self.launch_context.executable

        # We use the `rvpkg` executable next to the `rv` executable to
        # install and opt-in to the AYON plug-in packages
        rvpkg = Path(os.path.dirname(str(executable))) / "rvpkg"
        packages_src_folder = Path(OPENRV_ROOT_DIR) / "startup" / "pkgs_source"

        # TODO: Are we sure we want to deploy the addons into a temporary
        #   RV_SUPPORT_PATH on each launch. This would create redundant temp
        #   files that remain on disk but it does allow us to ensure RV is
        #   now running with the correct version of the RV packages of this
        #   current running AYON version
        ay_support_path = Path(tempfile.mkdtemp(
            prefix="ayon_openrv_ayon_feed_"
        ))

        # Write the AYON RV package zips directly to the support path
        # Packages/ folder then we don't need to `rvpkg -add` them afterwards
        packages_dest_folder = ay_support_path / "Packages"
        packages_dest_folder.mkdir(exist_ok=True)
        packages = ["ayon_feed"]
        for package_name in packages:
            package_src = packages_src_folder / package_name
            package_dest = packages_dest_folder / package_name

            self.log.debug(f"Writing: {package_dest}")
            package_res_zip_path = None
            if is_dev_mode_enabled():
                # only generating path and adding it into env var
                addon_repo_root = Path(
                    __file__).resolve().parent.parent.parent.parent
                fe_root = addon_repo_root / "frontend"
                for subpath_pair in FRONTEND_CLIENT_SUBFOLDERS:
                    if package_name not in subpath_pair[1]:
                        continue
                    fe_subpath_root_path = fe_root / subpath_pair[1]
                    fe_build_path = fe_subpath_root_path / "build"
                    env_key = subpath_pair[0] + "_OPENRV_FRONTEND"
                    self.launch_context.env[env_key] = fe_build_path
                    self.log.debug(f"Setting {env_key}: {fe_build_path}")
            else:
                shutil.make_archive(str(package_dest), "zip", str(package_src))
                # remove package_name
                if (
                    package_res_zip_path
                    and package_res_zip_path.with_suffix(".zip").exists()
                ):
                    # remove the zip file
                    package_res_zip_path.with_suffix(".zip").unlink()

        # Install and opt-in the AYON RV packages
        install_args = [rvpkg, "-only", ay_support_path, "-install", "-force"]
        install_args.extend(packages)
        optin_args = [rvpkg, "-only", ay_support_path, "-optin", "-force"]
        optin_args.extend(packages)
        run_subprocess(install_args, logger=self.log)
        run_subprocess(optin_args, logger=self.log)

        self.log.debug(f"Adding RV_SUPPORT_PATH: {ay_support_path}")
        support_path = self.launch_context.env.get("RV_SUPPORT_PATH")
        if support_path:
            support_path = os.pathsep.join([support_path,
                                            str(ay_support_path)])
        else:
            support_path = str(ay_support_path)
        self.log.debug(f"Setting RV_SUPPORT_PATH: {support_path}")
        self.launch_context.env["RV_SUPPORT_PATH"] = support_path


def _get_yarn_executable():
    cmd = "which"
    if platform.system().lower() == "windows":
        cmd = "where"

    for line in subprocess.check_output(
        [cmd, "yarn"], encoding="utf-8"
    ).splitlines():
        if not line or not Path(line).exists():
            continue
        try:
            subprocess.call([line, "--version"])
            return line
        except OSError:
            continue
    return None
