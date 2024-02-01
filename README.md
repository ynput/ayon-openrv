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