Two stages are configured once for all the projects, in *Settings > Support
Releases*:

* the preprod stage, applied when a release is received from preprod;
* the prod stage, applied when a release is received from prod.

The stage of the environment is applied to every ticket of the release, without
comparing it with the current one: the payload describes the state after the
deployment, and a release received out of order corrects the previous one. If
the stage is not linked to the project of a ticket, it is linked first,
otherwise the web client would silently replace it.

Once a release has a production deployment date, a payload coming from preprod
for the same version is ignored, so a preprod redeployment cannot reopen
tickets that are already closed.

The `next` release of a client is deleted when the first numbered version
arrives for that client, its tickets being part of the new payload.

Whatever could not be applied is written on the release, in the *Message* field
shown when it is not empty: unknown tickets, tickets of another partner or of a
project without partner, no stage configured for the environment, no user to
notify. Nothing is dropped silently.

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
