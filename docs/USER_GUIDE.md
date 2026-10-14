# PACE 7 quick guide

## Connections

- This computer only: binds 127.0.0.1. Users of the same computer can open the browser address while the host session runs PACE.
- Local network: keeps localhost and listens on detected private IPv4 interfaces. Open the address shown in tray Settings on a phone, iPad or computer on the same network. If Windows Firewall prompts, allow the bundled Python application on your private network. Guest Wi-Fi isolation may prevent connection. After changing networks, reselect the mode to refresh addresses.
- Tailscale: keeps localhost and listens on the connected Tailscale IPv4 address. Other authorized devices in your tailnet can open that address. PACE does not install, start, sign in to, or stop Tailscale. Switching back removes the remote listener.

PACE is a shared workspace: devices allowed to connect can view and edit its projects, including deletion. It has no separate accounts or login. Keep LAN access on a trusted network; Tailscale access follows your tailnet permissions. No router port forwarding is required. Browser HTTP is used; remote HDR/HTTPS setup is deferred.

## Appearance

Gear Settings contains Light, Dark, Save Custom preset, wallpaper thumbnails, file upload, brightness and the optional HDR renderer. Panels behind headings, counters and footer are opaque and switch with the theme. Uploaded images are stored under `data/backgrounds`; identical bytes are reused. Images may be PNG, JPEG or WebP up to 25 MB. Original supplied images and three new wallpapers are bundled. No generated image is described as native 4K unless its dimensions actually meet that size.

HDR uses an extended-range WebGPU canvas for accent highlights. It leaves HTML text, PDFs and standard wallpapers in SDR. It requires a compatible browser/GPU, HDR display and Windows HDR. LAN/Tailscale URLs use Legacy regardless of the saved preference. An unsupported browser or failed initialization falls back to Legacy with status information. Actual HDR appearance still requires testing on HDR hardware.

## Projects and maps

Four fictional sample projects have fillable PDFs. Change or delete them freely. Delete from a card's three-dot menu or Reorder removes the project folder and its contents after explicit confirmation. Back up anything you want to keep first. Samples do not return after deletion.

Click a project icon or choose Change icon from its menu to choose a built-in icon or upload your own. Custom icons live in `data/icons`. Card arrow controls and the Reorder dialog support moving projects.

In Canvas, Radial Map and Roadmap, click the center/root title to rename it. The name is shared across these three views and persists. The toolbar's Centered/Expanded control sits before Home; the existing fullscreen control remains available. Header branding stays PACE. Settings shows PACE26 and the software version separately.

## Data, backups and updates

The entire `data` folder contains your projects, preferences, document form values, images and view state. Keep it when upgrading. Backup/Restore and existing update controls are in dashboard Settings. V7.1 will test a configured GitHub release update separately. No release URL is preconfigured in this package.

The app checks projects every 15 seconds while visible. Rescan checks immediately. Use Exit PACE in the tray to stop its server. Closing the browser alone leaves PACE running.

Offline app-and-data recovery remains available through `RECOVER_PACE.cmd`, using the private runtime. Close PACE first and choose an existing PACE backup outside the installation. It retains the replaced files in a separate recovery folder.
