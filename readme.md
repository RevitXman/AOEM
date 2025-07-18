# Discord Buff Request Bot

This bot allows users on a Discord server to request time-slotted capital buffs. It manages requests to prevent double-booking, automatically clears old requests, and notifies a specific role when a new request is made.

## Features

* **/requestbuff**: A slash command that guides users through a series of dropdowns to select a date (today or tomorrow), buff type, time slot, and region.
* **5-Minute Reminders**: Automatically pings the designated role 5 minutes before a buff is scheduled to start, mentioning who originally requested it.
* **Scheduled List**: Posts the full list of active buffs to a specific channel every 3 hours.
* **Name Input**: Users can choose to use their Discord name or enter a custom in-game name for the request.
* **Conflict Detection**: Prevents users from booking a time slot for a buff that is already taken.
* **/viewbuffs**: Displays a list of all current and upcoming buff requests with the requester's name in bold.
* **/clearbuffs**: An admin-only command to manually wipe all current requests.
* **Automatic Data Cleanup**: Automatically removes requests that are more than 49 hours old.
* **Logging**: All new requests and important events are logged to a `bot.log` file, which rotates automatically on a weekly basis.

---

## Setup Instructions for Ubuntu

Follow these steps to get the bot running on your Ubuntu server.

### Prerequisites

* An Ubuntu server (20.04 or newer is recommended).
* Python 3.8 or newer.

### Step 1: Create the Discord Bot Application

1.  **Go to the [Discord Developer Portal](https://discord.com/developers/applications)** and create a new application.
2.  **Go to the "Bot" tab.** Click "Add Bot".
3.  **Get the Bot Token:** Click **"Reset Token"** to reveal the bot's token. Copy this and save it.
4.  **Enable Privileged Intents:** On the "Bot" page, enable the **SERVER MEMBERS INTENT** and **MESSAGE CONTENT INTENT**. This is crucial for the bot to find users and read commands.

### Step 2: Invite the Bot and Get IDs

1.  **Invite the Bot:**
    * Go to "OAuth2" -> "URL Generator".
    * In "Scopes", check `bot` and `applications.commands`.
    * In "Bot Permissions", check `Send Messages`, `Embed Links`, and `Read Message History`.
    * Copy the generated URL and use it to invite the bot to your server.
2.  **Get IDs:**
    * Enable Developer Mode in Discord (User Settings > Advanced).
    * Right-click the role you want to ping (e.g., "@Title Teller") and **"Copy Role ID"**.
    * Right-click the channel where you want scheduled lists and reminders to be posted and **"Copy Channel ID"**.

### Step 3: Set Up the Bot on Your Server

1.  **Create a Directory:**
    ```bash
    mkdir -p ~/discord-bot
    cd ~/discord-bot
    ```
2.  **Create the Python Script (`main.py`):**
    Create the file and paste the Python code from the Canvas into it.
3.  **Create the `config.json` File:**
    This file stores your secrets and IDs.
    ```bash
    nano config.json
    ```
    Paste the following into the file, replacing the placeholder values.
    ```json
    {
      "token": "YOUR_DISCORD_BOT_TOKEN",
      "ping_role_id": "YOUR_DISCORD_ROLE_ID",
      "log_channel_id": "YOUR_CHANNEL_ID_FOR_SCHEDULED_LISTS"
    }
    ```
4.  **Set up Python Environment:**
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install discord.py
    ```

### Step 4: Run the Bot as a Systemd Service

1.  **Deactivate the virtual environment:** `deactivate`.
2.  **Create the Service File:**
    ```bash
    sudo nano /etc/systemd/system/discord-bot.service
    ```
3.  **Paste the following configuration.** Replace `your_user` with your Ubuntu username.
    ```ini
    [Unit]
    Description=Discord Buff Request Bot
    After=network.target
    
    [Service]
    User=your_user
    Group=your_user
    WorkingDirectory=/home/your_user/discord-bot
    ExecStart=/home/your_user/discord-bot/venv/bin/python main.py
    Restart=always
    RestartSec=10
    
    [Install]
    WantedBy=multi-user.target
    ```
4.  **Reload, Enable, and Start the Service:**
    ```bash
    sudo systemctl daemon-reload
    sudo systemctl enable discord-bot.service
    sudo systemctl start discord-bot.service
    ```
5.  **Check the Status:**
    ```bash
    sudo systemctl status discord-bot.service
    ```
    If it says "active (running)", your bot is live. A `bot.log` file will be created in the directory to log all requests.

---

## Changelog

**2025-07-18**
* Reminder message now includes the name of the user who made the request.
* Date picker shortened from 7 days to 2 days (today and tomorrow).
* "Imperial City" moved to the top of the region list for easier access.
* Data cleanup time adjusted from 48 to 49 hours.
* Fixed a bug in the reminder task's time-checking logic to ensure reminders are sent reliably.
* Fixed a bug where the bot could crash when comparing old, timezone-naive data with new, timezone-aware data.
* Updated code to use modern, non-deprecated `datetime.now(timezone.utc)` for all current time operations.

**Previous Versions**
* **Major Feature Update:** Implemented a date picker, 5-minute reminders for upcoming buffs, a scheduled task to post the buff list every 3 hours, and weekly rotating log files. Formatted the username in the buff list to be bold.
* **Refinement:** Split the confirmation message after a request into two parts: the list embed and a separate ping message.
* **Automation:** Added functionality to automatically post the updated buff list to the channel after a successful request.
* **Security & UI:** Added "Imperial City" to the region list and sanitized custom name input to prevent abuse.
* **User Experience:** Added the ability for users to provide a custom in-game name or use their Discord name.
* **Admin Tools:** Added the `/clearbuffs` command for administrators.
* **Simplification:** Removed the initial multi-language support in favor of a single-language (English) script to reduce complexity.
* **Initial Version:** Created the core bot with dropdowns for buff selection, conflict detection, and a 7-day data cleanup schedule.
