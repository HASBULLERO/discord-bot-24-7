import discord
from discord.ext import commands
import json
import os
import asyncio
from datetime import datetime

# Configuración del bot SIN funciones de voz para evitar el error audioop
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Base de datos simple en memoria (para hosting gratuito)
economy_data = {}
tickets_data = {}
config_data = {
    "welcome_channel": None,
    "ticket_category": None,
    "ticket_counter": 0,
    "currency_name": "coins",
    "daily_amount": 100
}

# =================
# SISTEMA DE ECONOMIA
# =================

def get_user_data(user_id):
    user_id = str(user_id)
    if user_id not in economy_data:
        economy_data[user_id] = {
            "balance": 0,
            "bank": 0,
            "last_daily": None,
            "total_earned": 0
        }
    return economy_data[user_id]

def add_money(user_id, amount):
    user_data = get_user_data(user_id)
    user_data["balance"] += amount
    user_data["total_earned"] += amount

def remove_money(user_id, amount):
    user_data = get_user_data(user_id)
    if user_data["balance"] >= amount:
        user_data["balance"] -= amount
        return True
    return False

# =================
# SISTEMA DE TICKETS
# =================

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='🎫 Crear Ticket', style=discord.ButtonStyle.primary, custom_id='create_ticket')
    async def create_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verificar si ya tiene un ticket abierto
        user_id = str(interaction.user.id)
        
        for ticket_id, ticket_info in tickets_data.items():
            if ticket_info.get('user_id') == user_id and ticket_info.get('status') == 'open':
                await interaction.response.send_message("❌ Ya tienes un ticket abierto!", ephemeral=True)
                return
        
        # Crear nuevo ticket
        config_data['ticket_counter'] += 1
        ticket_number = config_data['ticket_counter']
        
        guild = interaction.guild
        category = discord.utils.get(guild.categories, id=config_data.get('ticket_category'))
        
        # Crear canal del ticket
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        
        # Agregar permisos para roles de staff
        for role in guild.roles:
            if any(perm in role.name.lower() for perm in ['admin', 'mod', 'staff', 'ayudante']):
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        
        channel = await guild.create_text_channel(
            name=f'ticket-{ticket_number}',
            category=category,
            overwrites=overwrites
        )
        
        # Guardar info del ticket
        tickets_data[str(channel.id)] = {
            'user_id': user_id,
            'ticket_number': ticket_number,
            'status': 'open',
            'created_at': datetime.utcnow().isoformat()
        }
        
        # Embed del ticket
        embed = discord.Embed(
            title=f"🎫 Ticket #{ticket_number}",
            description=f"¡Hola {interaction.user.mention}!\n\nGracias por crear un ticket. Un miembro del staff te atenderá pronto.\n\n**Por favor, describe tu problema o consulta con el mayor detalle posible.**",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.add_field(name="Usuario", value=interaction.user.mention, inline=True)
        embed.add_field(name="ID", value=interaction.user.id, inline=True)
        embed.add_field(name="Creado", value=f"<t:{int(datetime.utcnow().timestamp())}:R>", inline=True)
        
        close_view = TicketCloseView()
        await channel.send(embed=embed, view=close_view)
        
        await interaction.response.send_message(f"✅ Ticket creado: {channel.mention}", ephemeral=True)

class TicketCloseView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='🔒 Cerrar Ticket', style=discord.ButtonStyle.danger, custom_id='close_ticket')
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Verificar permisos
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message("❌ No tienes permisos para cerrar tickets.", ephemeral=True)
            return
        
        channel_id = str(interaction.channel.id)
        
        if channel_id in tickets_data:
            tickets_data[channel_id]['status'] = 'closed'
            tickets_data[channel_id]['closed_at'] = datetime.utcnow().isoformat()
            tickets_data[channel_id]['closed_by'] = str(interaction.user.id)
        
        embed = discord.Embed(
            title="🔒 Ticket Cerrado",
            description=f"Este ticket ha sido cerrado por {interaction.user.mention}.\nEl canal será eliminado en 10 segundos.",
            color=discord.Color.red(),
            timestamp=datetime.utcnow()
        )
        
        await interaction.response.send_message(embed=embed)
        await asyncio.sleep(10)
        await interaction.channel.delete()

