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
    """Removes buff requests where the scheduled time slot is more than 24 hours in the past."""
    requests = load_data()
    if not requests:
        return

    twenty_four_hours_ago = datetime.now(timezone.utc) - timedelta(hours=24)
    
    # Use a list of keys to delete to avoid modifying the dictionary while iterating
    keys_to_delete = []
    
    for req_id, req_data in requests.items():
        try:
            # Base the cleanup on the 'time_slot' of the event
            time_slot = datetime.fromisoformat(req_data['time_slot'])
            
            # Make the datetime object timezone-aware if it's naive (for handling old data)
            if time_slot.tzinfo is None:
                time_slot = time_slot.replace(tzinfo=timezone.utc)
            
            # If the scheduled time is older than 24 hours ago, mark it for deletion
            if time_slot < twenty_four_hours_ago:
                keys_to_delete.append(req_id)
                # Add a detailed log message for each expired buff
                logger.info(f"Cleaning up expired buff: '{req_data.get('title', 'N/A')}' for user '{req_data.get('user_name', 'N/A')}' (Scheduled at: {req_data.get('time_slot', 'N/A')})")

        except (ValueError, KeyError) as e:
            logger.warning(f"Skipping request during cleanup with ID {req_id} due to invalid data: {e}")
            continue

    # If there are items to delete, remove them from the original dictionary and save
    if keys_to_delete:
        for key in keys_to_delete:
            if key in requests:
                del requests[key]
        save_data(requests)
        logger.info(f"Finished cleanup. Removed {len(keys_to_delete)} expired buff requests.")

# --- Bot Setup ---
intents = discord.Intents.default()
intents.members = True 
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# --- Helper Function ---
async def create_buffs_embeds(guild: discord.Guild, limit: int = None):
    """Creates and returns a list of embeds for the buff list, filtering out past events."""
    requests = load_data()
    if not requests:
        return []

    now_utc = datetime.now(timezone.utc)
    # Filter out any requests where the time slot has already passed
    future_requests = [req for req in requests.values() if datetime.fromisoformat(req['time_slot']) > now_utc]

    if not future_requests:
        return []

    if limit:
        # Sort by the event time to get the soonest upcoming buffs, then take the limit
        sorted_requests = sorted(future_requests, key=lambda x: x['time_slot'])[:limit]
        title = f"Next {limit} Upcoming Buffs"
    else:
        # If no limit, show all future requests sorted chronologically by event time
        sorted_requests = sorted(future_requests, key=lambda x: x['time_slot'])
        title = "Current Buff Requests"
    
    embeds = []
    current_embed = discord.Embed(title=title, color=discord.Color.blue())
    field_count = 0

    for req in sorted_requests:
        if field_count >= 25:
            embeds.append(current_embed)
            current_embed = discord.Embed(title=f"{title} (Cont.)", color=discord.Color.blue())
            field_count = 0

        start_time_obj = datetime.fromisoformat(req['time_slot'])
        time_range_str = f"{start_time_obj.strftime('%Y-%m-%d %H:%M')} UTC"
        
        field_name = f"Title: {req['title']} | Region: {req['region']}"
        field_value = f"User: **{req['user_name']}**\nTime Slot: {time_range_str}"
        current_embed.add_field(name=field_name, value=field_value, inline=False)
        field_count += 1
    
    embeds.append(current_embed)
    return embeds

# --- UI Components ---

