"""Loader for image sequences and single frames in OpenRV."""

from __future__ import annotations

import os
from typing import ClassVar

from ayon_api import get_representations
from ayon_core.lib.transcoding import IMAGE_EXTENSIONS, VIDEO_EXTENSIONS
from ayon_core.pipeline import (
    get_current_project_name,
    get_representation_path,
    load,
)
from ayon_openrv.api.ocio import (
    set_group_ocio_active_state,
    set_group_ocio_colorspace,
)
from ayon_openrv.api.pipeline import imprint, imprint_container

import rv
import rv.extra_commands


class BaseMediaLoader(load.LoaderPlugin):
    """Base class for the media loaders."""
    skip_discovery = True  # mark as base class

    product_base_types: ClassVar[set] = {"*"}
    product_types = product_base_types
    representations: ClassVar[set] = {"*"}

    order = 0

    def load(
        self,
        context: dict,
        name: str | None = None,
        namespace: str | None = None,
        options: dict | None = None,
    ) -> None:
        """Load frames or video into OpenRV."""
        filepath = self.filepath_from_context(context)

        rep_name = os.path.basename(filepath)

        # change path
        namespace = namespace or context["folder"]["name"]
        loaded_node = rv.commands.addSourceVerbose([filepath])

        node = self._finalize_loaded_node(
            loaded_node,
            rep_name,
            filepath,
            context
        )

        # add the other media representations of the same version to the
        # switch group so the user can switch e.g. between exr and mov
        self._add_sibling_representations(node, context)

        # update colorspace
        self.set_representation_colorspace(node, context["representation"])

        imprint_container(
            node,
            name=name,
            namespace=namespace,
            context=context,
            loader=self.__class__.__name__,
        )

        rv.commands.sendInternalEvent(
            "ayon-source-loaded", str(node), self.__class__.__name__
        )
    def _add_sibling_representations(self, node, context):
        """Add other media representations of the same version to the
        switch group so the user can switch e.g. between exr and mov
        for faster playback."""
        project_name = get_current_project_name()
        version_id = context["version"]["id"]
        current_repre_id = context["representation"]["id"]

        media_extensions = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
        for repre in get_representations(
            project_name, version_ids={version_id}
        ):
            if repre["id"] == current_repre_id:
                continue
            ext = (
                repre.get("data", {}).get("context", {}).get("ext")
                or repre["name"]
            )
            if f".{ext}".lower() not in media_extensions:
                continue
            try:
                filepath = get_representation_path(repre)
            except Exception as exc:
                self.log.warning(
                    f"Skipping representation {repre['name']}: {exc}"
                )
                continue
            rep_name = os.path.basename(filepath)
            self.log.info(f"Adding sibling representation: {rep_name}")
            self._add_source_media_rep(node, rep_name, filepath)

    def _finalize_loaded_node(self, loaded_node, rep_name, filepath, context):
        """Finalize the loaded node in OpenRV.

        We are organizing all loaded sources under a switch group so we can
        let user switch between versions later on. Every new updated version is
        added as new media representation under the switch group.

        We are removing firstly added source since it does not have a name.

        Args:
            loaded_node (str): The node that was loaded.
            rep_name (str): The name of the representation.
            filepath (str): The path of the representation.
            context (dict[str, dict[str, Any]]): The context of the loaded
                representation.

        Returns:
            str: The node that was loaded.

        """
        node = loaded_node

        self._add_source_media_rep(node, rep_name, filepath)

        rv.commands.setActiveSourceMediaRep(
            loaded_node,
            rep_name,
        )
        switch_node = rv.commands.sourceMediaRepSwitchNode(loaded_node)

        for (
            source_node_name,
            source_node,
        ) in rv.commands.sourceMediaRepsAndNodes(switch_node):
            node_type = rv.commands.nodeType(source_node)
            node_group = rv.commands.nodeGroup(source_node)

            # We are removing the first added source since it does not have
            # a name, and we don't want to confuse the user with multiple
            # versions of the same source but one of them without a name
            if node_type == "RVFileSource" and source_node_name == "":
                rv.commands.deleteNode(node_group)
            else:
                node = source_node
                break

        # Rename the switch node and group as well for better debugging
        folder = context["folder"]
        product = context["product"]
        label = f"{folder['path']} > {product['name']}"
        rv.extra_commands.setUIName(
            switch_node,
            f"{label} Switch"
        )
        rv.extra_commands.setUIName(
            rv.commands.nodeGroup(switch_node),
            f"{label} Switch Group"
        )

        rv.commands.reload()
        return node

    def _add_source_media_rep(self, node, rep_name, filepath):
        """Add source media representation to the node.

        Returns:
            str: The added source node.
        """
        # Add source to the media rep to add it to the `switch node`
        added_source = rv.commands.addSourceMediaRep(
            node,
            rep_name,
            [filepath],
        )

        # Avoid long names on the added source media rep
        rv.extra_commands.setUIName(
            rv.commands.nodeGroup(added_source),
            rep_name
        )
        return added_source

    def _add_sibling_representations(self, node, context):
        """Add other media representations of the same version to the
        switch group so the user can switch between them (e.g. exr for
        full quality and mov for faster playback).

        Sibling nodes get the primary representation id imprinted so
        tools tracking the active representation (e.g. review-desktop)
        keep a stable context while switching reps.

        Args:
            node (str): The primary loaded source node.
            context (dict[str, dict[str, Any]]): The context of the loaded
                representation.
        """
        project_name = get_current_project_name()
        version_id = context["version"]["id"]
        primary_repre_id = context["representation"]["id"]

        media_extensions = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
        for repre in get_representations(
            project_name, version_ids={version_id}
        ):
            if repre["id"] == primary_repre_id or repre["data"].get("context", {}).get("representation") == "thumbnail":
                continue
            ext = (
                repre.get("data", {}).get("context", {}).get("ext")
                or repre["name"]
            )
            if f".{ext}".lower() not in media_extensions:
                continue
            try:
                filepath = get_representation_path(repre)
            except Exception as exc:
                self.log.warning(
                    f"Skipping representation {repre['name']}: {exc}"
                )
                continue
            rep_name = os.path.basename(filepath)
            self.log.info(f"Adding sibling representation: {rep_name}")
            added_node = self._add_source_media_rep(node, rep_name, filepath)
            imprint(
                added_node,
                {
                    "representation": primary_repre_id,
                    "project_name": project_name,
                },
                prefix="ayon",
            )

    def update(self, container, context):
        node = container["node"]

        filepath = self.filepath_from_context(context)

        repre_entity = context["representation"]

        new_rep_name = os.path.basename(filepath)
        source_reps = rv.commands.sourceMediaReps(node)
        self.log.warning(f">> source_reps: {source_reps}")

        if new_rep_name not in source_reps:
            # add version to the switch group if it's not there yet
            self._add_source_media_rep(node, new_rep_name, filepath)
        else:
            self.log.warning(
                f"New rep name already in source_reps: {new_rep_name}"
            )

        # activate the new version in the switch group
        rv.commands.setActiveSourceMediaRep(
            node,
            new_rep_name,
        )
        source_rep_name = rv.commands.sourceMediaRep(node)
        self.log.debug(f"New source_rep_name: {source_rep_name}")

        # update colorspace
        representation = context["representation"]
        self.set_representation_colorspace(node, representation)

        # add data for inventory manager
        # imprint all sources in the switch group (incl. siblings) so
        # representation tracking stays consistent after a version bump
        switch_node = rv.commands.sourceMediaRepSwitchNode(node)
        if switch_node:
            source_nodes = [
                source_node
                for _, source_node in rv.commands.sourceMediaRepsAndNodes(
                    switch_node
                )
                if rv.commands.nodeType(source_node) == "RVFileSource"
            ]
        else:
            source_nodes = [node]
        for source_node in source_nodes:
            imprint(
                source_node,
                {"representation": str(repre_entity["id"])},
                prefix="ayon",
            )
        rv.commands.reload()

    def remove(self, container: dict) -> None:  # noqa: PLR6301
        """Remove loaded container."""
        node = container["node"]
        # since we are organizing all loaded sources under a switch group
        # we need to remove all the source nodes organized under it
        switch_node = rv.commands.sourceMediaRepSwitchNode(node)
        if not switch_node:
            # just in case someone removed it maunally
            return

        for (
            source_node_name,
            source_node
        ) in rv.commands.sourceMediaRepsAndNodes(switch_node):
            node_type = rv.commands.nodeType(source_node)
            node_group = rv.commands.nodeGroup(source_node)

            if node_type == "RVFileSource":
                self.log.info(f"Removing: {source_node_name}")
                rv.commands.deleteNode(node_group)

        # switch node is child of some other node. find its parent node
        parent_node = rv.commands.nodeGroup(switch_node)
        if parent_node:
            self.log.info(f"Removing: {parent_node}")
            rv.commands.deleteNode(parent_node)

        rv.commands.reload()

    def switch(self, container, context):
        self.update(container, context)

    def set_representation_colorspace(self, node, representation):
        colorspace_data = representation.get("data", {}).get("colorspaceData")
        if colorspace_data:
            colorspace = colorspace_data["colorspace"]
            # TODO: Confirm colorspace is valid in current OCIO config
            #   otherwise errors will be spammed from OpenRV for invalid space

            self.log.info(f"Setting colorspace: {colorspace}")
            group = rv.commands.nodeGroup(node)

            # Enable OCIO for the node and set the colorspace
            set_group_ocio_active_state(group, state=True)
            set_group_ocio_colorspace(group, colorspace)


class FramesLoader(BaseMediaLoader):
    """Load frames into OpenRV."""

    label = "Load Frames"
    extensions: ClassVar[set] = {ext.lstrip(".") for ext in IMAGE_EXTENSIONS}

    icon = "code-fork"
    color = "orange"

    @classmethod
    def filepath_from_context(cls, context):
        return rv.commands.sequenceOfFile(
            super().filepath_from_context(context)
        )[0]


class MovLoader(BaseMediaLoader):
    """Load mov into OpenRV"""

    label = "Load MOV"
    extensions: ClassVar[set] = {"mov", "mp4"}

    icon = "code-fork"
    color = "orange"
