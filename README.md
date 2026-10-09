# OpenRV addon
This adds integration to OpenRV https://github.com/AcademySoftwareFoundation/OpenRV.
OpenRV is open source version of RV - image and sequence viewer for VFX and animation artists.

This addon doesn't provide OpenRV binaries because of licencing. Studios need to build appropriate binaries for OS they are using themselves.


## Settings
Path to binaries must be set in the Ayon Setting in `Applications` addon (`ayon+settings://applications/applications/openrv`) and added in `Anatomy`.`Attributes` for particular project to be visible in the Launcher.

### Implemented workflows
Currently there is workflow for versioning and tracking `.rv` workfiles. Instance of `workfile` product type is automatically created when `Publish` option in `Ayon` menu inside of `OpenRV` is pressed.

Another workflow would be publishing of `annotations`, but that is still WIP right now.

Integrations allows to load image, image sequence or `.mov` files to the `.rv` workfile.

### Web actions
Select a single version and choose **Open in RV**. The action prefers a
published `.rv` workfile and otherwise asks for a representation when multiple
media representations are available. After selecting the OpenRV application
variant, choose whether to use an existing instance:

- **No** launches a new OpenRV instance.
- **Yes** sends the selected image or video representation to an already
  running, network-connected OpenRV instance. It does not launch an application.
  RV workfiles cannot be loaded this way; choose **No** for those.

New instances launched by this action enable RV networking with
`-network`. An existing instance must have networking enabled and use the
connection settings configured in the OpenRV addon.

The existing-instance CLI command is:

```shell
ayon addon openrv open-representation --project PROJECT --representation ID --use-existing-rv-instance
```

It fails if the representation is not media or no existing RV connection is
available. Omit `--use-existing-rv-instance` to launch a new instance; it is a
flag and must not be followed by `True` or `False`.

After updating the addon, deploy the matching server and client versions and
restart RV. Server routing changes do not update an already installed client,
and `-network` only takes effect when a new RV process starts.