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
Select a single version to use either desktop action:

- **Open in RV** launches a new OpenRV instance, preferring a published `.rv`
  workfile and otherwise offering the available media representations.
- **Open in Existing RV** sends an image or video representation to a running,
  network-connected OpenRV instance. It never launches an application or offers
  an application variant. RV workfiles are not supported by this action.

Both actions ask for a representation when multiple media representations are
available. New instances launched by these actions enable RV networking with
`-network`. An existing instance must have networking enabled and use the
connection settings configured in the OpenRV addon.

The existing-instance CLI command is:

```shell
ayon addon openrv open-representation-in-existing-rv --project PROJECT --representation ID
```

It fails if the representation is not media or no existing RV connection is
available. `send-to-existing-rv` is retained as an alias.

After updating the addon, deploy the matching server and client versions and
restart RV. Server routing changes do not update an already installed client,
and `-network` only takes effect when a new RV process starts.