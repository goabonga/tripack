# Security Policy

## Supported versions

Tripack ships three independently versioned packages
(`tripack-contracts`, `tripack-runtime`, `tripack-container`). Security fixes
are applied only to the latest released minor of each package.

| Package | Supported |
| --- | --- |
| `tripack-contracts` - latest minor | ✅ |
| `tripack-runtime` - latest minor | ✅ |
| `tripack-container` - latest minor | ✅ |
| Older minors or pre-releases | ❌ |

## Reporting a vulnerability

**Please do not open a public issue.** GitHub's
[private vulnerability reporting](https://docs.github.com/en/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
is the preferred channel:

1. Go to the repository's **Security** tab.
2. Click **Report a vulnerability**.
3. Fill in the form with the affected package, version, reproduction steps and
   suggested mitigation.

If you cannot use GitHub's form, email **goabonga@pm.me** with the same
information. PGP encryption is available on request.

You can expect:

- an acknowledgement within **3 business days**;
- a triage assessment (severity, scope, affected packages) within **10
  business days**;
- a fix or written mitigation plan before any public disclosure.

## Disclosure process

Coordinated disclosure is the default. Once a fix is released:

1. A patched version is published to PyPI for each affected package.
2. A GitHub Security Advisory is opened with a CVE when applicable.
3. The reporter is credited in the advisory unless they request anonymity.

Thanks for helping keep Tripack and its users safe.
