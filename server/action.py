from typing import Optional, TYPE_CHECKING

from ayon_server.actions import DynamicActionManifest
from ayon_server.addons.library import AddonLibrary
from ayon_server.forms import SimpleForm
from ayon_server.forms.simple_form import FormSelectOption
from ayon_server.lib.postgres import Postgres
from ayon_server.logging import logger

if TYPE_CHECKING:
    from ayon_server.actions import ActionContext, ActionExecutor, ExecuteResponseModel


ACTION_IDENTIFIER = "openrv.open_in_rv"

# Media file extensions supported by the action (without leading dot, lowercase).
# These mirror IMAGE_EXTENSIONS and VIDEO_EXTENSIONS from ayon_core so that the
# server can query the database without depending on the client library.
IMAGE_EXTENSIONS: frozenset[str] = frozenset({
    "bmp", "cin", "dpx", "exr", "gif", "hdr",
    "jpg", "jpeg", "pic", "png", "psd",
    "rgb", "rgba", "sgi", "tga", "tif", "tiff", "xpm",
})
VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    "avi", "flv", "m4v", "mkv", "mov", "mp4",
    "mpg", "mpeg", "mxf", "webm", "wmv",
})
MEDIA_EXTENSIONS: frozenset[str] = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def get_open_in_rv_action() -> DynamicActionManifest:
    return DynamicActionManifest(
        identifier=ACTION_IDENTIFIER,
        label="Open in RV",
        category="Desktop tools",
        order=100,
        icon={
            "type": "material-symbols",
            "name": "live_tv",
            "color": "#FFA500",
        },
    )


async def can_open_in_rv(context: "ActionContext") -> bool:
    """Return True if the action can run for the given context."""

    logger.info(f"Checking if can be opened in context: {context}")

    project_name = context.project_name
    entity_ids = context.entity_ids or []
    if not project_name:
        return False
    if context.entity_type != "version" or len(entity_ids) != 1:
        return False

    version_id = entity_ids[0]
    representation_id = await _get_rv_workfile_representation_id(
        project_name, version_id
    )
    return representation_id is not None


async def _get_rv_workfile_representation_id(
    project_name: str,
    version_id: str,
) -> Optional[str]:
    """Return the id of the RV workfile representation for a version, or None."""
    query = f"""
        SELECT r.id
        FROM project_{project_name}.versions AS v
        JOIN project_{project_name}.products AS p
            ON p.id = v.product_id
        JOIN project_{project_name}.representations AS r
            ON r.version_id = v.id
        WHERE v.id = $1
            AND (
                p.product_base_type = 'workfile'
                OR p.product_type = 'workfile'
            )
            AND lower(r.name) = 'rv'
        LIMIT 1
    """
    result = await Postgres.fetchrow(query, version_id)
    return result["id"] if result else None


async def _get_media_representations(
    project_name: str,
    version_id: str,
) -> list[dict[str, str]]:
    """Return media (image/video) representations for a version.

    The representation ``name`` field holds the file extension (e.g. ``exr``,
    ``mov``), so filtering on it is sufficient to identify media files.
    Each returned row contains ``id``, ``name``, and ``data``.
    """
    query = f"""
        SELECT r.id, r.name, r.data
        FROM project_{project_name}.representations AS r
            WHERE r.version_id = $1
            AND (
                lower(r.name) = ANY($2)
                OR lower(r.data->'context'->>'ext') = ANY($2)
            )
    """
    return await Postgres.fetch(query, version_id, list(MEDIA_EXTENSIONS))


