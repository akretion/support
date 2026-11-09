This module records the releases deployed on a customer project and pushes them
to the Akretion support server, where the tickets shipped by each release are
linked and moved to the stage matching the deployment environment.

The information comes from a migration generated in the project by the release
script, so the module never reads git: it only stores what the migration hands
it and relays it.

A release is identified by its version. When no version is defined yet, the
version is `next`, and the first numbered version absorbs it.
