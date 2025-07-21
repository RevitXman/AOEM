import discord
from discord import app_commands
from discord.ui import Select, View, Button, Modal, TextInput
import json
import os
from datetime import datetime, timedelta, date, timezone
import asyncio
import logging
from logging.handlers import TimedRotatingFileHandler

# --- Logging Setup ---
log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
log_handler = TimedRotatingFileHandler('bot.log', when='D', interval=7, backupCount=4) # Rotates weekly
log_handler.setFormatter(log_formatter)
logger = logging.getLogger()
# To see more detailed logs for debugging, change logging.INFO to logging.DEBUG
logger.setLevel(logging.INFO) 
logger.addHandler(log_handler)

# --- Configuration ---
# Add "log_channel_id" for the scheduled list posting.
# {
#   "token": "YOUR_DISCORD_BOT_TOKEN",
#   "ping_role_id": "YOUR_DISCORD_ROLE_ID",
#   "log_channel_id": "YOUR_CHANNEL_ID_FOR_SCHEDULED_LISTS"
# }
with open('config.json', 'r') as f:
    config = json.load(f)

DISCORD_TOKEN = config['token']
PING_ROLE_ID = int(config['ping_role_id'])
LOG_CHANNEL_ID = int(config['log_channel_id'])

# --- Data Management ---
DATA_FILE = "buff_requests.json"
sent_reminders = set() # To avoid duplicate reminders

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def cleanup_old_data():
    """Removes entries older than 49 hours, handling both naive and aware datetimes."""
    requests = load_data()
    if not requests:
        return

    # Use timezone-aware datetime object for comparison
    forty_nine_hours_ago = datetime.now(timezone.utc) - timedelta(hours=49)
    
    # Create a new dictionary to hold the requests we want to keep
    cleaned_requests = {}
    
    for req_id, req_data in requests.items():
        try:
            # Load the request time from the stored ISO string
            request_time = datetime.fromisoformat(req_data['request_time'])
            
            # FIX: If the loaded datetime is naive (from old data), make it aware by setting its timezone to UTC
            if request_time.tzinfo is None:
                request_time = request_time.replace(tzinfo=timezone.utc)
            
            # Keep the request if it's NOT older than 49 hours
            if request_time < forty_nine_hours_ago:
                cleaned_requests[req_id] = req_data
        except (ValueError, KeyError) as e:
            # This handles malformed or missing 'request_time' entries in the JSON
            logger.warning(f"Skipping request with ID {req_id} due to invalid time data: {e}")
            continue

    # Only save if there's a change
    if len(cleaned_requests) != len(requests):
        save_data(cleaned_requests)
        logger.info(f"Cleaned up {len(requests) - len(cleaned_requests)} old buff requests.")

# --- Bot Setup ---
intents = discord.Intents.default()
intents.members = True 
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# --- Helper Function ---
async def create_buffs_embed(guild: discord.Guild):
    requests = load_data()
    if not requests:
        return None

    embed = discord.Embed(title="Current Buff Requests", color=discord.Color.blue())
    sorted_requests = sorted(requests.values(), key=lambda x: x['time_slot'])

    for req in sorted_requests:
        user = guild.get_member(req['user_id'])
        user_mention = user.mention if user else f"User ID: {req['user_id']}"
        start_time_obj = datetime.fromisoformat(req['time_slot'])
        time_range_str = f"{start_time_obj.strftime('%Y-%m-%d %H:%M')} UTC"
        
        # Make the username bold
        field_name = f"Title: {req['title']} | Region: {req['region']}"
        field_value = f"User: **{user_mention} ({req['user_name']})**\nTime Slot: {time_range_str}"
        embed.add_field(name=field_name, value=field_value, inline=False)
    
    return embed

# --- UI Components ---

