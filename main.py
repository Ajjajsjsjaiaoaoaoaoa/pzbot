import discord
from discord.ext import commands
import asyncio
import datetime

# --- CONFIGURACIÓN DE INTENTOS Y BOT ---
intents = discord.Intents.default()
intents.message_content = True  # Permite leer comandos de texto
intents.members = True          # Permite gestionar y ver usuarios

bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)

# --- BASE DE DATOS EN MEMORIA ---
# Sistema global temporal. Ideal para un solo archivo funcional.
tienda_abierta = True
productos = {
    "1": {"nombre": "Rango VIP", "precio": 500, "stock": 10},
    "2": {"nombre": "Monedas del Juego", "precio": 100, "stock": 50},
    "3": {"nombre": "Cuenta Premium", "precio": 1200, "stock": 3}
}
economia = {}  # {user_id: dinero}
vouches = []   # Historial de reseñas de clientes

# --- COMPONENTES INTERACTIVOS (BOTONES Y MENÚS) ---

class TicketView(discord.ui.View):
    """Botón persistente para la creación de tickets de compra"""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📩 Abrir Ticket de Compra", style=discord.ButtonStyle.green, custom_id="btn_crear_ticket")
    async def crear_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not tienda_abierta:
            await interaction.response.send_message("❌ Lo sentimos, la tienda está cerrada en este momento. No puedes abrir tickets.", ephemeral=True)
            return

        guild = interaction.guild
        member = interaction.user
        
        # Permisos del canal privado (Solo Staff y el Comprador)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_channel = await guild.create_text_channel(
            name=f"🛒-ticket-{member.name.lower()}",
            overwrites=overwrites,
            topic=f"Ticket de compra - ID Usuario: {member.id}"
        )
        
        # Mensaje de bienvenida dentro del ticket
        embed = discord.Embed(
            title=f"🏪 ¡Bienvenido a tu Ticket, {member.name}!",
            description="Por favor, indica qué producto deseas adquirir. Un administrador te atenderá en breve.\n\n🔒 Para cerrar este ticket, usa el comando: `!close`",
            color=discord.Color.blue()
        )
        await ticket_channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Tu ticket ha sido creado en: {ticket_channel.mention}", ephemeral=True)


class TiendaDropdown(discord.ui.Select):
    """Menú desplegable para seleccionar y comprar productos"""
    def __init__(self):
        options = [
            discord.SelectOption(label=f"{info['nombre']} (${info['precio']})", description=f"Stock: {info['stock']} unidades", value=id_prod)
            for id_prod, info in productos.items()
        ]
        super().__init__(placeholder="🛒 Selecciona un producto para comprar...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if not tienda_abierta:
            await interaction.response.send_message("❌ La tienda está cerrada. Las compras automáticas están deshabilitadas.", ephemeral=True)
            return

        prod_id = self.values[0]
        user_id = interaction.user.id
        saldo_usuario = economia.get(user_id, 0)
        producto = productos[prod_id]

        if producto["stock"] <= 0:
            await interaction.response.send_message(f"❌ ¡Oh no! El producto **{producto['nombre']}** está agotado.", ephemeral=True)
            return

        if saldo_usuario < producto["precio"]:
            await interaction.response.send_message(f"❌ Saldo insuficiente. El producto cuesta **${producto['precio']}** y tú tienes **${saldo_usuario}**.", ephemeral=True)
            return

        # Procesar Transacción Comercial
        economia[user_id] -= producto["precio"]
        productos[prod_id]["stock"] -= 1
        
        embed = discord.Embed(
            title="🛍️ ¡Compra Procesada con Éxito!",
            description=f"Has adquirido: **{producto['nombre']}**\n¡Muchas gracias por confiar en nosotros!",
            color=discord.Color.green()
        )
        embed.add_field(name="Saldo restante", value=f"${economia[user_id]}")
        await interaction.response.send_message(embed=embed)


class TiendaView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TiendaDropdown())


# --- EVENTOS PRINCIPALES ---

