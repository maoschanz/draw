# Install of the unstable version from `master`

## Run as flatpak with GNOME Builder (recommended)

- Clone this repo (`git clone https://github.com/maoschanz/drawing.git`)
- Open it as a project with GNOME Builder
- Be sure the runtime is installed
- Run it (or export it as a `.flatpak` bundle)

## Install on your system with meson

Dependencies:

| Distribution | Package names | Packages for building |
|--------------|---------------|-----------------------|
| Debian       | `python3-gi python3-gi-cairo gir1.2-gtk-3.0` | `meson appstream-util libglib2.0-dev-bin` |
| ...          | `???` | `meson ??? ???` |

(feel free to complete with other distros)

```
git clone https://github.com/maoschanz/drawing.git
cd drawing
meson _build
ninja -C _build
sudo ninja -C _build install
```

The app can then be removed with:
```
sudo ninja uninstall
```

You can also build a debian package with the script `deb_package.sh` and install/uninstall it.

## With flatpak-builder (not recommended, that's just for me)

Initial installation:
```
wget https://raw.githubusercontent.com/maoschanz/drawing/master/com.github.maoschanz.drawing.json
flatpak-builder --force-clean _build2/ --repo=_repo com.github.maoschanz.drawing.json
flatpak --user remote-add --no-gpg-verify local-drawing-repo _repo
flatpak --user install local-drawing-repo com.github.maoschanz.drawing
```

Update:
```
flatpak-builder --force-clean _build2/ --repo=_repo com.github.maoschanz.drawing.json
flatpak update
```