class ConfirmationView(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        self.confirmed = True
        # Start the main buff request process
        buff_view = BuffRequestView(interaction)
        await interaction.response.edit_message(content="Please select the details for your buff request.", view=buff_view)
        self.stop()

    @discord.ui.button(label="No", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        self.confirmed = False
        await interaction.response.edit_message(content="Please apply at the IC before continuing or DIOR will come knocking", view=None)
        self.stop()

class AoEMNameModal(Modal, title='Enter Your In-Game Name'):
    parent_view: 'BuffRequestView'
    name_input = TextInput(label='AoEM Name', placeholder='Enter your in-game name here...', style=discord.TextStyle.short, required=True, max_length=50)

    def __init__(self, view: 'BuffRequestView'):
        super().__init__(timeout=300)
        self.parent_view = view

    async def on_submit(self, interaction: discord.Interaction):
        await self.parent_view.finalize_request(interaction, self.name_input.value)

class UseDiscordNameButton(Button):
    def __init__(self):
        super().__init__(label="Use Discord Name", style=discord.ButtonStyle.primary, row=0)
    async def callback(self, interaction: discord.Interaction):
        await self.view.finalize_request(interaction, interaction.user.display_name)

class EnterCustomNameButton(Button):
    def __init__(self):
        super().__init__(label="Enter In-Game Name", style=discord.ButtonStyle.secondary, row=0)
    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(AoEMNameModal(view=self.view))

class BuffRequestView(View):
    def __init__(self, interaction: discord.Interaction):
        super().__init__(timeout=300)
        self.interaction = interaction
        self.buff_title = None
        self.time_slot = None
        self.region = None
        self.selected_date = None
        self.add_item(DateSelect())

    async def on_timeout(self):
        for item in self.children: item.disabled = True
        await self.interaction.edit_original_response(view=self)

    async def finalize_request(self, interaction: discord.Interaction, requester_name: str):
        await interaction.response.defer()
        for item in self.children: item.disabled = True
        await self.interaction.edit_original_response(content="Request submitted! The confirmation has been sent to the channel.", view=self)

        sanitized_name = discord.utils.escape_markdown(requester_name)
        requests = load_data()
        # Use timezone-aware datetime object
        request_time_utc = datetime.now(timezone.utc)
        start_time_obj = datetime.fromisoformat(self.time_slot)
        time_range_str = f"{start_time_obj.strftime('%H:%M')} UTC"

        request_id = str(request_time_utc.timestamp())
        requests[request_id] = {
            "user_id": interaction.user.id,
            "user_name": sanitized_name,
            "title": self.buff_title,
            "time_slot": self.time_slot,
            "region": self.region,
            "request_time": request_time_utc.isoformat()
        }
        save_data(requests)
        logger.info(f"New buff request by {interaction.user} ({sanitized_name}): {self.buff_title} in {self.region} at {self.time_slot}")

        embed = discord.Embed(title="New Capital Buff Request!", description=f"{interaction.user.mention} (**{sanitized_name}**) has requested the **{self.buff_title}** buff for **{start_time_obj.strftime('%Y-%m-%d')} at {time_range_str}** in the **{self.region}** region.", color=discord.Color.green())
        ping_role = interaction.guild.get_role(PING_ROLE_ID)
        ping_content = ping_role.mention if ping_role else f"@role({PING_ROLE_ID})"
        await interaction.channel.send(content=ping_content, embed=embed)

        updated_list_embed = await create_buffs_embed(interaction.guild)
        if updated_list_embed:
            await interaction.channel.send(embed=updated_list_embed)

class DateSelect(Select):
    def __init__(self):
        today = date.today()
        options = []
        # Show today and tomorrow
        for i in range(2):
            current_date = today + timedelta(days=i)
            options.append(discord.SelectOption(label=current_date.strftime('%A, %B %d'), value=current_date.isoformat()))
        super().__init__(placeholder="Step 1: Select a date...", options=options)
    
    async def callback(self, interaction: discord.Interaction):
        self.view.selected_date = self.values[0]
        self.disabled = True
        self.view.add_item(TitleSelect())
        await interaction.response.edit_message(view=self.view)

class TitleSelect(Select):
    def __init__(self):
        options = [discord.SelectOption(label=t, value=t) for t in ["Research", "Training", "Building", "Combat", "PvP"]]
        super().__init__(placeholder="Step 2: Select a buff title...", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.buff_title = self.values[0]
        self.disabled = True
        self.view.add_item(TimeSelect(self.view.selected_date))
        await interaction.response.edit_message(view=self.view)

class TimeSelect(Select):
    def __init__(self, selected_date_str: str):
        selected_date = date.fromisoformat(selected_date_str)
        options = []
        for i in range(24):
            # Create a timezone-aware datetime object for UTC
            dt_obj = datetime.combine(selected_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=i)
            label = f"{dt_obj.strftime('%H:%M')} - {(dt_obj + timedelta(hours=1)).strftime('%H:%M')} UTC"
            options.append(discord.SelectOption(label=label, value=dt_obj.isoformat()))
        super().__init__(placeholder="Step 3: Select a time slot (UTC)...", options=options)

    async def callback(self, interaction: discord.Interaction):
        requests = load_data()
        selected_time = self.values[0]
        for req in requests.values():
            if req['time_slot'] == selected_time and req['title'] == self.view.buff_title:
                await interaction.response.send_message("This time slot is already taken.", ephemeral=True)
                await self.view.interaction.edit_original_response(content="Selection conflict. Please start over.", view=BuffRequestView(self.view.interaction))
                return
        self.view.time_slot = selected_time
        self.disabled = True
        self.view.add_item(RegionSelect())
        await interaction.response.edit_message(view=self.view)

class RegionSelect(Select):
    def __init__(self):
        # Moved "Imperial City" to the top of the list
        regions = ["Imperial City", "Gaul", "Olympia", "Neilos", "Tinir", "East Kingsland", "Eastland", "Kyuno", "North Kingsland", "West Kingsland", "NA"]
        options = [discord.SelectOption(label=r, value=r) for r in regions]
        super().__init__(placeholder="Step 4: Select a region...", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.region = self.values[0]
        self.view.clear_items()
        self.view.add_item(UseDiscordNameButton())
        self.view.add_item(EnterCustomNameButton())
        await interaction.response.edit_message(content="Last step! Specify your name for the request.", view=self.view)

# --- Slash Commands ---
@tree.command(name="requestbuff", description="Request a capital buff.")
async def requestbuff(interaction: discord.Interaction):
    """Starts the buff request process with a confirmation step."""
    view = ConfirmationView()
    await interaction.response.send_message("Did you apply for the buff at the IC?", view=view, ephemeral=True)

@tree.command(name="viewbuffs", description="View all active buff requests.")
async def viewbuffs(interaction: discord.Interaction):
    """Displays the list of current buff requests."""
    # FIX: Add a check to ensure the command is used in a server.
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server channel.", ephemeral=True)
        return
        
    buff_list_embed = await create_buffs_embed(interaction.guild)
    if buff_list_embed:
        await interaction.response.send_message(embed=buff_list_embed)
    else:
        await interaction.response.send_message("There are no active buff requests.", ephemeral=True)

@tree.command(name="clearbuffs", description="[Admin] Manually clears all buff requests.")
@app_commands.checks.has_permissions(manage_guild=True)
async def clearbuffs(interaction: discord.Interaction):
    save_data({})
    sent_reminders.clear()
    logger.info(f"Buffs cleared manually by {interaction.user.name} ({interaction.user.id}).")
    await interaction.response.send_message("All buff requests have been cleared.", ephemeral=True)

@clearbuffs.error
async def on_clearbuffs_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You do not have permission.", ephemeral=True)
    else:
        logger.error(f"Error in clearbuffs command: {error}")
        await interaction.response.send_message("An error occurred.", ephemeral=True)

# --- Background Tasks ---
async def reminder_task():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            logger.debug("Reminder task checking for upcoming buffs...")
            requests = load_data()
            now_utc = datetime.now(timezone.utc)
            
            if not requests:
                logger.debug("Reminder check: No active requests found.")

            for req_id, req in requests.items():
                logger.debug(f"Checking request ID: {req_id}")
                if req_id in sent_reminders:
                    logger.debug(f"Skipping request {req_id}, reminder already sent.")
                    continue

                start_time = datetime.fromisoformat(req['time_slot'])
                time_diff = start_time - now_utc
                logger.debug(f"Request {req_id} starts at {start_time}. Time difference: {time_diff}")
                
                # Check if the time difference is between 4 and 5 minutes.
                if timedelta(minutes=4) < time_diff <= timedelta(minutes=5):
                    logger.info(f"Time condition met for request {req_id}. Preparing to send reminder.")
                    guild = client.guilds[0] # Assumes the bot is in one server
                    if not guild:
                        logger.warning("Reminder task could not find a guild.")
                        continue
                        
                    channel = guild.get_channel(LOG_CHANNEL_ID)
                    role = guild.get_role(PING_ROLE_ID)
                    user = guild.get_member(req['user_id'])
                    user_mention = user.mention if user else req['user_name']

                    if channel and role:
                        # Include the user who made the request in the reminder
                        reminder_msg = f"{role.mention} Reminder: The **{req['title']}** buff in **{req['region']}** requested by **{user_mention}** starts in 5 minutes!"
                        await channel.send(reminder_msg)
                        sent_reminders.add(req_id)
                        logger.info(f"Successfully sent 5-minute reminder for request {req_id}")
                    else:
                        if not channel:
                            logger.warning(f"Could not send reminder for {req_id}: Channel with ID {LOG_CHANNEL_ID} not found.")
                        if not role:
                            logger.warning(f"Could not send reminder for {req_id}: Role with ID {PING_ROLE_ID} not found.")
                else:
                    logger.debug(f"Time condition not met for request {req_id}. Skipping.")

        except Exception as e:
            logger.error(f"An unexpected error occurred in reminder_task: {e}", exc_info=True)
            
        await asyncio.sleep(60) # Check every minute

async def schedule_task():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            cleanup_old_data() # Also clean up data on this schedule
            guild = client.guilds[0]
            channel = guild.get_channel(LOG_CHANNEL_ID)
            if channel:
                embed = await create_buffs_embed(guild)
                if embed:
                    await channel.send("--- Scheduled Buff List Update ---", embed=embed)
                    logger.info("Posted scheduled buff list.")
        except Exception as e:
            logger.error(f"Error in schedule_task: {e}", exc_info=True)
            
        # Sleep for 12 hours
        await asyncio.sleep(12 * 60 * 60)

# --- Bot Events ---
@client.event
async def on_ready():
    await tree.sync()
    logger.info(f'Logged in as {client.user}!')
    print(f'Logged in as {client.user}!')
    
    # Start background tasks
    client.loop.create_task(reminder_task())
    client.loop.create_task(schedule_task())

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)