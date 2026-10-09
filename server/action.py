from typing import Optional, TYPE_CHECKING

from ayon_server.actions import SimpleActionManifest
from ayon_server.addons.library import AddonLibrary
from ayon_server.forms import SimpleForm
from ayon_server.forms.simple_form import FormSelectOption
from ayon_server.lib.postgres import Postgres

if TYPE_CHECKING:
    from ayon_server.actions import ActionContext, ActionExecutor, ExecuteResponseModel


ACTION_IDENTIFIER = "openrv.open_in_rv"
EXISTING_ACTION_IDENTIFIER = "openrv.open_in_existing_rv"

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


def get_open_in_rv_simple_action() -> SimpleActionManifest:
    return SimpleActionManifest(
        identifier=ACTION_IDENTIFIER,
        label="Open in RV",
        category="Desktop tools",
        order=100,
        icon={
            "type": "material-symbols",
            "name": "live_tv",
            "color": "#FFA500",
        },
        entity_type="version",
        entity_subtypes=None,
        allow_multiselection=False,
    )

def get_open_in_existing_rv_simple_action() -> SimpleActionManifest:
    return SimpleActionManifest(
        identifier=EXISTING_ACTION_IDENTIFIER,
        label="Open in Existing RV",
        category="Desktop tools",
        order=101,
        icon={
            "type": "material-symbols",
            "name": "live_tv",
            "color": "#DCEB58",
        },
        entity_type="version",
        entity_subtypes=None,
        allow_multiselection=False,
    )


async def can_open_in_rv(context: "ActionContext") -> bool:
    """Return True if the action can run for the given context."""
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

async def execute_openrv_action(
        executor: "ActionExecutor",
) -> "ExecuteResponseModel":
    if executor.identifier in {
        ACTION_IDENTIFIER,
        EXISTING_ACTION_IDENTIFIER,
    }:
        existing_rv = False if executor.identifier == ACTION_IDENTIFIER else True
        return await execute_open_in_rv_action(executor, use_existing_rv=existing_rv)
    return await executor.get_simple_response(
        success=False,
        message=(
            f"Unsupported action identifier: {executor.identifier}"
        ),
    )


async def _resolve_representation(
    executor: "ActionExecutor",
    *,
    media_only: bool = False,
) -> tuple[Optional[str], Optional["ExecuteResponseModel"]]:
    """Resolve the representation to open.

    Returns a ``(representation_id, response)`` tuple. When ``response`` is
    not None it has to be returned to the caller instead (form or error
    response).

    Args:
        executor: The action executor providing the context.
        media_only: When True only image and video representations are
            considered. This is required when loading into an existing
            OpenRV instance, which cannot open ``.rv`` workfiles.
    """
    context = executor.context
    project_name = context.project_name
    version_id = context.entity_ids[0]
    form_data = context.form_data or {}
    form = SimpleForm()

    representation_id = form_data.get("representation_id")
    if not representation_id and not media_only:
        # Prefer an RV workfile representation; fall back to media below.
        representation_id = await _get_rv_workfile_representation_id(
            project_name, version_id
        )

    if not representation_id or media_only:
        media_repres = await _get_media_representations(
            project_name, version_id
        )
        if representation_id:
            # A representation was already picked in the form. It is only
            # valid when it is still a media representation of this version.
            media_ids = {repre["id"] for repre in media_repres}
            if representation_id not in media_ids:
                return None, await executor.get_simple_response(
                    success=False,
                    message=(
                        "Selected representation is not available as media"
                        " for this version."
                    ),
                )
        elif len(media_repres) > 1:
            # If there are multiple media representations, ask the user to
            # select one.
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
            return None, await executor.get_form_response(
                success=True,
                title="Select representation to open in RV",
                fields=form,
                form_data=form_data,
            )
        elif media_repres:
            representation_id = media_repres[0]["id"]

    if not representation_id:
        description = "media" if media_only else "RV workfile or media"
        return None, await executor.get_simple_response(
            success=False,
            message=(
                f"Selected version has no {description} representation"
                " that can be opened in RV."
            ),
        )
    return representation_id, None


async def execute_open_in_rv_action(
    executor: "ActionExecutor",
    use_existing_rv: bool = False,
) -> "ExecuteResponseModel":
    context = executor.context
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
    form_data = context.form_data or {}

    representation_id, response = await _resolve_representation(
        executor, media_only=use_existing_rv
    )
    if response is not None:
        return response

    form = SimpleForm()
    # Store the representation_id so a following OpenRV variant form keeps
    # the selected representation
    form.hidden("representation_id", value=representation_id)

    if use_existing_rv:
        return await executor.get_launcher_response(
            args=[
                "addon",
                "openrv",
                "open-representation-in-existing-rv",
                "--project",
                project_name,
                "--representation",
                representation_id,
            ],
            message="Adding representation to existing RV session...",
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
