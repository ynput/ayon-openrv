"""Prepares server package from addon repo to upload to server.

Requires Python 3.9. (Or at least 3.8+).

This script should be called from cloned addon repo.

It will produce 'package' subdirectory which could be pasted into server
addon directory directly (eg. into `ayon-backend/addons`).

Format of package folder:
ADDON_REPO/package/{addon name}/{addon version}

You can specify `--output_dir` in arguments to change output directory where
package will be created. Existing package directory will always be purged if
already present! This could be used to create package directly in server folder
if available.

Package contains server side files directly,
client side code zipped in `private` subfolder.
"""

import os
import sys
import re
import shutil
import argparse
import platform
import logging
import collections
import zipfile
from typing import Optional, Iterable, Pattern, Union

import package

ADDON_NAME: str = package.name
ADDON_VERSION: str = package.version

# Name of folder where client code is located - e.g. 'ayon_maya'
# Picked from package.py. but it is optional (server only addons don't have it)
ADDON_CLIENT_DIR: Union[str, None] = None
if hasattr(package, "client_dir"):
    ADDON_CLIENT_DIR = package.client_dir
CLIENT_VERSION_CONTENT = '''# -*- coding: utf-8 -*-
"""Package declaring {} addon version."""
__version__ = "{}"
'''


# Patterns of directories to be skipped for server part of addon
IGNORE_DIR_PATTERNS: list[Pattern] = [
    re.compile(pattern)
    for pattern in [
        # Skip directories starting with '.'
        r"^\.",
        # Skip any pycache folders
        "^__pycache__$",
    ]
]

# Patterns of files to be skipped for server part of addon
IGNORE_FILE_PATTERNS: list[Pattern] = [
    re.compile(pattern)
    for pattern in {
        # Skip files starting with '.'
        # NOTE this could be an issue in some cases
        r"^\.",
        # Skip '.pyc' files
        r"\.pyc$",
    }
]


def calculate_file_checksum(filepath, hash_algorithm, chunk_size=10000):
    func = getattr(hashlib, hash_algorithm)
    hash_obj = func()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


class ZipFileLongPaths(zipfile.ZipFile):
    """Allows longer paths in zip files.

    Regular DOS paths are limited to MAX_PATH (260) characters, including
    the string's terminating NUL character.
    That limit can be exceeded by using an extended-length path that
    starts with the '\\?\' prefix.
    """

    _is_windows = platform.system().lower() == "windows"

    def _extract_member(self, member, tpath, pwd):
        if self._is_windows:
            tpath = os.path.abspath(tpath)
            if tpath.startswith("\\\\"):
                tpath = "\\\\?\\UNC\\" + tpath[2:]
            else:
                tpath = "\\\\?\\" + tpath

        return super(ZipFileLongPaths, self)._extract_member(
            member, tpath, pwd
        )


def safe_copy_file(src_path: str, dst_path: str):
    """Copy file and make sure destination directory exists.

    Ignore if destination already contains directories from source.

    Args:
        src_path (str): File path that will be copied.
        dst_path (str): Path to destination file.
    """

    if src_path == dst_path:
        return

    dst_dir: str = os.path.dirname(dst_path)
    try:
        os.makedirs(dst_dir)
    except Exception:
        pass

    shutil.copy2(src_path, dst_path)


def _value_match_regexes(value: str, regexes: Iterable[Pattern]) -> bool:
    return any(regex.search(value) for regex in regexes)


def find_files_in_subdir(
    src_path: str,
    ignore_file_patterns: Optional[list[Pattern]] = None,
    ignore_dir_patterns: Optional[list[Pattern]] = None,
) -> list[tuple[str, str]]:
    """Find all files to copy in subdirectories of given path.

    All files that match any of the patterns in 'ignore_file_patterns' will
        be skipped and any directories that match any of the patterns in
        'ignore_dir_patterns' will be skipped with all subfiles.

    Args:
        src_path (str): Path to directory to search in.
        ignore_file_patterns (Optional[list[Pattern]]): List of regexes
            to match files to ignore.
        ignore_dir_patterns (Optional[list[Pattern]]): List of regexes
            to match directories to ignore.

    Returns:
        list[tuple[str, str]]: List of tuples with path to file and parent
            directories relative to 'src_path'.
    """

    if ignore_file_patterns is None:
        ignore_file_patterns = IGNORE_FILE_PATTERNS

    if ignore_dir_patterns is None:
        ignore_dir_patterns = IGNORE_DIR_PATTERNS
    output: list[tuple[str, str]] = []

    hierarchy_queue: collections.deque = collections.deque()
    hierarchy_queue.append((src_path, []))
    while hierarchy_queue:
        item: tuple[str, str] = hierarchy_queue.popleft()
        dirpath, parents = item
        for name in os.listdir(dirpath):
            path: str = os.path.join(dirpath, name)
            if os.path.isfile(path):
                if not _value_match_regexes(name, ignore_file_patterns):
                    items: list[str] = list(parents)
                    items.append(name)
                    output.append((path, os.path.sep.join(items)))
                continue

            if not _value_match_regexes(name, ignore_dir_patterns):
                items: list[str] = list(parents)
                items.append(name)
                hierarchy_queue.append((path, items))

    return output


