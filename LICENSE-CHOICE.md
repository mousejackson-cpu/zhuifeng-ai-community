# License choice recommendation

This repository currently does **not** include a final legal license text yet.

Recommended default:
- **AGPL-3.0** if your goal is open-source distribution plus strong protection against third parties taking the code and running a closed hosted SaaS on top of it.

Alternative:
- **MIT** if your goal is maximum adoption and you do not mind commercial forks.

Suggested choice for this project:
- **AGPL-3.0**

Why:
1. The community edition is intended to drive traffic to the hosted Pro version.
2. The project has a clear commercial layer that should remain private.
3. AGPL is usually a better fit than MIT for self-hosted tools that want stronger reciprocity when deployed as a network service.

Before publishing publicly, add the full official text of the license you choose to a `LICENSE` file in the root.
