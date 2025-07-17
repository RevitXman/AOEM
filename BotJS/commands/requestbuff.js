const { SlashCommandBuilder, ActionRowBuilder, StringSelectMenuBuilder, ButtonBuilder, ButtonStyle, ModalBuilder, TextInputBuilder, TextInputStyle, EmbedBuilder, escapeMarkdown, Events } = require('discord.js');
const fs = require('node:fs');
const path = require('node:path');

// --- Data Management Helpers ---
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

function saveData(data) {
    fs.writeFileSync(DATA_FILE, JSON.stringify(data, null, 4));
}

// --- Helper to build the list embed ---
async function createBuffsEmbed(guild) {
    const requests = loadData();
    if (Object.keys(requests).length === 0) return null;

    const embed = new EmbedBuilder().setTitle("Current Buff Requests").setColor(0x3498DB);
    const sortedRequests = Object.values(requests).sort((a, b) => new Date(a.time_slot) - new Date(b.time_slot));

    for (const req of sortedRequests) {
        const user = await guild.members.fetch(req.user_id).catch(() => null);
        const userMention = user ? user.toString() : `User ID: ${req.user_id}`;
        const startTime = new Date(req.time_slot);
        const endTime = new Date(startTime.getTime() + 60 * 60 * 1000);
        const timeRangeStr = `${startTime.getUTCHours().toString().padStart(2, '0')}:${startTime.getUTCMinutes().toString().padStart(2, '0')} - ${endTime.getUTCHours().toString().padStart(2, '0')}:${endTime.getUTCMinutes().toString().padStart(2, '0')} UTC`;

        embed.addFields({
            name: `Title: ${req.title} | Region: ${req.region}`,
            value: `User: ${userMention} (${req.user_name})\nTime Slot: ${startTime.toISOString().slice(0, 10)} ${timeRangeStr}`
        });
    }
    return embed;
}

