# Snips-Squeezebox :sound:

An app for [Snips.ai](https://snips.ai/) for controlling a Logitech Media Server.

### :construction: Work in progress :construction:

##### Table of Contents  
[Features](#i-features)  
[Installation](#ii-installation)  
[Configuration](#iii-configuration)  
[Usage](#iv-usage)  
[Troubleshooting](#v-troubleshooting)  
[Coming soon](#vi-coming-soon)  
[Contribution](#vii-contribution)  


## I. Features

- Control each of your devices from any room :house:
- If you don't mention the room, the system recognizes what room you're in :speech_balloon:
- Pauses automatically with the wakeword and plays after the Snips session :ear:
- Listen to any radio station and podcast :radio:
- Synchronize multiple players :hear_no_evil:
- Bluetooth speakers and headphones support :headphones:

##### Example Device Setup:

![Example Device Setup](./resources/Device%20Setup.png?raw=true "Example Device Setup")

## II. Installation

:exclamation: The following instructions assume that [Snips](https://snips.gitbook.io/documentation/snips-basics) is
already configured and running on your device (e.g. a Raspberry Pi 3 from the 
[Snips Maker Kit](https://makers.snips.ai/kit/) with 
[Raspbian](https://www.raspberrypi.org/downloads/raspbian/) Stretch Lite). 
[SAM](https://snips.gitbook.io/getting-started/installation) should
also already be set up and connected to your device and your account.

1. In the German [app store](https://console.snips.ai/) add the
app `Wecker & Alarme` (by domi; [this](https://console.snips.ai/store/de/skill_61Vz8lVkXQbM)) to
your *German* assistant.

2. You want to have a more unique alarmclock? Take a look at the section [Configuration](#iii-configuration) below and
see what you can change.

3. In the console scroll down to the parameters section.

    Now you may change some parameter values of the alarmclock.
    
4. If you already have the same assistant on your platform, update it with:
      ```bash
      sam update-assistant
      ```
      
   Otherwise install the assistant on the platform with the following command to
   choose it (if you have multiple assistants in your Snips console):
      ```bash
      sam install assistant
      ```
    
## III. Configuration

### 1. Normal (single-room specific)

In the Snips console or manually in the file `/var/lib/snips/skills/Snips-Wecker/config.ini` you can change
some parameters that influence the behaviour of the alarm clock app:

## VI. Coming soon

- Append podcasts to your queue