# =================
# EVENTOS DEL BOT
# =================

@bot.event
async def on_ready():
    print(f'{bot.user} está conectado!')
    
    # Agregar vistas persistentes
    bot.add_view(TicketView())
    bot.add_view(TicketCloseView())
    
    # Sincronizar comandos slash
    try:
        synced = await bot.tree.sync()
        print(f"Sincronizados {len(synced)} comandos slash")
    except Exception as e:
        print(f"Error sincronizando comandos: {e}")

@bot.event
async def on_member_join(member):
    """Sistema de bienvenida"""
    if not config_data.get('welcome_channel'):
        return
    
    channel = bot.get_channel(config_data['welcome_channel'])
    if not channel:
        return
    
    # Embed de bienvenida personalizado
    embed = discord.Embed(
        title="🎉 ¡Bienvenido al servidor!",
        description=f"¡Hola {member.mention}! Nos alegra tenerte aquí.",
        color=discord.Color.green(),
        timestamp=datetime.utcnow()
    )
    
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.set_image(url="https://media.giphy.com/media/Cmr1OMJ2FN0B2/giphy.gif")
    
    embed.add_field(
        name="📋 Información del Usuario",
        value=f"**Nombre:** {member.display_name}\n**ID:** {member.id}\n**Cuenta creada:** <t:{int(member.created_at.timestamp())}:R>",
        inline=False
    )
    
    embed.add_field(
        name="🚀 Primeros pasos",
        value="• Lee las reglas del servidor\n• Presenta tu perfil\n• ¡Empieza a chatear y divertirte!",
        inline=False
    )
    
    embed.set_footer(text=f"Ahora somos {member.guild.member_count} miembros", icon_url=member.guild.icon.url if member.guild.icon else None)
    
    await channel.send(embed=embed)
    
    # Dar dinero de bienvenida
    add_money(member.id, 50)

# =================
# COMANDOS SLASH
# =================

@bot.tree.command(name="balance", description="Ver tu balance económico")
async def balance(interaction: discord.Interaction, usuario: discord.Member = None):
    target = usuario or interaction.user
    user_data = get_user_data(target.id)
    
    embed = discord.Embed(
        title=f"💰 Balance de {target.display_name}",
        color=discord.Color.gold()
    )
    embed.add_field(name="💵 Dinero en mano", value=f"{user_data['balance']:,} coins", inline=True)
    embed.add_field(name="🏦 Dinero en banco", value=f"{user_data['bank']:,} coins", inline=True)
    embed.add_field(name="📈 Total ganado", value=f"{user_data['total_earned']:,} coins", inline=True)
    embed.set_thumbnail(url=target.display_avatar.url)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="daily", description="Reclamar tu recompensa diaria")
async def daily(interaction: discord.Interaction):
    user_data = get_user_data(interaction.user.id)
    now = datetime.utcnow()
    
    if user_data['last_daily']:
        last_daily = datetime.fromisoformat(user_data['last_daily'])
        time_diff = now - last_daily
        
        if time_diff.total_seconds() < 86400:  # 24 horas
            remaining = 86400 - time_diff.total_seconds()
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            
            embed = discord.Embed(
                title="⏰ Ya reclamaste tu recompensa diaria",
                description=f"Podrás reclamar otra en {hours}h {minutes}m",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
    
    # Dar recompensa
    amount = 100
    add_money(interaction.user.id, amount)
    user_data['last_daily'] = now.isoformat()
    
    embed = discord.Embed(
        title="🎁 ¡Recompensa diaria reclamada!",
        description=f"Has recibido **{amount:,} coins**",
        color=discord.Color.green()
    )
    embed.add_field(name="💰 Nuevo balance", value=f"{user_data['balance']:,} coins", inline=False)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="work", description="Trabajar para ganar dinero")
