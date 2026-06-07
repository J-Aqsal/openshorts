import os
import asyncio
import uuid
import json
import glob
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, Defaults

# Load environment variables
load_dotenv()

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Constants
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    print("❌ Error: TELEGRAM_BOT_TOKEN not found in .env file.")
    exit(1)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the user."""
    await update.message.reply_text(
        "👋 Hello! I'm the OpenShorts Bot.\n\n"
        "Send me a YouTube link, and I'll turn it into viral vertical shorts for you! 🎬✨\n\n"
        "Available commands:\n"
        "/test [link] - Fast check (30s clip)\n"
        "/start - Show this message"
    )

async def run_processing_logic(cmd, update: Update, job_id, job_output_dir, status_message):
    """
    Executes the command in a fire-and-forget subprocess to avoid ANY event loop blockage.
    """
    try:
        logging.info(f"[{job_id}] Starting Subprocess: {' '.join(cmd)}")
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )

        last_update_text = ""
        
        # We consume output to log it, but we DON'T wait for it in a way that blocks Telegram
        while True:
            chunk = await process.stdout.read(4096)
            if not chunk:
                break
            decoded = chunk.decode(errors='ignore').strip()
            if decoded:
                for line in decoded.split('\n'):
                    clean_line = line.strip()
                    logging.info(f"[{job_id}] {clean_line}")
                    
                    # --- Live Status Updates ---
                    update_text = None
                    if "Transcribing video" in clean_line:
                        update_text = "🎙️ **Mentranskrip video...** (Proses ini mungkin memakan waktu)"
                    elif "Analyzing with Gemini" in clean_line:
                        update_text = "🤖 **Menganalisis viralitas dengan Gemini AI...**"
                    elif "Found" in clean_line and "viral clips!" in clean_line:
                        num_clips = "".join(filter(str.isdigit, clean_line))
                        update_text = f"🔥 **Ditemukan {num_clips} klip viral!** Memulai proses rendering..."
                    elif "Processing Clip" in clean_line:
                        clip_num = clean_line.split("Clip")[-1].split(":")[0].strip()
                        update_text = f"🎬 **Merender Klip {clip_num}...**\n\n_Proses ini berat dan memakan waktu, mohon tunggu sebentar ya..._"
                    elif "Clip" in clean_line and "ready" in clean_line:
                        clip_num = clean_line.split("Clip")[-1].split("ready")[0].strip()
                        update_text = f"✅ **Klip {clip_num} selesai dirender!**"
                    elif "Gemini is busy" in clean_line:
                        update_text = "⚠️ **Server Gemini sedang sibuk.** Mencoba ulang otomatis..."
                    elif "Fast Mode: Skipping scene detection" in clean_line:
                        update_text = "⏩ **Mode Test Aktif:** Melewati analisis AI dan langsung merender 30 detik pertama..."

                    if update_text and update_text != last_update_text:
                        try:
                            last_update_text = update_text
                            full_msg = f"🚀 **Progress Update (ID: `{job_id}`)**\n\n{update_text}"
                            await status_message.edit_text(full_msg, parse_mode='Markdown')
                        except Exception as e:
                            # Ignore Telegram rate limits or "message is not modified" errors
                            logging.debug(f"Status update failed: {e}")

        await process.wait()
        
        if process.returncode == 0:
            # Check for clips or test video
            json_files = glob.glob(os.path.join(job_output_dir, "*_metadata.json"))
            test_files = glob.glob(os.path.join(job_output_dir, "*_test_vertical.mp4"))
            fallback_files = [f for f in glob.glob(os.path.join(job_output_dir, "*_vertical.mp4")) if not f.endswith("_test_vertical.mp4")]
            
            if test_files:
                # Handle test mode result
                with open(test_files[0], 'rb') as vf:
                    await update.message.reply_document(
                        document=vf, 
                        caption="✅ **Hasil Test Selesai!** (Kualitas Original)", 
                        parse_mode='Markdown',
                        read_timeout=300,
                        write_timeout=300
                    )
                await status_message.delete()
            elif json_files:
                # Handle full processing result
                with open(json_files[0], 'r') as f:
                    data = json.load(f)
                
                base_name = os.path.basename(json_files[0]).replace('_metadata.json', '')
                clips = data.get('shorts', [])
                
                for i, clip in enumerate(clips):
                    clip_path = os.path.join(job_output_dir, f"{base_name}_clip_{i+1}.mp4")
                    if os.path.exists(clip_path):
                        caption = f"🔥 *Clip {i+1}*\n\n📌 *Hook:* {clip.get('viral_hook_text', 'N/A')}\n\nPowered by OpenShorts"
                        with open(clip_path, 'rb') as vf:
                            await update.message.reply_document(
                                document=vf, 
                                caption=caption, 
                                parse_mode='Markdown', 
                                read_timeout=300,
                                write_timeout=300
                            )
                
                await status_message.edit_text("✅ Semua clip berhasil dikirim!")
            elif fallback_files:
                # Handle fallback (Gemini failed, whole video converted)
                with open(fallback_files[0], 'rb') as vf:
                    await update.message.reply_document(
                        document=vf, 
                        caption="⚠️ **Analisis AI Gagal (Server Sibuk).**\n\nBerikut adalah hasil konversi vertikal dari keseluruhan video Anda sebagai fallback.", 
                        parse_mode='Markdown',
                        read_timeout=600,
                        write_timeout=600
                    )
                await status_message.delete()
            else:
                await status_message.edit_text("❌ Proses selesai tapi file tidak ditemukan.")
        else:
            await status_message.edit_text(f"❌ Gagal dengan kode {process.returncode}.")

    except Exception as e:
        logging.error(f"Error in background task {job_id}: {e}")
        await update.message.reply_text(f"❌ Terjadi kesalahan fatal: {str(e)}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text or not ("youtube.com" in text or "youtu.be" in text):
        await update.message.reply_text("Kirim link YouTube yang valid ya.")
        return

    url = text.strip()
    job_id = str(uuid.uuid4())[:8]
    job_output_dir = os.path.join(OUTPUT_DIR, f"telegram_{job_id}")
    os.makedirs(job_output_dir, exist_ok=True)

    status_message = await update.message.reply_text(
        f"🚀 **Memulai Pemrosesan**\nID: `{job_id}`\n\nVideo sedang diproses di background. Saya akan mengirimkan hasilnya ke sini jika sudah selesai. ⏳",
        parse_mode='Markdown'
    )

    # FIRE AND FORGET - Telegram doesn't wait for this to finish
    cmd = ["python", "-u", "main.py", "-u", url, "-o", job_output_dir]
    asyncio.create_task(run_processing_logic(cmd, update, job_id, job_output_dir, status_message))

async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Format: `/test [link]`")
        return

    url = context.args[0]
    job_id = f"test_{str(uuid.uuid4())[:6]}"
    job_output_dir = os.path.join(OUTPUT_DIR, f"telegram_{job_id}")
    os.makedirs(job_output_dir, exist_ok=True)

    status_message = await update.message.reply_text(
        f"🧪 **Mode Test Aktif**\nID: `{job_id}`\n\nSedang merender 30 detik pertama. Tunggu sebentar ya...",
        parse_mode='Markdown'
    )

    cmd = ["python", "-u", "main.py", "-u", url, "-o", job_output_dir, "--test"]
    asyncio.create_task(run_processing_logic(cmd, update, job_id, job_output_dir, status_message))

if __name__ == '__main__':
    # Use standard application with NO fancy timeouts that might trigger internal disconnects
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('test', test_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    
    print("🚀 OpenShorts Bot is RUNNING (Async Decoupled Mode)")
    application.run_polling()
