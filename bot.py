from telethon import TelegramClient, events, Button
from telethon.tl.functions.channels import GetParticipantRequest
from telethon.tl.functions.channels import EditBannedRequest
from telethon.tl.types import (
    ChannelParticipantAdmin, ChannelParticipantCreator, 
    MessageEntityUrl, MessageEntityTextUrl, ChatBannedRights,
    UpdateGroupCall, UpdateGroupCallParticipants, InputChannel
)
from telethon.errors import UserAdminInvalidError, ChatAdminRequiredError
from datetime import datetime, timedelta
import asyncio
import re
import json
import os
import time
import logging
from threading import Thread

# Loglama yapılandırması
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# API kimlik bilgileri
API_ID = 28857104
API_HASH = "c288d8be9f64e231b721c0b2f338b105"
BOT_TOKEN = "8065737316:AAFk6RBwAgHYKaNmhi8svJuqwGmDfRYQd3Q"
LOG_CHANNEL_ID = -1002288700632

# Farklı log kategorileri için thread ID'leri
THREAD_IDS = {
    "ban": 2173,
    "mute": 2172,
    "forbidden_words": 2171,
    "join_leave": 2144,
    "kicks": 2173,  # Bu thread'i oluşturmanız gerekecek
    "warns": 0,  # Bu thread'i oluşturmanız gerekecek
    "voice_chats": 2260,  # Bu thread'i oluşturmanız gerekecek
    "repeated_msgs": 0,  # Bu thread'i oluşturmanız gerekecek
    "appeals": 0,  # Bu thread'i oluşturmanız gerekecek
}

# Yapılandırma dosya yolu
CONFIG_FILE = 'bot_config.json'

# Varsayılan yapılandırma
DEFAULT_CONFIG = {
    "groups": {},
    "forbidden_words": {},
    "repeated_messages": {},
    "welcome_messages": {},
    "warn_settings": {},
    "admin_permissions": {},
    "active_calls": {}  # Sesli aramaları takip etmek için
}

# İstemciyi başlat
client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

# Yapılandırmayı yükle
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG

# Yapılandırmayı kaydet
def save_config(config):
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

# Global yapılandırma
config = load_config()

# Grubun yapılandırmada olduğundan emin ol
def ensure_group_in_config(chat_id):
    chat_id_str = str(chat_id)
    if chat_id_str not in config["groups"]:
        config["groups"][chat_id_str] = {
            "forbidden_words": [],
            "welcome_message": {
                "enabled": False,
                "text": "Gruba hoş geldiniz!",
                "buttons": []
            },
            "repeated_messages": {
                "enabled": False,
                "interval": 3600,
                "messages": [],
                "with_image": False,
                "buttons": []
            },
            "warn_settings": {
                "max_warns": 3,
                "action": "ban",  # veya "mute"
                "mute_duration": 24  # saat
            },
            "admin_permissions": {}
        }
        save_config(config)
    return chat_id_str

# Yönetici izinlerini kontrol et
# Yönetici izinlerini kontrol et - geliştirilmiş versiyon
async def check_admin_permission(event, permission_type):
    try:
        # Özel mesajlar için otomatik izin ver
        if event.is_private:
            return True
            
        chat = await event.get_chat()
        sender = await event.get_sender()
        chat_id_str = str(chat.id)
        
        # Kullanıcının kurucu olup olmadığını kontrol et
        try:
            if hasattr(chat, 'id') and hasattr(chat, 'username') or hasattr(chat, 'title'):  # Kanal ya da grup olduğundan emin ol
                participant = await client(GetParticipantRequest(
                    channel=chat,
                    participant=sender.id
                ))
                if isinstance(participant.participant, ChannelParticipantCreator):
                    return True
        except Exception as e:
            # Sadece debug amaçlı logluyoruz, hatayı bastırmıyoruz
            if "InputPeerUser" not in str(e):  # Bilinen hatayı loglama
                logger.debug(f"Kurucu durumu kontrol edilirken hata oluştu: {e}")
        
        # Özel izinleri kontrol et
        if chat_id_str in config["groups"]:
            admin_permissions = config["groups"][chat_id_str].get("admin_permissions", {})
            if str(sender.id) in admin_permissions:
                if permission_type in admin_permissions[str(sender.id)]:
                    return True
        
        # Normal yönetici izinlerini kontrol et
        try:
            if hasattr(chat, 'id') and (hasattr(chat, 'username') or hasattr(chat, 'title')):  # Kanal ya da grup olduğundan emin ol
                participant = await client(GetParticipantRequest(
                    channel=chat,
                    participant=sender.id
                ))
                if isinstance(participant.participant, ChannelParticipantAdmin):
                    admin_rights = participant.participant.admin_rights
                    if permission_type == "ban" and admin_rights.ban_users:
                        return True
                    elif permission_type == "mute" and admin_rights.ban_users:
                        return True
                    elif permission_type == "kick" and admin_rights.ban_users:
                        return True
                    elif permission_type == "warn" and admin_rights.ban_users:
                        return True
                    elif permission_type == "edit_group" and admin_rights.change_info:
                        return True
                    elif permission_type == "add_admin" and admin_rights.add_admins:
                        return True
        except Exception as e:
            # Sadece debug amaçlı logluyoruz, hatayı bastırmıyoruz
            if "InputPeerUser" not in str(e):  # Bilinen hatayı loglama
                logger.debug(f"Yönetici izinlerini kontrol ederken hata oluştu: {e}")
        
        # Bot geliştiricisi veya belirli bir kullanıcı ID'si için arka kapı
        if sender.id == 123456789:  # Buraya kendi ID'nizi ekleyebilirsiniz
            return True
            
        return False
    except Exception as e:
        logger.debug(f"İzin kontrolü sırasında genel hata: {e}")
        # Hata olunca varsayılan olarak izin verme
        return False

# Uygun thread'e log gönder
async def log_to_thread(log_type, text, buttons=None):
    thread_id = THREAD_IDS.get(log_type, 0)
    if thread_id:
        try:
            if buttons:
                await client.send_message(
                    LOG_CHANNEL_ID, 
                    text, 
                    buttons=buttons,
                    reply_to=thread_id
                )
            else:
                await client.send_message(
                    LOG_CHANNEL_ID, 
                    text,
                    reply_to=thread_id
                )
        except Exception as e:
            logger.error(f"Thread'e log gönderirken hata oluştu: {e}")

