import os
import shutil
import tempfile
from pathlib import Path

from ayon_openrv.constants import OPENRV_ROOT_DIR
from ayon_applications import PreLaunchHook
from ayon_core.lib.execute import run_subprocess


class PreReviewTool(PreLaunchHook):
    """Pre-hook for openrv"""
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
            prefix="ayon_openrv_support_path_"
        ))

        # Write the AYON RV package zips directly to the support path
        # Packages/ folder then we don't need to `rvpkg -add` them afterwards
        packages_dest_folder = ay_support_path / "Packages"
        packages_dest_folder.mkdir(exist_ok=True)
        packages = ["comments"]
        for package_name in packages:
            package_src = packages_src_folder / package_name
            package_dest = packages_dest_folder / "{}.zip".format(package_name)

            self.log.debug(f"Writing: {package_dest}")
            shutil.make_archive(str(package_dest), "zip", str(package_src))

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
