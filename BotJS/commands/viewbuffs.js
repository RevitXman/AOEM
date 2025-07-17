const { SlashCommandBuilder, EmbedBuilder } = require('discord.js');
const fs = require('node:fs');
const path = require('node:path');

const DATA_FILE = path.join(__dirname, '..', 'buff_requests.json');

function loadData() {
    if (fs.existsSync(DATA_FILE)) {
        try {
            const data = fs.readFileSync(DATA_FILE, 'utf8');
            return JSON.parse(data);
        } catch { return {}; }
    }
    return {};
}

module.exports = {
    data: new SlashCommandBuilder()
        .setName('viewbuffs')
        .setDescription('View all active buff requests.'),
    async execute(interaction) {
        const requests = loadData();
        if (Object.keys(requests).length === 0) {
            return interaction.reply({ content: 'There are no active buff requests.', ephemeral: true });
        }

        const embed = new EmbedBuilder().setTitle("Current Buff Requests").setColor(0x3498DB);
        const sortedRequests = Object.values(requests).sort((a, b) => new Date(a.time_slot) - new Date(b.time_slot));

        for (const req of sortedRequests) {
            const user = await interaction.guild.members.fetch(req.user_id).catch(() => null);
            const userMention = user ? user.toString() : `User ID: ${req.user_id}`;
            const startTime = new Date(req.time_slot);
            const endTime = new Date(startTime.getTime() + 60 * 60 * 1000);
            const timeRangeStr = `${startTime.getUTCHours().toString().padStart(2, '0')}:${startTime.getUTCMinutes().toString().padStart(2, '0')} - ${endTime.getUTCHours().toString().padStart(2, '0')}:${endTime.getUTCMinutes().toString().padStart(2, '0')} UTC`;

            embed.addFields({
                name: `Title: ${req.title} | Region: ${req.region}`,
                value: `User: ${userMention} (${req.user_name})\nTime Slot: ${startTime.toISOString().slice(0, 10)} ${timeRangeStr}`
            });
        }

        await interaction.reply({ embeds: [embed] });
    },
};