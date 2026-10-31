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

## Production notification

When a release reaches production, the users of its client (the portal users
attached to the `cross.connect.client`, the ones the connection creates) get an
email listing the tickets of the release: every title links to the ticket, and
the description of the ticket is folded under a *Description* summary.

The mail is queued like any other Odoo mail and sent by the mail queue, so a
mail server problem never fails the release. A client without a user having an
email address simply gets no mail.

The template is *Support Release: release in production*: change the wording,
the recipients or the layout there, the module only renders it.

The folding uses the HTML `<details>` element. Apple Mail, Thunderbird and the
iOS Mail application fold it; Gmail and Outlook drop it and show the
description unfolded. Email has no reliable alternative, so the message stays
readable everywhere.
