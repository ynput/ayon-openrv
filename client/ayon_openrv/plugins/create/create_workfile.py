import qtawesome
import ayon_api

from ayon_openrv.api.pipeline import (
    read, imprint
)
from ayon_core.pipeline import (
    AutoCreator,
    CreatedInstance,
)


class OpenRVWorkfileCreator(AutoCreator):
    identifier = "workfile"
    family = "workfile"
    label = "Workfile"

    default_variant = "Main"

    create_allow_context_change = False

    data_store_node = "root"
    data_store_prefix = "openpype_workfile."

    def collect_instances(self):

        data = read(node=self.data_store_node,
                    prefix=self.data_store_prefix)
        if not data:
            return

        instance = CreatedInstance(
            family=self.family,
            subset_name=data["subset"],
            data=data,
            creator=self
        )

        self._add_instance_to_context(instance)

    def update_instances(self, update_list):
        for created_inst, _changes in update_list:
            data = created_inst.data_to_store()
            imprint(node=self.data_store_node,
                    data=data,
                    prefix=self.data_store_prefix)

    def create(self, options=None):
        existing_instance = None
        for instance in self.create_context.instances:
            if instance.product_type == self.product_type:
                existing_instance = instance
                break

        context = self.create_context
        project_name = context.get_current_project_name()
        folder_path = context.get_current_folder_path()
        task_name = context.get_current_task_name()
        host_name = context.host_name

        existing_folder_path = None
        if existing_instance is not None:
            existing_folder_path = existing_instance.get("folderPath")

        if existing_instance is None:
            folder_entity = ayon_api.get_folder_by_path(
                project_name, folder_path
            )
            task_entity = ayon_api.get_task_by_name(
                project_name, folder_entity["id"], task_name
            )
            product_name = self.get_product_name(
                project_name,
                folder_entity,
                task_entity,
                self.default_variant,
                host_name,
            )
            data = {
                "folderPath": folder_path,
                "task": task_name,
                "variant": self.default_variant,
            }
            data.update(self.get_dynamic_data(
                project_name,
                folder_entity,
                task_entity,
                self.default_variant,
                host_name,
                None,
            ))

            new_instance = CreatedInstance(
                self.family, product_name, data, self
            )
            self._add_instance_to_context(new_instance)

        elif (
            existing_folder_path != folder_path
            or existing_instance["task"] != task_name
        ):
            folder_entity = ayon_api.get_folder_by_path(
                project_name, folder_path
            )
            task_entity = ayon_api.get_task_by_name(
                project_name, folder_entity["id"], task_name
            )
            product_name = self.get_product_name(
                project_name,
                folder_entity,
                task_entity,
                self.default_variant,
                host_name,
            )
            existing_instance["folderPath"] = folder_path
            existing_instance["task"] = task_name
            existing_instance["productName"] = product_name

    def get_icon(self):
        return qtawesome.icon("fa.file-o", color="white")
