Two stages are configured once for all the projects, in *Settings > Support
Releases*:

* the preprod stage, applied when a release is received from preprod;
* the prod stage, applied when a release is received from prod.

The stage of the environment is applied to every ticket of the release, without
comparing it with the current one: the payload describes the state after the
deployment, and a release received out of order corrects the previous one. The
stage is not added to the projects: the two configured stages have to be linked
to the projects of the client to appear in their kanban.

A client owns the projects whose *Cross Connect Client* is set to it. The
partner of the release is the partner of those projects; if they carry several
partners, the module raises and the reception fails, since the client must be
one customer. A ticket is linked when its project carries that partner, so the
tickets of the internal projects (maintenance done for the customer, without a
cross connect client) are linked too, while a ticket of another partner is
reported in the *Message* field and left untouched.

Each payload replaces the tickets of the release: a ticket removed from the
release is unlinked, so the production mail never announces it.

Once a release has a production deployment date, any further payload for that
version is ignored, whether it comes from preprod or from prod: a timeout that
replays the payload cannot send the mail twice.

The `next` release of a client is deleted when the first numbered version
arrives for that client, its tickets being part of the new payload.

Whatever could not be applied is written on the release, in the *Message* field
shown when it is not empty: unknown tickets, tickets of a project of another
client, no stage configured for the environment, no user to notify. Nothing is
dropped silently.

## Production notification

When a release reaches production, the users listed in *Release notification
users* on the partner of the release get an email listing the tickets of the
release: every title links to the ticket, and the description of the ticket is
folded under a *Description* summary. That list is set on the customer, so the
same people are notified for every release of that customer, and a customer
with no user listed simply gets no mail.

The mail is queued like any other Odoo mail and sent by the mail queue, so a
mail server problem never fails the release. A client without a user having an
email address simply gets no mail.

The template is *Support Release: release in production*: change the wording,
the recipients or the layout there, the module only renders it.

The folding uses the HTML `<details>` element. Apple Mail, Thunderbird and the
iOS Mail application fold it; Gmail and Outlook drop it and show the
description unfolded. Email has no reliable alternative, so the message stays
readable everywhere.

## Release notes

Check *Release notes* in the settings of a project to add a *Release note* tab on
its tickets. The note says what changes for the customer once the ticket is in
production:

* the customer users see it read-only in their form of the ticket, where the tab
  is hidden while the note is empty;
* the production mail shows it under the title of the ticket, and shows nothing
  when the note is empty or the project does not use release notes.