def copy_server_content(addon_output_dir, current_dir, log):
    """Copies server side folders to 'addon_package_dir'

    Args:
        addon_output_dir (str): Output directory path.
        current_dir (str): addon repo dir
        log (logging.Logger)
    """

    log.info("Copying server content")

    filepaths_to_copy: list[tuple[str, str]] = []
    server_dirpath: str = os.path.join(current_dir, "server")

    for name in os.listdir(server_dirpath):
        src_dir = os.path.join(server_dirpath, name)
        if not os.path.isdir(src_dir):
            filepaths_to_copy.append((src_dir, name))
            continue

        for item in find_files_in_subdir(src_dir):
            src_path, dst_subpath = item
            filepaths_to_copy.append((src_path, os.path.join(name, dst_subpath)))

    # Copy files
    for src_path, dst_path in filepaths_to_copy:
        safe_copy_file(src_path, os.path.join(addon_output_dir, "server", dst_path))


def _get_client_code_path(current_dir: str):
    return os.path.join(current_dir, "client", ADDON_CLIENT_DIR)


def _update_client_version(current_dir, log):
    """Make sure version.py in client code does contain correct version.

    The content of the file is defined by 'CLIENT_VERSION_CONTENT'. Is skipped
        if 'version.py' file does not exist.

    Args:
        current_dir (str): Directory path of addon source.
        log (logging.Logger): Logger object.
    """

    client_code_dir = _get_client_code_path(current_dir)
    version_file = os.path.join(client_code_dir, "version.py")

    with open(version_file, "w") as stream:
        stream.write(
            CLIENT_VERSION_CONTENT.format(ADDON_NAME, ADDON_VERSION)
        )
    log.info(f"Client 'version.py' updated to '{ADDON_VERSION}'")


def _get_client_zip_content(current_dir: str, log: logging.Logger):
    """

    Args:
        current_dir (str): Directory path of addon source.
        log (logging.Logger): Logger object.

    Returns:
        list[tuple[str, str]]: List of path mappings to copy. The destination
            path is relative to expected output directory.
    """


    log.info("Preparing client code zip")

    output: list[tuple[str, str]] = []

    # Add client code content to zip
    client_code_dir: str = _get_client_code_path(current_dir)
    for path, sub_path in find_files_in_subdir(client_code_dir):
        output.append((path, os.path.join(ADDON_CLIENT_DIR, sub_path)))
    return output


