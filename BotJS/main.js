const fs = require('node:fs');
const path = require('node:path');
const { Client, GatewayIntentBits, Collection, Events, ActionRowBuilder, StringSelectMenuBuilder, ButtonBuilder, ButtonStyle, ModalBuilder, TextInputBuilder, TextInputStyle, EmbedBuilder, escapeMarkdown } = require('discord.js');

// --- Configuration ---
const { token } = require('./config.json');

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMembers // Required to find users
    ]
});

client.commands = new Collection();
const commandsPath = path.join(__dirname, 'commands');
const commandFiles = fs.readdirSync(commandsPath).filter(file => file.endsWith('.js'));

for (const file of commandFiles) {
    const filePath = path.join(commandsPath, file);
    const command = require(filePath);
    if ('data' in command && 'execute' in command) {
        client.commands.set(command.data.name, command);
    } else {
        console.log(`[WARNING] The command at ${filePath} is missing a required "data" or "execute" property.`);
    }
}

// --- Data Management ---
const DATA_FILE = path.join(__dirname, 'buff_requests.json');

function loadData() {
    if (fs.existsSync(DATA_FILE)) {
        try {
            const data = fs.readFileSync(DATA_FILE, 'utf8');
            return JSON.parse(data);
        } catch (error) {
            console.error("Error reading or parsing data file:", error);
            return {};
        }
    }
    return {};
}

function saveData(data) {
    try {
        fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 4));
    } catch (error) {
        console.error("Error saving data:", error);
    }
}

function cleanupOldData() {
    const requests = loadData();
    const now = new Date();
    const twentyFourHoursAgo = now.getTime() - (24 * 60 * 60 * 1000);
    
    let changed = false;
    for (const key in requests) {
        const requestTime = new Date(requests[key].request_time).getTime();
        if (requestTime < twentyFourHoursAgo) {
            delete requests[key];
            changed = true;
        }
    }

    if (changed) {
        saveData(requests);
        console.log("Cleaned up old buff requests.");
    }
}

// --- Bot Events ---
client.once(Events.ClientReady, c => {
    console.log(`Ready! Logged in as ${c.user.tag}`);
    // Start periodic cleanup
    setInterval(cleanupOldData, 60 * 60 * 1000); // Run every hour
    cleanupOldData(); // Initial cleanup
});

client.on(Events.InteractionCreate, async interaction => {
    if (interaction.isChatInputCommand()) {
        const command = client.commands.get(interaction.commandName);
        if (!command) return;

        try {
            await command.execute(interaction);
        } catch (error) {
            console.error(error);
            if (interaction.replied || interaction.deferred) {
                await interaction.followUp({ content: 'There was an error while executing this command!', ephemeral: true });
            } else {
                await interaction.reply({ content: 'There was an error while executing this command!', ephemeral: true });
            }
        }
    } else if (interaction.isStringSelectMenu() || interaction.isButton() || interaction.isModalSubmit()) {
        // We will handle these within the command files where they are created
        // This keeps the logic organized.
    }
});

client.login(token);