async def work(interaction: discord.Interaction):
    import random
    
    jobs = [
        ("programador", (50, 150)),
        ("delivery", (30, 80)),
        ("streamer", (20, 200)),
        ("diseñador", (40, 120)),
        ("chef", (35, 90))
    ]
    
    job, (min_pay, max_pay) = random.choice(jobs)
    earnings = random.randint(min_pay, max_pay)
    
    add_money(interaction.user.id, earnings)
    
    embed = discord.Embed(
        title="💼 ¡Trabajo completado!",
        description=f"Trabajaste como **{job}** y ganaste **{earnings:,} coins**",
        color=discord.Color.blue()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="pay", description="Transferir dinero a otro usuario")
async def pay(interaction: discord.Interaction, usuario: discord.Member, cantidad: int):
    if usuario == interaction.user:
        await interaction.response.send_message("❌ No puedes transferirte dinero a ti mismo.", ephemeral=True)
        return
    
    if cantidad <= 0:
        await interaction.response.send_message("❌ La cantidad debe ser mayor a 0.", ephemeral=True)
        return
    
    if not remove_money(interaction.user.id, cantidad):
        await interaction.response.send_message("❌ No tienes suficiente dinero.", ephemeral=True)
        return
    
    add_money(usuario.id, cantidad)
    
    embed = discord.Embed(
        title="💸 Transferencia exitosa",
        description=f"{interaction.user.mention} transfirió **{cantidad:,} coins** a {usuario.mention}",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setup_welcome", description="Configurar canal de bienvenida")
@discord.app_commands.describe(canal="Canal donde se enviarán los mensajes de bienvenida")
async def setup_welcome(interaction: discord.Interaction, canal: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Necesitas permisos de administrador.", ephemeral=True)
        return
    
    config_data['welcome_channel'] = canal.id
    
    embed = discord.Embed(
        title="✅ Canal de bienvenida configurado",
        description=f"Los mensajes de bienvenida se enviarán en {canal.mention}",
        color=discord.Color.green()
    )
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="setup_tickets", description="Configurar sistema de tickets")
@discord.app_commands.describe(categoria="Categoría donde se crearán los tickets")
async def setup_tickets(interaction: discord.Interaction, categoria: discord.CategoryChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Necesitas permisos de administrador.", ephemeral=True)
        return
    
    config_data['ticket_category'] = categoria.id
    
    embed = discord.Embed(
        title="🎫 Sistema de Tickets",
        description="Haz clic en el botón de abajo para crear un ticket de soporte.",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="ℹ️ Información",
        value="• Solo puedes tener un ticket abierto a la vez\n• Describe tu problema con detalle\n• Un staff te atenderá pronto",
        inline=False
    )
    
    view = TicketView()
    await interaction.response.send_message(embed=embed, view=view)

@bot.tree.command(name="leaderboard", description="Ver el ranking de dinero")
async def leaderboard(interaction: discord.Interaction):
    # Ordenar usuarios por balance total
    sorted_users = sorted(
        economy_data.items(),
        key=lambda x: x[1]['balance'] + x[1]['bank'],
        reverse=True
    )[:10]
    
    embed = discord.Embed(
        title="🏆 Ranking Económico",
        color=discord.Color.gold()
    )
    
    description = ""
    for i, (user_id, data) in enumerate(sorted_users, 1):
        try:
            user = bot.get_user(int(user_id))
            username = user.display_name if user else f"Usuario {user_id}"
            total = data['balance'] + data['bank']
            
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            description += f"{medal} **{username}** - {total:,} coins\n"
        except:
            continue
    
    embed.description = description or "No hay datos disponibles"
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="info", description="Información del bot")
async def info(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🤖 Información del Bot",
        description="Bot multifuncional con sistema de economía, tickets y bienvenidas",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📊 Estadísticas",
        value=f"Servidores: {len(bot.guilds)}\nUsuarios: {len(bot.users)}\nLatencia: {round(bot.latency * 1000)}ms",
        inline=True
    )
    
    embed.add_field(
        name="⚙️ Funcionalidades",
        value="• Sistema de economía\n• Sistema de tickets\n• Mensajes de bienvenida\n• Comandos slash",
        inline=True
    )
    
    embed.set_footer(text="Creado con Python y discord.py")
    
    await interaction.response.send_message(embed=embed)

# Iniciar el bot
if __name__ == "__main__":
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("❌ Por favor, configura la variable de entorno DISCORD_TOKEN")
    else:
        bot.run(TOKEN)
