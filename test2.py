import pandas as pd
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
import io
from datetime import datetime

# Store user states
user_states = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Weekly Averages", callback_data='weekly')],
        [InlineKeyboardButton("Daily Candle Averages", callback_data='daily')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to the Financial Analysis Bot!\n"
        "Please choose an analysis type:",
        reply_markup=reply_markup
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    user_states[user_id] = {
        'analysis_type': query.data,
        'waiting_for': 'file'
    }
    
    await query.edit_message_text(
        "Please send me your CSV file containing the columns: time, high, low"
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_states:
        await update.message.reply_text("Please start over with /start")
        return

    if user_states[user_id]['waiting_for'] != 'file':
        return

    file = await context.bot.get_file(update.message.document.file_id)
    file_bytes = await file.download_as_bytearray()
    
    try:
        data = pd.read_csv(io.BytesIO(file_bytes))
        data['time'] = pd.to_datetime(data['time'])
        user_states[user_id]['data'] = data
        user_states[user_id]['waiting_for'] = 'start_date'
        
        # Get the range of dates from the data
        min_date = data['time'].min().strftime('%Y-%m-%d')
        max_date = data['time'].max().strftime('%Y-%m-%d')
        
        await update.message.reply_text(
            f"File received! Available date range: {min_date} to {max_date}\n"
            f"Please enter the start date in format YYYY-MM-DD:"
        )
    except Exception as e:
        await update.message.reply_text(f"Error processing file: {str(e)}")
        user_states.pop(user_id, None)

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if user_id not in user_states:
        await update.message.reply_text("Please start over with /start")
        return

    state = user_states[user_id]
    text = update.message.text.strip()

    try:
        if state['waiting_for'] == 'start_date':
            start_date = pd.to_datetime(text)
            state['start_date'] = start_date
            state['waiting_for'] = 'end_date'
            await update.message.reply_text(
                "Enter the end date in format YYYY-MM-DD (or type 'none' to analyze until the end):"
            )
        
        elif state['waiting_for'] == 'end_date':
            if text.lower() == 'none':
                end_date = None
            else:
                end_date = pd.to_datetime(text)
            
            # Perform the analysis
            result = perform_analysis(
                state['data'],
                state['analysis_type'],
                state['start_date'],
                end_date
            )
            
            # Send results
            await update.message.reply_text(result)
            
            # Clear user state
            user_states.pop(user_id, None)
            
    except ValueError:
        await update.message.reply_text("Please enter a valid date in format YYYY-MM-DD")
    except Exception as e:
        await update.message.reply_text(f"An error occurred: {str(e)}")
        user_states.pop(user_id, None)

def perform_analysis(data: pd.DataFrame, analysis_type: str, start_date: datetime, end_date: datetime = None) -> str:
    try:
        if end_date:
            data = data[(data['time'] >= start_date) & (data['time'] <= end_date)]
        else:
            data = data[data['time'] >= start_date]

        if analysis_type == 'weekly':
            data['average'] = (data['high'] + data['low']) / 2
            total_average = data['average'].mean()
            result = "Weekly Averages Analysis:\n\n"
            result += f"Date Range: {start_date.strftime('%Y-%m-%d')} to "
            result += f"{end_date.strftime('%Y-%m-%d') if end_date else data['time'].max().strftime('%Y-%m-%d')}\n"
            result += f"Total Average: {total_average:.4f}\n\n"
            result += "Recent values:\n"
            recent = data.tail(5)[['time', 'average']].to_string()
            result += recent
            
        else:  # daily
            data['daily_range'] = data['high'] - data['low']
            daily_average = data['daily_range'].mean()
            result = "Daily Candle Range Analysis:\n\n"
            result += f"Date Range: {start_date.strftime('%Y-%m-%d')} to "
            result += f"{end_date.strftime('%Y-%m-%d') if end_date else data['time'].max().strftime('%Y-%m-%d')}\n"
            result += f"Average Daily Range: {daily_average:.4f}\n\n"
            result += "Recent values:\n"
            recent = data.tail(5)[['time', 'daily_range']].to_string()
            result += recent

        # Add some statistics
        result += "\n\nAdditional Statistics:\n"
        result += f"Number of periods analyzed: {len(data)}\n"
        if analysis_type == 'weekly':
            result += f"Maximum average: {data['average'].max():.4f}\n"
            result += f"Minimum average: {data['average'].min():.4f}\n"
        else:
            result += f"Maximum daily range: {data['daily_range'].max():.4f}\n"
            result += f"Minimum daily range: {data['daily_range'].min():.4f}\n"

        return result

    except Exception as e:
        return f"Analysis error: {str(e)}"

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
Available commands:
/start - Start the analysis process
/help - Show this help message

How to use:
1. Click /start
2. Choose analysis type
3. Send your CSV file
4. Enter start date (YYYY-MM-DD)
5. Enter end date (YYYY-MM-DD or 'none')

Your CSV file should have columns:
- time (in YYYY-MM-DD format)
- high
- low
    """
    await update.message.reply_text(help_text)

def main():
    # Replace 'YOUR_BOT_TOKEN' with your actual bot token from BotFather
    app = Application.builder().token('7220951106:AAGxmixczMtMlnJnfnZgTKCFTLgQYvEnuPo').build()

    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', help_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("Bot started...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()