module.exports = {
    data: new SlashCommandBuilder()
        .setName('requestbuff')
        .setDescription('Request a capital buff.'),
    async execute(interaction) {
        const buffOptions = [
            { label: 'Research', value: 'Research' },
            { label: 'Training', value: 'Training' },
            { label: 'Building', value: 'Building' },
            { label: 'Combat', value: 'Combat' },
            { label: 'PvP', value: 'PvP' },
        ];

        const titleSelect = new StringSelectMenuBuilder()
            .setCustomId('title_select')
            .setPlaceholder('Select a buff title...')
            .addOptions(buffOptions);

        const row = new ActionRowBuilder().addComponents(titleSelect);

        await interaction.reply({
            content: 'Please select the details for your buff request.',
            components: [row],
            ephemeral: true
        });

        // Collector to handle the sequence of interactions
        const collector = interaction.channel.createMessageComponentCollector({
            filter: i => i.user.id === interaction.user.id,
            time: 300000 // 5 minutes
        });

        let buffTitle, timeSlot, region;

        collector.on('collect', async i => {
            // --- Step 1: Title Selection ---
            if (i.customId === 'title_select') {
                buffTitle = i.values[0];

                const nowUTC = new Date();
                const timeOptions = [];
                for (let j = 0; j < 24; j++) {
                    const startTime = new Date(nowUTC.getTime() + j * 60 * 60 * 1000);
                    startTime.setMinutes(0, 0, 0);
                    const endTime = new Date(startTime.getTime() + 60 * 60 * 1000);
                    timeOptions.push({
                        label: `${startTime.getUTCHours().toString().padStart(2, '0')}:00 - ${endTime.getUTCHours().toString().padStart(2, '0')}:00 UTC`,
                        value: startTime.toISOString()
                    });
                }

                const timeSelect = new StringSelectMenuBuilder()
                    .setCustomId('time_select')
                    .setPlaceholder('Select a time slot (UTC)...')
                    .addOptions(timeOptions);
                
                const timeRow = new ActionRowBuilder().addComponents(timeSelect);
                await i.update({ content: 'Step 2: Select a time slot.', components: [timeRow] });
            }

            // --- Step 2: Time Selection ---
            if (i.customId === 'time_select') {
                const selectedTime = i.values[0];
                const requests = loadData();
                const conflict = Object.values(requests).some(req => req.time_slot === selectedTime && req.title === buffTitle);

                if (conflict) {
                    await i.update({ content: 'This time slot is already taken for the selected buff. Please start over by using `/requestbuff` again.', components: [] });
                    return collector.stop();
                }

                timeSlot = selectedTime;
                const regionOptions = [
                    { label: 'Gaul', value: 'Gaul' }, { label: 'Olympia', value: 'Olympia' },
                    { label: 'Neilos', value: 'Neilos' }, { label: 'Tinir', value: 'Tinir' },
                    { label: 'East Kingsland', value: 'East Kingsland' }, { label: 'Eastland', value: 'Eastland' },
                    { label: 'Kyuno', value: 'Kyuno' }, { label: 'North Kingsland', value: 'North Kingsland' },
                    { label: 'West Kingsland', value: 'West Kingsland' }, { label: 'NA', value: 'NA' },
                    { label: 'Imperial City', value: 'Imperial City' }
                ];

                const regionSelect = new StringSelectMenuBuilder()
                    .setCustomId('region_select')
                    .setPlaceholder('Select a region...')
                    .addOptions(regionOptions);
                
                const regionRow = new ActionRowBuilder().addComponents(regionSelect);
                await i.update({ content: 'Step 3: Select a region.', components: [regionRow] });
            }

            // --- Step 3: Region Selection ---
            if (i.customId === 'region_select') {
                region = i.values[0];
                const useDiscordNameButton = new ButtonBuilder().setCustomId('use_discord_name').setLabel('Use Discord Name').setStyle(ButtonStyle.Primary);
                const useCustomNameButton = new ButtonBuilder().setCustomId('use_custom_name').setLabel('Enter In-Game Name').setStyle(ButtonStyle.Secondary);
                const nameRow = new ActionRowBuilder().addComponents(useDiscordNameButton, useCustomNameButton);
                await i.update({ content: 'Almost done! Please specify the name to use for the request.', components: [nameRow] });
            }

            // --- Step 4: Name Selection ---
            const finalize = async (interaction, name) => {
                const sanitizedName = escapeMarkdown(name);
                const requests = loadData();
                const requestId = Date.now().toString();

                requests[requestId] = {
                    user_id: interaction.user.id,
                    user_name: sanitizedName,
                    title: buffTitle,
                    time_slot: timeSlot,
                    region: region,
                    request_time: new Date().toISOString()
                };
                saveData(requests);

                await interaction.editReply({ content: 'Request submitted! The buff list has been updated.', components: [] });

                const updatedListEmbed = await createBuffsEmbed(interaction.guild);
                if (updatedListEmbed) {
                    await interaction.channel.send({ embeds: [updatedListEmbed] });
                }
                await interaction.channel.send('@Title Teller');
                collector.stop();
            };

            if (i.customId === 'use_discord_name') {
                await finalize(i, i.user.displayName);
            }

            if (i.customId === 'use_custom_name') {
                const modal = new ModalBuilder().setCustomId('name_modal').setTitle('Enter Your In-Game Name');
                const nameInput = new TextInputBuilder().setCustomId('name_input').setLabel('AoEM Name').setStyle(TextInputStyle.Short).setRequired(true).setMaxLength(50);
                modal.addComponents(new ActionRowBuilder().addComponents(nameInput));
                await i.showModal(modal);

                const modalInteraction = await i.awaitModalSubmit({ time: 60000 }).catch(() => null);
                if (modalInteraction) {
                    await finalize(modalInteraction, modalInteraction.fields.getTextInputValue('name_input'));
                }
            }
        });

        collector.on('end', collected => {
            if (collected.size === 0) {
                interaction.editReply({ content: 'Request timed out.', components: [] });
            }
        });
    },
};