def zip_client_side(addon_package_dir, current_dir, log):
    """Copy and zip `client` content into 'addon_package_dir'.

    Args:
        addon_package_dir (str): Output package directory path.
        current_dir (str): Directory path of addon source.
        log (logging.Logger): Logger object.
    """

    if not ADDON_CLIENT_DIR:
        log.info("Client directory was not defined. Skipping")
        return

    client_code_dir: str = _get_client_code_path(current_dir)
    if not os.path.isdir(client_code_dir):
        raise RuntimeError(
            f"Client directory was not found '{client_code_dir}'."
        )

    log.info("Preparing client code zip")
    private_dir: str = os.path.join(addon_package_dir, "private")

    if not os.path.exists(private_dir):
        os.makedirs(private_dir)

    _update_client_version(current_dir, log)
    mapping = _get_client_zip_content(current_dir, log)

    zip_filepath: str = os.path.join(os.path.join(private_dir, "client.zip"))
    with ZipFileLongPaths(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Add client code content to zip
        for path, sub_path in mapping:
            zipf.write(path, sub_path)

    log.info("Client zip created")

    pyproject_path = os.path.join(current_dir, "client", "pyproject.toml")
    if os.path.exists(pyproject_path):
        shutil.copy(pyproject_path, private_dir)


def create_server_package(output_dir: str, addon_output_dir: str, log: logging.Logger):
    """Create server package zip file.

    The zip file can be installed to a server using UI or rest api endpoints.

    Args:
        output_dir (str): Directory path to output zip file.
        addon_output_dir (str): Directory path to addon output directory.
        log (logging.Logger): Logger object.
    """

    log.info("Creating server package")
    output_path = os.path.join(output_dir, f"{ADDON_NAME}-{ADDON_VERSION}.zip")

    with ZipFileLongPaths(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Move addon content to zip into 'addon' directory
        addon_output_dir_offset = len(addon_output_dir) + 1
        for root, _, filenames in os.walk(addon_output_dir):
            if not filenames:
                continue

            dst_root = None
            if root != addon_output_dir:
                dst_root = root[addon_output_dir_offset:]
            for filename in filenames:
                src_path = os.path.join(root, filename)
                dst_path = filename
                if dst_root:
                    dst_path = os.path.join(dst_root, dst_path)
                zipf.write(src_path, dst_path)

    log.info(f"Output package can be found: {output_path}")


def copy_client_code(current_dir: str, output_dir: str, log: logging.Logger):
    """Copy client code to output directory.

    Args:
        current_dir (str): Directory path of addon source.
        output_dir (str): Directory path to output client code.
        log (logging.Logger): Logger object.
    """

    client_code_dir: str = _get_client_code_path(current_dir)
    if not os.path.isdir(client_code_dir):
        raise RuntimeError(
            f"Client directory '{client_code_dir}' was not found."
        )

    full_output_dir = os.path.join(output_dir, ADDON_CLIENT_DIR)
    if os.path.exists(full_output_dir):
        shutil.rmtree(full_output_dir)

    if os.path.exists(full_output_dir):
        raise RuntimeError(f"Failed to remove target folder '{full_output_dir}'")

    os.makedirs(output_dir, exist_ok=True)
    _update_client_version(current_dir, log)
    mapping = _get_client_zip_content(current_dir, log)
    for src_path, dst_path in mapping:
        full_dst_path = os.path.join(output_dir, dst_path)
        os.makedirs(os.path.dirname(full_dst_path), exist_ok=True)
        shutil.copy2(src_path, full_dst_path)


def main(
    output_dir: Optional[str] = None,
    skip_zip: Optional[bool] = False,
    keep_sources: Optional[bool] = False,
    only_client: Optional[bool] = False,
):
    log: logging.Logger = logging.getLogger("create_package")
    log.info("Start creating package")

    current_dir: str = os.path.dirname(os.path.abspath(__file__))
    if not output_dir:
        output_dir = os.path.join(current_dir, "package")

    log.info("Creating client folder")
    if not output_dir:
        raise RuntimeError(
            "Output directory must be defined" " for client only preparation."
        )
    copy_client_code(current_dir, output_dir, log)
    log.info("Client folder created")
    if only_client:
        return

    addon_output_root: str = os.path.join(output_dir, ADDON_NAME)
    addon_output_dir: str = os.path.join(addon_output_root, ADDON_VERSION)
    if os.path.isdir(addon_output_dir):
        log.info(f"Purging {addon_output_dir}")
        shutil.rmtree(output_dir)

    log.info(f"Preparing package for {ADDON_NAME}-{ADDON_VERSION}")

    if not os.path.exists(addon_output_dir):
        os.makedirs(addon_output_dir)

    src_package_file = os.path.join(current_dir, "package.py")
    dst_package_file = os.path.join(addon_output_dir, "package.py")

    failed = True
    try:
        safe_copy_file(src_package_file, dst_package_file)
        copy_server_content(addon_output_dir, current_dir, log)
        zip_client_side(addon_output_dir, current_dir, log)
        failed = False
    finally:
        if failed and os.path.isdir(addon_output_dir):
            log.info("Purging output dir after failed package creation")
            shutil.rmtree(output_dir)

    # Skip server zipping
    if not skip_zip:
        create_server_package(output_dir, addon_output_dir, log)
        # Remove sources only if zip file is created
        if not keep_sources:
            log.info("Removing source files for server package")
            shutil.rmtree(addon_output_root)
    log.info("Package creation finished")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-zip",
        dest="skip_zip",
        action="store_true",
        help=(
            "Skip zipping server package and create only" " server folder structure."
        ),
    )
    parser.add_argument(
        "--keep-sources",
        dest="keep_sources",
        action="store_true",
        help=("Keep folder structure when server package is created."),
    )
    parser.add_argument(
        "-o",
        "--output",
        dest="output_dir",
        default=None,
        help=(
            "Directory path where package will be created"
            " (Will be purged if already exists!)"
        ),
    )
    parser.add_argument(
        "--only-client",
        dest="only_client",
        action="store_true",
        help=(
            "Extract only client code. This is useful for development."
            " Requires '-o', '--output' argument to be filled."
        ),
    )
    parser.add_argument(
        "--debug", dest="debug", action="store_true", help="Debug log messages."
    )

    args = parser.parse_args(sys.argv[1:])
    level = logging.INFO
    if args.debug:
        level = logging.DEBUG
    logging.basicConfig(level=level)
    main(args.output_dir, args.skip_zip, args.keep_sources, args.only_client)
