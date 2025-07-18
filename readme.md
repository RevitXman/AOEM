Discord Buff Request Bot
This bot allows users on a Discord server to request time-slotted capital buffs. It manages requests to prevent double-booking, automatically clears old requests, and notifies a specific role when a new request is made.

Features
/requestbuff: A slash command that guides users through a series of dropdowns to select a buff type, time slot, and region.

Name Input: Users can choose to use their Discord name or enter a custom in-game name for the request.

Conflict Detection: Prevents users from booking a time slot for a buff that is already taken.

/viewbuffs: Displays a list of all current and upcoming buff requests.

/clearbuffs: An admin-only command to manually wipe all current requests.

Automatic Data Cleanup: Automatically removes requests that are more than 24 hours old.

Setup Instructions for Ubuntu
Follow these steps to get the bot running on your Ubuntu server.

Prerequisites
An Ubuntu server (20.04 or newer is recommended).

Python 3.8 or newer.

git for cloning the repository.

You can install these with:

sudo apt update
sudo apt install python3 python3-pip python3-venv git -y

Step 1: Create the Discord Bot Application
Before setting up the server, you need to create the bot in Discord's Developer Portal.

Go to the Discord Developer Portal and click "New Application". Give it a name and click "Create".

Create a Bot User: In the left-hand menu, go to the "Bot" tab. Click "Add Bot", then "Yes, do it!".

Get the Bot Token: Under the bot's username, click "Reset Token" to reveal the bot's token. Copy this token and save it somewhere safe. This is your bot's password; do not share it.

Enable Privileged Intents: On the same "Bot" page, scroll down to "Privileged Gateway Intents" and enable the "Message Content Intent".

Invite the Bot to Your Server:

In the left-hand menu, go to "OAuth2" -> "URL Generator".

In the "Scopes" box, check bot and applications.commands.

A "Bot Permissions" box will appear below. Check the following permissions:

Send Messages

Embed Links

Read Message History

Copy the generated URL at the bottom of the page, paste it into your browser, and invite the bot to your Discord server.

Step 2: Get the Role ID to Ping
You need the ID of the role you want the bot to ping for new requests.

Enable Developer Mode in Discord: Go to User Settings > Advanced > and turn on "Developer Mode".

Copy Role ID: In your server, go to Server Settings > Roles. Right-click the role you want to ping and click "Copy Role ID". Save this ID.

Step 3: Set Up the Bot on Your Server
Now, let's configure the files on your Ubuntu machine.

Create a Directory for the Bot:

mkdir ~/discord-bot
cd ~/discord-bot

Create the Python Script:
Create a file named main.py and paste the entire Python script from the Canvas into it.

nano main.py 
# (Paste the code, then press CTRL+X, then Y, then Enter to save)

Create the config.json File:
This file will store your secret token and role ID.

nano config.json

Paste the following into the file, replacing the placeholder values with your actual bot token and role ID.

{
  "token": "YOUR_DISCORD_BOT_TOKEN",
  "ping_role_id": "YOUR_DISCORD_ROLE_ID"
}

Save and exit the editor.

Create a Python Virtual Environment:
It's best practice to run Python applications in a virtual environment.

python3 -m venv venv

Activate the Virtual Environment:

source venv/bin/activate

Your command prompt should now be prefixed with (venv).

Install Dependencies:
The bot requires the discord.py library.

pip install 

Step 4: Run the Bot Manually (for Testing)
You can run the bot directly from your terminal to make sure everything is working.

python3 main.py

If successful, you will see output like this, and the bot will appear as "online" in your Discord server:

Logged in as YourBotName#1234!
Synced X commands.

You can now test the /requestbuff and other commands in Discord. Press CTRL+C to stop the bot.

Step 5: Run the Bot as a Systemd Service
To ensure the bot runs 24/7 and restarts automatically if it crashes or the server reboots, you should run it as a systemd service.

Deactivate the virtual environment by typing deactivate.

Create the Service File:

sudo nano /etc/systemd/system/discord-bot.service

Paste the following configuration into the file. You MUST replace your_user with your actual Ubuntu username.

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

User/Group: Your Ubuntu username.

WorkingDirectory: The absolute path to your bot's folder.

ExecStart: The absolute path to the Python executable inside your virtual environment.

Reload, Enable, and Start the Service:

sudo systemctl daemon-reload
sudo systemctl enable discord-bot.service
sudo systemctl start discord-bot.service

Check the Status:
You can verify that the service is running correctly with:

sudo systemctl status discord-bot.service

If it says "active (running)", your bot is now running as a background service!

Your bot is now fully deployed and will run automatically.