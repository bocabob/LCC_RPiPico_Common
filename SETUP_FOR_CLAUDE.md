# Development Environment Setup: Guide for Claude

This file is for a Claude session helping someone set up a computer to build, flash and modify the
`LCC_RPiPico_*` node examples. The person-facing version of this process is
[`GETTING_STARTED.md`](GETTING_STARTED.md). Everything here is also readable by a person who wants to
do the setup by hand.

The person is probably a model railroader, not a programmer. Assume they're capable and new to this:
explain what each step is for in a sentence, and define terms like "library" or "commit" the first
time they come up.

## How to run this setup

The person stays in charge throughout:

- **Look before changing anything.** Do [step 2](#2-check-what-is-already-installed) first, then show
  a short plan: what you'd install, where from, and roughly how large. Wait for their OK.
- **Install only what's listed here or what they ask for.** Skip anything already installed and
  working. Don't upgrade or remove an existing tool without asking, since they may use it for other
  projects.
- **Use the official sources listed here.** Don't use mirrors or third-party installers.
- **Sign-ins are theirs.** They run commands like `gh auth login` themselves, in a terminal. Never ask
  them to paste a password or token into the chat.
- **Leave the example repos unmodified,** except for the local `sketch.yaml` change in
  [step 6](#6-build-an-example). Don't commit or push unless they ask.
- **Flash hardware only when they ask,** with the board on a bench.
- **Report what happened.** If a step fails or you couldn't test something, say so, and show the error.
  This file was tested on Windows only, so tell macOS and Linux users that you may need to adapt it.

## 1. Ask what they want

| Question | Options |
|---|---|
| Which examples? | `LCC_RPiPico_PixelLights`, `LCC_RPiPico_Clock_Lights`, `LCC_RPiPico_Roundhouse`, `LCC_RPiPico_Turntable`, or all four. PixelLights has the fewest dependencies, so suggest it if they're unsure. |
| Which optional tools? | VS Code, KiCad, JMRI, GitHub CLI. See [step 8](#8-optional-tools). |
| Where should the work live? | The folder this session is open in, normally `Documents/Arduino`. Move away from it if it syncs to OneDrive, iCloud or similar. |
| What hardware do they have? | None is needed to build. Flashing needs a Pico 2 and a USB data cable. |

`LCC_NODE_STANDARD.md` also names `LCC_RPiPico_CommandStation` and `LCC_RPiPico_Booster`. Those repos
are private, so they can't be cloned, and this setup doesn't cover them.

## 2. Check what is already installed

Change nothing in this step. Run each check, and report a short table of what's found.

```bash
git --version
arduino-cli version
arduino-cli config get directories.user
arduino-cli config get board_manager.additional_urls
arduino-cli core list
arduino-cli lib list
```

A "command not found" here just means that tool still needs installing. Also check for the Arduino IDE, plus VS
Code and KiCad if they asked for them. On Windows, installed programs are listed under
`HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*` and the same path under `HKCU:`.

Check these two Windows problems now, because each one causes confusing failures later:

- **Non-ASCII Windows user name.** The arduino-pico toolchain fails with linker errors if the user name
  has non-ASCII characters. If so, stop and explain the fix: an ASCII-only Windows user account.
- **Microsoft Store Arduino IDE.** It has trouble detecting a Pico. If that's the version installed,
  recommend replacing it with the one from arduino.cc.

## 3. Install the tools

Required: Git, Arduino IDE 2, and arduino-cli.

| Tool | Windows (`winget`) | macOS (Homebrew) | Official page |
|---|---|---|---|
| Git | `winget install --id Git.Git -e` | `brew install git` | <https://git-scm.com/install/> |
| Arduino IDE 2 | `winget install --id ArduinoSA.IDE.stable -e` | `brew install --cask arduino-ide` | <https://www.arduino.cc/en/software> |
| arduino-cli | `winget install --id ArduinoSA.CLI -e` | `brew install arduino-cli` | <https://arduino.github.io/arduino-cli/latest/installation/> |

On Linux, use the distribution's package for Git, the AppImage from the Arduino page for the IDE, and
the official pages above for the others.

A terminal opened before an install won't see the new command. If one isn't found afterward, open a new
terminal or use its full path before you conclude that the install failed.

## 4. Set up the Arduino tools

**Use Earle Philhower's Arduino-Pico core, never the Mbed-based `arduino:mbed_rp2040`.** Both offer boards
called "Raspberry Pi Pico".

The IDE and arduino-cli keep **separate settings** but share the same installed cores. Both need the same
board URL and the same sketchbook folder, or a library installed by one won't be seen by the other.

```bash
arduino-cli config init
arduino-cli config add board_manager.additional_urls https://github.com/earlephilhower/arduino-pico/releases/download/global/package_rp2040_index.json
arduino-cli config set directories.user "<the work folder>"
arduino-cli core update-index
arduino-cli core install rp2040:rp2040
```

`config init` reports an error if a config file already exists. That's fine, so carry on.

Then have the person make the same two settings in the IDE, in **File > Preferences**:

- **Sketchbook location:** the work folder.
- **Additional boards manager URLs:** the URL above.

## 5. Install the libraries

All of these go in `<work folder>/libraries`.

| Library | Install command | Needed by |
|---|---|---|
| ACAN2517 | `arduino-cli lib install ACAN2517` | All |
| I2C_EEPROM (Rob Tillaart) | `arduino-cli lib install I2C_EEPROM` | All |
| LibPrintf | `arduino-cli lib install LibPrintf` | All |
| NeoPixelBus by Makuna | `arduino-cli lib install "NeoPixelBus by Makuna"` | PixelLights, Clock_Lights, Roundhouse, Turntable |
| NeoPixelConnect | `arduino-cli lib install NeoPixelConnect` | Roundhouse, Turntable |
| RA8876_RP2040 | `git clone https://github.com/bocabob/RA8876_RP2040.git` | Clock_Lights. Turntable only if `DISPLAY_DRIVER_RA8876_NATIVE` is selected. |
| TFT_eSPI_RA8876 | `git clone https://github.com/bocabob/TFT_eSPI_RA8876.git` | Turntable |
| Adafruit-Servo-Driver-Library-Pi-Pico | `git clone https://github.com/grzesiek2201/Adafruit-Servo-Driver-Library-Pi-Pico.git` | Roundhouse |

Run the three `git clone` commands from inside `<work folder>/libraries`. Those three aren't in the Arduino
Library Manager. The servo library is what provides `PCA9685_servo.h` and `PCA9685_servo_driver.h`, even
though some READMEs make those sound like Library Manager entries. It has no `library.properties`, so it
shows up without a version number, which is normal.

Don't add libraries beyond this table to fix a build. In particular:

- `PicoOTA`, `LittleFS`, `Wire`, `SPI` and `EEPROM` come with the core.
- The OpenLCB stack is vendored in each example's `src/`. Don't install it separately.
- `AccelStepper` and `my_bb_captouch` are modified copies under Turntable's `src/application_drivers/`.
  Don't install the stock versions for this project.
- `Adafruit_EEPROM_I2C.h`, `Adafruit_FRAM_I2C.h`, `FRAM.h`, `driver/gpio.h` and `driver/i2c.h` appear in
  `#include` lines that are switched off in the default configuration.

## 6. Build an example

Clone with Git from inside the work folder. Clone `LCC_RPiPico_Common` too, because each example's
`CLAUDE.md` and README link to it by relative path.

```bash
git clone https://github.com/bocabob/LCC_RPiPico_Common.git
git clone https://github.com/bocabob/LCC_RPiPico_PixelLights.git
```

Use the same form for `LCC_RPiPico_Clock_Lights`, `LCC_RPiPico_Roundhouse` and `LCC_RPiPico_Turntable`, if they
chose those.

Keep the repos side by side, and keep their folder names. A sketch folder has to match its `.ino` file
name, and that's why a GitHub ZIP download fails: it adds `-main` to the folder name.

**Check `sketch.yaml` before building.** A current copy has only comments and a `default_fqbn` line. An older
copy or a fork may also have a `profiles:` section or a `default_profile:` line. With either of those,
`arduino-cli` excludes every library you just installed, even if you pass `--libraries` or `--fqbn`, and the build
stops with `fatal error: LibPrintf.h: No such file or directory`. Run `git pull` to get the current file. If that
isn't possible, replace the whole file with this one line:

```yaml
default_fqbn: rp2040:rp2040:rpipico2:flash=4194304_2097152,dbgport=Disabled,dbglvl=None,usbstack=picosdk,opt=Small,rtti=Disabled,stackprotect=Disabled,exceptions=Disabled,ipbtstack=ipv4only,uploadmethod=default,profile=Disabled
```

That's the form [`LCC_NODE_STANDARD.md` §10.1](LCC_NODE_STANDARD.md#101-firmware-upgrade-through-lcc)
prescribes. Tell the person it's a local change to leave uncommitted. A comment that only mentions profiles
isn't a problem, so leave a current file alone. The IDE doesn't read `sketch.yaml`, so this affects `arduino-cli`
only.

Then build, from inside the example's folder:

```bash
arduino-cli compile .
```

The first build takes several minutes because it compiles the core, so run it in the background if you can,
and warn the person. A successful build ends with `Sketch uses ...` and `Global variables use ...`. Compare
with [Tested configuration](#tested-configuration).

Turntable prints `TOUCH_CS pin not defined` several times. That's expected, because its touch screen goes through
its own `my_bb_captouch` copy rather than the display library's touch functions.

Don't use `--export-binaries` (`-e`). It writes into the example's `build/` folder, which is tracked by Git.
That folder's prebuilt images are older than the source, so build from source instead of flashing them.

Setup is done when this build succeeds. Tell the person plainly what was and wasn't verified.

## 7. Set up the IDE and flash

The Arduino IDE keeps board settings **for each sketch** and has lost them before, so have the person check
these under **Tools** for each example they open. Only the IDE needs this.

| Menu | Setting |
|---|---|
| Board | Raspberry Pi Pico/RP2040/RP2350 > **Raspberry Pi Pico 2** |
| Flash Size | **4MB (Sketch: 2MB, FS: 2MB)** |
| Optimize | **Small (-Os) (standard)** |
| USB Stack | Pico SDK |
| RTTI, Stack Protector, C++ Exceptions, Debug Port, Profiling | Disabled |
| Debug Level | None |
| IP/Bluetooth Stack | IPv4 Only |
| Upload Method | Default (UF2) |

The Flash Size matters most. It needs the 2 MB filesystem for firmware upgrades over LCC. CommandStation's
build stops if it's wrong, but these four examples don't have that guard yet: they build and run with the
wrong setting, and the upgrade fails later.

**First upload:** the person holds BOOTSEL while plugging in the Pico 2, selects **Tools > Port > UF2 Board**,
and clicks Upload. Then they select the new serial port. Later uploads reset the board automatically, unless
the board has hung.

**With arduino-cli:** find the port with `arduino-cli board list`, then run `arduino-cli upload -p <port> .`.

**Serial console:** 115200 baud, in the IDE's Serial Monitor or `arduino-cli monitor -p <port> -c baudrate=115200`.
The commands are in `LCC_NODE_STANDARD.md` §11. `c`, `i` and `r` erase configuration, so don't send them
without explaining that first.

**Node ID:** an unprovisioned node warns on the console and uses `NODE_ID_DEFAULT`, which is in the author's
registered range (`05.01.01.01.94.xx`). That's fine on a bench but not on a layout. The person should request
their own range at <https://registry.openlcb.org/requestuniqueidrange>, then send `N<12 hex digits>` and
confirm with `Y` (§7.1). Never pick an ID for them or suggest one from the author's range. If two nodes share
one image, each still needs its own ID.

**USB is for the bench** (§4.1). A USB cable to a mains-powered PC ties its ground to the node's and, through
the LCC bus, to the layout's. On a layout, use the LCC bus or an isolated USB-LCC adapter.

You can't see the hardware. Don't claim a node works based on a build alone. Ask the person what the console
shows.

## 8. Optional tools

**VS Code** (`winget install --id Microsoft.VisualStudioCode -e`, `brew install --cask visual-studio-code`, or
<https://code.visualstudio.com/download>). It's for editing. Build with `arduino-cli` in its terminal, or with
the IDE. Install the C/C++ extension: `code --install-extension ms-vscode.cpptools`. Two tracked settings need
attention:

- `.vscode/extensions.json` recommends PlatformIO. Decline that prompt, since these projects don't use it.
- `.vscode/settings.json` and `.vscode/c_cpp_properties.json` hard-code `C:/GdriveBG/Arduino/libraries/**`. This
  only affects code navigation and red squiggles, not builds. If the person wants it fixed, change that path to
  their `<work folder>/libraries/**`, and leave the change uncommitted.

**KiCad** (`winget install --id KiCad.KiCad -e`, `brew install --cask kicad`, or
<https://www.kicad.org/download/>). The boards are at <https://github.com/bocabob/LCC-RPi-Pico-Board>. The files
are in KiCad 9 format, so they need **KiCad 9 or newer**. Warn the person that saving in a newer version converts
the file, and older versions can't open it after that. On Windows `kicad-cli` isn't on the PATH: it's in
`C:\Program Files\KiCad\<version>\bin`. Clone the repo outside `libraries`. It isn't a sketch, so it can live
anywhere, though beside the examples is tidy.

KiCad will warn about missing libraries when a project opens. The repo's `fp-lib-table` and `sym-lib-table` include
entries that point to the author's own `C:/GdriveBG/KiCad` folder, including `SLW-864587-2A-RA-N-D.kicad_sym`, and
those files aren't in the repo. Parts already placed are stored in the design files, so viewing, plotting and
ordering don't need them. Placing a new copy of one of those parts or updating it from its library would.

**JMRI** (<https://www.jmri.org/download/>). It configures running nodes over LCC through its OpenLCB tools. JMRI
5.16 needs Java 11 or later and recommends Java 21. It also needs a USB-LCC adapter, and it should be an isolated
one on a layout (§4.1). This setup has no way to test the connection without that hardware.

**GitHub CLI** (`winget install --id GitHub.cli -e`, `brew install gh`, or <https://cli.github.com/>). The person
runs `gh auth login` themselves. It's needed for forking, not for cloning these public repos. To keep their
changes, they can fork from the example's folder with `gh repo fork --remote`. Before forking, make sure they
understand a fork of a public repo is public.

## 9. When they start changing an example

Open a new session in the example's folder, so its `CLAUDE.md` loads. Then read
[`LCC_NODE_STANDARD.md`](LCC_NODE_STANDARD.md), which is the source of truth and overrides anything here about
conventions. The rules people run into first:

- **Board choice:** `ProjectConfig.h` is the single switch (§4). Pin numbers belong in `board_configs/` (§3).
- **Vendored stack:** don't edit `src/openlcb/` or `src/drivers/canbus/` (§10).
- **LCC events:** `callbacks.cpp` is the only integration point (§3, §10).
- **Core 0:** no blocking calls (§8). EEPROM writes are deferred, never made from a callback (§7).
- **Configuration changes:** when `CDI.xml` changes, regenerate `_cdi_data[]` with `cdi_to_c_array.py` and
  bump `EEPROM_VERSION` (§7). A stale byte array or layout misreads stored settings without any error.
- **Identity:** a modified node should say it's theirs. See §7.3 for the SNIP fields, which `CDI.xml` has to
  mirror.
- **Licensing:** firmware images can inherit AGPL or GPL terms from their libraries, so before someone distributes
  a build, point them to that example's `THIRD_PARTY_NOTICES.md`.

To run `cdi_to_c_array.py` on Windows, use `py -3`. In some shells `python` resolves to a Microsoft Store stub that
prints "Python was not found". The script only uses the standard library, so if Python is missing, offer
`winget install --id Python.Python.3.13 -e`.

Pin assignments and wiring affect real hardware. Check them against the schematics in the board repo before
telling someone to power up, and say so when you haven't been able to.

## Known problems

| Symptom | Cause | Fix |
|---|---|---|
| `fatal error: LibPrintf.h: No such file or directory` from arduino-cli, with the library installed | A `profiles:` section or `default_profile:` line in an older `sketch.yaml` | `git pull`, or the one-line `sketch.yaml` in [step 6](#6-build-an-example). Passing `--libraries` or `--fqbn` doesn't help. |
| A library installed with the CLI is missing in the IDE, or the reverse | Separate sketchbook settings | Match `directories.user` and the IDE's Sketchbook location ([step 4](#4-set-up-the-arduino-tools)). |
| `rp2040:rp2040` reported as not found | Board URL missing | Add it, then run `arduino-cli core update-index`. |
| IDE can't detect the Pico | Microsoft Store version of the IDE | Install from arduino.cc. |
| No UF2 Board port | Not in BOOTSEL mode, or a charge-only cable | Hold BOOTSEL while plugging in. Try another cable. |
| Linker errors from `pqt-gcc` on Windows | Non-ASCII user name | An ASCII-only user account. |
| `Python was not found` | Microsoft Store stub | Use `py -3`, or install Python. |
| IDE won't open the sketch, or wants to move it | Folder name doesn't match the `.ino` (usually a ZIP download) | Clone with Git. |
| Links to `../LCC_RPiPico_Common` are broken | Repos aren't side by side, or Common isn't cloned | Clone Common beside the example. |
| Firmware upgrade over LCC fails at `LittleFS.begin()` | Flash Size lost its filesystem | Set Flash Size in the IDE and re-flash ([step 7](#7-set-up-the-ide-and-flash)). |
| Git shows changes in `.vscode/` or `sketch.yaml` | The local changes from this setup | Expected. Leave them uncommitted. |
| On Linux, the serial port is denied | Permissions | Add the user to the `dialout` group, then log out and back in. |

If you find a new problem and fix it, tell the person. They might want to report it at
<https://github.com/bocabob/LCC_RPiPico_Common/issues>.

## Tested configuration

Last tested 2026-11-05 on Windows 11. Each example was built from its `main` branch with a plain
`arduino-cli compile .`, in a test sketchbook that held only the libraries in [step 5](#5-install-the-libraries).

| Example | Program storage | Global variables |
|---|---|---|
| PixelLights | 145,716 bytes (6%) | 35,688 bytes (6%) |
| Clock_Lights | 1,111,184 bytes (53%) | 46,752 bytes (8%) |
| Roundhouse | 141,280 bytes (6%) | 35,640 bytes (6%) |
| Turntable | 268,756 bytes (12%) | 53,064 bytes (10%) |

These sizes will drift as the examples change. Numbers in the same range are a good sign, not a requirement.

| Component | Version |
|---|---|
| arduino-cli | 1.4.1 |
| Arduino-Pico core (`rp2040:rp2040`) | 6.3.2 |
| ACAN2517 | 1.1.16 |
| I2C_EEPROM | 1.9.4 |
| LibPrintf | 1.2.13 |
| NeoPixelBus by Makuna | 2.8.4 |
| NeoPixelConnect | 1.4.0 |
| RA8876_RP2040 | 1.0.0 |
| TFT_eSPI_RA8876 | 2.5.43 |
| Adafruit-Servo-Driver-Library-Pi-Pico | No version number; last changed upstream 2023-11-15 |

If a newer version breaks a build, try the one above, for example `arduino-cli lib install "ACAN2517@1.1.16"` or
`arduino-cli core install rp2040:rp2040@6.3.2`.

**Not covered by that test, so check these as you go:**

- A computer starting from nothing. The core and tools were already installed, though the libraries were isolated.
- arduino-cli 1.5, which is what `winget` currently installs.
- macOS and Linux.
- The Arduino IDE steps and the upload commands, which weren't run as part of this test. Nor was real hardware.
- KiCad on a computer without the author's library folder, and JMRI.
