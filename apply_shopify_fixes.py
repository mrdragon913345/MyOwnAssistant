import re

with open('bot/handlers/shopify_cmds.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the <tg-spoiler> tags which might be causing ParseMode.HTML to crash
content = content.replace('<tg-spoiler>', '<span class="tg-spoiler">')
content = content.replace('</tg-spoiler>', '</span>')

# Now fix the notification logic in mass check (shopify_doc_handler)
old_mass_notification = """                # Show immediately on chat whatever group or DM
                if status in ('Charged', 'Approved'):
                    msg_to_send = txt
                    try:
                        if status == 'Charged':
                            sent_msg = await context.bot.send_animation(
                                chat_id=update.effective_chat.id,
                                animation='https://media1.tenor.com/m/25ykirk3P4YAAAAC/oz-oz-yarimasu.gif',
                                caption=msg_to_send,
                                parse_mode=ParseMode.HTML
                            )
                        else:
                            sent_msg = await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=msg_to_send,
                                parse_mode=ParseMode.HTML,
                                link_preview_options=LinkPreviewOptions(is_disabled=True)
                            )
                        if status == 'Charged' and update.effective_chat.type == 'private':
                            try:
                                await context.bot.pin_chat_message(chat_id=update.effective_chat.id, message_id=sent_msg.message_id)
                            except Exception:
                                pass
                    except Exception as e:
                        try:
                            sent_msg = await context.bot.send_message(
                                chat_id=update.effective_chat.id,
                                text=msg_to_send,
                                parse_mode=ParseMode.HTML,
                                link_preview_options=LinkPreviewOptions(is_disabled=True)
                            )
                        except Exception as inner_e:
                            logger.error(f"Failed to send hit message to DM: {inner_e}")
                
                if status in ('Charged', 'Approved'):
                    gw_type = 'shopify_charged' if status == 'Charged' else 'shopify_approved'
                    send_hit(txt, gw=gw_type, user_info=user_info)
                    consume_daily_quota(uid, 1, gw_type)
                    try:
                        from bot.utils.formatter import format_clean_hit_message
                        clean_msg = format_clean_hit_message(
                            user_tag=user_tag,
                            status=status,
                            price=price,
                            gateway_name=gate,
                            response=msg
                        )
                        if str(update.effective_chat.id) != str(MAIN_GROUP_ID):
                            await context.bot.send_message(
                                chat_id=MAIN_GROUP_ID,
                                text=clean_msg,
                                parse_mode=ParseMode.HTML,
                                link_preview_options=LinkPreviewOptions(is_disabled=True)
                            )
                    except Exception as e:
                        logger.error(f"Failed to send clean hit to main group chat from mass check: {e}")"""

new_mass_notification = """                # Notifications Logic
                if status in ('Charged', 'Approved'):
                    gw_type = 'shopify_charged' if status == 'Charged' else 'shopify_approved'
                    send_hit(txt, gw=gw_type, user_info=user_info)
                    consume_daily_quota(uid, 1, gw_type)
                    try:
                        from bot.utils.formatter import format_clean_hit_message
                        clean_msg = format_clean_hit_message(
                            user_tag=user_tag,
                            status=status,
                            price=price,
                            gateway_name=gate,
                            response=msg
                        )
                        
                        # 1. Full Response to DM (uid)
                        if status == 'Charged':
                            try:
                                await context.bot.send_animation(chat_id=uid, animation='https://media1.tenor.com/m/25ykirk3P4YAAAAC/oz-oz-yarimasu.gif', caption=txt, parse_mode=ParseMode.HTML)
                            except Exception:
                                try:
                                    await context.bot.send_message(chat_id=uid, text=txt, parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
                                except Exception: pass
                        else:
                            try:
                                await context.bot.send_message(chat_id=uid, text=txt, parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
                            except Exception: pass

                        # 2. Compact Response to MAIN_GROUP_ID
                        if MAIN_GROUP_ID:
                            try:
                                await context.bot.send_message(chat_id=MAIN_GROUP_ID, text=clean_msg, parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
                            except Exception: pass
                            
                        # 3. Compact Response to current group (if executed in a group other than MAIN_GROUP)
                        if str(update.effective_chat.id) != str(uid) and str(update.effective_chat.id) != str(MAIN_GROUP_ID):
                            try:
                                await context.bot.send_message(chat_id=update.effective_chat.id, text=clean_msg, parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
                            except Exception: pass

                    except Exception as e:
                        logger.error(f"Notification error: {e}")"""

content = content.replace(old_mass_notification, new_mass_notification)

with open('bot/handlers/shopify_cmds.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated shopify_cmds.py successfully!")
