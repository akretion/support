The release information is registered by a migration generated in the project
(usually `custom_all`) at each deployment:

```python
from openupgradelib import openupgrade


@openupgrade.migrate(use_env=True)
def migrate(env, version):
    if "support.release" not in env:
        return
    env["support.release"]._register_deployment(
        version="next",  # or the numbered version, e.g. "14.0.2610.26.0"
        tickets=[25882, 25890],
    )
```

The guard on the model presence keeps a database where this module is not
installed from failing its module update.

Releases are then pushed by the cron *Support Release: push pending releases*
(every 10 minutes, one release per run, oldest first), or immediately with the
*Push pending releases* button.

The push only happens when `running_env` is `preprod` or `prod`: it is set by
`server_environment` from the `RUNNING_ENV` environment variable, so there is
nothing else to configure in the module.

The generated migration must exist on the **main branch only**: the CI sets
`RUNNING_ENV=preprod` on every container, so a review environment carrying a
migration would announce a version that was never deployed.
