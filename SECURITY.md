# Security

Report a security weakness privately, through GitHub's private vulnerability reporting on this repository. On the repository page, open the Security tab and choose "Report a vulnerability". Please do not open a public issue for it.

Never put confidential supervisory information, a real bank document, text from a real finding or a real person's name in a report. Describe the weakness with an invented example, as the cases in this repository do.

## What counts

- The finding tool printing a name on a finding's deny list.
- A signature recorded while the check still has rows on its list, or by a script with no terminal attached.
- A crafted PDF, Word file, workbook, CSV or email that makes the document reader crash, hang or read text a person cannot see.
- The finding tool opening a network connection, starting a process or writing outside the finding folder it was given.
- A change to a covered file that leaves an old fingerprint or an old signature standing.

The engine's optional model step, `tieout/providers.py`, sends text to an endpoint its operator names. The finding tool never imports it, and a weakness there is in scope too.

## Supported versions

Only the latest release gets fixes.

This is a personal project with one maintainer and no service-level promise. Reports are read and answered as time allows.