async def _get_openrv_app_options(
    settings_variant: str,
) -> list[tuple[str, str]]:
    library = AddonLibrary.getinstance()
    addons_by_name = await library.get_addons_by_variant(settings_variant)
    applications_addon = addons_by_name.get("applications")
    if applications_addon is None:
        raise Exception(
            f"Applications addon not found in bundle: {settings_variant}..."
        )

    addon_studio_settings = await applications_addon.get_studio_settings(
        variant=settings_variant
    )
    if not addon_studio_settings:
        raise Exception(
            f"Could not load applications addon settings for"
            f" variant: {settings_variant}..."
        )

    applications_settings = getattr(addon_studio_settings, "applications", None)
    openrv_settings = getattr(applications_settings, "openrv", None)
    if openrv_settings is None:
        return []

    group_label = getattr(openrv_settings, "label", "") or "openrv"
    variants = getattr(openrv_settings, "variants", []) or []
    output: list[tuple[str, str]] = []
    for variant in variants:
        variant_name = getattr(variant, "name", None)
        if not variant_name:
            continue
        variant_label = getattr(variant, "label", "") or variant_name
        output.append(
            (
                f"openrv/{variant_name}",
                f"{group_label} {variant_label}",
            )
        )
    return output


async def execute_open_in_rv_action(
    executor: "ActionExecutor",
) -> "ExecuteResponseModel":
    context = executor.context

    if executor.identifier != ACTION_IDENTIFIER:
        return await executor.get_simple_response(
            success=False,
            message=(
                f"Unsupported action identifier: {executor.identifier}"
            ),
        )

    if context.entity_type != "version":
        return await executor.get_simple_response(
            success=False,
            message=(
                f"Unsupported entity type in action context: {context}"
            ),
        )

    entity_ids = context.entity_ids or []
    if len(entity_ids) != 1:
        return await executor.get_simple_response(
            success=False,
            message="Action requires exactly one selected version.",
        )

    project_name = context.project_name
    version_id = entity_ids[0]
    form_data = context.form_data or {}
    form = SimpleForm()

    representation_id = form_data.get("representation_id")
    if not representation_id:
        # Prefer an RV workfile representation; fall back to any media
        # representation.
        representation_id = await _get_rv_workfile_representation_id(
            project_name, version_id
        )
        if representation_id is None:
            media_repres = await _get_media_representations(
                project_name,
                version_id
            )
            # If there are multiple media representations, ask the user to
            # select one.
            if len(media_repres) > 1:
                form.select(
                    name="representation_id",
                    label="Representation",
                    options=[
                        FormSelectOption(
                            value=repre["id"],
                            label=repre["name"],
                        )
                        for repre in media_repres
                    ],
                    value=media_repres[0]["id"],
                )
                return await executor.get_form_response(
                    success=True,
                    title="Select representation to open in RV",
                    fields=form,
                    form_data=form_data,
                )
            representation_id = media_repres[0]["id"]

    # Store the representation_id
    form.hidden("representation_id", value=representation_id)

    if representation_id is None:
        return await executor.get_simple_response(
            success=False,
            message=(
                "Selected version has no RV workfile or media representation"
                " that can be opened in RV."
            ),
        )

    app_name = form_data.get("app_name")
    app_options = await _get_openrv_app_options(executor.variant)
    if not app_name and len(app_options) == 1:
        app_name = app_options[0][0]

    if not app_name:
        if not app_options:
            return await executor.get_simple_response(
                success=False,
                message=(
                    "No OpenRV variants are configured in Applications "
                    "settings for this bundle variant."
                ),
            )

        form.label("Select OpenRV version to launch")
        form.select(
            name="app_name",
            label="OpenRV variant",
            options=[
                FormSelectOption(
                    value=value,
                    label=label,
                )
                for value, label in app_options
            ],
            value=app_options[0][0],
        )
        return await executor.get_form_response(
            success=True,
            title="Select OpenRV variant",
            fields=form,
            form_data=form_data,
        )

    allowed_apps = {value for value, _ in app_options}
    if app_name not in allowed_apps:
        return await executor.get_simple_response(
            success=False,
            message="Selected OpenRV variant is not available.",
        )

    return await executor.get_launcher_response(
        args=[
            "addon",
            "openrv",
            "open-representation",
            "--project",
            project_name,
            "--app",
            app_name,
            "--representation",
            representation_id,
        ],
        message="Launching OpenRV...",
    )