class ConfirmationView(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.confirmed = None

    @discord.ui.button(label="Yes", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        self.confirmed = True
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

        # Display the next 10 upcoming buffs after a new request
        buff_embeds = await create_buffs_embeds(interaction.guild, limit=10)
        for an_embed in buff_embeds:
            await interaction.channel.send(embed=an_embed)

class DateSelect(Select):
    def __init__(self):
        today = date.today()
        options = []
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
        regions = ["Imperial City", "Gaul", "Olympia", "Neilos", "Tinir", "East Kingsland", "Eastland", "Kyuno", "North Kingsland", "West Kingsland", "NA"]
        options = [discord.SelectOption(label=r, value=r) for r in regions]
        super().__init__(placeholder="Step 4: Select a region...", options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.region = self.values[0]
        self.view.clear_items()
        self.view.add_item(UseDiscordNameButton())
        self.view.add_item(EnterCustomNameButton())
        await interaction.response.edit_message(content="Last step! Specify your name for the request.", view=self.view)

class MyBuffsView(View):
    def __init__(self, user_buffs: dict):
        super().__init__(timeout=180)
        self.user_buffs = user_buffs
        self.selected_buff_id = None

        options = []
        for req_id, req in user_buffs.items():
            start_time = datetime.fromisoformat(req['time_slot'])
            label = f"{req['title']} in {req['region']} at {start_time.strftime('%Y-%m-%d %H:%M')}"
            options.append(discord.SelectOption(label=label, value=req_id))

        self.buff_select = Select(placeholder="Select a buff to manage...", options=options)
        self.buff_select.callback = self.on_select
        self.add_item(self.buff_select)

        self.change_title_button = Button(label="Change Title", style=discord.ButtonStyle.secondary, disabled=True)
        self.change_title_button.callback = self.on_change_title
        self.add_item(self.change_title_button)

        self.change_time_button = Button(label="Change Time", style=discord.ButtonStyle.secondary, disabled=True)
        self.change_time_button.callback = self.on_change_time
        self.add_item(self.change_time_button)

        self.delete_button = Button(label="Delete Buff", style=discord.ButtonStyle.danger, disabled=True)
        self.delete_button.callback = self.on_delete
        self.add_item(self.delete_button)

    async def on_select(self, interaction: discord.Interaction):
        self.selected_buff_id = interaction.data['values'][0]
        self.delete_button.disabled = False
        self.change_title_button.disabled = False
        self.change_time_button.disabled = False
        await interaction.response.edit_message(view=self)

    async def on_change_title(self, interaction: discord.Interaction):
        view = ChangeTitleView(self.selected_buff_id)
        await interaction.response.edit_message(content="Please select the new title for your buff.", view=view)

    async def on_change_time(self, interaction: discord.Interaction):
        requests = load_data()
        if self.selected_buff_id not in requests:
            await interaction.response.edit_message(content="This buff seems to have been deleted or expired.", view=None)
            return
        
        original_buff_date = datetime.fromisoformat(requests[self.selected_buff_id]['time_slot']).date()
        view = ChangeTimeView(self.selected_buff_id, original_buff_date.isoformat())
        await interaction.response.edit_message(content="Please select the new time slot for your buff.", view=view)

    async def on_delete(self, interaction: discord.Interaction):
        requests = load_data()
        if self.selected_buff_id in requests:
            del requests[self.selected_buff_id]
            save_data(requests)
            logger.info(f"User {interaction.user} deleted their buff request (ID: {self.selected_buff_id})")
            
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(content="Your buff request has been successfully deleted.", view=self)
        else:
            for item in self.children:
                item.disabled = True
            await interaction.response.edit_message(content="This buff may have already been deleted or expired.", view=self)

class ChangeTitleView(View):
    def __init__(self, buff_id: str):
        super().__init__(timeout=180)
        self.buff_id = buff_id

        options = [discord.SelectOption(label=t, value=t) for t in ["Research", "Training", "Building", "Combat", "PvP"]]
        title_select = Select(placeholder="Select a new title for your buff...", options=options)
        title_select.callback = self.on_title_change
        self.add_item(title_select)

    async def on_title_change(self, interaction: discord.Interaction):
        new_title = interaction.data['values'][0]
        requests = load_data()

        if self.buff_id not in requests:
            await interaction.response.edit_message(content="This buff seems to have been deleted or expired.", view=None)
            return

        original_buff = requests[self.buff_id]
        original_time_slot = original_buff['time_slot']

        for req_id, req in requests.items():
            if req_id != self.buff_id and req['time_slot'] == original_time_slot and req['title'] == new_title:
                await interaction.response.edit_message(content=f"A **{new_title}** buff is already scheduled for this time slot.", view=None)
                return

        requests[self.buff_id]['title'] = new_title
        save_data(requests)
        logger.info(f"User {interaction.user} changed title for buff {self.buff_id} to {new_title}")
        await interaction.response.edit_message(content=f"Your buff's title has been changed to **{new_title}**.", view=None)

class ChangeTimeView(View):
    def __init__(self, buff_id: str, buff_date_str: str):
        super().__init__(timeout=180)
        self.buff_id = buff_id
        
        buff_date = date.fromisoformat(buff_date_str)
        options = []
        for i in range(24):
            dt_obj = datetime.combine(buff_date, datetime.min.time(), tzinfo=timezone.utc) + timedelta(hours=i)
            label = f"{dt_obj.strftime('%H:%M')} - {(dt_obj + timedelta(hours=1)).strftime('%H:%M')} UTC"
            options.append(discord.SelectOption(label=label, value=dt_obj.isoformat()))

        time_select = Select(placeholder="Select a new time slot...", options=options)
        time_select.callback = self.on_time_change
        self.add_item(time_select)

    async def on_time_change(self, interaction: discord.Interaction):
        new_time_slot = interaction.data['values'][0]
        requests = load_data()

        if self.buff_id not in requests:
            await interaction.response.edit_message(content="This buff seems to have been deleted or expired.", view=None)
            return

        original_title = requests[self.buff_id]['title']

        for req_id, req in requests.items():
            if req_id != self.buff_id and req['time_slot'] == new_time_slot and req['title'] == original_title:
                await interaction.response.edit_message(content=f"A **{original_title}** buff is already scheduled for this new time.", view=None)
                return

        requests[self.buff_id]['time_slot'] = new_time_slot
        save_data(requests)
        logger.info(f"User {interaction.user} changed time for buff {self.buff_id} to {new_time_slot}")
        new_time_obj = datetime.fromisoformat(new_time_slot)
        await interaction.response.edit_message(content=f"Your buff's time has been changed to **{new_time_obj.strftime('%Y-%m-%d %H:%M')} UTC**.", view=None)

# --- Slash Commands ---
@tree.command(name="requestbuff", description="Request a capital buff.")
async def requestbuff(interaction: discord.Interaction):
    view = ConfirmationView()
    await interaction.response.send_message("Did you apply for the buff at the IC?", view=view, ephemeral=True)

@tree.command(name="viewbuffs", description="View all active buff requests.")
async def viewbuffs(interaction: discord.Interaction):
    if not interaction.guild:
        await interaction.response.send_message("This command can only be used in a server channel.", ephemeral=True)
        return
        
    buff_embeds = await create_buffs_embeds(interaction.guild)
    if buff_embeds:
        await interaction.response.send_message(embed=buff_embeds[0])
        for embed in buff_embeds[1:]:
            await interaction.followup.send(embed=embed)
    else:
        await interaction.response.send_message("There are no active buff requests.", ephemeral=True)

@tree.command(name="mybuffs", description="View and manage your active buff requests.")
async def mybuffs(interaction: discord.Interaction):
    requests = load_data()
    now_utc = datetime.now(timezone.utc)
    
    user_buffs = {
        req_id: req for req_id, req in requests.items()
        if req.get('user_id') == interaction.user.id and datetime.fromisoformat(req['time_slot']) > now_utc
    }
    
    if not user_buffs:
        await interaction.response.send_message("You have no active, upcoming buff requests.", ephemeral=True)
        return

    view = MyBuffsView(user_buffs)
    await interaction.response.send_message("Select a buff to manage it.", view=view, ephemeral=True)

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
            
            for req_id, req in requests.items():
                if req_id in sent_reminders:
                    continue

                start_time = datetime.fromisoformat(req['time_slot'])
                time_diff = start_time - now_utc
                
                if timedelta(minutes=4) < time_diff <= timedelta(minutes=5):
                    logger.info(f"Time condition met for request {req_id}. Preparing to send reminder.")
                    guild = client.guilds[0]
                    if not guild:
                        logger.warning("Reminder task could not find a guild.")
                        continue
                        
                    channel = guild.get_channel(LOG_CHANNEL_ID)
                    role = guild.get_role(PING_ROLE_ID)
                    user = guild.get_member(req['user_id'])
                    user_mention = user.mention if user else req['user_name']

                    if channel and role:
                        reminder_msg = f"{role.mention} Reminder: The **{req['title']}** buff in **{req['region']}** requested by **{user_mention} ({req['user_name']})** starts in 5 minutes!"
                        await channel.send(reminder_msg)
                        sent_reminders.add(req_id)
                        logger.info(f"Successfully sent 5-minute reminder for request {req_id}")
                    else:
                        if not channel: logger.warning(f"Could not send reminder for {req_id}: Channel with ID {LOG_CHANNEL_ID} not found.")
                        if not role: logger.warning(f"Could not send reminder for {req_id}: Role with ID {PING_ROLE_ID} not found.")
                
        except Exception as e:
            logger.error(f"An unexpected error occurred in reminder_task: {e}", exc_info=True)
            
        await asyncio.sleep(60)

async def schedule_task():
    await client.wait_until_ready()
    while not client.is_closed():
        try:
            cleanup_old_data()
            guild = client.guilds[0]
            channel = guild.get_channel(LOG_CHANNEL_ID)
            if channel:
                embeds = await create_buffs_embeds(guild)
                if embeds:
                    await channel.send("--- Scheduled Buff List Update ---")
                    for embed in embeds:
                        await channel.send(embed=embed)
                    logger.info("Posted scheduled buff list.")
        except Exception as e:
            logger.error(f"Error in schedule_task: {e}", exc_info=True)
            
        await asyncio.sleep(12 * 60 * 60)

# --- Bot Events ---
@client.event
async def on_ready():
    await tree.sync()
    logger.info(f'Logged in as {client.user}!')
    print(f'Logged in as {client.user}!')
    
    client.loop.create_task(reminder_task())
    client.loop.create_task(schedule_task())

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)