# Raw Updates - Sesli sohbet tespiti için
@client.on(events.Raw)
async def voice_chat_handler(event):
    try:
        if isinstance(event, UpdateGroupCall):
            # Sesli sohbet başlatıldı veya sonlandırıldı
            chat_id = event.chat_id
            call = event.call
            
            # Aktif aramalar sözlüğünü kontrol et
            if "active_calls" not in config:
                config["active_calls"] = {}
                
            call_id_str = str(call.id)
            is_new_call = False
            
            if call_id_str not in config["active_calls"]:
                # Yeni başlatılan sesli sohbet
                is_new_call = True
                config["active_calls"][call_id_str] = {
                    "chat_id": chat_id,
                    "start_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    "participants": []
                }
                save_config(config)
                
                try:
                    chat = await client.get_entity(chat_id)
                    
                    # Log metni
                    log_text = f"🎙️ **SESLİ SOHBET BAŞLATILDI**\n\n" \
                            f"**Grup:** {chat.title} (`{chat_id}`)\n" \
                            f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    
                    await log_to_thread("voice_chats", log_text)
                except Exception as e:
                    logger.error(f"Sesli sohbet başlatma loglanırken hata oluştu: {e}")
            
            # Arama sonlandırıldı mı kontrol et
            if not is_new_call and not call.schedule_date and hasattr(call, 'duration'):
                # Arama sonlandırıldı
                try:
                    chat = await client.get_entity(chat_id)
                    call_data = config["active_calls"].get(call_id_str, {})
                    start_time_str = call_data.get("start_time", "Bilinmiyor")
                    
                    # Başlangıç ve bitiş zamanları arasındaki farkı hesapla
                    duration = "Bilinmiyor"
                    try:
                        start_time = datetime.strptime(start_time_str, '%Y-%m-%d %H:%M:%S')
                        end_time = datetime.now()
                        duration_seconds = int((end_time - start_time).total_seconds())
                        
                        hours, remainder = divmod(duration_seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        
                        if hours > 0:
                            duration = f"{hours} saat, {minutes} dakika, {seconds} saniye"
                        elif minutes > 0:
                            duration = f"{minutes} dakika, {seconds} saniye"
                        else:
                            duration = f"{seconds} saniye"
                    except:
                        pass
                    
                    # Log metni
                    log_text = f"🎙️ **SESLİ SOHBET SONLANDIRILDI**\n\n" \
                            f"**Grup:** {chat.title} (`{chat_id}`)\n" \
                            f"**Süre:** {duration}\n" \
                            f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    
                    await log_to_thread("voice_chats", log_text)
                    
                    # Aktif aramalardan kaldır
                    if call_id_str in config["active_calls"]:
                        del config["active_calls"][call_id_str]
                        save_config(config)
                        
                except Exception as e:
                    logger.error(f"Sesli sohbet bitirme loglanırken hata oluştu: {e}")
                    
        elif isinstance(event, UpdateGroupCallParticipants):
            # Sesli sohbet katılımcıları güncellendi
            participants = event.participants
            call = event.call
            
            if "active_calls" not in config:
                config["active_calls"] = {}
                
            call_id_str = str(call.id)
            
            if call_id_str in config["active_calls"]:
                # Her katılımcı için
                for participant in participants:
                    user_id = participant.user_id
                    is_joining = not participant.left
                    
                    # Kullanıcı listesini güncelle
                    if is_joining and user_id not in config["active_calls"][call_id_str]["participants"]:
                        config["active_calls"][call_id_str]["participants"].append(user_id)
                        save_config(config)
                        
                        # Katılmayı logla
                        try:
                            chat_id = config["active_calls"][call_id_str]["chat_id"]
                            chat = await client.get_entity(chat_id)
                            user = await client.get_entity(user_id)
                            
                            log_text = f"🎙️ **SESLİ SOHBETE KATILDI**\n\n" \
                                    f"**Grup:** {chat.title} (`{chat_id}`)\n" \
                                    f"**Kullanıcı:** {user.first_name} (`{user_id}`)\n" \
                                    f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            
                            await log_to_thread("voice_chats", log_text)
                        except Exception as e:
                            logger.error(f"Sesli sohbete katılma loglanırken hata oluştu: {e}")
                            
                    elif participant.left and user_id in config["active_calls"][call_id_str]["participants"]:
                        config["active_calls"][call_id_str]["participants"].remove(user_id)
                        save_config(config)
                        
                        # Ayrılmayı logla
                        try:
                            chat_id = config["active_calls"][call_id_str]["chat_id"]
                            chat = await client.get_entity(chat_id)
                            user = await client.get_entity(user_id)
                            
                            log_text = f"🎙️ **SESLİ SOHBETTEN AYRILDI**\n\n" \
                                    f"**Grup:** {chat.title} (`{chat_id}`)\n" \
                                    f"**Kullanıcı:** {user.first_name} (`{user_id}`)\n" \
                                    f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                            
                            await log_to_thread("voice_chats", log_text)
                        except Exception as e:
                            logger.error(f"Sesli sohbetten ayrılma loglanırken hata oluştu: {e}")
    except Exception as e:
        logger.error(f"Sesli sohbet event işleyicisinde hata: {e}")

# MODERASYON KOMUTLARI
# Anti-flood functionality - Paste this code at the end of your existing code before client.run_until_disconnected()

# Dictionary to track user messages: {chat_id: {user_id: [message_timestamps]}}
user_messages = {}

# Default flood settings for each chat
default_flood_settings = {
    "enabled": True,
    "messages": 5,         # Number of messages
    "seconds": 10,         # In this many seconds
    "mute_time": 15,       # Mute duration in minutes
    "action": "mute"       # Action to take: 'mute' or 'warn'
}

# Add flood config to existing config
def add_flood_config():
    # Check if flood_settings exists in config
    for chat_id in config["groups"]:
        if "flood_settings" not in config["groups"][chat_id]:
            config["groups"][chat_id]["flood_settings"] = default_flood_settings.copy()
    save_config(config)

# Function to check if a user is flooding
async def check_flood(event):
    if event.is_private:  # Skip private messages
        return False
        
    # Skip messages from admins
    if await check_admin_permission(event, "mute"):
        return False
        
    chat_id = event.chat_id
    chat_id_str = str(chat_id)
    user_id = event.sender_id
    current_time = time.time()
    
    # Ensure chat is in config
    ensure_group_in_config(chat_id)
    
    # Get flood settings for this chat
    if chat_id_str not in config["groups"] or "flood_settings" not in config["groups"][chat_id_str]:
        add_flood_config()
    
    flood_settings = config["groups"][chat_id_str]["flood_settings"]
    
    if not flood_settings["enabled"]:
        return False
    
    max_messages = flood_settings["messages"]
    timeframe = flood_settings["seconds"]
    
    # Initialize tracking for this chat if needed
    if chat_id not in user_messages:
        user_messages[chat_id] = {}
    
    # Initialize tracking for this user if needed
    if user_id not in user_messages[chat_id]:
        user_messages[chat_id][user_id] = []
    
    # Add timestamp of current message
    user_messages[chat_id][user_id].append(current_time)
    
    # Remove timestamps older than the timeframe
    user_messages[chat_id][user_id] = [
        timestamp for timestamp in user_messages[chat_id][user_id]
        if current_time - timestamp <= timeframe
    ]
    
    # Check if user has sent too many messages in the timeframe
    if len(user_messages[chat_id][user_id]) >= max_messages:
        # Clear the timestamps to avoid multiple mutes
        user_messages[chat_id][user_id] = []
        return True
    
    return False

# Function to handle flooding user
# Function to handle flooding user - Fixed version
# Function to handle flooding user - Fixed version
async def handle_flood(event):
    chat_id = event.chat_id
    chat_id_str = str(chat_id)
    user_id = event.sender_id
    
    # Get flood settings for this chat
    flood_settings = config["groups"][chat_id_str]["flood_settings"]
    mute_time = flood_settings["mute_time"]  # Minutes
    action = flood_settings["action"]
    
    try:
        # Get chat and user information using client instead of event
        chat = await client.get_entity(chat_id)
        user = await client.get_entity(user_id)
        
        if action == "mute":
            # Calculate mute duration
            until_date = datetime.now() + timedelta(minutes=mute_time)
            
            # Mute the user
            await client(EditBannedRequest(
                chat.id,
                user_id,
                ChatBannedRights(
                    until_date=until_date,
                    send_messages=True,
                    send_media=True,
                    send_stickers=True,
                    send_gifs=True,
                    send_games=True,
                    send_inline=True,
                    embed_links=True
                )
            ))
            
            # Create appeal button
            appeal_button = Button.inline("Susturmaya İtiraz Et", data=f"appeal_flood_{user_id}")
            
            # Log the mute action
            log_text = f"🔇 **KULLANICI FLOOD NEDENİYLE SUSTURULDU**\n\n" \
                      f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                      f"**Kullanıcı:** {user.first_name} (`{user_id}`)\n" \
                      f"**Sebep:** {flood_settings['messages']} mesaj / {flood_settings['seconds']} saniye limitini aşma\n" \
                      f"**Süre:** {mute_time} dakika\n" \
                      f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await log_to_thread("mute", log_text)
            
            # Inform the chat and also send the appeal button to the user in private message
            await client.send_message(
                chat_id,
                f"⚠️ {user.first_name} flood yaptığı için {mute_time} dakika susturuldu.\n"
                f"Limit: {flood_settings['messages']} mesaj / {flood_settings['seconds']} saniye"
            )
            
            # Send appeal button to user in private message
            try:
                await client.send_message(
                    user_id,
                    f"⚠️ {chat.title} grubunda flood yaptığınız için {mute_time} dakika susturuldunuz.\n"
                    f"Limit: {flood_settings['messages']} mesaj / {flood_settings['seconds']} saniye\n\n"
                    f"İtiraz etmek istiyorsanız, aşağıdaki butona tıklayabilirsiniz.",
                    buttons=[[appeal_button]]
                )
            except Exception as e:
                logger.error(f"Kullanıcıya özel mesaj gönderirken hata: {e}")
                # If we can't message the user, add the button to the group notification
                await client.send_message(
                    chat_id,
                    f"⚠️ {user.first_name}, flood nedeniyle susturulmanıza itiraz etmek için aşağıdaki butonu kullanabilirsiniz.",
                    buttons=[[appeal_button]]
                )
            
        elif action == "warn":
            # Check if user_warnings exists
            if "user_warnings" not in config["groups"][chat_id_str]:
                config["groups"][chat_id_str]["user_warnings"] = {}
            
            user_id_str = str(user_id)
            if user_id_str not in config["groups"][chat_id_str]["user_warnings"]:
                config["groups"][chat_id_str]["user_warnings"][user_id_str] = []
            
            # Add warning
            warning = {
                "reason": f"Flood: {flood_settings['messages']} mesaj / {flood_settings['seconds']} saniye limitini aşma",
                "admin_id": None,  # System warning
                "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }
            
            config["groups"][chat_id_str]["user_warnings"][user_id_str].append(warning)
            save_config(config)
            
            # Get warning count
            warn_count = len(config["groups"][chat_id_str]["user_warnings"][user_id_str])
            warn_settings = config["groups"][chat_id_str]["warn_settings"]
            max_warns = warn_settings["max_warns"]
            
            # Create appeal button
            appeal_button = Button.inline("Uyarıya İtiraz Et", data=f"appeal_flood_warn_{user_id}")
            
            # Log the warning
            log_text = f"⚠️ **KULLANICI FLOOD NEDENİYLE UYARILDI**\n\n" \
                      f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                      f"**Kullanıcı:** {user.first_name} (`{user_id}`)\n" \
                      f"**Sebep:** {flood_settings['messages']} mesaj / {flood_settings['seconds']} saniye limitini aşma\n" \
                      f"**Uyarı Sayısı:** {warn_count}/{max_warns}\n" \
                      f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await log_to_thread("warns", log_text)
            
            # Inform the chat
            await client.send_message(
                chat_id,
                f"⚠️ {user.first_name} flood yaptığı için uyarıldı.\n"
                f"Uyarı Sayısı: {warn_count}/{max_warns}\n"
                f"Limit: {flood_settings['messages']} mesaj / {flood_settings['seconds']} saniye"
            )
            
            # Send appeal button to user in private message
            try:
                await client.send_message(
                    user_id,
                    f"⚠️ {chat.title} grubunda flood yaptığınız için uyarıldınız.\n"
                    f"Uyarı Sayısı: {warn_count}/{max_warns}\n"
                    f"Limit: {flood_settings['messages']} mesaj / {flood_settings['seconds']} saniye\n\n"
                    f"İtiraz etmek istiyorsanız, aşağıdaki butona tıklayabilirsiniz.",
                    buttons=[[appeal_button]]
                )
            except Exception as e:
                logger.error(f"Kullanıcıya özel mesaj gönderirken hata: {e}")
                # If we can't message the user, add the button to the group notification
                await client.send_message(
                    chat_id,
                    f"⚠️ {user.first_name}, uyarıya itiraz etmek için aşağıdaki butonu kullanabilirsiniz.",
                    buttons=[[appeal_button]]
                )
            
            # Check if max warnings reached
            if warn_count >= max_warns:
                # Apply punishment based on warn settings
                if warn_settings['action'] == 'ban':
                    await client(EditBannedRequest(
                        chat.id,
                        user_id,
                        ChatBannedRights(
                            until_date=None,
                            view_messages=True
                        )
                    ))
                    
                    # Log the ban
                    log_text = f"🚫 **KULLANICI UYARILAR NEDENİYLE BANLANDI**\n\n" \
                              f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                              f"**Kullanıcı:** {user.first_name} (`{user_id}`)\n" \
                              f"**Sebep:** Maksimum uyarı sayısına ulaşma ({max_warns})\n" \
                              f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    
                    await log_to_thread("ban", log_text)
                    
                    await client.send_message(chat_id, f"Kullanıcı {user.first_name} maksimum uyarı sayısına ulaştığı için banlandı!")
                
                elif warn_settings['action'] == 'mute':
                    mute_duration = warn_settings.get('mute_duration', 24)  # Saat cinsinden
                    until_date = datetime.now() + timedelta(hours=mute_duration)
                    
                    await client(EditBannedRequest(
                        chat.id,
                        user_id,
                        ChatBannedRights(
                            until_date=until_date,
                            send_messages=True,
                            send_media=True,
                            send_stickers=True,
                            send_gifs=True,
                            send_games=True,
                            send_inline=True,
                            embed_links=True
                        )
                    ))
                    
                    # Log the mute
                    log_text = f"🔇 **KULLANICI UYARILAR NEDENİYLE SUSTURULDU**\n\n" \
                              f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                              f"**Kullanıcı:** {user.first_name} (`{user_id}`)\n" \
                              f"**Süre:** {mute_duration} saat\n" \
                              f"**Sebep:** Maksimum uyarı sayısına ulaşma ({max_warns})\n" \
                              f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    
                    await log_to_thread("mute", log_text)
                    
                    await client.send_message(chat_id, f"Kullanıcı {user.first_name} maksimum uyarı sayısına ulaştığı için {mute_duration} saat susturuldu!")
                
                # Reset warnings
                config["groups"][chat_id_str]["user_warnings"][user_id_str] = []
                save_config(config)
    
    except Exception as e:
        logger.error(f"Flood işleme hatası: {e}")

# Message handler for anti-flood
@client.on(events.NewMessage)
async def anti_flood_handler(event):
    # Skip non-group messages, bot commands, and service messages
    if event.is_private or (event.text and event.text.startswith('/')) or not event.message:
        return
    
    # Check for flooding
    if await check_flood(event):
        await handle_flood(event)

# Anti-flood configuration commands
@client.on(events.NewMessage(pattern=r'/antiflood(?:@\w+)?'))
async def antiflood_settings(event):
    if not await check_admin_permission(event, "edit_group"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    chat = await event.get_chat()
    chat_id_str = ensure_group_in_config(chat.id)
    
    # Make sure flood settings exist
    if "flood_settings" not in config["groups"][chat_id_str]:
        add_flood_config()
        
    flood_settings = config["groups"][chat_id_str]["flood_settings"]
    
    # Create status text
    status = "Aktif ✅" if flood_settings["enabled"] else "Devre Dışı ❌"
    action_text = "Sustur 🔇" if flood_settings["action"] == "mute" else "Uyar ⚠️"
    
    settings_text = f"🌊 **Anti-Flood Ayarları**\n\n" \
                   f"**Durum:** {status}\n" \
                   f"**Limit:** {flood_settings['messages']} mesaj / {flood_settings['seconds']} saniye\n" \
                   f"**Ceza:** {action_text}\n" \
                   f"**Susturma Süresi:** {flood_settings['mute_time']} dakika"
    
    # Create setting buttons
    toggle_button = Button.inline(
        "Devre Dışı Bırak ❌" if flood_settings["enabled"] else "Aktifleştir ✅", 
        data="flood_toggle"
    )
    
    limit_button = Button.inline("Limit Ayarla 🔢", data="flood_limit")
    action_button = Button.inline("Ceza Değiştir 🔄", data="flood_action")
    mute_time_button = Button.inline("Susturma Süresi ⏱️", data="flood_mute_time")
    
    buttons = [
        [toggle_button],
        [limit_button, action_button],
        [mute_time_button]
    ]
    
    await event.respond(settings_text, buttons=buttons)

# Handle button clicks for flood settings
@client.on(events.CallbackQuery(pattern=r'flood_(.+)'))
async def flood_button_handler(event):
    try:
        action = event.pattern_match.group(1).decode()
        
        if not await check_admin_permission(event, "edit_group"):
            await event.answer("Bu işlemi yapmak için yetkiniz yok.", alert=True)
            return
        
        chat = await event.get_chat()
        chat_id_str = ensure_group_in_config(chat.id)
        
        if "flood_settings" not in config["groups"][chat_id_str]:
            add_flood_config()
            
        flood_settings = config["groups"][chat_id_str]["flood_settings"]
        
        if action == "toggle":
            # Toggle enabled state
            flood_settings["enabled"] = not flood_settings["enabled"]
            status = "aktifleştirildi ✅" if flood_settings["enabled"] else "devre dışı bırakıldı ❌"
            await event.answer(f"Anti-flood {status}")
            
        elif action == "limit":
            # Go to conversation mode to get new limits
            async with client.conversation(event.sender_id, timeout=300) as conv:
                await event.answer()
                await event.delete()
                
                await conv.send_message("Lütfen mesaj limitini girin (örn: 5):")
                msg_resp = await conv.get_response()
                
                try:
                    msg_limit = int(msg_resp.text)
                    if msg_limit < 2 or msg_limit > 20:
                        await conv.send_message("Geçersiz değer. Limit 2 ile 20 arasında olmalıdır.")
                        return
                except ValueError:
                    await conv.send_message("Geçersiz değer. Lütfen bir sayı girin.")
                    return
                
                await conv.send_message("Şimdi süre limitini saniye cinsinden girin (örn: 10):")
                time_resp = await conv.get_response()
                
                try:
                    time_limit = int(time_resp.text)
                    if time_limit < 3 or time_limit > 60:
                        await conv.send_message("Geçersiz değer. Süre 3 ile 60 saniye arasında olmalıdır.")
                        return
                except ValueError:
                    await conv.send_message("Geçersiz değer. Lütfen bir sayı girin.")
                    return
                
                # Update settings
                flood_settings["messages"] = msg_limit
                flood_settings["seconds"] = time_limit
                save_config(config)
                
                await conv.send_message(f"Anti-flood limiti güncellendi: {msg_limit} mesaj / {time_limit} saniye")
                
                # Restart antiflood menu
                await antiflood_settings(await conv.get_response())
                
        elif action == "action":
            # Toggle action between mute and warn
            new_action = "warn" if flood_settings["action"] == "mute" else "mute"
            flood_settings["action"] = new_action
            action_text = "Uyarı ⚠️" if new_action == "warn" else "Susturma 🔇"
            await event.answer(f"Anti-flood cezası {action_text} olarak ayarlandı")
            
        elif action == "mute_time":
            # Go to conversation mode to get new mute time
            async with client.conversation(event.sender_id, timeout=300) as conv:
                await event.answer()
                await event.delete()
                
                await conv.send_message("Susturma süresini dakika cinsinden girin (örn: 15):")
                time_resp = await conv.get_response()
                
                try:
                    mute_time = int(time_resp.text)
                    if mute_time < 1 or mute_time > 10080:  # max 1 week
                        await conv.send_message("Geçersiz değer. Süre 1 dakika ile 10080 dakika (1 hafta) arasında olmalıdır.")
                        return
                except ValueError:
                    await conv.send_message("Geçersiz değer. Lütfen bir sayı girin.")
                    return
                
                # Update settings
                flood_settings["mute_time"] = mute_time
                save_config(config)
                
                await conv.send_message(f"Susturma süresi {mute_time} dakika olarak ayarlandı")
                
                # Restart antiflood menu
                await antiflood_settings(await conv.get_response())
        
        # Update the message with new settings
        save_config(config)
        
        # If the event wasn't already answered or deleted, update the menu
        if action in ["toggle", "action"]:
            status = "Aktif ✅" if flood_settings["enabled"] else "Devre Dışı ❌"
            action_text = "Sustur 🔇" if flood_settings["action"] == "mute" else "Uyar ⚠️"
            
            settings_text = f"🌊 **Anti-Flood Ayarları**\n\n" \
                           f"**Durum:** {status}\n" \
                           f"**Limit:** {flood_settings['messages']} mesaj / {flood_settings['seconds']} saniye\n" \
                           f"**Ceza:** {action_text}\n" \
                           f"**Susturma Süresi:** {flood_settings['mute_time']} dakika"
            
            toggle_button = Button.inline(
                "Devre Dışı Bırak ❌" if flood_settings["enabled"] else "Aktifleştir ✅", 
                data="flood_toggle"
            )
            
            limit_button = Button.inline("Limit Ayarla 🔢", data="flood_limit")
            action_button = Button.inline("Ceza Değiştir 🔄", data="flood_action")
            mute_time_button = Button.inline("Susturma Süresi ⏱️", data="flood_mute_time")
            
            buttons = [
                [toggle_button],
                [limit_button, action_button],
                [mute_time_button]
            ]
            
            await event.edit(settings_text, buttons=buttons)
            
    except Exception as e:
        logger.error(f"Anti-flood button handler error: {e}")
        await event.answer("İşlem sırasında bir hata oluştu.", alert=True)

# Appeal handlers for flood actions
@client.on(events.CallbackQuery(pattern=r'appeal_flood_(\d+)'))
async def flood_appeal_handler(event):
    try:
        user_id = int(event.pattern_match.group(1).decode())
        
        # Only the person who was muted can appeal
        if event.sender_id != user_id:
            await event.answer("Bu itiraz sizin için değil.", alert=True)
            return
        
        # Start appeal conversation
        async with client.conversation(event.sender_id, timeout=600) as conv:
            await event.answer()
            
            await conv.send_message(
                "Flood nedeniyle susturulmanıza itiraz etmek istediğinizi anlıyoruz. "
                "Lütfen itiraz nedeninizi aşağıda belirtin:"
            )
            
            appeal_msg = await conv.get_response()
            appeal_text = appeal_msg.text
            
            if len(appeal_text) < 10:
                await conv.send_message("İtiraz metnini daha detaylı yazın (en az 10 karakter).")
                return
            
            # Log the appeal
            user = await client.get_entity(user_id)
            
            log_text = f"🙋‍♂️ **FLOOD SUSTURMASINA İTİRAZ**\n\n" \
                      f"**Kullanıcı:** {user.first_name} (`{user_id}`)\n" \
                      f"**İtiraz Metni:** {appeal_text}\n" \
                      f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # Create action buttons for admins
            accept_button = Button.inline("İtirazı Kabul Et ✅", data=f"appeal_accept_flood_{user_id}")
            reject_button = Button.inline("İtirazı Reddet ❌", data=f"appeal_reject_flood_{user_id}")
            
            await log_to_thread("appeals", log_text, [[accept_button, reject_button]])
            
            await conv.send_message(
                "İtirazınız yöneticilere iletildi. En kısa sürede incelenecektir. "
                "Lütfen sabırlı olun."
            )
            
    except Exception as e:
        logger.error(f"Flood appeal handler error: {e}")
        await event.answer("İtiraz işlemi sırasında bir hata oluştu.", alert=True)

# Process admin actions on appeals
@client.on(events.CallbackQuery(pattern=r'appeal_(accept|reject)_flood_(\d+)'))
async def appeal_action_handler(event):
    try:
        action = event.pattern_match.group(1).decode()
        user_id = int(event.pattern_match.group(2).decode())
        
        if not await check_admin_permission(event, "mute"):
            await event.answer("Bu işlemi yapmak için yetkiniz yok.", alert=True)
            return
        
        chat = await event.get_chat()
        
        if action == "accept":
            # Unmute the user
            try:
                await client(EditBannedRequest(
                    chat.id,
                    user_id,
                    ChatBannedRights(
                        until_date=None,
                        send_messages=False,
                        send_media=False,
                        send_stickers=False,
                        send_gifs=False,
                        send_games=False,
                        send_inline=False,
                        embed_links=False
                    )
                ))
                
                user = await client.get_entity(user_id)
                admin = await event.get_sender()
                
                # Log the action
                log_text = f"✅ **FLOOD İTİRAZI KABUL EDİLDİ**\n\n" \
                          f"**Kullanıcı:** {user.first_name} (`{user_id}`)\n" \
                          f"**Yönetici:** {admin.first_name} (`{admin.id}`)\n" \
                          f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                await log_to_thread("appeals", log_text)
                await event.answer("İtiraz kabul edildi ve kullanıcının susturması kaldırıldı.", alert=True)
                
                # Notify user
                try:
                    await client.send_message(
                        user_id,
                        f"Flood nedeniyle susturulmanıza karşı itirazınız kabul edildi ve susturmanız kaldırıldı."
                    )
                except:
                    pass
                
            except Exception as e:
                logger.error(f"Error unmuting user in appeal: {e}")
                await event.answer("Kullanıcının susturmasını kaldırırken bir hata oluştu.", alert=True)
                
        elif action == "reject":
            user = await client.get_entity(user_id)
            admin = await event.get_sender()
            
            # Log the action
            log_text = f"❌ **FLOOD İTİRAZI REDDEDİLDİ**\n\n" \
                      f"**Kullanıcı:** {user.first_name} (`{user_id}`)\n" \
                      f"**Yönetici:** {admin.first_name} (`{admin.id}`)\n" \
                      f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await log_to_thread("appeals", log_text)
            await event.answer("İtiraz reddedildi.", alert=True)
            
            # Notify user
            try:
                await client.send_message(
                    user_id,
                    f"Flood nedeniyle susturulmanıza karşı itirazınız reddedildi."
                )
            except:
                pass
                
        # Update the message to remove buttons
        await event.edit(
            event.text + "\n\n" + 
            f"**Karar:** {'✅ Kabul Edildi' if action == 'accept' else '❌ Reddedildi'}\n" +
            f"**Yönetici:** {admin.first_name}"
        )
            
    except Exception as e:
        logger.error(f"Appeal action handler error: {e}")
        await event.answer("İşlem sırasında bir hata oluştu.", alert=True)

# If THREAD_IDS doesn't have an entry for appeals, add it
if "appeals" not in THREAD_IDS or THREAD_IDS["appeals"] == 0:
    # You need to create this thread in your log channel
    THREAD_IDS["appeals"] = 0  # Replace with actual thread ID when created

# Initial setup for flood settings
add_flood_config()
# Ban komutu
@client.on(events.NewMessage(pattern=r'/ban(?:@\w+)?(\s+(?:@\w+|\d+))?(\s+.+)?'))
async def ban_command(event):
    if not await check_admin_permission(event, "ban"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    args = event.pattern_match.group(1)
    reason = event.pattern_match.group(2)
    
    if not args:
        if event.reply_to:
            user_id = (await event.get_reply_message()).sender_id
        else:
            await event.respond("Banlamak için bir kullanıcıya yanıt verin veya kullanıcı adı/ID belirtin.")
            return
    else:
        args = args.strip()
        if args.startswith('@'):
            try:
                user = await client.get_entity(args)
                user_id = user.id
            except:
                await event.respond("Belirtilen kullanıcı bulunamadı.")
                return
        else:
            try:
                user_id = int(args)
            except ValueError:
                await event.respond("Geçersiz kullanıcı ID formatı.")
                return
    
    if not reason:
        await event.respond("Lütfen ban sebebi belirtin.")
        return
    
    reason = reason.strip()
    chat = await event.get_chat()
    
    try:
        banned_user = await client.get_entity(user_id)
        await client(EditBannedRequest(
            chat.id,
            user_id,
            ChatBannedRights(
                until_date=None,
                view_messages=True,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                embed_links=True
            )
        ))
        
        # İtiraz butonu oluştur
        appeal_button = Button.inline("Bana İtiraz Et", data=f"appeal_ban_{user_id}")
        
        # Ban'i logla
        log_text = f"🚫 **KULLANICI BANLANDI**\n\n" \
                  f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                  f"**Kullanıcı:** {banned_user.first_name} (`{user_id}`)\n" \
                  f"**Yönetici:** {event.sender.first_name} (`{event.sender_id}`)\n" \
                  f"**Sebep:** {reason}\n" \
                  f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await log_to_thread("ban", log_text, [[appeal_button]])
        
        await event.respond(f"Kullanıcı {banned_user.first_name} şu sebepten banlandı: {reason}")
    except UserAdminInvalidError:
        await event.respond("Bir yöneticiyi banlayamam.")
    except Exception as e:
        await event.respond(f"Bir hata oluştu: {str(e)}")

# Unban komutu (YENİ)
@client.on(events.NewMessage(pattern=r'/unban(?:@\w+)?(\s+(?:@\w+|\d+))?(\s+.+)?'))
async def unban_command(event):
    if not await check_admin_permission(event, "ban"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    args = event.pattern_match.group(1)
    reason = event.pattern_match.group(2)
    
    if not args:
        if event.reply_to:
            user_id = (await event.get_reply_message()).sender_id
        else:
            await event.respond("Ban kaldırmak için bir kullanıcıya yanıt verin veya kullanıcı adı/ID belirtin.")
            return
    else:
        args = args.strip()
        if args.startswith('@'):
            try:
                user = await client.get_entity(args)
                user_id = user.id
            except:
                await event.respond("Belirtilen kullanıcı bulunamadı.")
                return
        else:
            try:
                user_id = int(args)
            except ValueError:
                await event.respond("Geçersiz kullanıcı ID formatı.")
                return
    
    if not reason:
        await event.respond("Lütfen ban kaldırma sebebi belirtin.")
        return
    
    reason = reason.strip()
    chat = await event.get_chat()
    
    try:
        unbanned_user = await client.get_entity(user_id)
        await client(EditBannedRequest(
            chat.id,
            user_id,
            ChatBannedRights(
                until_date=None,
                view_messages=False,
                send_messages=False,
                send_media=False,
                send_stickers=False,
                send_gifs=False,
                send_games=False,
                send_inline=False,
                embed_links=False
            )
        ))
        
        # Ban kaldırmayı logla
        log_text = f"✅ **KULLANICI BANI KALDIRILDI**\n\n" \
                  f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                  f"**Kullanıcı:** {unbanned_user.first_name} (`{user_id}`)\n" \
                  f"**Yönetici:** {event.sender.first_name} (`{event.sender_id}`)\n" \
                  f"**Sebep:** {reason}\n" \
                  f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await log_to_thread("ban", log_text)
        
        await event.respond(f"Kullanıcı {unbanned_user.first_name} ban kaldırıldı. Sebep: {reason}")
    except Exception as e:
        await event.respond(f"Bir hata oluştu: {str(e)}")

# Mute komutu
@client.on(events.NewMessage(pattern=r'/mute(?:@\w+)?(\s+(?:@\w+|\d+))?(\s+(\d+)([dhm]))?(\s+.+)?'))
async def mute_command(event):
    if not await check_admin_permission(event, "mute"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    args = event.pattern_match.group(1)
    duration_num = event.pattern_match.group(3)
    duration_unit = event.pattern_match.group(4)
    reason = event.pattern_match.group(5)
    
    if not args:
        if event.reply_to:
            user_id = (await event.get_reply_message()).sender_id
        else:
            await event.respond("Susturmak için bir kullanıcıya yanıt verin veya kullanıcı adı/ID belirtin.")
            return
    else:
        args = args.strip()
        if args.startswith('@'):
            try:
                user = await client.get_entity(args)
                user_id = user.id
            except:
                await event.respond("Belirtilen kullanıcı bulunamadı.")
                return
        else:
            try:
                user_id = int(args)
            except ValueError:
                await event.respond("Geçersiz kullanıcı ID formatı.")
                return
    
    if not reason:
        await event.respond("Lütfen susturma sebebi belirtin.")
        return
    
    reason = reason.strip()
    chat = await event.get_chat()
    
    # Mute süresini hesapla
    until_date = None
    if duration_num and duration_unit:
        duration = int(duration_num)
        if duration_unit == 'd':
            until_date = datetime.now() + timedelta(days=duration)
            duration_text = f"{duration} gün"
        elif duration_unit == 'h':
            until_date = datetime.now() + timedelta(hours=duration)
            duration_text = f"{duration} saat"
        elif duration_unit == 'm':
            until_date = datetime.now() + timedelta(minutes=duration)
            duration_text = f"{duration} dakika"
    else:
        # Varsayılan: 1 gün sustur
        until_date = datetime.now() + timedelta(days=1)
        duration_text = "1 gün"
    
    try:
        muted_user = await client.get_entity(user_id)
        await client(EditBannedRequest(
            chat.id,
            user_id,
            ChatBannedRights(
                until_date=until_date,
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                embed_links=True
            )
        ))
        
        # İtiraz butonu oluştur
        appeal_button = Button.inline("Susturmaya İtiraz Et", data=f"appeal_mute_{user_id}")
        
        # Mute'u logla
        until_text = "süresiz" if not until_date else f"{until_date.strftime('%Y-%m-%d %H:%M:%S')} tarihine kadar"
        log_text = f"🔇 **KULLANICI SUSTURULDU**\n\n" \
                  f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                  f"**Kullanıcı:** {muted_user.first_name} (`{user_id}`)\n" \
                  f"**Yönetici:** {event.sender.first_name} (`{event.sender_id}`)\n" \
                  f"**Süre:** {duration_text}\n" \
                  f"**Sebep:** {reason}\n" \
                  f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await log_to_thread("mute", log_text, [[appeal_button]])
        
        await event.respond(f"Kullanıcı {muted_user.first_name} {duration_text} boyunca şu sebepten susturuldu: {reason}")
    except UserAdminInvalidError:
        await event.respond("Bir yöneticiyi susturamam.")
    except Exception as e:
        await event.respond(f"Bir hata oluştu: {str(e)}")

# Unmute komutu (YENİ)
@client.on(events.NewMessage(pattern=r'/unmute(?:@\w+)?(\s+(?:@\w+|\d+))?(\s+.+)?'))
async def unmute_command(event):
    if not await check_admin_permission(event, "mute"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    args = event.pattern_match.group(1)
    reason = event.pattern_match.group(2)
    
    if not args:
        if event.reply_to:
            user_id = (await event.get_reply_message()).sender_id
        else:
            await event.respond("Susturmayı kaldırmak için bir kullanıcıya yanıt verin veya kullanıcı adı/ID belirtin.")
            return
    else:
        args = args.strip()
        if args.startswith('@'):
            try:
                user = await client.get_entity(args)
                user_id = user.id
            except:
                await event.respond("Belirtilen kullanıcı bulunamadı.")
                return
        else:
            try:
                user_id = int(args)
            except ValueError:
                await event.respond("Geçersiz kullanıcı ID formatı.")
                return
    
    if not reason:
        await event.respond("Lütfen susturmayı kaldırma sebebi belirtin.")
        return
    
    reason = reason.strip()
    chat = await event.get_chat()
    
    try:
        unmuted_user = await client.get_entity(user_id)
        await client(EditBannedRequest(
            chat.id,
            user_id,
            ChatBannedRights(
                until_date=None,
                send_messages=False,
                send_media=False,
                send_stickers=False,
                send_gifs=False,
                send_games=False,
                send_inline=False,
                embed_links=False
            )
        ))
        
        # Susturma kaldırmayı logla
        log_text = f"🔊 **KULLANICI SUSTURMASI KALDIRILDI**\n\n" \
                  f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                  f"**Kullanıcı:** {unmuted_user.first_name} (`{user_id}`)\n" \
                  f"**Yönetici:** {event.sender.first_name} (`{event.sender_id}`)\n" \
                  f"**Sebep:** {reason}\n" \
                  f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await log_to_thread("mute", log_text)
        
        await event.respond(f"Kullanıcı {unmuted_user.first_name} susturması kaldırıldı. Sebep: {reason}")
    except Exception as e:
        await event.respond(f"Bir hata oluştu: {str(e)}")

# Kick komutu
@client.on(events.NewMessage(pattern=r'/kick(?:@\w+)?(\s+(?:@\w+|\d+))?(\s+.+)?'))
async def kick_command(event):
    if not await check_admin_permission(event, "kick"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    args = event.pattern_match.group(1)
    reason = event.pattern_match.group(2)
    
    if not args:
        if event.reply_to:
            user_id = (await event.get_reply_message()).sender_id
        else:
            await event.respond("Atmak için bir kullanıcıya yanıt verin veya kullanıcı adı/ID belirtin.")
            return
    else:
        args = args.strip()
        if args.startswith('@'):
            try:
                user = await client.get_entity(args)
                user_id = user.id
            except:
                await event.respond("Belirtilen kullanıcı bulunamadı.")
                return
        else:
            try:
                user_id = int(args)
            except ValueError:
                await event.respond("Geçersiz kullanıcı ID formatı.")
                return
    
    if not reason:
        await event.respond("Lütfen atma sebebi belirtin.")
        return
    
    reason = reason.strip()
    chat = await event.get_chat()
    
    try:
        kicked_user = await client.get_entity(user_id)
        
        # Kullanıcıyı at ve sonra yasağı kaldır
        await client(EditBannedRequest(
            chat.id,
            user_id,
            ChatBannedRights(
                until_date=None,
                view_messages=True
            )
        ))
        
        await client(EditBannedRequest(
            chat.id,
            user_id,
            ChatBannedRights(
                until_date=None,
                view_messages=False
            )
        ))
        
        # Kick'i logla
        log_text = f"👢 **KULLANICI ATILDI**\n\n" \
                  f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                  f"**Kullanıcı:** {kicked_user.first_name} (`{user_id}`)\n" \
                  f"**Yönetici:** {event.sender.first_name} (`{event.sender_id}`)\n" \
                  f"**Sebep:** {reason}\n" \
                  f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await log_to_thread("kicks", log_text)
        
        await event.respond(f"Kullanıcı {kicked_user.first_name} şu sebepten gruptan atıldı: {reason}")
    except UserAdminInvalidError:
        await event.respond("Bir yöneticiyi atamam.")
    except Exception as e:
        await event.respond(f"Bir hata oluştu: {str(e)}")

# Uyarı komutu
@client.on(events.NewMessage(pattern=r'/warn(?:@\w+)?(\s+(?:@\w+|\d+))?(\s+.+)?'))
async def warn_command(event):
    if not await check_admin_permission(event, "warn"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    args = event.pattern_match.group(1)
    reason = event.pattern_match.group(2)
    
    if not args:
        if event.reply_to:
            user_id = (await event.get_reply_message()).sender_id
        else:
            await event.respond("Uyarmak için bir kullanıcıya yanıt verin veya kullanıcı adı/ID belirtin.")
            return
    else:
        args = args.strip()
        if args.startswith('@'):
            try:
                user = await client.get_entity(args)
                user_id = user.id
            except:
                await event.respond("Belirtilen kullanıcı bulunamadı.")
                return
        else:
            try:
                user_id = int(args)
            except ValueError:
                await event.respond("Geçersiz kullanıcı ID formatı.")
                return
    
    if not reason:
        await event.respond("Lütfen uyarı sebebi belirtin.")
        return
    
    reason = reason.strip()
    chat = await event.get_chat()
    chat_id_str = ensure_group_in_config(chat.id)
    
    # Kullanıcının uyarılarını kontrol et
    if "user_warnings" not in config["groups"][chat_id_str]:
        config["groups"][chat_id_str]["user_warnings"] = {}
    
    user_id_str = str(user_id)
    if user_id_str not in config["groups"][chat_id_str]["user_warnings"]:
        config["groups"][chat_id_str]["user_warnings"][user_id_str] = []
    
    # Yeni uyarı ekle
    warning = {
        "reason": reason,
        "admin_id": event.sender_id,
        "time": datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    config["groups"][chat_id_str]["user_warnings"][user_id_str].append(warning)
    save_config(config)
    
    # Uyarı sayısını kontrol et
    warn_count = len(config["groups"][chat_id_str]["user_warnings"][user_id_str])
    warn_settings = config["groups"][chat_id_str]["warn_settings"]
    
    try:
        warned_user = await client.get_entity(user_id)
        
        # Uyarıyı logla
        log_text = f"⚠️ **KULLANICI UYARILDI**\n\n" \
                  f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                  f"**Kullanıcı:** {warned_user.first_name} (`{user_id}`)\n" \
                  f"**Yönetici:** {event.sender.first_name} (`{event.sender_id}`)\n" \
                  f"**Sebep:** {reason}\n" \
                  f"**Uyarı Sayısı:** {warn_count}/{warn_settings['max_warns']}\n" \
                  f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        # İtiraz butonu oluştur
        appeal_button = Button.inline("Uyarıya İtiraz Et", data=f"appeal_warn_{user_id}")
        
        await log_to_thread("warns", log_text, [[appeal_button]])
        
        response = f"Kullanıcı {warned_user.first_name} şu sebepten uyarıldı: {reason}\n" \
                  f"Uyarı Sayısı: {warn_count}/{warn_settings['max_warns']}"
        
        # Maksimum uyarı sayısına ulaşıldıysa ceza uygula
        if warn_count >= warn_settings['max_warns']:
            if warn_settings['action'] == 'ban':
                await client(EditBannedRequest(
                    chat.id,
                    user_id,
                    ChatBannedRights(
                        until_date=None,
                        view_messages=True,
                        send_messages=True,
                        send_media=True,
                        send_stickers=True,
                        send_gifs=True,
                        send_games=True,
                        send_inline=True,
                        embed_links=True
                    )
                ))
                
                response += f"\n\nKullanıcı maksimum uyarı sayısına ulaştığı için banlandı!"
                
                # Ban'i logla
                log_text = f"🚫 **KULLANICI UYARILAR NEDENİYLE BANLANDI**\n\n" \
                          f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                          f"**Kullanıcı:** {warned_user.first_name} (`{user_id}`)\n" \
                          f"**Yönetici:** {event.sender.first_name} (`{event.sender_id}`)\n" \
                          f"**Uyarı Sayısı:** {warn_count}/{warn_settings['max_warns']}\n" \
                          f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                await log_to_thread("ban", log_text, [[appeal_button]])
                
            elif warn_settings['action'] == 'mute':
                mute_duration = warn_settings.get('mute_duration', 24)  # Saat cinsinden
                until_date = datetime.now() + timedelta(hours=mute_duration)
                
                await client(EditBannedRequest(
                    chat.id,
                    user_id,
                    ChatBannedRights(
                        until_date=until_date,
                        send_messages=True,
                        send_media=True,
                        send_stickers=True,
                        send_gifs=True,
                        send_games=True,
                        send_inline=True,
                        embed_links=True
                    )
                ))
                
                response += f"\n\nKullanıcı maksimum uyarı sayısına ulaştığı için {mute_duration} saat susturuldu!"
                
                # Mute'u logla
                log_text = f"🔇 **KULLANICI UYARILAR NEDENİYLE SUSTURULDU**\n\n" \
                          f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                          f"**Kullanıcı:** {warned_user.first_name} (`{user_id}`)\n" \
                          f"**Yönetici:** {event.sender.first_name} (`{event.sender_id}`)\n" \
                          f"**Süre:** {mute_duration} saat\n" \
                          f"**Uyarı Sayısı:** {warn_count}/{warn_settings['max_warns']}\n" \
                          f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                await log_to_thread("mute", log_text, [[appeal_button]])
            
            # Uyarı sayısını sıfırla
            config["groups"][chat_id_str]["user_warnings"][user_id_str] = []
            save_config(config)
        
        await event.respond(response)
        
    except Exception as e:
        await event.respond(f"Bir hata oluştu: {str(e)}")

# Unwarn komutu (YENİ)
@client.on(events.NewMessage(pattern=r'/unwarn(?:@\w+)?(\s+(?:@\w+|\d+))?(\s+.+)?'))
async def unwarn_command(event):
    if not await check_admin_permission(event, "warn"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    args = event.pattern_match.group(1)
    reason = event.pattern_match.group(2)
    
    if not args:
        if event.reply_to:
            user_id = (await event.get_reply_message()).sender_id
        else:
            await event.respond("Uyarı kaldırmak için bir kullanıcıya yanıt verin veya kullanıcı adı/ID belirtin.")
            return
    else:
        args = args.strip()
        if args.startswith('@'):
            try:
                user = await client.get_entity(args)
                user_id = user.id
            except:
                await event.respond("Belirtilen kullanıcı bulunamadı.")
                return
        else:
            try:
                user_id = int(args)
            except ValueError:
                await event.respond("Geçersiz kullanıcı ID formatı.")
                return
    
    if not reason:
        await event.respond("Lütfen uyarı kaldırma sebebi belirtin.")
        return
    
    reason = reason.strip()
    chat = await event.get_chat()
    chat_id_str = ensure_group_in_config(chat.id)
    
    user_id_str = str(user_id)
    
    # Kullanıcının uyarıları var mı kontrol et
    if ("user_warnings" not in config["groups"][chat_id_str] or 
        user_id_str not in config["groups"][chat_id_str]["user_warnings"] or
        not config["groups"][chat_id_str]["user_warnings"][user_id_str]):
        await event.respond("Bu kullanıcının hiç uyarısı yok.")
        return
    
    # Son uyarıyı kaldır
    removed_warning = config["groups"][chat_id_str]["user_warnings"][user_id_str].pop()
    save_config(config)
    
    try:
        warned_user = await client.get_entity(user_id)
        
        # Kalan uyarı sayısı
        warn_count = len(config["groups"][chat_id_str]["user_warnings"][user_id_str])
        warn_settings = config["groups"][chat_id_str]["warn_settings"]
        
        # Uyarı kaldırmayı logla
        log_text = f"⚠️ **KULLANICI UYARISI KALDIRILDI**\n\n" \
                  f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                  f"**Kullanıcı:** {warned_user.first_name} (`{user_id}`)\n" \
                  f"**Yönetici:** {event.sender.first_name} (`{event.sender_id}`)\n" \
                  f"**Sebep:** {reason}\n" \
                  f"**Kalan Uyarı Sayısı:** {warn_count}/{warn_settings['max_warns']}\n" \
                  f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await log_to_thread("warns", log_text)
        
        await event.respond(f"Kullanıcı {warned_user.first_name} bir uyarısı kaldırıldı.\n"
                          f"Kalan Uyarı Sayısı: {warn_count}/{warn_settings['max_warns']}\n"
                          f"Sebep: {reason}")
        
    except Exception as e:
        await event.respond(f"Bir hata oluştu: {str(e)}")

# Kullanıcı bilgisi komutu
@client.on(events.NewMessage(pattern=r'/info(?:@\w+)?(\s+(?:@\w+|\d+))?'))
async def info_command(event):
    args = event.pattern_match.group(1)
    
    if not args:
        if event.reply_to:
            user_id = (await event.get_reply_message()).sender_id
        else:
            await event.respond("Bilgi almak için bir kullanıcıya yanıt verin veya kullanıcı adı/ID belirtin.")
            return
    else:
        args = args.strip()
        if args.startswith('@'):
            try:
                user = await client.get_entity(args)
                user_id = user.id
            except:
                await event.respond("Belirtilen kullanıcı bulunamadı.")
                return
        else:
            try:
                user_id = int(args)
            except ValueError:
                await event.respond("Geçersiz kullanıcı ID formatı.")
                return
    
    chat = await event.get_chat()
    chat_id_str = ensure_group_in_config(chat.id)
    
    try:
        user = await client.get_entity(user_id)
        
        # Kullanıcının gruba katılma tarihini al
        join_date = "Bilinmiyor"
        try:
            participant = await client(GetParticipantRequest(chat, user_id))
            join_date = participant.participant.date.strftime('%Y-%m-%d %H:%M:%S')
        except:
            pass
        
        # Kullanıcının mesaj sayısını al (bu örnek için varsayılan bir değer)
        message_count = "Bilinmiyor"
        
        # Kullanıcının uyarı sayısını al
        warn_count = 0
        if "user_warnings" in config["groups"][chat_id_str]:
            if str(user_id) in config["groups"][chat_id_str]["user_warnings"]:
                warn_count = len(config["groups"][chat_id_str]["user_warnings"][str(user_id)])
        
        # Kullanıcı bilgisini hazırla
        user_info = f"👤 **KULLANICI BİLGİSİ**\n\n" \
                   f"**İsim:** {user.first_name}" + (f" {user.last_name}" if user.last_name else "") + "\n" \
                   f"**Kullanıcı Adı:** @{user.username}\n" if user.username else "" \
                   f"**ID:** `{user_id}`\n" \
                   f"**Gruba Katılma:** {join_date}\n" \
                   f"**Mesaj Sayısı:** {message_count}\n" \
                   f"**Uyarı Sayısı:** {warn_count}"
        
        # Yönetim butonlarını hazırla
        ban_button = Button.inline("🚫 Ban", data=f"action_ban_{user_id}")
        mute_button = Button.inline("🔇 Sustur", data=f"action_mute_{user_id}")
        kick_button = Button.inline("👢 At", data=f"action_kick_{user_id}")
        warn_button = Button.inline("⚠️ Uyar", data=f"action_warn_{user_id}")
        
        buttons = [
            [ban_button, mute_button],
            [kick_button, warn_button]
        ]
        
        await event.respond(user_info, buttons=buttons)
    except Exception as e:
        await event.respond(f"Bir hata oluştu: {str(e)}")

# BUTON İŞLEYİCİLERİ

# Yönetim işlem butonları
@client.on(events.CallbackQuery(pattern=r'action_(ban|mute|kick|warn)_(\d+)'))
async def action_button_handler(event):
    try:
        # Byte tipindeki match gruplarını stringe dönüştür
        action = event.pattern_match.group(1).decode()
        user_id = int(event.pattern_match.group(2).decode())
        
        permission_type = action
        if not await check_admin_permission(event, permission_type):
            await event.answer("Bu işlemi yapmak için yetkiniz yok.", alert=True)
            return
        
        # İşlem türüne göre kullanıcıdan bir sebep isteyin
        action_names = {
            "ban": "banlamak",
            "mute": "susturmak",
            "kick": "atmak",
            "warn": "uyarmak"
        }
        
        async with client.conversation(event.sender_id, timeout=300) as conv:
            await event.answer()
            await event.delete()
            
            # Sebep sor
            await conv.send_message(f"Kullanıcıyı {action_names[action]} için bir sebep girin:")
            reason_response = await conv.get_response()
            reason = reason_response.text
            
            if action == "mute":
                # Süre sor
                await conv.send_message("Susturma süresi belirtin (örn. '1d', '12h', '30m'):")
                duration_response = await conv.get_response()
                duration_text = duration_response.text
                
                duration_match = re.match(r'(\d+)([dhm])', duration_text)
                if duration_match:
                    duration_num = int(duration_match.group(1))
                    duration_unit = duration_match.group(2)
                else:
                    await conv.send_message("Geçersiz süre formatı. Varsayılan olarak 1 gün uygulanacak.")
                    duration_num = 1
                    duration_unit = 'd'
            
            # Komutları chat'te çalıştır
            if action == "ban":
                await client.send_message(conv.chat_id, f"/ban {user_id} {reason}")
            elif action == "mute":
                await client.send_message(conv.chat_id, f"/mute {user_id} {duration_num}{duration_unit} {reason}")
            elif action == "kick":
                await client.send_message(conv.chat_id, f"/kick {user_id} {reason}")
            elif action == "warn":
                await client.send_message(conv.chat_id, f"/warn {user_id} {reason}")
    except Exception as e:
        logger.error(f"Buton işleyicisinde hata: {str(e)}")
        await event.answer("İşlem sırasında bir hata oluştu", alert=True)

# İtiraz işleme butonları
@client.on(events.CallbackQuery(pattern=r'appeal_(ban|mute|warn)_(\d+)'))
async def appeal_button_handler(event):
    try:
        # Byte tipindeki match gruplarını stringe dönüştür
        action = event.pattern_match.group(1).decode()
        user_id = int(event.pattern_match.group(2).decode())
        
        if event.sender_id != user_id:
            await event.answer("Bu butonu sadece ceza alan kullanıcı kullanabilir.", alert=True)
            return
        
        async with client.conversation(event.sender_id, timeout=300) as conv:
            await event.answer()
            
            # İtiraz sebebi sor
            await conv.send_message(f"{action.capitalize()} cezasına itiraz sebebinizi yazın:")
            reason_response = await conv.get_response()
            appeal_reason = reason_response.text
            
            # İtirazı logla
            action_names = {
                "ban": "Ban",
                "mute": "Susturma",
                "warn": "Uyarı"
            }
            
            log_text = f"🔍 **CEZA İTİRAZI**\n\n" \
                    f"**Ceza Türü:** {action_names[action]}\n" \
                    f"**Kullanıcı ID:** `{user_id}`\n" \
                    f"**İtiraz Sebebi:** {appeal_reason}\n" \
                    f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            # İtiraz butonları
            approve_button = Button.inline("✅ Onayla", data=f"appeal_approve_{action}_{user_id}")
            reject_button = Button.inline("❌ Reddet", data=f"appeal_reject_{action}_{user_id}")
            
            buttons = [[approve_button, reject_button]]
            
            await log_to_thread("appeals", log_text, buttons)
            
            await conv.send_message("İtirazınız yöneticilere iletildi. İncelendiğinde size bildirim yapılacak.")
    except Exception as e:
        logger.error(f"İtiraz buton işleyicisinde hata: {str(e)}")
        await event.answer("İşlem sırasında bir hata oluştu", alert=True)

# İtiraz değerlendirme butonları
@client.on(events.CallbackQuery(pattern=r'appeal_(approve|reject)_(ban|mute|warn)_(\d+)'))
async def appeal_decision_handler(event):
    try:
        # Byte tipindeki match gruplarını stringe dönüştür
        decision = event.pattern_match.group(1).decode()
        action = event.pattern_match.group(2).decode()
        user_id = int(event.pattern_match.group(3).decode())
        
        # Yönetici kontrolü
        chat = await event.get_chat()
        if not await check_admin_permission(event, action):
            await event.answer("İtirazları değerlendirmek için yetkiniz yok.", alert=True)
            return
        
        await event.answer()
        
        try:
            appealing_user = await client.get_entity(user_id)
            
            if decision == "approve":
                # Cezayı kaldır
                if action == "ban" or action == "mute":
                    chat_id = chat.id
                    await client(EditBannedRequest(
                        chat_id,
                        user_id,
                        ChatBannedRights(
                            until_date=None,
                            view_messages=False,
                            send_messages=False,
                            send_media=False,
                            send_stickers=False,
                            send_gifs=False,
                            send_games=False,
                            send_inline=False,
                            embed_links=False
                        )
                    ))
                
                # Uyarıları temizle
                if action == "warn":
                    for group_id, group_data in config["groups"].items():
                        if "user_warnings" in group_data and str(user_id) in group_data["user_warnings"]:
                            group_data["user_warnings"][str(user_id)] = []
                    save_config(config)
                
                response_text = f"✅ **İTİRAZ ONAYLANDI**\n\n" \
                            f"**Kullanıcı:** {appealing_user.first_name} (`{user_id}`)\n" \
                            f"**Ceza Türü:** {action}\n" \
                            f"**Onaylayan:** {event.sender.first_name}\n" \
                            f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                # Kullanıcıya bildirim gönder
                try:
                    await client.send_message(user_id, f"İtirazınız onaylandı ve {action} cezanız kaldırıldı.")
                except:
                    pass
                    
            else:  # reject
                response_text = f"❌ **İTİRAZ REDDEDİLDİ**\n\n" \
                            f"**Kullanıcı:** {appealing_user.first_name} (`{user_id}`)\n" \
                            f"**Ceza Türü:** {action}\n" \
                            f"**Reddeden:** {event.sender.first_name}\n" \
                            f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                # Kullanıcıya bildirim gönder
                try:
                    await client.send_message(user_id, f"İtirazınız reddedildi ve {action} cezanız devam edecek.")
                except:
                    pass
            
            await event.edit(response_text)
            
        except Exception as e:
            await event.edit(f"İtiraz işlemi sırasında bir hata oluştu: {str(e)}")
    except Exception as e:
        logger.error(f"İtiraz değerlendirme buton işleyicisinde hata: {str(e)}")
        await event.answer("İşlem sırasında bir hata oluştu", alert=True)

# YASAKLI KELİME VE BAĞLANTI FİLTRELEME

# Yasaklı kelime ayarları
@client.on(events.NewMessage(pattern=r'/yasaklikelimeler'))
async def forbidden_words_menu(event):
    if not await check_admin_permission(event, "edit_group"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    chat = await event.get_chat()
    chat_id_str = ensure_group_in_config(chat.id)
    
    if "forbidden_words" not in config["groups"][chat_id_str]:
        config["groups"][chat_id_str]["forbidden_words"] = []
        save_config(config)
    
    forbidden_words = config["groups"][chat_id_str]["forbidden_words"]
    
    # Menü butonları
    add_button = Button.inline("➕ Kelime Ekle", data=f"forbidden_add_{chat.id}")
    list_button = Button.inline("📋 Listeyi Göster", data=f"forbidden_list_{chat.id}")
    clear_button = Button.inline("🗑️ Listeyi Temizle", data=f"forbidden_clear_{chat.id}")
    
    buttons = [
        [add_button],
        [list_button, clear_button]
    ]
    
    await event.respond("🚫 **Yasaklı Kelimeler Menüsü**\n\nYasaklı kelimeler listesini yönetmek için bir seçenek seçin:", buttons=buttons)

# Yasaklı kelime menü işleyicileri
@client.on(events.CallbackQuery(pattern=r'forbidden_(add|list|clear)_(-?\d+)'))
async def forbidden_words_handler(event):
    try:
        # Byte tipindeki match gruplarını stringe dönüştür
        action = event.pattern_match.group(1).decode()
        chat_id = int(event.pattern_match.group(2).decode())
        
        if not await check_admin_permission(event, "edit_group"):
            await event.answer("Bu işlemi yapmak için yetkiniz yok.", alert=True)
            return
        
        chat_id_str = ensure_group_in_config(chat_id)
        
        await event.answer()
        
        if action == "add":
            async with client.conversation(event.sender_id, timeout=300) as conv:
                await event.delete()
                await conv.send_message("Eklemek istediğiniz yasaklı kelimeyi girin:")
                word_response = await conv.get_response()
                word = word_response.text.lower()
                
                if word and word not in config["groups"][chat_id_str]["forbidden_words"]:
                    config["groups"][chat_id_str]["forbidden_words"].append(word)
                    save_config(config)
                    await conv.send_message(f"'{word}' yasaklı kelimeler listesine eklendi.")
                else:
                    await conv.send_message("Bu kelime zaten listede veya geçersiz.")
        
        elif action == "list":
            forbidden_words = config["groups"][chat_id_str]["forbidden_words"]
            if forbidden_words:
                word_list = "\n".join([f"- {word}" for word in forbidden_words])
                await event.edit(f"📋 **Yasaklı Kelimeler Listesi**\n\n{word_list}")
            else:
                await event.edit("Yasaklı kelimeler listesi boş.")
        
        elif action == "clear":
            config["groups"][chat_id_str]["forbidden_words"] = []
            save_config(config)
            await event.edit("Yasaklı kelimeler listesi temizlendi.")
    except Exception as e:
        logger.error(f"Yasaklı kelime buton işleyicisinde hata: {str(e)}")
        await event.answer("İşlem sırasında bir hata oluştu", alert=True)

# Mesaj filtreleme (yasaklı kelimeler ve bağlantılar)
@client.on(events.NewMessage)
async def filter_messages(event):
    # Özel mesajları kontrol etme
    if event.is_private:
        return
    
    try:
        chat = await event.get_chat()
        sender = await event.get_sender()
        chat_id_str = ensure_group_in_config(chat.id)
        
        # Yöneticileri kontrol etme - onlar filtrelenmeyecek
        is_admin = False
        try:
            participant = await client(GetParticipantRequest(chat, sender.id))
            if isinstance(participant.participant, (ChannelParticipantAdmin, ChannelParticipantCreator)):
                is_admin = True
        except:
            pass
        
        message = event.message
        text = message.text or message.message or ""
        
        # Yasaklı kelimeler kontrolü
        if not is_admin and "forbidden_words" in config["groups"][chat_id_str]:
            forbidden_words = config["groups"][chat_id_str]["forbidden_words"]
            for word in forbidden_words:
                if word.lower() in text.lower():
                    try:
                        await event.delete()
                        
                        # Yasaklı kelime kullanımını logla
                        log_text = f"🔤 **YASAKLI KELİME KULLANILDI**\n\n" \
                                f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                                f"**Kullanıcı:** {sender.first_name} (`{sender.id}`)\n" \
                                f"**Yasaklı Kelime:** {word}\n" \
                                f"**Mesaj:** {text}\n" \
                                f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                        
                        await log_to_thread("forbidden_words", log_text)
                        return
                    except:
                        pass
        
        # Bağlantı kontrolü
        if not is_admin:
            # Telegram bağlantıları ve web bağlantıları kontrol et
            has_link = False
            
            # Metin içinde URL kontrolü
            if re.search(r'(https?://\S+|www\.\S+)', text):
                has_link = True
            
            # Telegram t.me/ bağlantıları kontrolü
            if re.search(r't\.me/[\w\+]+', text):
                has_link = True
            
            # Mesaj varlıklarında URL kontrolü
            if message.entities:
                for entity in message.entities:
                    if isinstance(entity, (MessageEntityUrl, MessageEntityTextUrl)):
                        has_link = True
                        break
            
            if has_link:
                try:
                    await event.delete()
                    
                    # Bağlantı paylaşımını logla
                    log_text = f"🔗 **YASAK BAĞLANTI PAYLAŞILDI**\n\n" \
                            f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                            f"**Kullanıcı:** {sender.first_name} (`{sender.id}`)\n" \
                            f"**Mesaj:** {text}\n" \
                            f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                    
                    await log_to_thread("forbidden_words", log_text)
                except:
                    pass
    except Exception as e:
        logger.error(f"Mesaj filtreleme sırasında hata: {str(e)}")

# HOŞGELDİN MESAJLARI

# Hoşgeldin mesajı ayarları
@client.on(events.NewMessage(pattern=r'/hosgeldinmesaji'))
async def welcome_message_menu(event):
    if not await check_admin_permission(event, "edit_group"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    chat = await event.get_chat()
    chat_id_str = ensure_group_in_config(chat.id)
    
    if "welcome_message" not in config["groups"][chat_id_str]:
        config["groups"][chat_id_str]["welcome_message"] = {
            "enabled": False,
            "text": "Gruba hoş geldiniz!",
            "buttons": []
        }
        save_config(config)
    
    welcome_settings = config["groups"][chat_id_str]["welcome_message"]
    status = "Açık ✅" if welcome_settings["enabled"] else "Kapalı ❌"
    
    # Menü butonları
    toggle_button = Button.inline(
        f"{'Kapat 🔴' if welcome_settings['enabled'] else 'Aç 🟢'}", 
        data=f"welcome_toggle_{chat.id}"
    )
    set_text_button = Button.inline("✏️ Mesajı Değiştir", data=f"welcome_text_{chat.id}")
    add_button_button = Button.inline("➕ Buton Ekle", data=f"welcome_add_button_{chat.id}")
    clear_buttons_button = Button.inline("🗑️ Butonları Temizle", data=f"welcome_clear_buttons_{chat.id}")
    
    buttons = [
        [toggle_button],
        [set_text_button],
        [add_button_button, clear_buttons_button]
    ]
    
    welcome_text = welcome_settings["text"]
    button_info = ""
    if welcome_settings["buttons"]:
        button_info = "\n\n**Mevcut Butonlar:**\n"
        for btn in welcome_settings["buttons"]:
            button_info += f"- {btn['text']} -> {btn['url']}\n"
    
    await event.respond(
        f"👋 **Hoşgeldin Mesajı Ayarları**\n\n"
        f"**Durum:** {status}\n"
        f"**Mevcut Mesaj:**\n{welcome_text}"
        f"{button_info}",
        buttons=buttons
    )

# Hoşgeldin mesajı menü işleyicileri
@client.on(events.CallbackQuery(pattern=r'welcome_(toggle|text|add_button|clear_buttons)_(-?\d+)'))
async def welcome_settings_handler(event):
    try:
        # Byte tipindeki match gruplarını stringe dönüştür
        action = event.pattern_match.group(1).decode()
        chat_id = int(event.pattern_match.group(2).decode())
        
        if not await check_admin_permission(event, "edit_group"):
            await event.answer("Bu işlemi yapmak için yetkiniz yok.", alert=True)
            return
        
        chat_id_str = ensure_group_in_config(chat_id)
        
        await event.answer()
        
        if action == "toggle":
            config["groups"][chat_id_str]["welcome_message"]["enabled"] = not config["groups"][chat_id_str]["welcome_message"]["enabled"]
            save_config(config)
            
            status = "açıldı ✅" if config["groups"][chat_id_str]["welcome_message"]["enabled"] else "kapatıldı ❌"
            await event.edit(f"Hoşgeldin mesajı {status}")
        
        elif action == "text":
            async with client.conversation(event.sender_id, timeout=300) as conv:
                await event.delete()
                await conv.send_message("Yeni hoşgeldin mesajını girin:")
                text_response = await conv.get_response()
                new_text = text_response.text
                
                if new_text:
                    config["groups"][chat_id_str]["welcome_message"]["text"] = new_text
                    save_config(config)
                    await conv.send_message("Hoşgeldin mesajı güncellendi.")
                else:
                    await conv.send_message("Geçersiz mesaj. Değişiklik yapılmadı.")
        
        elif action == "add_button":
            async with client.conversation(event.sender_id, timeout=300) as conv:
                await event.delete()
                await conv.send_message("Buton metni girin:")
                text_response = await conv.get_response()
                button_text = text_response.text
                
                await conv.send_message("Buton URL'sini girin:")
                url_response = await conv.get_response()
                button_url = url_response.text
                
                if button_text and button_url:
                    if "buttons" not in config["groups"][chat_id_str]["welcome_message"]:
                        config["groups"][chat_id_str]["welcome_message"]["buttons"] = []
                    
                    config["groups"][chat_id_str]["welcome_message"]["buttons"].append({
                        "text": button_text,
                        "url": button_url
                    })
                    save_config(config)
                    await conv.send_message(f"Buton eklendi: {button_text} -> {button_url}")
                else:
                    await conv.send_message("Geçersiz buton bilgisi. Buton eklenemedi.")
        
        elif action == "clear_buttons":
            config["groups"][chat_id_str]["welcome_message"]["buttons"] = []
            save_config(config)
            await event.edit("Tüm butonlar temizlendi.")
    except Exception as e:
        logger.error(f"Hoşgeldin mesajı buton işleyicisinde hata: {str(e)}")
        await event.answer("İşlem sırasında bir hata oluştu", alert=True)

# Hoşgeldin mesajı gönderme
@client.on(events.ChatAction)
async def welcome_new_users(event):
    try:
        # Sadece kullanıcı katılma olaylarını kontrol et
        if not event.user_joined and not event.user_added:
            return
        
        chat = await event.get_chat()
        chat_id_str = ensure_group_in_config(chat.id)
        
        if "welcome_message" in config["groups"][chat_id_str] and config["groups"][chat_id_str]["welcome_message"]["enabled"]:
            welcome_settings = config["groups"][chat_id_str]["welcome_message"]
            
            user = await event.get_user()
            welcome_text = welcome_settings["text"].replace("{user}", f"[{user.first_name}](tg://user?id={user.id})")
            
            # Butonları hazırla
            buttons = None
            if welcome_settings.get("buttons"):
                buttons = []
                row = []
                for i, btn in enumerate(welcome_settings["buttons"]):
                    row.append(Button.url(btn["text"], btn["url"]))
                    
                    # Her 2 butondan sonra yeni satır
                    if (i + 1) % 2 == 0 or i == len(welcome_settings["buttons"]) - 1:
                        buttons.append(row)
                        row = []
            
            # Hoşgeldin mesajını gönder
            try:
                await client.send_message(
                    chat.id,
                    welcome_text,
                    buttons=buttons,
                    parse_mode='md'
                )
                
                # Girişi logla
                log_text = f"👋 **YENİ ÜYE KATILDI**\n\n" \
                        f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                        f"**Kullanıcı:** {user.first_name} (`{user.id}`)\n" \
                        f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                
                await log_to_thread("join_leave", log_text)
            except Exception as e:
                logger.error(f"Hoşgeldin mesajı gönderilirken hata oluştu: {e}")
    except Exception as e:
        logger.error(f"Hoşgeldin mesajı işleyicisinde hata: {str(e)}")

# Çıkış olaylarını loglama
@client.on(events.ChatAction)
async def log_user_left(event):
    try:
        if not event.user_kicked and not event.user_left:
            return
        
        chat = await event.get_chat()
        user = await event.get_user()
        
        log_text = f"👋 **ÜYE AYRILDI**\n\n" \
                f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                f"**Kullanıcı:** {user.first_name} (`{user.id}`)\n" \
                f"**Eylem:** {'Atıldı' if event.user_kicked else 'Ayrıldı'}\n" \
                f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        
        await log_to_thread("join_leave", log_text)
    except Exception as e:
        logger.error(f"Üye ayrılma loglamasında hata: {str(e)}")

# TEKRARLANAN MESAJLAR

# Tekrarlanan mesaj ayarları
@client.on(events.NewMessage(pattern=r'/tekrarlanmesaj'))
async def repeated_messages_menu(event):
    if not await check_admin_permission(event, "edit_group"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    chat = await event.get_chat()
    chat_id_str = ensure_group_in_config(chat.id)
    
    if "repeated_messages" not in config["groups"][chat_id_str]:
        config["groups"][chat_id_str]["repeated_messages"] = {
            "enabled": False,
            "interval": 3600,  # Varsayılan: 1 saat
            "messages": [],
            "with_image": False,
            "buttons": []
        }
        save_config(config)
    
    repeated_settings = config["groups"][chat_id_str]["repeated_messages"]
    status = "Açık ✅" if repeated_settings["enabled"] else "Kapalı ❌"
    
    # Zaman biçimlendirme
    interval = repeated_settings["interval"]
    if interval < 60:
        interval_text = f"{interval} saniye"
    elif interval < 3600:
        interval_text = f"{interval // 60} dakika"
    else:
        interval_text = f"{interval // 3600} saat"
    
    # Menü butonları
    toggle_button = Button.inline(
        f"{'Kapat 🔴' if repeated_settings['enabled'] else 'Aç 🟢'}", 
        data=f"repeated_toggle_{chat.id}"
    )
    set_interval_button = Button.inline("⏱️ Aralık Ayarla", data=f"repeated_interval_{chat.id}")
    add_message_button = Button.inline("✏️ Mesaj Ekle", data=f"repeated_add_message_{chat.id}")
    list_messages_button = Button.inline("📋 Mesajları Listele", data=f"repeated_list_messages_{chat.id}")
    clear_messages_button = Button.inline("🗑️ Mesajları Temizle", data=f"repeated_clear_messages_{chat.id}")
    toggle_image_button = Button.inline(
        f"📷 {'Resim Kapat' if repeated_settings['with_image'] else 'Resim Aç'}", 
        data=f"repeated_toggle_image_{chat.id}"
    )
    add_button_button = Button.inline("➕ Buton Ekle", data=f"repeated_add_button_{chat.id}")
    clear_buttons_button = Button.inline("🗑️ Butonları Temizle", data=f"repeated_clear_buttons_{chat.id}")
    
    buttons = [
        [toggle_button],
        [set_interval_button],
        [add_message_button, list_messages_button],
        [clear_messages_button],
        [toggle_image_button],
        [add_button_button, clear_buttons_button]
    ]
    
    message_info = f"Mesaj Sayısı: {len(repeated_settings['messages'])}"
    button_info = f"Buton Sayısı: {len(repeated_settings.get('buttons', []))}"
    image_status = "Açık ✅" if repeated_settings.get("with_image", False) else "Kapalı ❌"
    
    await event.respond(
        f"🔄 **Tekrarlanan Mesaj Ayarları**\n\n"
        f"**Durum:** {status}\n"
        f"**Aralık:** {interval_text}\n"
        f"**{message_info}**\n"
        f"**{button_info}**\n"
        f"**Resim Durumu:** {image_status}",
        buttons=buttons
    )

# Tekrarlanan mesaj menü işleyicileri
@client.on(events.CallbackQuery(pattern=r'repeated_(toggle|interval|add_message|list_messages|clear_messages|toggle_image|add_button|clear_buttons)_(-?\d+)'))
async def repeated_settings_handler(event):
    try:
        # Byte tipindeki match gruplarını stringe dönüştür
        action = event.pattern_match.group(1).decode()
        chat_id = int(event.pattern_match.group(2).decode())
        
        if not await check_admin_permission(event, "edit_group"):
            await event.answer("Bu işlemi yapmak için yetkiniz yok.", alert=True)
            return
        
        chat_id_str = ensure_group_in_config(chat_id)
        
        await event.answer()
        
        if action == "toggle":
            current_state = config["groups"][chat_id_str]["repeated_messages"]["enabled"]
            new_state = not current_state
            config["groups"][chat_id_str]["repeated_messages"]["enabled"] = new_state
            save_config(config)
            
            status = "açıldı ✅" if new_state else "kapatıldı ❌"
            await event.edit(f"Tekrarlanan mesajlar {status}")
            
            # Eğer açıldıysa ve mesajlar varsa zamanlayıcıyı başlat
            if new_state and config["groups"][chat_id_str]["repeated_messages"]["messages"]:
                # Bu örnek için zamanlayıcıyı yeniden başlatmak gerekir
                # Gerçek uygulamada bir arka plan göreviyle kontrol edilir
                pass
        
        elif action == "interval":
            async with client.conversation(event.sender_id, timeout=300) as conv:
                await event.delete()
                await conv.send_message(
                    "Tekrarlama aralığını belirtin:\n"
                    "- Saat için: 1h, 2h, vb.\n"
                    "- Dakika için: 1m, 30m, vb.\n"
                    "- Saniye için: 30s, 45s, vb."
                )
                interval_response = await conv.get_response()
                interval_text = interval_response.text.lower()
                
                match = re.match(r'(\d+)([hms])', interval_text)
                if match:
                    value = int(match.group(1))
                    unit = match.group(2)
                    
                    if unit == 'h':
                        seconds = value * 3600
                    elif unit == 'm':
                        seconds = value * 60
                    else:  # 's'
                        seconds = value
                    
                    config["groups"][chat_id_str]["repeated_messages"]["interval"] = seconds
                    save_config(config)
                    
                    if seconds < 60:
                        interval_text = f"{seconds} saniye"
                    elif seconds < 3600:
                        interval_text = f"{seconds // 60} dakika"
                    else:
                        interval_text = f"{seconds // 3600} saat"
                    
                    await conv.send_message(f"Tekrarlama aralığı {interval_text} olarak ayarlandı.")
                else:
                    await conv.send_message("Geçersiz format. Değişiklik yapılmadı.")
        
        elif action == "add_message":
            async with client.conversation(event.sender_id, timeout=300) as conv:
                await event.delete()
                await conv.send_message("Eklemek istediğiniz mesajı girin:")
                message_response = await conv.get_response()
                message_text = message_response.text
                
                if message_text:
                    if "messages" not in config["groups"][chat_id_str]["repeated_messages"]:
                        config["groups"][chat_id_str]["repeated_messages"]["messages"] = []
                    
                    config["groups"][chat_id_str]["repeated_messages"]["messages"].append(message_text)
                    save_config(config)
                    await conv.send_message("Mesaj eklendi.")
                else:
                    await conv.send_message("Geçersiz mesaj. Değişiklik yapılmadı.")
        
        elif action == "list_messages":
            messages = config["groups"][chat_id_str]["repeated_messages"]["messages"]
            if messages:
                message_list = ""
                for i, message in enumerate(messages, 1):
                    # Mesajı kısaltıp göster (çok uzunsa)
                    if len(message) > 50:
                        message_preview = message[:47] + "..."
                    else:
                        message_preview = message
                    message_list += f"{i}. {message_preview}\n"
                
                await event.edit(f"📋 **Tekrarlanan Mesajlar**\n\n{message_list}")
            else:
                await event.edit("Henüz tekrarlanan mesaj eklenmemiş.")
        
        elif action == "clear_messages":
            config["groups"][chat_id_str]["repeated_messages"]["messages"] = []
            save_config(config)
            await event.edit("Tüm tekrarlanan mesajlar temizlendi.")
        
        elif action == "toggle_image":
            current_state = config["groups"][chat_id_str]["repeated_messages"].get("with_image", False)
            new_state = not current_state
            config["groups"][chat_id_str]["repeated_messages"]["with_image"] = new_state
            save_config(config)
            
            status = "açıldı ✅" if new_state else "kapatıldı ❌"
            await event.edit(f"Tekrarlanan mesajlarda resim desteği {status}")
        
        elif action == "add_button":
            async with client.conversation(event.sender_id, timeout=300) as conv:
                await event.delete()
                await conv.send_message("Buton metni girin:")
                text_response = await conv.get_response()
                button_text = text_response.text
                
                await conv.send_message("Buton URL'sini girin:")
                url_response = await conv.get_response()
                button_url = url_response.text
                
                if button_text and button_url:
                    if "buttons" not in config["groups"][chat_id_str]["repeated_messages"]:
                        config["groups"][chat_id_str]["repeated_messages"]["buttons"] = []
                    
                    config["groups"][chat_id_str]["repeated_messages"]["buttons"].append({
                        "text": button_text,
                        "url": button_url
                    })
                    save_config(config)
                    await conv.send_message(f"Buton eklendi: {button_text} -> {button_url}")
                else:
                    await conv.send_message("Geçersiz buton bilgisi. Buton eklenemedi.")
        
        elif action == "clear_buttons":
            config["groups"][chat_id_str]["repeated_messages"]["buttons"] = []
            save_config(config)
            await event.edit("Tüm butonlar temizlendi.")
    except Exception as e:
        logger.error(f"Tekrarlanan mesaj buton işleyicisinde hata: {str(e)}")
        await event.answer("İşlem sırasında bir hata oluştu", alert=True)

# Tekrarlanan mesajları gönderme işlevi
async def send_repeated_messages():
    while True:
        try:
            current_time = time.time()
            
            for chat_id_str, group_data in config["groups"].items():
                if "repeated_messages" in group_data:
                    repeated_settings = group_data["repeated_messages"]
                    
                    if repeated_settings["enabled"] and repeated_settings["messages"]:
                        chat_id = int(chat_id_str)
                        
                        # Son gönderim zamanını kontrol et
                        last_sent = repeated_settings.get("last_sent", 0)
                        interval = repeated_settings["interval"]
                        
                        if current_time - last_sent >= interval:
                            # Rastgele bir mesaj seç
                            import random
                            message = random.choice(repeated_settings["messages"])
                            
                            # Butonları hazırla
                            buttons = None
                            if repeated_settings.get("buttons"):
                                buttons = []
                                row = []
                                for i, btn in enumerate(repeated_settings["buttons"]):
                                    row.append(Button.url(btn["text"], btn["url"]))
                                    
                                    # Her 2 butondan sonra yeni satır
                                    if (i + 1) % 2 == 0 or i == len(repeated_settings["buttons"]) - 1:
                                        buttons.append(row)
                                        row = []
                            
                            try:
                                # Resimli mesaj gönderimi
                                if repeated_settings.get("with_image", False):
                                    # Örnek resim dosyası - gerçek uygulamada farklı resimler kullanılabilir
                                    image_path = "./repeat_image.jpg"
                                    
                                    # Resim dosyası varsa gönder, yoksa normal mesaj
                                    if os.path.exists(image_path):
                                        await client.send_file(
                                            chat_id,
                                            image_path,
                                            caption=message,
                                            buttons=buttons
                                        )
                                    else:
                                        await client.send_message(
                                            chat_id,
                                            message,
                                            buttons=buttons
                                        )
                                else:
                                    # Normal metin mesajı
                                    await client.send_message(
                                        chat_id,
                                        message,
                                        buttons=buttons
                                    )
                                
                                # Son gönderim zamanını güncelle
                                config["groups"][chat_id_str]["repeated_messages"]["last_sent"] = current_time
                                save_config(config)
                                
                                # Tekrarlanan mesajı logla
                                log_text = f"🔄 **TEKRARLANAN MESAJ GÖNDERİLDİ**\n\n" \
                                        f"**Grup ID:** `{chat_id}`\n" \
                                        f"**Mesaj:** {message[:100]}{'...' if len(message) > 100 else ''}\n" \
                                        f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                                
                                await log_to_thread("repeated_msgs", log_text)
                                
                            except Exception as e:
                                logger.error(f"Tekrarlanan mesaj gönderilirken hata oluştu: {e}")
        
        except Exception as e:
            logger.error(f"Tekrarlanan mesaj döngüsünde hata oluştu: {e}")
        
        # Her 30 saniyede bir kontrol et
        await asyncio.sleep(30)

# YÖNETİCİ YETKİLERİ

# Yetki verme komutu
@client.on(events.NewMessage(pattern=r'/yetkiver(?:@\w+)?(\s+(?:@\w+|\d+))?(\s+.+)?'))
async def grant_permission(event):
    if not await check_admin_permission(event, "add_admin"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    args = event.pattern_match.group(1)
    permission_type = event.pattern_match.group(2)
    
    if not args:
        if event.reply_to:
            user_id = (await event.get_reply_message()).sender_id
        else:
            await event.respond("Yetki vermek için bir kullanıcıya yanıt verin veya kullanıcı adı/ID belirtin.")
            return
    else:
        args = args.strip()
        if args.startswith('@'):
            try:
                user = await client.get_entity(args)
                user_id = user.id
            except:
                await event.respond("Belirtilen kullanıcı bulunamadı.")
                return
        else:
            try:
                user_id = int(args)
            except ValueError:
                await event.respond("Geçersiz kullanıcı ID formatı.")
                return
    
    valid_permissions = ["ban", "mute", "kick", "warn", "edit_group"]
    
    if not permission_type:
        permission_list = ", ".join(valid_permissions)
        await event.respond(f"Lütfen bir yetki türü belirtin. Geçerli yetkiler: {permission_list}")
        return
    
    permission_type = permission_type.strip().lower()
    
    if permission_type not in valid_permissions:
        permission_list = ", ".join(valid_permissions)
        await event.respond(f"Geçersiz yetki türü. Geçerli yetkiler: {permission_list}")
        return
    
    chat = await event.get_chat()
    chat_id_str = ensure_group_in_config(chat.id)
    
    if "admin_permissions" not in config["groups"][chat_id_str]:
        config["groups"][chat_id_str]["admin_permissions"] = {}
    
    user_id_str = str(user_id)
    if user_id_str not in config["groups"][chat_id_str]["admin_permissions"]:
        config["groups"][chat_id_str]["admin_permissions"][user_id_str] = []
    
    if permission_type not in config["groups"][chat_id_str]["admin_permissions"][user_id_str]:
        config["groups"][chat_id_str]["admin_permissions"][user_id_str].append(permission_type)
        save_config(config)
        
        try:
            user = await client.get_entity(user_id)
            permission_names = {
                "ban": "Banlama",
                "mute": "Susturma",
                "kick": "Atma",
                "warn": "Uyarma",
                "edit_group": "Grup Düzenleme"
            }
            
            await event.respond(f"Kullanıcı {user.first_name} için {permission_names[permission_type]} yetkisi verildi.")
            
            # Yetki değişikliğini logla
            log_text = f"👮 **YETKİ VERİLDİ**\n\n" \
                    f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                    f"**Kullanıcı:** {user.first_name} (`{user_id}`)\n" \
                    f"**Veren Yönetici:** {event.sender.first_name} (`{event.sender_id}`)\n" \
                    f"**Yetki:** {permission_names[permission_type]}\n" \
                    f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await log_to_thread("join_leave", log_text)  # Özel bir log thread'i oluşturulabilir
            
        except Exception as e:
            await event.respond(f"Bir hata oluştu: {str(e)}")
    else:
        await event.respond("Bu kullanıcının zaten bu yetkisi var.")

# Yetki alma komutu
@client.on(events.NewMessage(pattern=r'/yetkial(?:@\w+)?(\s+(?:@\w+|\d+))?(\s+.+)?'))
async def revoke_permission(event):
    if not await check_admin_permission(event, "add_admin"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    args = event.pattern_match.group(1)
    permission_type = event.pattern_match.group(2)
    
    if not args:
        if event.reply_to:
            user_id = (await event.get_reply_message()).sender_id
        else:
            await event.respond("Yetki almak için bir kullanıcıya yanıt verin veya kullanıcı adı/ID belirtin.")
            return
    else:
        args = args.strip()
        if args.startswith('@'):
            try:
                user = await client.get_entity(args)
                user_id = user.id
            except:
                await event.respond("Belirtilen kullanıcı bulunamadı.")
                return
        else:
            try:
                user_id = int(args)
            except ValueError:
                await event.respond("Geçersiz kullanıcı ID formatı.")
                return
    
    valid_permissions = ["ban", "mute", "kick", "warn", "edit_group"]
    
    if not permission_type:
        permission_list = ", ".join(valid_permissions)
        await event.respond(f"Lütfen bir yetki türü belirtin. Geçerli yetkiler: {permission_list}")
        return
    
    permission_type = permission_type.strip().lower()
    
    if permission_type not in valid_permissions:
        permission_list = ", ".join(valid_permissions)
        await event.respond(f"Geçersiz yetki türü. Geçerli yetkiler: {permission_list}")
        return
    
    chat = await event.get_chat()
    chat_id_str = ensure_group_in_config(chat.id)
    
    user_id_str = str(user_id)
    if "admin_permissions" in config["groups"][chat_id_str] and \
       user_id_str in config["groups"][chat_id_str]["admin_permissions"] and \
       permission_type in config["groups"][chat_id_str]["admin_permissions"][user_id_str]:
        
        config["groups"][chat_id_str]["admin_permissions"][user_id_str].remove(permission_type)
        
        # Eğer kullanıcının hiç yetkisi kalmadıysa listeden çıkar
        if not config["groups"][chat_id_str]["admin_permissions"][user_id_str]:
            del config["groups"][chat_id_str]["admin_permissions"][user_id_str]
        
        save_config(config)
        
        try:
            user = await client.get_entity(user_id)
            permission_names = {
                "ban": "Banlama",
                "mute": "Susturma",
                "kick": "Atma",
                "warn": "Uyarma",
                "edit_group": "Grup Düzenleme"
            }
            
            await event.respond(f"Kullanıcı {user.first_name} için {permission_names[permission_type]} yetkisi alındı.")
            
            # Yetki değişikliğini logla
            log_text = f"👮 **YETKİ ALINDI**\n\n" \
                    f"**Grup:** {chat.title} (`{chat.id}`)\n" \
                    f"**Kullanıcı:** {user.first_name} (`{user_id}`)\n" \
                    f"**Alan Yönetici:** {event.sender.first_name} (`{event.sender_id}`)\n" \
                    f"**Yetki:** {permission_names[permission_type]}\n" \
                    f"**Zaman:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            
            await log_to_thread("join_leave", log_text)  # Özel bir log thread'i oluşturulabilir
            
        except Exception as e:
            await event.respond(f"Bir hata oluştu: {str(e)}")
    else:
        await event.respond("Bu kullanıcıda bu yetki zaten yok.")

# UYARI AYARLARI

# Uyarı ayarları
@client.on(events.NewMessage(pattern=r'/uyariayarlari'))
async def warn_settings_menu(event):
    if not await check_admin_permission(event, "edit_group"):
        await event.respond("Bu komutu kullanma yetkiniz yok.")
        return
    
    chat = await event.get_chat()
    chat_id_str = ensure_group_in_config(chat.id)
    
    if "warn_settings" not in config["groups"][chat_id_str]:
        config["groups"][chat_id_str]["warn_settings"] = {
            "max_warns": 3,
            "action": "ban",  # veya "mute"
            "mute_duration": 24  # saat
        }
        save_config(config)
    
    warn_settings = config["groups"][chat_id_str]["warn_settings"]
    
    # Menü butonları
    set_max_button = Button.inline("🔢 Maksimum Uyarı", data=f"warn_max_{chat.id}")
    set_action_button = Button.inline(
        f"🔄 Eylem: {'Ban' if warn_settings['action'] == 'ban' else 'Mute'}", 
        data=f"warn_action_{chat.id}"
    )
    set_duration_button = Button.inline("⏱️ Mute Süresi", data=f"warn_duration_{chat.id}")
    
    buttons = [
        [set_max_button],
        [set_action_button],
        [set_duration_button]
    ]
    
    action_text = "Ban" if warn_settings["action"] == "ban" else f"Mute ({warn_settings['mute_duration']} saat)"
    
    await event.respond(
        f"⚠️ **Uyarı Ayarları**\n\n"
        f"**Maksimum Uyarı:** {warn_settings['max_warns']}\n"
        f"**Eylem:** {action_text}",
        buttons=buttons
    )

# Uyarı ayarları menü işleyicileri
@client.on(events.CallbackQuery(pattern=r'warn_(max|action|duration)_(-?\d+)'))
async def warn_settings_handler(event):
    try:
        # Byte tipindeki match gruplarını stringe dönüştür
        action = event.pattern_match.group(1).decode()
        chat_id = int(event.pattern_match.group(2).decode())
        
        if not await check_admin_permission(event, "edit_group"):
            await event.answer("Bu işlemi yapmak için yetkiniz yok.", alert=True)
            return
        
        chat_id_str = ensure_group_in_config(chat_id)
        
        await event.answer()
        
        if action == "max":
            async with client.conversation(event.sender_id, timeout=300) as conv:
                await event.delete()
                await conv.send_message("Maksimum uyarı sayısını girin (1-10):")
                max_response = await conv.get_response()
                
                try:
                    max_warns = int(max_response.text)
                    if 1 <= max_warns <= 10:
                        config["groups"][chat_id_str]["warn_settings"]["max_warns"] = max_warns
                        save_config(config)
                        await conv.send_message(f"Maksimum uyarı sayısı {max_warns} olarak ayarlandı.")
                    else:
                        await conv.send_message("Geçersiz değer. 1 ile 10 arasında bir sayı girin.")
                except ValueError:
                    await conv.send_message("Geçersiz değer. Lütfen bir sayı girin.")
        
        elif action == "action":
            current_action = config["groups"][chat_id_str]["warn_settings"]["action"]
            new_action = "mute" if current_action == "ban" else "ban"
            
            config["groups"][chat_id_str]["warn_settings"]["action"] = new_action
            save_config(config)
            
            action_text = "Ban" if new_action == "ban" else "Mute"
            await event.edit(f"Uyarı eylem türü '{action_text}' olarak değiştirildi.")
        
        elif action == "duration":
            if config["groups"][chat_id_str]["warn_settings"]["action"] != "mute":
                await event.edit("Bu ayar sadece eylem türü 'Mute' olduğunda geçerlidir.")
                return
            
            async with client.conversation(event.sender_id, timeout=300) as conv:
                await event.delete()
                await conv.send_message("Mute süresini saat cinsinden girin (1-168):")
                duration_response = await conv.get_response()
                
                try:
                    duration = int(duration_response.text)
                    if 1 <= duration <= 168:  # 1 saat - 1 hafta
                        config["groups"][chat_id_str]["warn_settings"]["mute_duration"] = duration
                        save_config(config)
                        await conv.send_message(f"Mute süresi {duration} saat olarak ayarlandı.")
                    else:
                        await conv.send_message("Geçersiz değer. 1 ile 168 (1 hafta) arasında bir sayı girin.")
                except ValueError:
                    await conv.send_message("Geçersiz değer. Lütfen bir sayı girin.")
    except Exception as e:
        logger.error(f"Uyarı ayarları buton işleyicisinde hata: {str(e)}")
        await event.answer("İşlem sırasında bir hata oluştu", alert=True)

# Yardım komutu
@client.on(events.NewMessage(pattern=r'/yardim|/help'))
async def help_command(event):
    help_text = """🤖 **Moderasyon Bot Komutları** 🤖

**👮‍♂️ Moderasyon Komutları:**
/ban <kullanıcı> <sebep> - Kullanıcıyı yasaklar
/unban <kullanıcı> <sebep> - Kullanıcının yasağını kaldırır
/mute <kullanıcı> [süre] <sebep> - Kullanıcıyı susturur
/unmute <kullanıcı> <sebep> - Kullanıcının susturmasını kaldırır
/kick <kullanıcı> <sebep> - Kullanıcıyı gruptan atar
/warn <kullanıcı> <sebep> - Kullanıcıyı uyarır
/unwarn <kullanıcı> <sebep> - Kullanıcının son uyarısını kaldırır
/info <kullanıcı> - Kullanıcı hakkında bilgi verir

**⚙️ Yapılandırma Komutları:**
/yasaklikelimeler - Yasaklı kelimeler menüsünü açar
/hosgeldinmesaji - Hoşgeldin mesajı ayarları
/tekrarlanmesaj - Tekrarlanan mesaj ayarları
/uyariayarlari - Uyarı sistemi ayarları

**👮‍♂️ Yönetici Komutları:**
/yetkiver <kullanıcı> <yetki> - Kullanıcıya özel yetki verir
/yetkial <kullanıcı> <yetki> - Kullanıcıdan yetkiyi alır

**ℹ️ Diğer Komutlar:**
/yardim - Bu mesajı gösterir

📢 Tüm moderasyon işlemleri otomatik olarak loglanır.
⚠️ Moderasyon komutları için sebep belirtmek zorunludur.
"""
    
    await event.respond(help_text)

# Ana fonksiyon
async def main():
    # Tekrarlanan mesajlar için arka plan görevi
    asyncio.create_task(send_repeated_messages())
    
    print("Bot çalışıyor!")
    
    # Bot sonsuza kadar çalışsın
    await client.run_until_disconnected()

# Bot'u başlat
with client:
    client.loop.run_until_complete(main())
