import discord
from discord import app_commands
from discord.ui import Select, View, Button, Modal, TextInput
import json
import os
from datetime import datetime, timedelta

# --- Configuration ---
# Make sure to create a 'config.json' file with your bot token and the role to ping.
# {
#   "token": "YOUR_DISCORD_BOT_TOKEN",
#   "ping_role_id": YOUR_DISCORD_ROLE_ID
# }
with open('config.json', 'r') as f:
    config = json.load(f)

DISCORD_TOKEN = config['token']
PING_ROLE_ID = int(config['ping_role_id'])

# --- Data Management ---
DATA_FILE = "buff_requests.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {} # Return empty dict if file is empty or corrupted
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

def cleanup_old_data():
    """Removes entries older than 24 hours."""
    requests = load_data()
    if not requests:
        return
    twenty_four_hours_ago = datetime.utcnow() - timedelta(hours=24)
    cleaned_requests = {
        ts_str: req for ts_str, req in requests.items()
        if datetime.fromisoformat(req['request_time']) > twenty_four_hours_ago
    }
    if len(cleaned_requests) != len(requests):
        save_data(cleaned_requests)
        print("Cleaned up old buff requests.")

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# --- Helper Function ---
async def create_buffs_embed(guild: discord.Guild):
    """Creates and returns an embed of the current buff list, or None if no requests exist."""
    cleanup_old_data()
    requests = load_data()
    if not requests:
        return None

    embed = discord.Embed(title="Current Buff Requests", color=discord.Color.blue())
    sorted_requests = sorted(requests.values(), key=lambda x: x['time_slot'])

    for req in sorted_requests:
        user = guild.get_member(req['user_id'])
        user_mention = user.mention if user else f"User ID: {req['user_id']}"
        start_time_obj = datetime.fromisoformat(req['time_slot'])
        end_time_obj = start_time_obj + timedelta(hours=1)
        time_range_str = f"{start_time_obj.strftime('%Y-%m-%d %H:%M')} - {end_time_obj.strftime('%H:%M')} UTC"
        field_name = f"Title: {req['title']} | Region: {req['region']}"
        field_value = f"User: {user_mention} ({req['user_name']})\nTime Slot: {time_range_str}"
        embed.add_field(name=field_name, value=field_value, inline=False)
    
    return embed

# --- UI Components ---

class AoEMNameModal(Modal, title='Enter Your In-Game Name'):
    """A modal for the user to enter their custom in-game name."""
    parent_view: 'BuffRequestView'

    name_input = TextInput(
        label='AoEM Name',
        placeholder='Enter your in-game name here...',
        style=discord.TextStyle.short,
        required=True,
        max_length=50,
    )

    def __init__(self, view: 'BuffRequestView'):
        super().__init__(timeout=300)
        self.parent_view = view

    async def on_submit(self, interaction: discord.Interaction):
        await self.parent_view.finalize_request(interaction, self.name_input.value)

class UseDiscordNameButton(Button):
    """A button to confirm the request using the user's Discord display name."""
    def __init__(self):
        super().__init__(label="Use Discord Name", style=discord.ButtonStyle.primary, row=0)

    async def callback(self, interaction: discord.Interaction):
        await self.view.finalize_request(interaction, interaction.user.display_name)

class EnterCustomNameButton(Button):
    """A button that opens the modal to enter a custom in-game name."""
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
        self.add_item(TitleSelect())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.interaction.edit_original_response(view=self)

    async def finalize_request(self, interaction: discord.Interaction, requester_name: str):
        """Saves the data and sends all confirmations. This is the final step."""
        await interaction.response.defer()
        for item in self.children:
            item.disabled = True
        await self.interaction.edit_original_response(content="Request submitted! The confirmation has been sent to the channel.", view=self)

        sanitized_name = discord.utils.escape_markdown(requester_name)
        requests = load_data()
        request_time_utc = datetime.utcnow()
        start_time_obj = datetime.fromisoformat(self.time_slot)
        end_time_obj = start_time_obj + timedelta(hours=1)
        time_range_str = f"{start_time_obj.strftime('%H:%M')} - {end_time_obj.strftime('%H:%M')} UTC"

        request_id = str(request_time_utc.timestamp())
        requests[request_id] = {
            "user_id": self.interaction.user.id,
            "user_name": sanitized_name,
            "title": self.buff_title,
            "time_slot": self.time_slot,
            "region": self.region,
            "request_time": request_time_utc.isoformat()
        }
        save_data(requests)

        embed = discord.Embed(
            title="New Capital Buff Request!",
            description=f"{self.interaction.user.mention} (**{sanitized_name}**) has requested the **{self.buff_title}** buff for **{time_range_str}** in the **{self.region}** region.",
            color=discord.Color.green()
        )
        ping_role = self.interaction.guild.get_role(PING_ROLE_ID)
        ping_content = ping_role.mention if ping_role else f"@role({PING_ROLE_ID})"
        await self.interaction.channel.send(content=ping_content, embed=embed)

        # Automatically post the updated buff list to the channel
        updated_list_embed = await create_buffs_embed(self.interaction.guild)
        if updated_list_embed:
            await self.interaction.channel.send(embed=updated_list_embed)

class TitleSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Research", value="Research"),
            discord.SelectOption(label="Training", value="Training"),
            discord.SelectOption(label="Building", value="Building"),
            discord.SelectOption(label="Combat", value="Combat"),
            discord.SelectOption(label="PvP", value="PvP")
        ]
        super().__init__(placeholder="Select a buff title...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.buff_title = self.values[0]
        self.disabled = True
        self.view.add_item(TimeSelect())
        await interaction.response.edit_message(view=self.view)

class TimeSelect(Select):
    def __init__(self):
        now_utc = datetime.utcnow()
        options = []
        for i in range(24):
            start_time = (now_utc + timedelta(hours=i)).replace(minute=0, second=0, microsecond=0)
            end_time = start_time + timedelta(hours=1)
            label = f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} UTC"
            value = f"{start_time.isoformat()}"
            options.append(discord.SelectOption(label=label, value=value))
        super().__init__(placeholder="Select a time slot (UTC)...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        requests = load_data()
        selected_time = self.values[0]
        for req_details in requests.values():
            if req_details['time_slot'] == selected_time and req_details['title'] == self.view.buff_title:
                await interaction.response.send_message("This time slot is already taken for the selected buff.", ephemeral=True)
                await self.view.interaction.edit_original_response(content="The previous selection was taken. Please start over.", view=BuffRequestView(self.view.interaction))
                return
        self.view.time_slot = selected_time
        self.disabled = True
        self.view.add_item(RegionSelect())
        await interaction.response.edit_message(view=self.view)

class RegionSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Gaul", value="Gaul"),
            discord.SelectOption(label="Olympia", value="Olympia"),
            discord.SelectOption(label="Neilos", value="Neilos"),
            discord.SelectOption(label="Tinir", value="Tinir"),
            discord.SelectOption(label="East Kingsland", value="East Kingsland"),
            discord.SelectOption(label="Eastland", value="Eastland"),
            discord.SelectOption(label="Kyuno", value="Kyuno"),
            discord.SelectOption(label="North Kingsland", value="North Kingsland"),
            discord.SelectOption(label="West Kingsland", value="West Kingsland"),
            discord.SelectOption(label="NA", value="NA"),
            discord.SelectOption(label="Imperial City", value="Imperial City")
        ]
        super().__init__(placeholder="Select a region...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        self.view.region = self.values[0]
        self.view.clear_items()
        self.view.add_item(UseDiscordNameButton())
        self.view.add_item(EnterCustomNameButton())
        await interaction.response.edit_message(content="Almost done! Please specify the name to use for the request.", view=self.view)

# --- Slash Commands ---
@tree.command(name="requestbuff", description="Request a capital buff.")
async def requestbuff(interaction: discord.Interaction):
    view = BuffRequestView(interaction)
    await interaction.response.send_message("Please select the details for your buff request.", view=view, ephemeral=True)

@tree.command(name="viewbuffs", description="View all active buff requests.")
async def viewbuffs(interaction: discord.Interaction):
    """Displays the list of current buff requests."""
    buff_list_embed = await create_buffs_embed(interaction.guild)
    if buff_list_embed:
        await interaction.response.send_message(embed=buff_list_embed)
    else:
        await interaction.response.send_message("There are no active buff requests.", ephemeral=True)

# --- Admin Command: Clear Buffs ---
@tree.command(name="clearbuffs", description="[Admin] Manually clears all buff requests.")
@app_commands.checks.has_permissions(manage_guild=True)
async def clearbuffs(interaction: discord.Interaction):
    save_data({})
    print(f"Buffs cleared manually by {interaction.user.name} ({interaction.user.id}).")
    await interaction.response.send_message("All buff requests have been successfully cleared.", ephemeral=True)

@clearbuffs.error
async def on_clearbuffs_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You do not have 'Manage Server' permission to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message("An unexpected error occurred.", ephemeral=True)
        raise error

# --- Bot Events ---
@client.event
async def on_ready():
    await tree.sync()
    print(f'Logged in as {client.user}!')
    print(f'Synced {len(await tree.fetch_commands())} commands.')
    cleanup_old_data()

if __name__ == "__main__":
    client.run(DISCORD_TOKEN)