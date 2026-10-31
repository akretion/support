Two stages are configured once for all the projects, in *Settings > Support
Releases*:

* the preprod stage, applied when a release is received from preprod;
* the prod stage, applied when a release is received from prod.

A ticket is never moved backwards: the stage is only written when the target
stage is further than the current one, comparing their sequences.

Once a release has a production deployment date, a payload coming from preprod
for the same version is ignored, so a preprod redeployment cannot reopen
tickets that are already closed.

The `next` release of a client is absorbed by the first numbered version
received for that client, then removed.