@bot.event
async def on_ready():
    print(f'======================================')
    print(f'🤖 BOT DE TIENDA ONLINE CONFIGURADO')
    print(f'Conectado como: {bot.user.name}')
    print(f'======================================')
    # Mantener el botón de tickets activo tras reinicios del bot
    bot.add_view(TicketView())
    await bot.change_presence(activity=discord.Game(name="🟢 Tienda Abierta | !ayuda"))


# --- SISTEMA DE ABIERTO / CERRADO ---

@bot.command()
@commands.has_permissions(administrator=True)
async def tienda(ctx, estado: str):
    """Controla el acceso al negocio: !tienda abrir o !tienda cerrar"""
    global tienda_abierta
    if estado.lower() == "abrir":
        tienda_abierta = True
        await bot.change_presence(activity=discord.Game(name="🟢 Tienda Abierta | !ayuda"))
        await ctx.send("🟩 **¡Atención! La tienda se encuentra ABIERTA. Ya pueden abrir tickets y realizar compras.**")
    elif estado.lower() == "cerrar":
        tienda_abierta = False
        await bot.change_presence(activity=discord.Game(name="🔴 Tienda Cerrada | !ayuda"))
        await ctx.send("🟥 **¡Atención! La tienda ha CERRADO. Los sistemas de compra y tickets se han pausado hasta nuevo aviso.**")
    else:
        await ctx.send("⚠️ Parámetro incorrecto. Usa `!tienda abrir` o `!tienda cerrar`.")


# --- SISTEMA DE TICKETS ---

@bot.command()
@commands.has_permissions(administrator=True)
async def panelticket(ctx):
    """Envía el panel interactivo con el botón de soporte/compras"""
    embed = discord.Embed(
        title="🏪 Centro de Atención al Cliente",
        description="¿Quieres realizar un pedido personalizado, reportar un pago o hablar con el dueño?\n\nPresiona el botón verde que verás aquí abajo para abrir un canal privado de atención.",
        color=discord.Color.purple()
    )
    embed.set_footer(text="Atención 100% segura y privada.")
    await ctx.send(embed=embed, view=TicketView())

@bot.command()
async def close(ctx):
    """Cierra y elimina el ticket actual"""
    if "ticket-" in ctx.channel.name:
        await ctx.send("🔒 **Este ticket se cerrará y eliminará permanentemente en 5 segundos...**")
        await asyncio.sleep(5)
        await ctx.channel.delete()
    else:
        await ctx.send("❌ Este comando solo puede utilizarse dentro de un canal de ticket activo.")


# --- SISTEMA DE TIENDA Y ECONOMÍA ---

@bot.command()
async def ver_tienda(ctx):
    """Muestra el catálogo de artículos y el menú de compra masiva"""
    embed = discord.Embed(title="🏬 Catálogo Oficial de Productos", color=discord.Color.gold())
    estado = "🟩 ABIERTA" if tienda_abierta else "🟥 CERRADA"
    embed.description = f"Estado comercial: **{estado}**\n\nUsa el menú desplegable de abajo para efectuar compras automáticas con tu crédito."
    
    for id_prod, info in productos.items():
        embed.add_field(
            name=f"📦 [{id_prod}] {info['nombre']}", 
            value=f"Precio: **${info['precio']}** | Stock disponible: `{info['stock']}`", 
            inline=False
        )
    
    await ctx.send(embed=embed, view=TiendaView())

@bot.command()
async def dinero(ctx, miembro: discord.Member = None):
    """Muestra el balance monetario de un cliente"""
    miembro = miembro or ctx.author
    saldo = economia.get(miembro.id, 0)
    await ctx.send(f"💰 {miembro.mention} cuenta con un saldo de: **${saldo}**")

@bot.command()
@commands.has_permissions(administrator=True)
async def dardinero(ctx, miembro: discord.Member, cantidad: int):
    """Asigna dinero a un cliente (Simulación de recargas de dinero real)"""
    if cantidad <= 0:
        return await ctx.send("❌ Ingresa un monto mayor a 0.")
    economia[miembro.id] = economia.get(miembro.id, 0) + cantidad
    await ctx.send(f"💵 Se han depositado **${cantidad}** en la cuenta de {miembro.mention}. ¡Nuevo Saldo: ${economia[miembro.id]}!")


