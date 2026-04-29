const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');

const APOLLO_API = 'http://localhost:8001';
const YOUR_NUMBER = '7868209015@c.us';  // e.g. '15551234567@c.us'

const client = new Client({
    authStrategy: new LocalAuth(),
    puppeteer: { headless: true }
});

client.on('qr', qr => {
    console.log('Scan this QR code with WhatsApp:');
    qrcode.generate(qr, { small: true });
});

client.on('ready', () => {
    console.log('WhatsApp bridge ready. Messages from your number will go to Apollo.');
});

client.on('message', async msg => {
    // Only respond to messages from your own number
    if (msg.from !== YOUR_NUMBER) return;

    console.log(`Received: ${msg.body}`);

    try {
        const response = await axios.post(`${APOLLO_API}/chat`, {
            message: msg.body,
            channel: 'whatsapp'
        });
        const reply = response.data.response;
        await msg.reply(reply);
        console.log(`Sent: ${reply.substring(0, 80)}...`);
    } catch (err) {
        await msg.reply('Apollo is unavailable right now.');
        console.error('Apollo API error:', err.message);
    }
});

client.initialize();
