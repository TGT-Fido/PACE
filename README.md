# PACE — Projects At a glanCE

**A free, open-source, self-hosted project dashboard for Windows.**

PACE helps you organize your projects, documents, plans, and progress in one customizable workspace. Whether you're managing personal goals, technical projects, studies, or long-term plans, PACE gives you a visual way to keep everything together.

**Current release: PACE26 v7.4.1**

[**Download the latest version for Windows**](https://github.com/TGT-Fido/PACE/releases/latest)

## Features

### Four ways to organize your projects

- **Cards:** A dashboard with customizable project cards, categories, priorities, colors, and progress information.
- **Canvas:** A flexible visual workspace for arranging projects.
- **Radial Map:** Visualize projects and their relationships.
- **Roadmap:** Organize and navigate your plans visually.

Create multiple saved layouts, customize their appearance, and switch between views without losing your projects.

### Documents and PDFs

- Import and organize PDF documents within projects.
- View PDFs directly inside PACE.
- Keep project document versions and history.
- Search project information and PDF contents.
- Manage documents without opening separate applications.

### Customization and productivity

- Dark and Light appearance.
- Custom wallpapers, icons, colors, and badges.
- Project duplication and bulk editing.
- Multiple saved workspace layouts.
- Keyboard shortcuts.
- Session-based Undo and Redo.
- Optional HDR accents on supported local displays.

### Access from multiple devices

PACE runs on your main computer and can be accessed through a web browser.

Supported access modes:

- **This computer only:** Use PACE directly on the host computer.
- **Local network:** Access PACE from devices on your home network.
- **Tailscale:** Access PACE remotely through your private Tailscale network.

Your host computer must remain powered on, connected, and running PACE for other devices to access it.

Tailscale is optional and requires separate installation and sign-in.

## Installation — Windows

1. Visit the [latest releases page](https://github.com/TGT-Fido/PACE/releases/latest).
2. Download the Windows Setup ZIP.
3. Extract the ZIP.
4. Run the included setup executable.
5. Follow the installation instructions.
6. Launch PACE from your desktop or Windows Start menu.

**No separate Python installation is required.** PACE includes its own Python runtime.

The installer may trigger a Windows security warning because it is not digitally signed.

## Getting Started

After launching PACE, open the dashboard in your browser.

Default local address:

`http://127.0.0.1:8765`

Start by creating a project, adding your documents, and choosing your preferred layout.

To access PACE from another device, open the PACE notification tray settings and choose Local network or Tailscale.

The tray also provides connection information and usable network addresses.

## Updating PACE

PACE includes an **Updates and backups** section.

Before updating, create a backup of your existing data.

For supported application updates, use the matching update package from the official GitHub release. Do not use the Windows installer ZIP as an application update package.

Some updates to installer-owned components may require running a newer Windows installer.

See the documentation included with your installation for update and recovery details.

## Privacy and Hosting

PACE is designed to run on your own computer.

Your project files and workspace are stored locally. You do not need a cloud account to use the dashboard.

Remote access through Tailscale uses your own private network configuration.

PACE is not intended to be exposed directly to the public internet without appropriate security protections.

## Compatibility

- **Primary platform:** Windows 64-bit.
- **Interface:** Web browser.
- **Other devices:** Phones, tablets, and computers using a supported network connection.
- **Advanced users:** Source-based operation is possible on Linux and macOS, but the bundled Windows tray application and runtime are Windows-specific.

## Documentation

The complete package includes additional documentation covering installation, features, networking, updates, and recovery.

For version-specific changes, refer to the release notes included with each release.

## License

PACE is free and open-source software.

First-party source code is licensed under the **GNU General Public License v3.0 (GPLv3)**.

Third-party components retain their respective licenses and notices.

Copyright © 2026 Yahya Nazzal.

---

**[Download PACE](https://github.com/TGT-Fido/PACE/releases/latest)** | **[Report an issue](https://github.com/TGT-Fido/PACE/issues)**

*PACE26 is the 2026 edition of Projects At a glanCE.*
