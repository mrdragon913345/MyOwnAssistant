import sys

code = """

async def parse_cmd(update, context):
    from telegram.constants import ParseMode
    from bot.utils.ui import clean_html_text
    import io
    import re
    
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text("<b>Usage:</b> Reply to a `.txt` file with <code>/parse</code>", parse_mode=ParseMode.HTML)
        return
        
    doc = update.message.reply_to_message.document
    if not doc.file_name.endswith('.txt'):
        await update.message.reply_text("<b>Error:</b> Please reply to a .txt file.", parse_mode=ParseMode.HTML)
        return
        
    if doc.file_size > 20 * 1024 * 1024:
        await update.message.reply_text("<b>Error:</b> File is too large.", parse_mode=ParseMode.HTML)
        return

    status_msg = await update.message.reply_text("<i>Downloading and parsing file...</i>", parse_mode=ParseMode.HTML)
    
    try:
        tg_file = await context.bot.get_file(doc.file_id)
        file_bytes = await tg_file.download_as_bytearray()
        text = file_bytes.decode('utf-8', errors='ignore')
        
        parsed_cards = []
        for line in text.splitlines():
            # Try specific format first
            match = re.search(r'^(\\d{15,16}).*?CVV:(\\d{3,4})EXPIRE:(\\d{2})/(\\d{2})', line, re.IGNORECASE)
            if match:
                cc = match.group(1)
                cvv = match.group(2)
                mm = match.group(3)
                yy = match.group(4)
                if len(yy) == 2: yy = '20' + yy
                parsed_cards.append(f"{cc}|{mm}|{yy}|{cvv}")
                continue
                
            # Generic extractor as fallback
            gen_match = re.search(r'(\\d{15,16})[\\s|:/]+(\\d{1,2})[\\s|:/]+(\\d{2,4})[\\s|:/]+(\\d{3,4})', line)
            if gen_match:
                cc, mm, yy, cvv = gen_match.groups()
                if len(mm) == 1: mm = '0' + mm
                if len(yy) == 2: yy = '20' + yy
                parsed_cards.append(f"{cc}|{mm}|{yy}|{cvv}")
                
        if not parsed_cards:
            await status_msg.edit_text("<b>Error:</b> Could not find any valid credit cards in that file.", parse_mode=ParseMode.HTML)
            return
            
        # Deduplicate
        seen = set()
        unique_cards = []
        for c in parsed_cards:
            if c not in seen:
                seen.add(c)
                unique_cards.append(c)
                
        output_text = "\\n".join(unique_cards)
        bio = io.BytesIO(output_text.encode('utf-8'))
        base_name = doc.file_name.replace('.txt', '')
        bio.name = f"{base_name}_parsed.txt"
        
        await context.bot.send_document(
            chat_id=update.effective_chat.id,
            document=bio,
            filename=bio.name,
            caption=f"<b>Parsed {len(unique_cards)} unique cards!</b>",
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
