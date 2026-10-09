import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch


ROOT = Path(__file__).resolve().parents[1]


def module(name, **attributes):
    result = ModuleType(name)
    result.__dict__.update(attributes)
    return result


def import_file(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    sys.modules[name] = result
    spec.loader.exec_module(result)
    return result


class Form:
    def __init__(self):
        self.fields = []

    def hidden(self, name, **kwargs):
        self.fields.append(("hidden", {"name": name, **kwargs}))

    def select(self, **kwargs):
        self.fields.append(("select", kwargs))

    def label(self, text):
        self.fields.append(("label", text))


class WebActionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        modules = patch.dict(sys.modules, {
            "ayon_server": module("ayon_server"),
            "ayon_server.actions": module(
                "ayon_server.actions", SimpleActionManifest=SimpleNamespace
            ),
            "ayon_server.addons": module(
                "ayon_server.addons", BaseServerAddon=object
            ),
            "ayon_server.addons.library": module(
                "ayon_server.addons.library", AddonLibrary=Mock()
            ),
            "ayon_server.forms": module(
                "ayon_server.forms", SimpleForm=Form
            ),
            "ayon_server.forms.simple_form": module(
                "ayon_server.forms.simple_form",
                FormSelectOption=SimpleNamespace,
            ),
            "ayon_server.lib": module("ayon_server.lib"),
            "ayon_server.lib.postgres": module(
                "ayon_server.lib.postgres", Postgres=Mock()
            ),
            "webaction_test_server.settings": module(
                "webaction_test_server.settings",
                OpenRVSettings=object, DEFAULT_VALUES={},
            ),
        })
        modules.start()
        self.addCleanup(modules.stop)
        server = import_file(
            "webaction_test_server", ROOT / "server" / "__init__.py"
        )
        self.addon = server.OpenRVAddon()
        self.action = sys.modules["webaction_test_server.action"]
        self.rv = AsyncMock(return_value="workfile")
        self.media = AsyncMock(return_value=[{"id": "media", "name": "mov"}])
        self.apps = AsyncMock(return_value=[("openrv/test", "RV")])
        for name, value in (
            ("_get_rv_workfile_representation_id", self.rv),
            ("_get_media_representations", self.media),
            ("_get_openrv_app_options", self.apps),
        ):
            replacement = patch.object(self.action, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def executor(self, existing=False, **context):
        return SimpleNamespace(
            identifier=(
                self.action.EXISTING_ACTION_IDENTIFIER if existing
                else self.action.ACTION_IDENTIFIER
            ),
            variant="production",
            context=SimpleNamespace(**{
                "project_name": "project",
                "entity_type": "version",
                "entity_ids": ["version"],
                "form_data": {},
                **context,
            }),
            get_simple_response=AsyncMock(side_effect=lambda **kw: kw),
            get_form_response=AsyncMock(side_effect=lambda **kw: kw),
            get_launcher_response=AsyncMock(side_effect=lambda **kw: kw),
        )

    async def test_existing_action_routes_to_media_without_app_lookup(self):
        response = await self.addon.execute_action(self.executor(existing=True))
        self.assertEqual(response["args"], [
            "addon", "openrv", "open-representation-in-existing-rv",
            "--project", "project", "--representation", "media",
        ])
        self.rv.assert_not_awaited()
        self.apps.assert_not_awaited()

    async def test_new_action_still_prefers_workfile(self):
        response = await self.addon.execute_action(self.executor())
        self.assertEqual(response["args"], [
            "addon", "openrv", "open-representation",
            "--project", "project", "--app", "openrv/test",
            "--representation", "workfile",
        ])
        self.media.assert_not_awaited()

    async def test_both_manifests_and_unknown_identifier(self):
        manifests = await self.addon.get_simple_actions()
        self.assertEqual(
            {m.identifier for m in manifests},
            {self.action.ACTION_IDENTIFIER,
             self.action.EXISTING_ACTION_IDENTIFIER},
        )
        executor = self.executor()
        executor.identifier = "unknown"
        response = await self.addon.execute_action(executor)
        self.assertFalse(response["success"])
        self.rv.assert_not_awaited()

    async def test_invalid_context_guards(self):
        for existing in (False, True):
            for context in (
                {"entity_type": "folder"},
                {"entity_ids": []},
                {"entity_ids": None},
                {"entity_ids": ["one", "two"]},
            ):
                with self.subTest(existing=existing, context=context):
                    response = await self.addon.execute_action(
                        self.executor(existing=existing, **context)
                    )
                    self.assertFalse(response["success"])
        self.media.assert_not_awaited()
        self.rv.assert_not_awaited()

    async def test_empty_media_returns_failure_not_index_error(self):
        self.rv.return_value = None
        self.media.return_value = []
        for existing in (False, True):
            response = await self.addon.execute_action(
                self.executor(existing=existing)
            )
            self.assertFalse(response["success"])
        self.apps.assert_not_awaited()

    async def test_existing_form_selection_and_workfile_rejection(self):
        self.media.return_value = [
            {"id": "image", "name": "exr"},
            {"id": "video", "name": "mov"},
        ]
        response = await self.addon.execute_action(self.executor(existing=True))
        self.assertEqual(response["fields"].fields[0][1]["name"],
                         "representation_id")
        self.assertEqual(response["form_data"], {})
        response = await self.addon.execute_action(self.executor(
            existing=True, form_data={"representation_id": "video"}
        ))
        self.assertEqual(response["args"][-1], "video")
        response = await self.addon.execute_action(self.executor(
            existing=True, form_data={"representation_id": "workfile"}
        ))
        self.assertFalse(response["success"])
        self.rv.assert_not_awaited()
        self.apps.assert_not_awaited()

    async def test_representation_then_app_form_loop(self):
        self.rv.return_value = None
        self.media.return_value = [
            {"id": "image", "name": "exr"},
            {"id": "video", "name": "mov"},
        ]
        self.apps.return_value = [
            ("openrv/one", "RV One"), ("openrv/two", "RV Two"),
        ]
        response = await self.addon.execute_action(self.executor())
        self.assertEqual(response["fields"].fields[0][1]["name"],
                         "representation_id")
        selection = {"representation_id": "video"}
        response = await self.addon.execute_action(
            self.executor(form_data=selection)
        )
        self.assertEqual(response["form_data"], selection)
        self.assertIn(
            ("hidden", {"name": "representation_id", "value": "video"}),
            response["fields"].fields,
        )
        response = await self.addon.execute_action(self.executor(
            form_data={**selection, "app_name": "openrv/two"}
        ))
        self.assertEqual(response["args"][-1], "video")
        self.assertIn("openrv/two", response["args"])
        self.rv.assert_awaited_once()
        self.media.assert_awaited_once()


class ClientTests(unittest.TestCase):
    def setUp(self):
        self.api = Mock()
        self.sender = Mock()
        self.path = Mock(return_value="image.EXR")
        self.manager = Mock()
        modules = patch.dict(sys.modules, {
            "ayon_api": self.api,
            "ayon_core": module("ayon_core"),
            "ayon_core.addon": module(
                "ayon_core.addon",
                AYONAddon=type("AYONAddon", (), {}),
                IHostAddon=type("IHostAddon", (), {}),
                IPluginPaths=type("IPluginPaths", (), {}),
                click_wrap=Mock(),
                ensure_addons_are_process_ready=Mock(),
            ),
            "ayon_core.lib": module("ayon_core.lib"),
            "ayon_core.lib.transcoding": module(
                "ayon_core.lib.transcoding",
                IMAGE_EXTENSIONS={".exr"}, VIDEO_EXTENSIONS={".mov"},
            ),
            "ayon_core.pipeline": module(
                "ayon_core.pipeline", get_representation_path=self.path
            ),
            "ayon_openrv": module("ayon_openrv"),
            "ayon_openrv.constants": module(
                "ayon_openrv.constants", OPENRV_ROOT_DIR=str(ROOT / "client")
            ),
            "ayon_openrv.version": module(
                "ayon_openrv.version", __version__="test"
            ),
            "ayon_openrv.networking": module(
                "ayon_openrv.networking",
                send_representation_to_existing_rv=self.sender,
            ),
            "ayon_applications": module(
                "ayon_applications",
                ApplicationManager=Mock(return_value=self.manager),
            ),
        })
        modules.start()
        self.addCleanup(modules.stop)
        self.module = import_file(
            "ayon_openrv.addon", ROOT / "client" / "ayon_openrv" / "addon.py"
        )
        self.addon = self.module.OpenRVAddon()
        self.representation = {
            "id": "representation", "name": "preview",
            "context": {"ext": ".MOV"},
        }
        self.api.get_representation_by_id.return_value = self.representation

    def invoke(self):
        self.addon._cli_open_representation_in_existing_rv(
            "project", "representation"
        )

    def test_media_and_legacy_alias(self):
        self.invoke()
        self.representation["context"] = {}
        self.addon._cli_send_to_existing_rv("project", "representation")
        self.assertEqual(self.sender.call_count, 2)
        self.sender.assert_called_with("project", self.representation)
        self.path.assert_called_once()

    def test_workfile_rejected_before_send(self):
        self.representation["context"]["ext"] = "rv"
        with self.assertRaisesRegex(RuntimeError, "Only image and video"):
            self.invoke()
        self.sender.assert_not_called()

    def test_missing_representation_and_path(self):
        self.api.get_representation_by_id.return_value = None
        with self.assertRaisesRegex(RuntimeError, "Could not find"):
            self.invoke()
        self.api.get_representation_by_id.return_value = self.representation
        self.representation["context"] = {}
        self.path.return_value = None
        with self.assertRaisesRegex(RuntimeError, "Could not resolve"):
            self.invoke()
        self.sender.assert_not_called()

    def test_connection_failure_propagates(self):
        error = ConnectionError("No connection")
        self.sender.side_effect = error
        with self.assertRaises(ConnectionError) as result:
            self.invoke()
        self.assertIs(result.exception, error)
        self.manager.launch.assert_not_called()

    def test_launch_enables_network_and_keeps_representation_data(self):
        self.addon._launch_openrv(
            "project", "/folder", "task",
            app_name="openrv/test", representation_id="representation",
        )
        args, kwargs = self.manager.launch.call_args
        self.assertEqual(args, ("openrv/test",))
        self.assertEqual(kwargs["app_args"], ["-network"])
        self.assertEqual(kwargs["representation_ids"], ["representation"])
        self.assertFalse(kwargs["start_last_workfile"])


if __name__ == "__main__":
    unittest.main()
