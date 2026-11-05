# Getting Started: Build and Change the LCC Node Examples

This guide gets your computer ready to build, run and change the LCC node examples in this
family, even if you have never set up a programming environment. You install one program and
start a subscription. From there, Claude (Anthropic's AI assistant) works through the rest with
you, asks before it installs anything, and test-builds an example to prove the setup works.

The examples:

| Example | What it does |
|---|---|
| [LCC_RPiPico_PixelLights](https://github.com/bocabob/LCC_RPiPico_PixelLights) | Drives up to four NeoPixel LED strings from LCC events and the fast clock |
| [LCC_RPiPico_Clock_Lights](https://github.com/bocabob/LCC_RPiPico_Clock_Lights) | Shows a fast clock on a touch screen and drives NeoPixel accessory lights |
| [LCC_RPiPico_Roundhouse](https://github.com/bocabob/LCC_RPiPico_Roundhouse) | Opens and closes roundhouse doors with servos |
| [LCC_RPiPico_Turntable](https://github.com/bocabob/LCC_RPiPico_Turntable) | Runs a stepper-motor turntable with a touch screen |

They run on the [LCC Pico Node board](https://github.com/bocabob/LCC-RPi-Pico-Board), a
Raspberry Pi Pico 2 carrier board with the CAN hardware LCC needs.

## What you need

- **A computer** running Windows, macOS or Linux. These steps have only been tested on Windows.
  The other two should work, but expect Claude to have to adapt a few things.
- **A Claude subscription: Pro or higher.** The free plan does not include Claude Code, the part
  of Claude that can work on your computer. See step 1 for the cost.
- **About an hour,** most of it waiting on downloads.
- **Free disk space:** about 3 GB for the Arduino tools, and about 5 GB more if you add KiCad.
- **For running a node, not for building one:** a Pico 2, a USB data cable, and a Node board. You
  can do everything up to the first upload with no hardware at all.

## Step 1: Get a Claude subscription

Go to [claude.com/pricing](https://claude.com/pricing) and sign up for **Pro** or higher. In
November 2026, Pro costs $20 a month, or $17 a month if you pay $200 for the year, before tax.
Check that page for current prices.

Pro is plenty for this setup and for making changes to an example. If you later work on the
firmware for long stretches and keep hitting the usage limit, Max offers more.

## Step 2: Install the Claude desktop app

Download it from [claude.com/download](https://claude.com/download), install it and sign in.

On Linux the app is in beta and needs Ubuntu 22.04 or later, or Debian 12 or later. On other Linux
systems, use the [Claude Code command-line version](https://code.claude.com/docs/en/setup) instead.

## Step 3: Make a folder for your work

Create a folder called `Arduino` inside your `Documents` folder, unless it already exists. Everything
goes here: the examples, the libraries they use, and your own projects. It's also where the Arduino
tools look by default.

> **If your Documents folder syncs to OneDrive or iCloud,** use a folder outside it, such as
> `C:\Arduino`, and tell Claude you did. Sync services can interfere with builds and with Git.

## Step 4: Start Claude on the setup

1. Open the Claude app and click the **Code** tab at the top of the sidebar.
2. In the environment selector, choose the top entry under **Local**.
3. Click the project folder control beside it, choose **Open folder…**, and pick the folder from step 3.
4. Leave the permission mode, shown under the prompt box, on **Manual**. Claude then has to ask you
   before it changes or runs anything. That suits a first setup, because you see each step.
5. Paste this message and press Enter:

```text
I want to set up this computer to build and modify Bob Gamble's LCC node examples.
Please read https://raw.githubusercontent.com/bocabob/LCC_RPiPico_Common/master/SETUP_FOR_CLAUDE.md
and use it as the guide for this setup. I'm in charge: check what I already have, show me
your plan, and ask me before you install anything.
```

That file holds the details Claude needs: which tools, which versions, which libraries, and the
problems others have already run into. It's plain text, so you can [read it
yourself](SETUP_FOR_CLAUDE.md) before you start. You can also follow it by hand if you'd rather not
use Claude.

## Step 5: Work through it together

Claude will:

1. Ask which examples you want and which optional tools you'd like.
2. Check what's already on your computer, without changing anything.
3. Show you a plan and wait for your OK.
4. Install what's missing: Git, Arduino IDE, arduino-cli, the Pico 2 board support, and the libraries.
5. Download the examples and build one to prove that everything works.

The optional tools:

| Tool | What it's for | Who needs it |
|---|---|---|
| **KiCad** | Viewing or changing the circuit board designs | Anyone who wants to modify or order boards |
| **Visual Studio Code** | A more capable code editor than the Arduino IDE | Anyone who plans to read or edit a lot of code |
| **JMRI** | Configuring a running node over the LCC bus | Anyone putting a node on a layout (you also need a USB-LCC adapter) |
| **GitHub account** | Saving your changes online and sharing them | Anyone who wants a backup or plans to share changes |

Some steps only you can do, and Claude will tell you when:

- Approving each command it asks to run.
- Clicking **Yes** on any installer's permission pop-up.
- Signing in to anything. **Never paste a password or access token into the chat.** Claude doesn't
  need them, and if it ever asks, say no.
- Pressing the button on the Pico and plugging in the cable.

Ask questions as you go. "What does that do?" and "Why do I need this?" are good ones.

## Step 6: Put the firmware on a Pico 2

The first upload goes like this in the Arduino IDE. Claude can also upload for you from the command line.

1. Hold the **BOOTSEL** button on the Pico 2 while you plug it into your computer's USB port.
2. In the Arduino IDE, open the example's `.ino` file and select **Tools > Board > Raspberry Pi
   Pico/RP2040/RP2350 > Raspberry Pi Pico 2**.
3. Select **Tools > Flash Size > 4MB (Sketch: 2MB, FS: 2MB)** and **Tools > Optimize > Small
   (-Os) (standard)**. Claude's setup file lists the rest of the settings.
4. Select **Tools > Port > UF2 Board** and click **Upload**.
5. Afterward, select the new serial port under **Tools > Port**. Later uploads don't need the
   BOOTSEL button.

**Check the Flash Size setting before each upload.** The IDE remembers it for each sketch, and it has
been known to lose it. These examples still build and run with the wrong setting, but updating the
firmware over LCC can then fail.

To see what the node is doing, open **Tools > Serial Monitor** and set the speed to 115200.

## Step 7: Give each node its own ID

Every LCC node needs a unique ID, and none of the examples should go on your layout with its built-in
one. Those defaults come from a range registered to the author, `05.01.01.01.94.xx`.

1. [Request your own range](https://registry.openlcb.org/requestuniqueidrange) from the OpenLCB
   registry.
2. With the node on your bench, type this in the Serial Monitor, using your own ID in place of the
   example: `N050101019422`.
3. The node asks you to confirm. Type `Y`. It saves the ID and restarts.

The ID survives firmware updates and configuration resets, so you only do this once per node.

## Step 8: Change an example to suit your layout

Start a new Claude session in the Code tab, and this time open the example's own folder. Claude reads
that project's `CLAUDE.md` and this repo's Node Standard, so it follows the same rules the examples
were built with. Describe what you want in your own words:

- *"Walk me through how this project is organized. I've never read Arduino code before."*
- *"I have a Node board v3.0. Is this project set up for it, and what would I change for a different
  board?"*
- *"Add a fifth lighting group that turns on with its own LCC event, and make it configurable in
  JMRI."*
- *"The servo for door 3 moves the wrong way. Help me find out why."*

Three rules are worth knowing, and Claude will apply them for you:

- **Pick your board in `ProjectConfig.h`.** Pin numbers live in `board_configs/`, not in the code.
- **Leave `src/openlcb/` and `src/drivers/canbus/` alone.** That's the shared OpenLcbCLib library.
- **When the node's configuration changes, three things change together:** `CDI.xml`, the compiled
  copy of it in `openlcb_user_config.c`, and the version number `EEPROM_VERSION`.

To keep your changes safe, ask Claude to help you fork the example on GitHub so you have your own copy.
Then commit each working change.

## Changing the circuit boards

The board designs are in [LCC-RPi-Pico-Board](https://github.com/bocabob/LCC-RPi-Pico-Board). You need
**KiCad 9 or newer** to open them. A newer KiCad will convert a file when you save it, and older
versions can't open it after that.

The `Documentation` folder there has the user guides and schematics, and the `gerbers` folder has
files ready to order from a board maker. Not every design there has been built and tested. The v3.0
Node board is the one the examples run on.

## If something goes wrong

Your first move is to tell Claude what happened and paste the exact error message. It has a list of
known problems to check. These come up most often:

| What you see | What's going on |
|---|---|
| The first build seems stuck | It can take several minutes while it builds the Pico support. Later builds are much faster. |
| `LibPrintf.h: No such file or directory` with `arduino-cli`, though it's installed | A setting in the example's `sketch.yaml` hides your libraries. Claude's setup file has the fix. |
| No **UF2 Board** under Tools > Port | Hold BOOTSEL while plugging in, and try another cable. Many USB cables only carry power. |
| The Arduino IDE can't find your Pico | The Microsoft Store version of the IDE has this problem. Install the one from [arduino.cc](https://www.arduino.cc/en/software). |
| Strange linker errors on Windows | The Pico compiler can fail if your Windows user name has non-English characters. Tell Claude. |
| Claude says you've hit your usage limit | Wait for it to reset and pick up where you left off, or look at a higher plan. |

The [OpenLCB Groups.io community](https://groups.io/g/openlcb) can help with LCC questions.

## Safety and licensing

**These are hobby projects, not certified products.** They have had no FCC or other compliance testing,
they aren't toys, and they come with no warranty. Build and use them at your own risk. Read the
**Safety** section in each example's README before you power anything up. In particular:

- **USB is for the bench.** A USB cable to a mains-powered computer ties the computer's ground to the
  node's, and through the LCC bus to your layout's, which can create a ground loop. On the layout,
  configure the node over the LCC bus.
- **Use listed (UL or ETL) power supplies, and fuse them** for the wiring they feed.
- **Don't leave a node running unattended.**

The code here is under the BSD 2-Clause license, and the board designs are under CERN-OHL-S-2.0. Some
libraries have stricter terms. If you give someone else a firmware build, read that example's
`THIRD_PARTY_NOTICES.md` first, because you may have to provide its source code too.

Claude can make mistakes, especially with hardware it can't see. Before you power up a change, check
any wiring or pin assignment it suggests against the board's schematic.
