# PS4 remote installation — setup and safeguards

## Current state (2026-11-23)
- Remote PKG Installer NextGen v0.0.10 is running on PS4, LAN port 12800, 192.168.1.120.
- Dell read-only API queries system, storage, jobs and logs returned HTTP 200.
- Installer has 0 install jobs and is awaiting commands.
- Dashboard shows 0 B available. Its API returns total 0 bytes and free 7357090675977879552 bytes. These are impossible values, likely a statvfs compatibility problem; they do not prove that PS4 storage is full.
- Verify actual free capacity independently in PS4 Settings > Storage before remote installation.
- BinLoader port 9090 was not accessed.

## PC client
Run from the repository root:

    python pc/ps4_remote_install.py status
    python pc/ps4_remote_install.py install --pkg PATH_TO_SMALL_APP.pkg --sha256 EXPECTED_SHA

Second command is a dry-run: verifies the PKG checksum without requesting installation. An actual install requires --execute and remains blocked while storage readings are invalid; do not bypass this before verifying real free space.

After owner verification of the current PS4 Storage screen, pass --confirmed-free-gb with the displayed free GB rounded down, only when the API is invalid. The default still refuses invalid capacity; reliable API values always take precedence. At least 1 GB and twice the package size are required. The downloader needs to reach the Dell single-PKG HTTP server on the LAN. Any firewall changes require separate review.

## Remote control is separate
Remote PKG Installer cannot control the PS4 interface. To view/control the screen, pair Chiaki-ng with PS4 via Settings > Remote Play Connection Settings > Add Device.
Chiaki is installed on Dell at D:\BlackServ_Coder\tools\chiaki-ng\chiaki-ng-Win\chiaki.exe.
Pairing data must remain local and out of Git/logs. SentinelX executes as the Windows service account (DELL$), not in the user's interactive desktop session, and by itself cannot view or control the Chiaki GUI.