from typing import Optional, TYPE_CHECKING

from ayon_server.actions import SimpleActionManifest
from ayon_server.addons.library import AddonLibrary
from ayon_server.forms import SimpleForm
from ayon_server.forms.simple_form import FormSelectOption
from ayon_server.lib.postgres import Postgres

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
    app_options = await _get_openrv_app_options(executor.variant)
    if not app_options:
        return await executor.get_simple_response(
            success=False,
            message=(
                "No OpenRV variants are configured in Applications "
                "settings for this bundle variant."
            ),
        )
    allowed_apps = {value for value, _ in app_options}

    media_repres = await _get_media_representations(
        project_name, version_id
    )
    media_by_id = {repre["id"]: repre for repre in media_repres}
    workfile_representation_id = (
        await _get_rv_workfile_representation_id(project_name, version_id)
    )
    app_name = form_data.get("app_name")
    media_representation_id = form_data.get("media_representation_id")
    instance_option = form_data.get(
        "use_existing_rv_instance"
    )
    if instance_option is None or isinstance(instance_option, bool):
        use_existing_rv_instance = instance_option
    elif instance_option == "yes":
        use_existing_rv_instance = True
    elif instance_option == "no":
        use_existing_rv_instance = False
    else:
        return await executor.get_simple_response(
            success=False,
            message="Selected OpenRV instance option must be Yes or No.",
        )

    # Keep accepting representation_id from a form submitted before this
    # combined form was displayed, but only when it identifies media.
    previous_representation_id = form_data.get("representation_id")
    if (
        media_representation_id is None
        and isinstance(previous_representation_id, str)
        and previous_representation_id in media_by_id
    ):
        media_representation_id = previous_representation_id

    if (
        app_name is None
        or use_existing_rv_instance is None
        or (media_repres and media_representation_id is None)
    ):
        form = SimpleForm()
        form.select(
            name="app_name",
            label="OpenRV variant",
            options=[
                FormSelectOption(value=value, label=label)
                for value, label in app_options
            ],
            value=(
                app_name
                if app_name in allowed_apps
                else app_options[0][0]
            ),
        )
        boolean_options = [(True, "Yes"), (False, "No")]
        form.select(
            name="use_existing_rv_instance",
            label="Use existing OpenRV Session",
            options=[
                FormSelectOption(value=value, label=label)
                for value, label in boolean_options
            ],
            value=boolean_options[0][0],
        )
        if media_repres:
            form.select(
                name="media_representation_id",
                label="Media representation",
                options=[
                    FormSelectOption(
                        value=repre["id"],
                        label=repre["name"],
                    )
                    for repre in media_repres
                ],
                value=(
                    media_representation_id
                    if media_representation_id in media_by_id
                    else media_repres[0]["id"]
                ),
            )
        return await executor.get_form_response(
            success=True,
            title="Choose OpenRV options",
            fields=form,
            form_data=form_data,
        )

    if app_name not in allowed_apps:
        return await executor.get_simple_response(
            success=False,
            message="Selected OpenRV variant is not available.",
        )

    if (
        media_representation_id is not None
        and (
            not isinstance(media_representation_id, str)
            or media_representation_id not in media_by_id
        )
    ):
        return await executor.get_simple_response(
            success=False,
            message="Selected media representation is not available.",
        )

    if use_existing_rv_instance:
        if media_representation_id is None:
            return await executor.get_simple_response(
                success=False,
                message=(
                    "Selected version has no media representation that"
                    " can be opened in an existing OpenRV session. Select"
                    " 'No' to open a published RV workfile instead."
                ),
            )
        representation_id = media_representation_id
    elif workfile_representation_id is not None:
        representation_id = workfile_representation_id
    else:
        representation_id = media_representation_id

    if representation_id is None:
        return await executor.get_simple_response(
            success=False,
            message=(
                "Selected version has no RV workfile or media representation"
                " that can be opened in RV."
            ),
        )

    args = [
        "addon",
        "openrv",
        "open-representation",
        "--project",
        project_name,
        "--app",
        app_name,
        "--representation",
        representation_id,
    ]
    if use_existing_rv_instance:
        args.append("--use-existing-rv-instance")
    return await executor.get_launcher_response(
        args=args,
        message="Launching OpenRV...",
    )
