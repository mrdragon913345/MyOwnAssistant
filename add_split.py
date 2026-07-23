import sys

code = """
async def split_cmd(update, context):
    from telegram.constants import ParseMode
    from bot.utils.ui import clean_html_text
    import io
    
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text("<b>Usage:</b> Reply to a `.txt` file with <code>/split &lt;lines_per_file&gt;</code>\\n\\nExample: <code>/split 500</code>", parse_mode=ParseMode.HTML)
        return
        
    try:
        lines_per_file = int(context.args[0])
        if lines_per_file <= 0:
            raise ValueError()
    except (IndexError, ValueError):
        await update.message.reply_text("<b>Error:</b> Please provide a valid number of lines. Example: <code>/split 500</code>", parse_mode=ParseMode.HTML)
        return

    doc = update.message.reply_to_message.document
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("<b>Error:</b> Please reply to a .txt file.", parse_mode=ParseMode.HTML)
        return
        
    if doc.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("<b>Error:</b> File is too large.", parse_mode=ParseMode.HTML)
        return

    status_msg = await update.message.reply_text("<i>Downloading file...</i>", parse_mode=ParseMode.HTML)
    
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()
        text = file_bytes.decode('utf-8', errors='ignore')
        lines = text.splitlines()
        
        if not lines:
            await status_msg.edit_text("<b>Error:</b> File is empty.", parse_mode=ParseMode.HTML)
            return
            
        total_lines = len(lines)
        if total_lines <= lines_per_file:
            await status_msg.edit_text("<b>Error:</b> File has fewer lines than the split amount.", parse_mode=ParseMode.HTML)
            return
            
        await status_msg.edit_text(f"<i>Splitting {total_lines} lines into files of {lines_per_file} lines each...</i>", parse_mode=ParseMode.HTML)
        
        base_name = doc.file_name.replace('.txt', '')
        chunks = [lines[i:i + lines_per_file] for i in range(0, total_lines, lines_per_file)]
        
        for idx, chunk in enumerate(chunks, 1):
            chunk_text = "\\n".join(chunk)
            bio = io.BytesIO(chunk_text.encode('utf-8'))
            bio.name = f"{base_name}_part_{idx}.txt"
            await context.bot.send_document(
                chat_id=update.effective_chat.id,
                document=bio,
                filename=bio.name,
                caption=f"<b>Part {idx}/{len(chunks)}</b> ({len(chunk)} lines)",
                parse_mode=ParseMode.HTML,
                reply_to_message_id=update.message.message_id
            )
            
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"<b>Error:</b> {clean_html_text(str(e))}", parse_mode=ParseMode.HTML)
"""

with open('bot/handlers/user.py', 'a', encoding='utf-8') as f:
    f.write(code)
print("Done")