# --- SISTEMA DE AUTOVOUCH (REPUTACIÓN) ---

@bot.command()
async def vouch(ctx, estrellas: int, *, comentario: str):
    """Permite a un cliente dejar una reseña: !vouch 5 Entrega rápida e impecable"""
    if estrellas < 1 or estrellas > 5:
        return await ctx.send("⚠️ La puntuación debe estar comprendida entre 1 y 5 estrellas ⭐.")

    vouch_info = {
        "cliente": ctx.author.name,
        "estrellas": estrellas,
        "comentario": comentario,
        "fecha": datetime.datetime.now().strftime("%d/%m/%Y")
    }
    vouches.append(vouch_info)

    marcador_estrellas = "⭐" * estrellas
    embed = discord.Embed(title="✅ ¡Nueva Reseña de Cliente Recibida!", color=discord.Color.green())
    embed.add_field(name="👤 Comprador:", value=ctx.author.mention, inline=True)
    embed.add_field(name="⭐ Calificación:", value=marcador_estrellas, inline=True)
    embed.add_field(name="💬 Opinión Comercial:", value=f'"{comentario}"', inline=False)
    embed.set_footer(text=f"Reseña registrada el {vouch_info['fecha']}")
    
    await ctx.send(embed=embed)


# --- SISTEMA DE MODERACIÓN ---

@bot.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, razon="Violación de términos de la tienda"):
    """Expulsa a un usuario molesto o problemático"""
    await member.kick(reason=razon)
    await ctx.send(f"🚪 **{member.name}** ha sido expulsado del servidor. Motivo: {razon}")

@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, razon="Estafa / Intento de fraude comercial"):
    """Banea permanentemente a un usuario malintencionado"""
    await member.ban(reason=razon)
    await ctx.send(f"🚫 **{member.name}** fue vetado permanentemente de la tienda. Motivo: {razon}")

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, cantidad: int):
    """Limpia el historial de chat para mantener el orden"""
    await ctx.channel.purge(limit=cantidad + 1)
    msg = await ctx.send(f"🗑️ Acción de limpieza: **{cantidad}** mensajes eliminados de este canal.")
    await asyncio.sleep(2)
    await msg.delete()


# --- PANEL GENERAL DE AYUDA ---

@bot.command()
async def ayuda(ctx):
    """Menú guía estructurado por áreas"""
    embed = discord.Embed(
        title="📖 Directorio de Comandos Comerciales",
        description="Aquí tienes la lista completa de acciones disponibles dentro del bot.",
        color=discord.Color.orange()
    )
    embed.add_field(name="⚙️ Control Administrativo", value="`!tienda abrir/cerrar` - Habilita/Inhabilita compras\n`!panelticket` - Despliega panel con botón de soporte\n`!dardinero [@cliente] [cant]` - Agrega fondos", inline=False)
    embed.add_field(name="🛍️ Catálogo y Tienda", value="`!ver_tienda` - Muestra productos y menú desplegable\n`!dinero` - Revisa tus fondos disponibles\n`!close` - Cierra un ticket desde el canal privado", inline=False)
    embed.add_field(name="⭐ Sistema de Reputación", value="`!vouch [1-5] [reseña]` - Publica una reseña visual con estrellas", inline=False)
    embed.add_field(name="🛡️ Moderación", value="`!kick [@user]` - Expulsión\n`!ban [@user]` - Bloqueo permanente\n`!clear [n]` - Borrado de mensajes", inline=False)
    await ctx.send(embed=embed)


# --- INSERTA AQUÍ TU TOKEN SECRETO ---
bot.run('MTUxMTg0MDIyNzcwOTQyMzc1Nw.GAebVX.eXJPXeUOiLGwqFryn1kjmJaPV9Ho2i3PBMb86w')
