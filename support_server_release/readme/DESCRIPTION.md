This module receives the releases pushed by a customer project (see
`support_release`), creates a release per version, links the tickets it ships
and moves them to the stage matching the deployment environment.

The core is a single POST route added to the existing `cross_connect`
endpoint, authenticated by the same `api-key` as the support feature. There is
no git logic here: the ticket ids are given by the payload, and the partner of
the release is the one of the projects of the tickets.
