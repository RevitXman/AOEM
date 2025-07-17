const { SlashCommandBuilder, PermissionFlagsBits } = require('discord.js');
const fs = require('node:fs');
const path = require('node:path');

const DATA_FILE = path.join(__dirname, '..', 'buff_requests.json');

function saveData(data) {
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 4));
}

module.exports = {
    data: new SlashCommandBuilder()
        .setName('clearbuffs')
        .setDescription('[Admin] Manually clears all buff requests.')
        .setDefaultMemberPermissions(PermissionFlagsBits.ManageGuild), // Admin only
    async execute(interaction) {
        saveData({});
        console.log(`Buffs cleared manually by ${interaction.user.tag}.`);
        await interaction.reply({ content: 'All buff requests have been successfully cleared.', ephemeral: true });
    },
};